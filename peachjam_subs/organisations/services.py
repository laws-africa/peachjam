from dataclasses import dataclass

from allauth.account.models import EmailAddress
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from guardian.shortcuts import assign_perm, get_objects_for_user

from peachjam_subs.models import (
    Organisation,
    OrganisationAuditEvent,
    OrganisationInvitation,
    OrganisationMembership,
    OrganisationSeat,
    OrganisationSeatAssignment,
    OrganisationSeatChange,
    OrganisationSeatChangeItem,
    ProductOffering,
    Subscription,
    subscription_settings,
)
from peachjam_subs.organisations.notifications import (
    notify_email,
    notify_invitation,
    notify_member,
)
from peachjam_subs.organisations.signals import (
    organisation_billing_recipients_changed,
    organisation_invitation_accepted,
    organisation_ownership_transferred,
    organisation_seat_assigned,
    organisation_seat_plan_changed,
    organisation_seat_released,
)


@dataclass(frozen=True)
class SeatChangePreview:
    action: str
    current_offering: ProductOffering | None
    requested_offering: ProductOffering | None
    effective_on: object


@dataclass(frozen=True)
class OrganisationSubscriptionState:
    """Describe whether an organisation controls a user's subscription."""

    membership: OrganisationMembership | None
    assignment: OrganisationSeatAssignment | None
    status: str

    @property
    def is_pending(self):
        """Return whether an assigned seat is awaiting organisation activation."""
        return self.status == "pending"

    @property
    def is_managed(self):
        """Return whether the organisation currently controls the subscription."""
        return self.status == "managed"


class OrganisationService:
    """Coordinate organisation membership and entitlement workflows."""

    def public_offerings(self):
        """Return paid offerings configured for the public product catalogue."""
        return ProductOffering.objects.filter(
            selectable_for_products__in=subscription_settings().key_products.all(),
            pricing_plan__price__gt=0,
        )

    def offerings_available_to_organisation(self, organisation=None, actor=None):
        """Return public and permitted private offerings for an organisation.

        The organisation owner's object permissions are authoritative after an
        owner exists. ``actor`` supports staff-assisted setup before that point.
        """
        eligible_user = organisation.owner if organisation else None
        if eligible_user is None:
            eligible_user = actor
        permitted_ids = ProductOffering.objects.none().values("pk")
        if eligible_user and eligible_user.is_authenticated:
            permitted_ids = get_objects_for_user(
                eligible_user,
                "peachjam_subs.can_subscribe",
                klass=ProductOffering,
            ).values("pk")
        queryset = ProductOffering.objects.filter(
            Q(pk__in=self.public_offerings().values("pk")) | Q(pk__in=permitted_ids)
        )
        if organisation:
            queryset = queryset.filter(pricing_plan__period=organisation.billing_period)
        return (
            queryset.select_related("product", "pricing_plan")
            .distinct()
            .order_by("product__tier", "pricing_plan__price")
        )

    def ensure_offering_available(self, organisation, offering, actor=None):
        """Raise unless an offering may be newly selected for an organisation."""
        if (
            not self.offerings_available_to_organisation(organisation, actor=actor)
            .filter(pk=offering.pk)
            .exists()
        ):
            raise ValidationError(_("This plan is not available to this organisation."))

    def subscription_state_for_user(self, user):
        """Return the user's current organisation subscription-management state."""
        membership = (
            OrganisationMembership.objects.filter(
                user=user,
                status=OrganisationMembership.Status.ACTIVE,
            )
            .select_related("organisation")
            .first()
        )
        assignment = None
        status = "none"
        if membership:
            assignment = (
                membership.seat_assignments.filter(ended_at__isnull=True)
                .select_related(
                    "seat__organisation",
                    "seat__product_offering__product",
                    "seat__product_offering__pricing_plan",
                    "seat__pending_product_offering__product",
                    "seat__pending_product_offering__pricing_plan",
                    "subscription",
                )
                .first()
            )
        if assignment:
            if assignment.seat.status == OrganisationSeat.Status.PROVISIONAL:
                status = "pending"
            elif assignment.seat.status in {
                OrganisationSeat.Status.ACTIVE,
                OrganisationSeat.Status.SUSPENDED,
            }:
                status = "managed"
        return OrganisationSubscriptionState(
            membership=membership,
            assignment=assignment,
            status=status,
        )

    def ensure_can_manage(self, actor, organisation):
        """Raise when the actor may not manage the organisation."""
        if actor is None:
            return
        if actor.is_staff:
            return
        membership = OrganisationMembership.objects.filter(
            organisation=organisation,
            user=actor,
            status=OrganisationMembership.Status.ACTIVE,
            role__in=[
                OrganisationMembership.Role.OWNER,
                OrganisationMembership.Role.ADMIN,
            ],
        ).first()
        if not membership:
            raise PermissionDenied

    def ensure_organisation_accepts_invitations(self, organisation):
        """Raise unless memberships may still be invited into the organisation."""
        if organisation.status not in {
            Organisation.Status.PROVISIONAL,
            Organisation.Status.ACTIVE,
        }:
            raise ValidationError(
                _("This organisation is no longer accepting invitations.")
            )

    def ensure_invitation_recipient_available(self, organisation, email):
        """Reject recipients who already have an invitation or organisation."""
        email = email.strip().lower()
        if OrganisationInvitation.objects.filter(
            organisation=organisation,
            email__iexact=email,
            status__in=[
                OrganisationInvitation.Status.AWAITING_PAYMENT,
                OrganisationInvitation.Status.PENDING,
            ],
        ).exists():
            raise ValidationError(
                _("This person already has an open invitation to this organisation.")
            )

        verified_user_ids = EmailAddress.objects.filter(
            email__iexact=email, verified=True
        ).values("user_id")
        memberships = OrganisationMembership.objects.filter(
            Q(user__email__iexact=email) | Q(user_id__in=verified_user_ids),
            status=OrganisationMembership.Status.ACTIVE,
        )
        if memberships.filter(organisation=organisation).exists():
            raise ValidationError(
                _(
                    "This person is already a member of this organisation. "
                    "Manage their seat from the members list."
                )
            )
        if memberships.exists():
            raise ValidationError(
                _(
                    "This account already belongs to an organisation and cannot "
                    "accept this invitation."
                )
            )

    @transaction.atomic
    def create_organisation(
        self, *, name, billing_period, privacy_mode, actor, owner=None
    ):
        """Create an organisation and, optionally, its initial owner."""
        organisation = Organisation.objects.create(
            name=name,
            billing_period=billing_period,
            privacy_mode=privacy_mode,
        )
        membership = None
        if owner:
            membership = OrganisationMembership.objects.create(
                organisation=organisation,
                user=owner,
                role=OrganisationMembership.Role.OWNER,
            )
        OrganisationAuditEvent.objects.create(
            organisation=organisation,
            actor=actor,
            membership=membership,
            event_type=OrganisationAuditEvent.EventType.CREATED,
            message="Created organisation.",
            event_data={"billing_period": billing_period, "privacy_mode": privacy_mode},
        )
        return organisation

    @transaction.atomic
    def send_invitation(
        self, *, organisation, email, role, requested_product_offering=None, actor
    ):
        """Create and send an organisation invitation."""
        organisation = Organisation.objects.select_for_update().get(pk=organisation.pk)
        self.ensure_can_manage(actor, organisation)
        self.ensure_organisation_accepts_invitations(organisation)
        self.ensure_invitation_recipient_available(organisation, email)
        if requested_product_offering:
            self.ensure_offering_available(
                organisation, requested_product_offering, actor=actor
            )
        if role == OrganisationMembership.Role.OWNER and organisation.owner:
            raise ValidationError(
                _("Transfer ownership instead of inviting another owner.")
            )
        if role == OrganisationMembership.Role.ADMIN:
            organisation.validate_dunning_recipient_limit(additional_emails=[email])

        seat = None
        change = None
        status = OrganisationInvitation.Status.PENDING

        # An invitation may be membership-only, for example when an administrator
        # will keep their personal subscription instead of receiving a funded seat.
        if requested_product_offering:
            seat = self.find_available_seat(organisation, requested_product_offering)
            if not seat:
                # There is no unused seat of the requested plan to reserve. This can
                # happen when an administrator invites more people than the
                # organisation's current paid capacity, so prepare a new seat for
                # this invitation rather than waiting until it is accepted.
                seat = OrganisationSeat.objects.create(
                    organisation=organisation,
                    product_offering=requested_product_offering,
                    status=OrganisationSeat.Status.PROVISIONAL,
                )
                if organisation.status == Organisation.Status.ACTIVE:
                    # An active organisation must settle the prorated seat cost
                    # before the seat becomes active and the invitation is sent.
                    change = self.create_seat_change(
                        organisation=organisation, actor=actor
                    )
                    OrganisationSeatChangeItem.objects.create(
                        change=change,
                        action=OrganisationSeatChangeItem.Action.ADD,
                        seat=seat,
                        requested_offering=requested_product_offering,
                    )
                    status = OrganisationInvitation.Status.AWAITING_PAYMENT

        invitation = OrganisationInvitation(
            organisation=organisation,
            email=email,
            role=role,
            requested_product_offering=requested_product_offering,
            invited_by=actor,
            reserved_seat=seat,
            status=status,
            sent_at=(
                timezone.now()
                if status == OrganisationInvitation.Status.PENDING
                else None
            ),
        )
        invitation.full_clean()
        invitation.save()
        OrganisationAuditEvent.objects.create(
            organisation=organisation,
            actor=actor,
            invitation=invitation,
            event_type=OrganisationAuditEvent.EventType.INVITATION_SENT,
            message=(
                "Prepared organisation invitation awaiting seat payment."
                if change
                else "Sent organisation invitation."
            ),
            event_data={
                "email": invitation.email,
                "role": role,
                "product_offering_id": (
                    requested_product_offering.pk
                    if requested_product_offering
                    else None
                ),
            },
        )
        if invitation.status == OrganisationInvitation.Status.PENDING:
            notify_invitation(invitation)
        return invitation

    @transaction.atomic
    def create_seat_change(self, *, organisation, actor):
        """Create a single pending settlement-gated seat change for this organisation."""
        organisation = Organisation.objects.select_for_update().get(pk=organisation.pk)
        self.ensure_can_manage(actor, organisation)
        self.ensure_no_pending_seat_change(organisation)
        change = OrganisationSeatChange.objects.create(
            organisation=organisation, requested_by=actor
        )
        OrganisationAuditEvent.objects.create(
            organisation=organisation,
            actor=actor,
            event_type=OrganisationAuditEvent.EventType.SEAT_CHANGE_REQUESTED,
            message="Requested an organisation seat change.",
        )
        return change

    def ensure_no_pending_seat_change(self, organisation):
        """Reject a new paid change while another seat change awaits settlement."""
        if organisation.seat_changes.filter(
            status=OrganisationSeatChange.Status.AWAITING_SETTLEMENT
        ).exists():
            raise ValidationError(
                _(
                    "Complete or cancel the existing seat change before starting another."
                )
            )

    @transaction.atomic
    def stage_capacity_additions(self, *, organisation, additions, actor):
        """Create provisional seats for positive plan quantities awaiting settlement."""
        change = self.create_seat_change(organisation=organisation, actor=actor)
        for offering, quantity in additions:
            self.ensure_offering_available(organisation, offering, actor=actor)
            for _seat_number in range(quantity):
                seat = OrganisationSeat.objects.create(
                    organisation=organisation,
                    product_offering=offering,
                    status=OrganisationSeat.Status.PROVISIONAL,
                )
                OrganisationSeatChangeItem.objects.create(
                    change=change,
                    action=OrganisationSeatChangeItem.Action.ADD,
                    seat=seat,
                    requested_offering=offering,
                )
        return change

    @transaction.atomic
    def stage_seat_upgrade(self, *, seat, offering, actor):
        """Stage a paid seat upgrade without changing the current entitlement."""
        seat = (
            OrganisationSeat.objects.select_for_update()
            .select_related("organisation", "product_offering__product")
            .get(pk=seat.pk)
        )
        self.ensure_can_manage(actor, seat.organisation)
        preview = self.preview_seat_change(seat, offering)
        if preview.action != "upgrade":
            raise ValidationError(
                _("Only upgrades require settlement before applying.")
            )
        change = self.create_seat_change(organisation=seat.organisation, actor=actor)
        assignment = seat.active_assignment
        OrganisationSeatChangeItem.objects.create(
            change=change,
            action=OrganisationSeatChangeItem.Action.UPGRADE,
            seat=seat,
            previous_offering=seat.product_offering,
            requested_offering=offering,
            previous_membership=assignment.membership if assignment else None,
            requested_membership=assignment.membership if assignment else None,
        )
        return change

    @transaction.atomic
    def stage_seat_reassignment(self, *, seat, membership, actor):
        """Stage reassignment while retaining the existing member until settlement."""
        seat = (
            OrganisationSeat.objects.select_for_update()
            .select_related("organisation", "product_offering")
            .get(pk=seat.pk)
        )
        membership = OrganisationMembership.objects.select_for_update().get(
            pk=membership.pk,
            organisation=seat.organisation,
            status=OrganisationMembership.Status.ACTIVE,
        )
        self.ensure_can_manage(actor, seat.organisation)
        if membership.seat_assignments.filter(ended_at__isnull=True).exists():
            raise ValidationError(_("The replacement member already has a seat."))
        assignment = seat.active_assignment
        if not assignment:
            raise ValidationError(_("This seat is not currently assigned."))
        change = self.create_seat_change(organisation=seat.organisation, actor=actor)
        OrganisationSeatChangeItem.objects.create(
            change=change,
            action=OrganisationSeatChangeItem.Action.REASSIGN,
            seat=seat,
            previous_offering=seat.product_offering,
            requested_offering=seat.product_offering,
            previous_membership=assignment.membership,
            requested_membership=membership,
        )
        return change

    @transaction.atomic
    def apply_seat_change(self, *, change, actor=None):
        """Apply a settled seat change exactly once and activate its entitlements."""
        change = (
            OrganisationSeatChange.objects.select_for_update()
            .select_related("organisation")
            .get(pk=change.pk)
        )
        if change.status == OrganisationSeatChange.Status.APPLIED:
            return change
        if change.status != OrganisationSeatChange.Status.AWAITING_SETTLEMENT:
            raise ValidationError(_("This seat change can no longer be applied."))
        for item in change.items.select_related(
            "seat__product_offering",
            "requested_offering",
            "previous_membership__user",
            "requested_membership__user",
        ):
            seat = OrganisationSeat.objects.select_for_update().get(pk=item.seat_id)
            if item.action == OrganisationSeatChangeItem.Action.ADD:
                seat.status = OrganisationSeat.Status.ACTIVE
                seat.starts_on = timezone.localdate()
                seat.save(update_fields=["status", "starts_on"])
                invitation = getattr(seat, "reserved_invitation", None)
                if (
                    invitation
                    and invitation.status
                    == OrganisationInvitation.Status.AWAITING_PAYMENT
                ):
                    self.send_reserved_invitation(invitation)
            elif item.action == OrganisationSeatChangeItem.Action.UPGRADE:
                seat.product_offering = item.requested_offering
                seat.pending_product_offering = None
                seat.pending_change_on = None
                seat.save(
                    update_fields=[
                        "product_offering",
                        "pending_product_offering",
                        "pending_change_on",
                    ]
                )
                assignment = seat.active_assignment
                if assignment:
                    if (
                        assignment.subscription
                        and not assignment.subscription.is_closed
                    ):
                        assignment.subscription.close()
                    assignment.subscription = None
                    assignment.save(update_fields=["subscription"])
                    if seat.status == OrganisationSeat.Status.ACTIVE:
                        self.activate_assignment(assignment)
            elif item.action == OrganisationSeatChangeItem.Action.REASSIGN:
                assignment = seat.active_assignment
                if assignment:
                    self.release_assignment(assignment=assignment, actor=actor)
                replacement = OrganisationSeatAssignment.objects.create(
                    seat=seat, membership=item.requested_membership
                )
                self.activate_assignment(replacement)
        change.status = OrganisationSeatChange.Status.APPLIED
        change.applied_at = timezone.now()
        change.save(update_fields=["status", "applied_at"])
        OrganisationAuditEvent.objects.create(
            organisation=change.organisation,
            actor=actor,
            event_type=OrganisationAuditEvent.EventType.SEAT_CHANGE_APPLIED,
            message="Applied an organisation seat change after settlement.",
        )
        return change

    @transaction.atomic
    def cancel_seat_change(self, *, change, actor):
        """Cancel an unsettled seat change and remove only its provisional capacity."""
        change = OrganisationSeatChange.objects.select_for_update().get(pk=change.pk)
        self.ensure_can_manage(actor, change.organisation)
        if change.status == OrganisationSeatChange.Status.CANCELLED:
            return change
        if change.status != OrganisationSeatChange.Status.AWAITING_SETTLEMENT:
            raise ValidationError(_("This seat change can no longer be cancelled."))

        for item in change.items.select_related("seat"):
            if item.action == OrganisationSeatChangeItem.Action.ADD:
                invitation = getattr(item.seat, "reserved_invitation", None)
                if (
                    invitation
                    and invitation.status
                    == OrganisationInvitation.Status.AWAITING_PAYMENT
                ):
                    invitation.cancel()

                item.seat.status = OrganisationSeat.Status.ENDED
                item.seat.ends_on = timezone.localdate()
                item.seat.save(update_fields=["status", "ends_on"])

        change.status = OrganisationSeatChange.Status.CANCELLED
        change.cancelled_at = timezone.now()
        change.save(update_fields=["status", "cancelled_at"])

        OrganisationAuditEvent.objects.create(
            organisation=change.organisation,
            actor=actor,
            event_type=OrganisationAuditEvent.EventType.SEAT_CHANGE_CANCELLED,
            message="Cancelled an organisation seat change.",
        )
        return change

    def send_reserved_invitation(self, invitation):
        """Mark a paid seat invitation as sent and start its fourteen-day expiry."""
        invitation.mark_sent()
        notify_invitation(invitation)
        return invitation

    def verified_invitation_email(self, user, invitation):
        """Return whether the user has verified the invitation email address."""
        return EmailAddress.objects.filter(
            user=user, email__iexact=invitation.email, verified=True
        ).exists()

    def find_available_seat(self, organisation, offering):
        """Return an unassigned active seat for the exact offering."""
        active_assignments = OrganisationSeatAssignment.objects.filter(
            seat=OuterRef("pk"), ended_at__isnull=True
        )
        active_reservations = OrganisationInvitation.objects.filter(
            reserved_seat=OuterRef("pk"),
            status__in=[
                OrganisationInvitation.Status.AWAITING_PAYMENT,
                OrganisationInvitation.Status.PENDING,
            ],
        )
        statuses = [OrganisationSeat.Status.ACTIVE]
        if organisation.status == Organisation.Status.PROVISIONAL:
            statuses.append(OrganisationSeat.Status.PROVISIONAL)
        return (
            OrganisationSeat.objects.select_for_update()
            .filter(
                organisation=organisation,
                product_offering=offering,
                status__in=statuses,
                ends_on__isnull=True,
            )
            .annotate(has_active_assignment=Exists(active_assignments))
            .annotate(has_active_reservation=Exists(active_reservations))
            .filter(has_active_assignment=False, has_active_reservation=False)
            .order_by("pk")
            .first()
        )

    def activate_assignment(self, assignment):
        """Activate the sponsored subscription for a seat assignment."""
        assignment = (
            OrganisationSeatAssignment.objects.select_for_update(of=("self",))
            .select_related(
                "seat__organisation",
                "seat__product_offering",
                "membership__user",
                "subscription",
            )
            .get(pk=assignment.pk)
        )
        if assignment.ended_at:
            return assignment
        assignment.clean()
        if (
            assignment.membership.status != OrganisationMembership.Status.ACTIVE
            or assignment.seat.organisation_id != assignment.membership.organisation_id
            or assignment.seat.organisation.status != Organisation.Status.ACTIVE
            or assignment.seat.status != OrganisationSeat.Status.ACTIVE
        ):
            raise ValidationError(
                _("This seat assignment cannot provide an active subscription.")
            )
        if assignment.subscription and assignment.subscription.is_active:
            return assignment
        subscription = Subscription.objects.create(
            user=assignment.membership.user,
            product_offering=assignment.seat.product_offering,
            starts_on=timezone.localdate(),
        )
        assignment.subscription = subscription
        assignment.save(update_fields=["subscription"])
        subscription.activate(allow_trial=False)
        return assignment

    @transaction.atomic
    def expire_invitation(self, *, token):
        """Persist expiry for a pending invitation and return whether it expired."""
        organisation_id = OrganisationInvitation.objects.values_list(
            "organisation_id", flat=True
        ).get(token=token)
        Organisation.objects.select_for_update().get(pk=organisation_id)
        invitation = (
            OrganisationInvitation.objects.select_for_update(of=("self",))
            .select_related("organisation")
            .get(token=token)
        )
        if not invitation.is_expired:
            return False
        invitation.expire()
        OrganisationAuditEvent.objects.create(
            organisation=invitation.organisation,
            invitation=invitation,
            event_type=OrganisationAuditEvent.EventType.INVITATION_EXPIRED,
            message="Organisation invitation expired.",
        )
        return True

    def accept_invitation(self, *, token, user):
        """Accept an invitation and create its membership and optional assignment."""
        if self.expire_invitation(token=token):
            raise ValidationError(_("This invitation has expired."))
        return self.accept_pending_invitation(token=token, user=user)

    @transaction.atomic
    def accept_pending_invitation(self, *, token, user):
        """Accept a locked, unexpired invitation."""
        organisation_id = OrganisationInvitation.objects.values_list(
            "organisation_id", flat=True
        ).get(token=token)
        organisation = Organisation.objects.select_for_update().get(pk=organisation_id)
        invitation = (
            OrganisationInvitation.objects.select_for_update(of=("self",))
            .select_related(
                "organisation", "requested_product_offering", "reserved_seat"
            )
            .get(token=token)
        )
        if invitation.status == OrganisationInvitation.Status.ACCEPTED:
            if (
                not invitation.accepted_membership
                or invitation.accepted_membership.user_id != user.pk
            ):
                raise ValidationError(_("This invitation has already been accepted."))
            return invitation.accepted_membership
        if invitation.status != OrganisationInvitation.Status.PENDING:
            raise ValidationError(_("This invitation is no longer available."))
        self.ensure_organisation_accepts_invitations(organisation)
        if not self.verified_invitation_email(user, invitation):
            raise ValidationError(
                _("Sign in with the verified email address that was invited.")
            )
        if OrganisationMembership.objects.filter(
            user=user, status=OrganisationMembership.Status.ACTIVE
        ).exists():
            raise ValidationError(_("This account already belongs to an organisation."))
        if invitation.role == OrganisationMembership.Role.OWNER and organisation.owner:
            raise ValidationError(_("This organisation already has an owner."))
        if invitation.role == OrganisationMembership.Role.ADMIN:
            organisation.validate_dunning_recipient_limit(
                additional_emails=[user.email]
            )

        if (
            invitation.role == OrganisationMembership.Role.OWNER
            and not organisation.owner
            and invitation.requested_product_offering
            and not self.public_offerings()
            .filter(pk=invitation.requested_product_offering_id)
            .exists()
        ):
            # A staff-authorised private offering selected during setup becomes
            # the owner's permission when they accept the invitation.
            assign_perm(
                "peachjam_subs.can_subscribe",
                user,
                invitation.requested_product_offering,
            )
        if invitation.requested_product_offering:
            self.ensure_offering_available(
                organisation,
                invitation.requested_product_offering,
                actor=user,
            )

        membership = OrganisationMembership.objects.create(
            organisation=organisation, user=user, role=invitation.role
        )
        seat = None
        assignment = None
        created_seat = False
        if invitation.requested_product_offering:
            seat = invitation.reserved_seat
            if seat and seat.status == OrganisationSeat.Status.ENDED:
                raise ValidationError(_("The reserved seat is no longer available."))
            if not seat:
                seat = self.find_available_seat(
                    organisation, invitation.requested_product_offering
                )
            if not seat:
                if organisation.status == Organisation.Status.ACTIVE:
                    raise ValidationError(
                        _("This invitation no longer has a reserved seat.")
                    )
                created_seat = True
                seat = OrganisationSeat.objects.create(
                    organisation=organisation,
                    product_offering=invitation.requested_product_offering,
                    status=(
                        OrganisationSeat.Status.ACTIVE
                        if organisation.status == Organisation.Status.ACTIVE
                        else OrganisationSeat.Status.PROVISIONAL
                    ),
                    starts_on=(
                        timezone.localdate()
                        if organisation.status == Organisation.Status.ACTIVE
                        else None
                    ),
                )
            assignment = OrganisationSeatAssignment.objects.create(
                seat=seat, membership=membership
            )
            if organisation.status == Organisation.Status.ACTIVE:
                self.activate_assignment(assignment)

        invitation.accept(membership)
        OrganisationAuditEvent.objects.create(
            organisation=organisation,
            actor=user,
            membership=membership,
            invitation=invitation,
            seat=seat,
            event_type=OrganisationAuditEvent.EventType.INVITATION_ACCEPTED,
            message="Accepted organisation invitation.",
        )
        organisation_invitation_accepted.send(
            sender=OrganisationInvitation,
            invitation=invitation,
            membership=membership,
            assignment=assignment,
        )
        if membership.role in {
            OrganisationMembership.Role.OWNER,
            OrganisationMembership.Role.ADMIN,
        }:
            organisation_billing_recipients_changed.send(
                sender=OrganisationMembership,
                organisation=organisation,
            )
        organisation.notify_administrators(
            _("A member joined %(organisation)s") % {"organisation": organisation.name},
            _("%(email)s accepted their organisation invitation.")
            % {"email": user.email},
        )
        if assignment:
            organisation_seat_assigned.send(
                sender=OrganisationSeatAssignment,
                assignment=assignment,
                created_seat=created_seat,
                opening=False,
            )
        return membership

    @transaction.atomic
    def cancel_invitation(self, *, invitation, actor):
        """Cancel a pending organisation invitation."""
        invitation = (
            OrganisationInvitation.objects.select_for_update()
            .select_related("organisation")
            .get(pk=invitation.pk)
        )
        self.ensure_can_manage(actor, invitation.organisation)

        if invitation.status not in {
            OrganisationInvitation.Status.PENDING,
            OrganisationInvitation.Status.AWAITING_PAYMENT,
        }:
            raise ValidationError(_("Only open invitations can be cancelled."))

        if invitation.status == OrganisationInvitation.Status.AWAITING_PAYMENT:
            # This invitation reserved a new provisional seat through a paid seat
            # change. Cancel that change so settlement cannot later activate the
            # seat; the change service also ends the seat and cancels the invitation.
            awaiting_change = (
                OrganisationSeatChange.objects.filter(
                    organisation=invitation.organisation,
                    status=OrganisationSeatChange.Status.AWAITING_SETTLEMENT,
                    items__seat=invitation.reserved_seat,
                )
                .distinct()
                .first()
            )
            if awaiting_change:
                self.cancel_seat_change(change=awaiting_change, actor=actor)
                invitation.refresh_from_db()
                return invitation

        # A sent invitation may reserve an existing, already-paid seat. Releasing
        # that reservation leaves the seat active and unused for another member.
        invitation.cancel()

        OrganisationAuditEvent.objects.create(
            organisation=invitation.organisation,
            actor=actor,
            invitation=invitation,
            event_type=OrganisationAuditEvent.EventType.INVITATION_CANCELLED,
            message="Cancelled organisation invitation.",
        )

        notify_email(
            invitation.email,
            _("Your organisation invitation was cancelled"),
            _("Your invitation to %(organisation)s is no longer available.")
            % {"organisation": invitation.organisation.name},
        )

        return invitation

    @transaction.atomic
    def resend_invitation(self, *, invitation, actor):
        """Refresh and resend a pending organisation invitation."""
        invitation = (
            OrganisationInvitation.objects.select_for_update()
            .select_related("organisation")
            .get(pk=invitation.pk)
        )
        self.ensure_can_manage(actor, invitation.organisation)
        self.ensure_organisation_accepts_invitations(invitation.organisation)
        if invitation.status != OrganisationInvitation.Status.PENDING:
            raise ValidationError(_("Only pending invitations can be resent."))
        invitation.resend()
        notify_invitation(invitation)
        return invitation

    @transaction.atomic
    def activate_organisation(self, *, organisation, actor=None):
        """Activate an organisation and its provisional seats and assignments."""
        organisation = Organisation.objects.select_for_update().get(pk=organisation.pk)
        if organisation.status == Organisation.Status.ACTIVE:
            return organisation
        if organisation.status != Organisation.Status.PROVISIONAL:
            raise ValidationError(_("This organisation cannot be activated."))
        if not organisation.owner:
            raise ValidationError(
                _("An organisation must have an owner before activation.")
            )
        organisation.status = Organisation.Status.ACTIVE
        organisation.activated_at = timezone.now()
        organisation.save(update_fields=["status", "activated_at"])
        seats = organisation.seats.select_for_update().filter(
            status=OrganisationSeat.Status.PROVISIONAL
        )
        seats.update(
            status=OrganisationSeat.Status.ACTIVE, starts_on=timezone.localdate()
        )
        for assignment in OrganisationSeatAssignment.objects.filter(
            seat__organisation=organisation, ended_at__isnull=True
        ):
            self.activate_assignment(assignment)
            organisation_seat_assigned.send(
                sender=OrganisationSeatAssignment,
                assignment=assignment,
                created_seat=True,
                opening=True,
            )
        OrganisationAuditEvent.objects.create(
            organisation=organisation,
            actor=actor,
            event_type=OrganisationAuditEvent.EventType.ACTIVATED,
            message="Activated organisation.",
        )
        return organisation

    @transaction.atomic
    def release_assignment(self, *, assignment, actor=None, event_type=None):
        """End a seat assignment and restore the member's fallback subscription."""
        assignment = (
            OrganisationSeatAssignment.objects.select_for_update(of=("self",))
            .select_related("seat__organisation", "membership__user", "subscription")
            .get(pk=assignment.pk)
        )
        self.ensure_can_manage(actor, assignment.seat.organisation)
        if assignment.ended_at:
            return assignment
        if assignment.subscription and not assignment.subscription.is_closed:
            assignment.subscription.close()
        assignment.ended_at = timezone.now()
        assignment.save(update_fields=["ended_at"])
        Subscription.get_or_create_active_for_user(assignment.membership.user)
        OrganisationAuditEvent.objects.create(
            organisation=assignment.seat.organisation,
            actor=actor,
            membership=assignment.membership,
            seat=assignment.seat,
            event_type=event_type or OrganisationAuditEvent.EventType.SEAT_RELEASED,
            message="Released organisation subscription.",
        )
        organisation_seat_released.send(
            sender=OrganisationSeatAssignment, assignment=assignment
        )
        notify_member(
            assignment.membership.user,
            _("Your organisation-funded subscription ended"),
            _(
                "Your %(organisation)s-funded subscription has ended. "
                "Your account and private research have been preserved."
            )
            % {"organisation": assignment.seat.organisation.name},
        )
        return assignment

    @transaction.atomic
    def assign_subscription(self, *, membership, offering, actor):
        """Assign an existing unused exact-plan seat to a membership."""
        membership = (
            OrganisationMembership.objects.select_for_update()
            .select_related("organisation", "user")
            .get(pk=membership.pk, status=OrganisationMembership.Status.ACTIVE)
        )
        self.ensure_can_manage(actor, membership.organisation)
        self.ensure_organisation_accepts_invitations(membership.organisation)
        self.ensure_offering_available(membership.organisation, offering, actor=actor)
        if membership.seat_assignments.filter(ended_at__isnull=True).exists():
            raise ValidationError(_("This member already has an assigned seat."))
        seat = self.find_available_seat(membership.organisation, offering)
        if not seat:
            raise ValidationError(
                _("There is no unused seat on this plan. Add a seat first.")
            )
        assignment = OrganisationSeatAssignment.objects.create(
            seat=seat, membership=membership
        )
        if membership.organisation.status == Organisation.Status.ACTIVE:
            self.activate_assignment(assignment)
        OrganisationAuditEvent.objects.create(
            organisation=membership.organisation,
            actor=actor,
            membership=membership,
            seat=seat,
            event_type=OrganisationAuditEvent.EventType.SEAT_ASSIGNED,
            message="Assigned organisation subscription.",
        )
        organisation_seat_assigned.send(
            sender=OrganisationSeatAssignment,
            assignment=assignment,
            created_seat=False,
            opening=False,
        )
        notify_member(
            membership.user,
            _("Your organisation-funded subscription is ready"),
            _("%(organisation)s assigned you a %(plan)s subscription.")
            % {
                "organisation": membership.organisation.name,
                "plan": offering.product.name,
            },
        )
        return assignment

    @transaction.atomic
    def remove_membership(self, *, membership, actor, member_left=False):
        """End a membership and release its sponsored assignment."""
        membership = (
            OrganisationMembership.objects.select_for_update()
            .select_related("organisation", "user")
            .get(pk=membership.pk)
        )
        if not (member_left and actor.pk == membership.user_id):
            self.ensure_can_manage(actor, membership.organisation)
        if membership.role == OrganisationMembership.Role.OWNER:
            raise ValidationError(_("Transfer ownership before removing the owner."))
        assignment = membership.seat_assignments.filter(ended_at__isnull=True).first()
        if assignment:
            self.release_assignment(assignment=assignment, actor=actor)
        membership.status = OrganisationMembership.Status.ENDED
        membership.ended_at = timezone.now()
        membership.save(update_fields=["status", "ended_at"])
        if membership.role == OrganisationMembership.Role.ADMIN:
            organisation_billing_recipients_changed.send(
                sender=OrganisationMembership,
                organisation=membership.organisation,
            )
        OrganisationAuditEvent.objects.create(
            organisation=membership.organisation,
            actor=actor,
            membership=membership,
            event_type=(
                OrganisationAuditEvent.EventType.MEMBER_LEFT
                if member_left
                else OrganisationAuditEvent.EventType.MEMBER_REMOVED
            ),
            message="Ended organisation membership.",
        )
        notify_member(
            membership.user,
            _("Your organisation membership ended"),
            _(
                "Your membership of %(organisation)s has ended. Your account and private research have been preserved."
            )
            % {"organisation": membership.organisation.name},
        )
        membership.organisation.notify_administrators(
            (
                _("Organisation member left")
                if member_left
                else _("Organisation member removed")
            ),
            _("%(email)s is no longer a member of %(organisation)s.")
            % {
                "email": membership.user.email,
                "organisation": membership.organisation.name,
            },
        )
        return membership

    @transaction.atomic
    def schedule_membership_removal(self, *, membership, effective_on, actor):
        """Schedule a membership to end on a future date."""
        membership = (
            OrganisationMembership.objects.select_for_update()
            .select_related("organisation")
            .get(pk=membership.pk, status=OrganisationMembership.Status.ACTIVE)
        )
        self.ensure_can_manage(actor, membership.organisation)
        if membership.role == OrganisationMembership.Role.OWNER:
            raise ValidationError(_("Transfer ownership before removing the owner."))
        membership.pending_end_on = effective_on
        membership.save(update_fields=["pending_end_on"])
        OrganisationAuditEvent.objects.create(
            organisation=membership.organisation,
            actor=actor,
            membership=membership,
            event_type=OrganisationAuditEvent.EventType.MEMBER_REMOVED,
            message="Scheduled organisation membership removal.",
            event_data={"effective_on": effective_on.isoformat()},
        )
        notify_member(
            membership.user,
            _("Your organisation membership is scheduled to end"),
            _("Your membership of %(organisation)s is scheduled to end on %(date)s.")
            % {"organisation": membership.organisation.name, "date": effective_on},
        )
        return membership

    @transaction.atomic
    def cancel_scheduled_membership_removal(self, *, membership, actor):
        """Cancel a future membership removal."""
        membership = (
            OrganisationMembership.objects.select_for_update()
            .select_related("organisation", "user")
            .get(pk=membership.pk, status=OrganisationMembership.Status.ACTIVE)
        )
        self.ensure_can_manage(actor, membership.organisation)
        previous_end_on = membership.pending_end_on
        if not previous_end_on:
            raise ValidationError(_("This membership has no scheduled removal."))
        membership.pending_end_on = None
        membership.save(update_fields=["pending_end_on"])
        OrganisationAuditEvent.objects.create(
            organisation=membership.organisation,
            actor=actor,
            membership=membership,
            event_type=OrganisationAuditEvent.EventType.MEMBER_REMOVED,
            message="Cancelled scheduled organisation membership removal.",
            event_data={
                "cancelled_effective_on": (
                    previous_end_on.isoformat() if previous_end_on else None
                )
            },
        )
        notify_member(
            membership.user,
            _("Your organisation membership will continue"),
            _("Your membership of %(organisation)s is no longer scheduled to end.")
            % {"organisation": membership.organisation.name},
        )
        return membership

    @transaction.atomic
    def change_role(self, *, membership, role, actor):
        """Change an active non-owner membership role."""
        membership = (
            OrganisationMembership.objects.select_for_update()
            .select_related("organisation", "user")
            .get(pk=membership.pk, status=OrganisationMembership.Status.ACTIVE)
        )
        self.ensure_can_manage(actor, membership.organisation)
        if (
            membership.role == OrganisationMembership.Role.OWNER
            or role == OrganisationMembership.Role.OWNER
        ):
            raise ValidationError(_("Use ownership transfer to change the owner."))
        previous = membership.role
        if role == OrganisationMembership.Role.ADMIN:
            membership.organisation.validate_dunning_recipient_limit(
                additional_emails=[membership.user.email]
            )
        membership.role = role
        membership.save(update_fields=["role"])
        organisation_billing_recipients_changed.send(
            sender=OrganisationMembership,
            organisation=membership.organisation,
        )
        OrganisationAuditEvent.objects.create(
            organisation=membership.organisation,
            actor=actor,
            membership=membership,
            event_type=OrganisationAuditEvent.EventType.ROLE_CHANGED,
            message="Changed organisation role.",
            event_data={"before": previous, "after": role},
        )
        notify_member(
            membership.user,
            _("Your organisation role changed"),
            _("Your role in %(organisation)s is now %(role)s.")
            % {
                "organisation": membership.organisation.name,
                "role": membership.get_role_display(),
            },
        )
        return membership

    @transaction.atomic
    def transfer_ownership(self, *, organisation, new_owner_membership, actor):
        """Transfer ownership and demote the previous owner to administrator."""
        organisation = Organisation.objects.select_for_update().get(pk=organisation.pk)
        self.ensure_can_manage(actor, organisation)
        current = organisation.memberships.select_for_update().get(
            status=OrganisationMembership.Status.ACTIVE,
            role=OrganisationMembership.Role.OWNER,
        )
        if actor and not actor.is_staff and actor.pk != current.user_id:
            raise PermissionDenied
        new_owner = organisation.memberships.select_for_update().get(
            pk=new_owner_membership.pk, status=OrganisationMembership.Status.ACTIVE
        )
        if current.pk == new_owner.pk:
            return new_owner
        private_offerings = get_objects_for_user(
            current.user,
            "peachjam_subs.can_subscribe",
            klass=ProductOffering,
        ).exclude(pk__in=self.public_offerings().values("pk"))
        for offering in private_offerings:
            assign_perm("peachjam_subs.can_subscribe", new_owner.user, offering)
        organisation.validate_dunning_recipient_limit(
            additional_emails=[new_owner.user.email]
        )
        current.role = OrganisationMembership.Role.ADMIN
        current.save(update_fields=["role"])
        new_owner.role = OrganisationMembership.Role.OWNER
        new_owner.save(update_fields=["role"])
        organisation_ownership_transferred.send(
            sender=Organisation,
            organisation=organisation,
            previous_owner=current.user,
            new_owner=new_owner.user,
        )
        OrganisationAuditEvent.objects.create(
            organisation=organisation,
            actor=actor,
            membership=new_owner,
            event_type=OrganisationAuditEvent.EventType.OWNERSHIP_TRANSFERRED,
            message="Transferred organisation ownership.",
            event_data={
                "previous_owner_id": current.user_id,
                "new_owner_id": new_owner.user_id,
            },
        )
        notify_member(
            new_owner.user,
            _("You are now the organisation owner"),
            _("You are now the owner of %(organisation)s.")
            % {"organisation": organisation.name},
        )
        notify_member(
            current.user,
            _("Organisation ownership transferred"),
            _("You transferred ownership of %(organisation)s to %(email)s.")
            % {"organisation": organisation.name, "email": new_owner.user.email},
        )
        return new_owner

    def preview_seat_change(self, seat, offering, effective_on=None):
        """Validate and describe a requested seat plan change."""
        self.ensure_offering_available(seat.organisation, offering)
        if offering.pricing_plan.period != seat.organisation.billing_period:
            raise ValidationError(
                _("The plan must use the organisation's billing period.")
            )
        action = (
            "upgrade"
            if offering.product.tier > seat.product_offering.product.tier
            else "downgrade"
        )
        return SeatChangePreview(
            action=action,
            current_offering=seat.product_offering,
            requested_offering=offering,
            effective_on=effective_on or timezone.localdate(),
        )

    @transaction.atomic
    def change_seat_plan(self, *, seat, offering, renewal_on, actor):
        """Apply an upgrade now or schedule a downgrade for renewal."""
        seat = (
            OrganisationSeat.objects.select_for_update(of=("self",))
            .select_related(
                "organisation", "product_offering__product", "pending_product_offering"
            )
            .get(pk=seat.pk)
        )
        self.ensure_can_manage(actor, seat.organisation)
        preview = self.preview_seat_change(seat, offering)
        previous_offering = seat.product_offering
        if preview.action == "upgrade":
            raise ValidationError(
                _("Upgrades must be staged until their charge has settled.")
            )
        else:
            seat.pending_product_offering = offering
            seat.pending_change_on = renewal_on
            seat.save(update_fields=["pending_product_offering", "pending_change_on"])
        OrganisationAuditEvent.objects.create(
            organisation=seat.organisation,
            actor=actor,
            seat=seat,
            event_type=OrganisationAuditEvent.EventType.PLAN_CHANGED,
            message="Changed organisation subscription plan.",
            event_data={
                "previous_offering_id": previous_offering.pk,
                "requested_offering_id": offering.pk,
                "effective_on": (
                    timezone.localdate() if preview.action == "upgrade" else renewal_on
                ).isoformat(),
            },
        )
        organisation_seat_plan_changed.send(
            sender=OrganisationSeat,
            seat=seat,
            previous_offering=previous_offering,
            immediate=preview.action == "upgrade",
        )
        assignment = seat.active_assignment
        if assignment:
            notify_member(
                assignment.membership.user,
                _("Your organisation-funded subscription is changing"),
                _(
                    "Your %(organisation)s-funded subscription changes to %(plan)s on %(date)s."
                )
                % {
                    "organisation": seat.organisation.name,
                    "plan": offering.product.name,
                    "date": (
                        timezone.localdate()
                        if preview.action == "upgrade"
                        else renewal_on
                    ),
                },
            )
        return seat

    @transaction.atomic
    def schedule_seat_end(self, *, seat, renewal_on, actor):
        """Schedule a seat to end at renewal."""
        seat = (
            OrganisationSeat.objects.select_for_update()
            .select_related("organisation")
            .get(pk=seat.pk)
        )
        self.ensure_can_manage(actor, seat.organisation)
        seat.ends_on = renewal_on
        seat.save(update_fields=["ends_on"])
        OrganisationAuditEvent.objects.create(
            organisation=seat.organisation,
            actor=actor,
            seat=seat,
            event_type=OrganisationAuditEvent.EventType.PLAN_CHANGED,
            message="Scheduled organisation subscription to end.",
            event_data={"effective_on": renewal_on.isoformat()},
        )
        assignment = seat.active_assignment
        if assignment:
            notify_member(
                assignment.membership.user,
                _("Your organisation-funded subscription is scheduled to end"),
                _(
                    "Your %(organisation)s-funded subscription is scheduled to end on %(date)s."
                )
                % {"organisation": seat.organisation.name, "date": renewal_on},
            )
        return seat

    @transaction.atomic
    def end_unused_free_seat(self, *, seat, actor):
        """End an unused zero-cost seat immediately."""
        seat = (
            OrganisationSeat.objects.select_for_update()
            .select_related("organisation", "product_offering__pricing_plan")
            .get(pk=seat.pk)
        )
        self.ensure_can_manage(actor, seat.organisation)
        if seat.status != OrganisationSeat.Status.ACTIVE:
            raise ValidationError(_("Only an active seat can be ended."))
        if seat.product_offering.pricing_plan.price != 0:
            raise ValidationError(_("Paid seats can only end at renewal."))
        if seat.active_assignment:
            raise ValidationError(_("Unassign the member before removing this seat."))
        if OrganisationInvitation.objects.filter(
            reserved_seat=seat,
            status__in=[
                OrganisationInvitation.Status.AWAITING_PAYMENT,
                OrganisationInvitation.Status.PENDING,
            ],
        ).exists():
            raise ValidationError(_("Cancel the invitation before removing this seat."))
        if seat.pending_product_offering_id:
            raise ValidationError(_("Cancel the pending plan change first."))
        today = timezone.localdate()
        seat.status = OrganisationSeat.Status.ENDED
        seat.ends_on = today
        seat.save(update_fields=["status", "ends_on"])
        OrganisationAuditEvent.objects.create(
            organisation=seat.organisation,
            actor=actor,
            seat=seat,
            event_type=OrganisationAuditEvent.EventType.PLAN_CHANGED,
            message="Ended unused free organisation seat.",
            event_data={"effective_on": today.isoformat()},
        )
        return seat

    @transaction.atomic
    def cancel_scheduled_seat_change(self, *, seat, actor):
        """Cancel a seat's scheduled plan change or end."""
        seat = (
            OrganisationSeat.objects.select_for_update()
            .select_related("organisation")
            .get(pk=seat.pk)
        )
        self.ensure_can_manage(actor, seat.organisation)
        seat.pending_product_offering = None
        seat.pending_change_on = None
        seat.ends_on = None
        seat.save(
            update_fields=["pending_product_offering", "pending_change_on", "ends_on"]
        )
        OrganisationAuditEvent.objects.create(
            organisation=seat.organisation,
            actor=actor,
            seat=seat,
            event_type=OrganisationAuditEvent.EventType.PLAN_CHANGED,
            message="Cancelled scheduled organisation subscription change.",
        )
        return seat

    @transaction.atomic
    def apply_scheduled_organisation_changes(self, today=None):
        """Apply membership and seat changes due on or before today."""
        today = today or timezone.localdate()
        for membership in OrganisationMembership.objects.select_for_update().filter(
            status=OrganisationMembership.Status.ACTIVE,
            pending_end_on__lte=today,
        ):
            self.remove_membership(membership=membership, actor=None)
        for seat in OrganisationSeat.objects.select_for_update().filter(
            pending_change_on__lte=today,
            pending_product_offering__isnull=False,
            status=OrganisationSeat.Status.ACTIVE,
        ):
            seat.product_offering = seat.pending_product_offering
            seat.pending_product_offering = None
            seat.pending_change_on = None
            seat.save(
                update_fields=[
                    "product_offering",
                    "pending_product_offering",
                    "pending_change_on",
                ]
            )
            assignment = seat.active_assignment
            if assignment:
                if assignment.subscription and not assignment.subscription.is_closed:
                    assignment.subscription.close()
                assignment.subscription = None
                assignment.save(update_fields=["subscription"])
                self.activate_assignment(assignment)
        for seat in OrganisationSeat.objects.select_for_update().filter(
            ends_on__lte=today,
            status__in=[
                OrganisationSeat.Status.ACTIVE,
                OrganisationSeat.Status.SUSPENDED,
            ],
        ):
            assignment = seat.active_assignment
            if assignment:
                self.release_assignment(assignment=assignment, actor=None)
            seat.status = OrganisationSeat.Status.ENDED
            seat.save(update_fields=["status"])

    @transaction.atomic
    def suspend_organisation_entitlements(self, *, organisation, actor=None):
        """Suspend all organisation-funded entitlements."""
        organisation = Organisation.objects.select_for_update().get(pk=organisation.pk)
        if organisation.status != Organisation.Status.ACTIVE:
            raise ValidationError(_("This organisation's access cannot be suspended."))
        seats = list(
            organisation.seats.select_for_update().filter(
                status=OrganisationSeat.Status.ACTIVE
            )
        )
        if not seats:
            return organisation
        for seat in seats:
            assignment = seat.active_assignment
            if (
                assignment
                and assignment.subscription
                and not assignment.subscription.is_closed
            ):
                assignment.subscription.close()
                Subscription.get_or_create_active_for_user(assignment.membership.user)
            seat.status = OrganisationSeat.Status.SUSPENDED
            seat.save(update_fields=["status"])
        OrganisationAuditEvent.objects.create(
            organisation=organisation,
            actor=actor,
            event_type=OrganisationAuditEvent.EventType.SUSPENDED,
            message="Suspended organisation-funded access.",
        )
        return organisation

    @transaction.atomic
    def restore_organisation_entitlements(self, *, organisation, actor=None):
        """Restore all suspended organisation-funded entitlements."""
        organisation = Organisation.objects.select_for_update().get(pk=organisation.pk)
        if organisation.status != Organisation.Status.ACTIVE:
            raise ValidationError(_("This organisation's access cannot be restored."))
        seats = list(
            organisation.seats.select_for_update().filter(
                status=OrganisationSeat.Status.SUSPENDED
            )
        )
        if not seats:
            return organisation
        for seat in seats:
            seat.status = OrganisationSeat.Status.ACTIVE
            seat.save(update_fields=["status"])
            assignment = seat.active_assignment
            if assignment:
                assignment.subscription = None
                assignment.save(update_fields=["subscription"])
                self.activate_assignment(assignment)
        OrganisationAuditEvent.objects.create(
            organisation=organisation,
            actor=actor,
            event_type=OrganisationAuditEvent.EventType.RESTORED,
            message="Restored organisation-funded access.",
        )
        return organisation

    @transaction.atomic
    def close_organisation(self, *, organisation, actor=None):
        """Close an organisation and end its memberships and funded access."""
        organisation = Organisation.objects.select_for_update().get(pk=organisation.pk)
        if organisation.status == Organisation.Status.CLOSED:
            return organisation
        now = timezone.now()
        today = timezone.localdate()
        organisation.notify_administrators(
            _("Your LawLibrary organisation is closing"),
            _(
                "Organisation-funded access for %(organisation)s has ended. "
                "Member accounts and private research have been preserved."
            )
            % {"organisation": organisation.name},
            include_billing_contacts=True,
        )
        if organisation.status == Organisation.Status.ACTIVE:
            self.suspend_organisation_entitlements(
                organisation=organisation, actor=actor
            )
        for invitation in organisation.invitations.select_for_update().filter(
            status=OrganisationInvitation.Status.PENDING
        ):
            invitation.cancel(now=now)
            OrganisationAuditEvent.objects.create(
                organisation=organisation,
                actor=actor,
                invitation=invitation,
                event_type=OrganisationAuditEvent.EventType.INVITATION_CANCELLED,
                message="Cancelled invitation during organisation closure.",
            )
            notify_email(
                invitation.email,
                _("Your organisation invitation was cancelled"),
                _("Your invitation to %(organisation)s is no longer available.")
                % {"organisation": organisation.name},
            )
        for assignment in OrganisationSeatAssignment.objects.select_for_update().filter(
            seat__organisation=organisation, ended_at__isnull=True
        ):
            self.release_assignment(assignment=assignment, actor=actor)
        organisation.seats.select_for_update().exclude(
            status=OrganisationSeat.Status.ENDED
        ).update(status=OrganisationSeat.Status.ENDED, ends_on=today)
        memberships = list(
            organisation.memberships.select_for_update().filter(
                status=OrganisationMembership.Status.ACTIVE
            )
        )
        for membership in memberships:
            membership.status = OrganisationMembership.Status.ENDED
            membership.pending_end_on = None
            membership.ended_at = now
            membership.save(update_fields=["status", "pending_end_on", "ended_at"])
            OrganisationAuditEvent.objects.create(
                organisation=organisation,
                actor=actor,
                membership=membership,
                event_type=OrganisationAuditEvent.EventType.MEMBER_REMOVED,
                message="Ended organisation membership during organisation closure.",
            )
        organisation.status = Organisation.Status.CLOSED
        organisation.closed_at = now
        organisation.save(update_fields=["status", "closed_at"])
        OrganisationAuditEvent.objects.create(
            organisation=organisation,
            actor=actor,
            event_type=OrganisationAuditEvent.EventType.CLOSED,
            message="Closed organisation.",
        )
        return organisation

    @transaction.atomic
    def expire_invitations(self, now=None):
        """Expire pending invitations whose deadlines have passed."""
        now = now or timezone.now()
        invitations = OrganisationInvitation.objects.select_for_update().filter(
            status=OrganisationInvitation.Status.PENDING,
            expires_at__lte=now,
        )
        count = 0
        for invitation in invitations:
            invitation.expire()
            OrganisationAuditEvent.objects.create(
                organisation=invitation.organisation,
                invitation=invitation,
                event_type=OrganisationAuditEvent.EventType.INVITATION_EXPIRED,
                message="Organisation invitation expired.",
            )
            invitation.organisation.notify_administrators(
                _("Organisation invitation expired"),
                _("The invitation for %(email)s has expired.")
                % {"email": invitation.email},
            )
            count += 1
        return count

    @transaction.atomic
    def send_invitation_reminders(self, now=None):
        """Send one reminder for invitations nearing expiry."""
        now = now or timezone.now()
        invitations = OrganisationInvitation.objects.select_for_update().filter(
            status=OrganisationInvitation.Status.PENDING,
            reminder_sent_at__isnull=True,
            expires_at__gt=now,
            expires_at__lte=now + timezone.timedelta(days=7),
            organisation__status__in=[
                Organisation.Status.PROVISIONAL,
                Organisation.Status.ACTIVE,
            ],
        )
        count = 0
        for invitation in invitations:
            invitation.mark_reminder_sent(now=now)
            notify_invitation(invitation)
            count += 1
        return count

    @transaction.atomic
    def change_privacy_mode(self, *, organisation, privacy_mode, actor):
        """Immediately apply a staff-authorized organisation privacy change."""
        organisation = Organisation.objects.select_for_update().get(pk=organisation.pk)
        if not actor or not actor.is_staff:
            raise PermissionDenied
        if privacy_mode not in Organisation.PrivacyMode.values:
            raise ValidationError(_("Choose a valid organisation privacy mode."))
        if privacy_mode == organisation.privacy_mode:
            return organisation
        previous = organisation.privacy_mode
        organisation.privacy_mode = privacy_mode
        organisation.save(update_fields=["privacy_mode"])
        OrganisationAuditEvent.objects.create(
            organisation=organisation,
            actor=actor,
            event_type=OrganisationAuditEvent.EventType.PRIVACY_CHANGED,
            message="Changed organisation privacy mode.",
            event_data={"before": previous, "after": privacy_mode},
        )
        return organisation

    def member_usage_summary(self, membership):
        """Return the usage fields permitted by the organisation's privacy mode."""
        if (
            membership.organisation.privacy_mode
            != Organisation.PrivacyMode.MANAGED_USAGE
        ):
            return None
        user = membership.user
        return {
            "activated": bool(user.last_login),
            "last_login": user.last_login,
            "saved_documents": user.saved_documents.filter(
                subscription_locked_at__isnull=True
            ).count(),
            "folders": user.folders.filter(subscription_locked_at__isnull=True).count(),
            "search_alerts": user.saved_searches.filter(
                subscription_locked_at__isnull=True
            ).count(),
            "following": user.following.filter(
                subscription_locked_at__isnull=True
            ).count(),
        }


organisation_service = OrganisationService()
