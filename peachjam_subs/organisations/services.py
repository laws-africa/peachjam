from dataclasses import dataclass

from allauth.account.models import EmailAddress
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Exists, OuterRef
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from peachjam_subs.models import (
    Organisation,
    OrganisationAuditEvent,
    OrganisationInvitation,
    OrganisationMembership,
    OrganisationSeat,
    OrganisationSeatAssignment,
    ProductOffering,
    Subscription,
)
from peachjam_subs.organisations.notifications import (
    notify_email,
    notify_invitation,
    notify_member,
)
from peachjam_subs.organisations.signals import (
    organisation_invitation_accepted,
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


class OrganisationService:
    """Coordinate organisation membership and entitlement workflows."""

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
        if role == OrganisationMembership.Role.OWNER and organisation.owner:
            raise ValidationError(
                _("Transfer ownership instead of inviting another owner.")
            )
        invitation = OrganisationInvitation(
            organisation=organisation,
            email=email,
            role=role,
            requested_product_offering=requested_product_offering,
            invited_by=actor,
        )
        invitation.full_clean()
        invitation.save()
        OrganisationAuditEvent.objects.create(
            organisation=organisation,
            actor=actor,
            invitation=invitation,
            event_type=OrganisationAuditEvent.EventType.INVITATION_SENT,
            message="Sent organisation invitation.",
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
        return (
            OrganisationSeat.objects.select_for_update()
            .filter(
                organisation=organisation,
                product_offering=offering,
                status__in=[
                    OrganisationSeat.Status.PROVISIONAL,
                    OrganisationSeat.Status.ACTIVE,
                ],
                ends_on__isnull=True,
            )
            .annotate(has_active_assignment=Exists(active_assignments))
            .filter(has_active_assignment=False)
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
        if (
            assignment.ended_at
            or assignment.seat.organisation.status != Organisation.Status.ACTIVE
        ):
            return assignment
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
    def accept_invitation(self, *, token, user):
        """Accept an invitation and create its membership and optional assignment."""
        invitation = (
            OrganisationInvitation.objects.select_for_update(of=("self",))
            .select_related("organisation", "requested_product_offering")
            .get(token=token)
        )
        organisation = Organisation.objects.select_for_update().get(
            pk=invitation.organisation_id
        )
        if invitation.status == OrganisationInvitation.Status.ACCEPTED:
            if invitation.accepted_membership.user_id != user.pk:
                raise ValidationError(_("This invitation has already been accepted."))
            return invitation.accepted_membership
        if invitation.is_expired:
            invitation.status = OrganisationInvitation.Status.EXPIRED
            invitation.save(update_fields=["status"])
            OrganisationAuditEvent.objects.create(
                organisation=organisation,
                invitation=invitation,
                event_type=OrganisationAuditEvent.EventType.INVITATION_EXPIRED,
                message="Organisation invitation expired.",
            )
            raise ValidationError(_("This invitation has expired."))
        if invitation.status != OrganisationInvitation.Status.PENDING:
            raise ValidationError(_("This invitation is no longer available."))
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

        membership = OrganisationMembership.objects.create(
            organisation=organisation, user=user, role=invitation.role
        )
        seat = None
        assignment = None
        created_seat = False
        if invitation.requested_product_offering:
            seat = self.find_available_seat(
                organisation, invitation.requested_product_offering
            )
            if not seat:
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

        invitation.status = OrganisationInvitation.Status.ACCEPTED
        invitation.accepted_at = timezone.now()
        invitation.accepted_membership = membership
        invitation.save(update_fields=["status", "accepted_at", "accepted_membership"])
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
        if invitation.status != OrganisationInvitation.Status.PENDING:
            raise ValidationError(_("Only pending invitations can be cancelled."))
        invitation.status = OrganisationInvitation.Status.CANCELLED
        invitation.cancelled_at = timezone.now()
        invitation.save(update_fields=["status", "cancelled_at"])
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
        if invitation.status != OrganisationInvitation.Status.PENDING:
            raise ValidationError(_("Only pending invitations can be resent."))
        invitation.expires_at = timezone.now() + timezone.timedelta(days=14)
        invitation.reminder_sent_at = timezone.now()
        invitation.save(update_fields=["expires_at", "reminder_sent_at"])
        notify_invitation(invitation)
        return invitation

    @transaction.atomic
    def activate_organisation(self, *, organisation, actor=None):
        """Activate an organisation and its provisional seats and assignments."""
        organisation = Organisation.objects.select_for_update().get(pk=organisation.pk)
        if organisation.status == Organisation.Status.ACTIVE:
            return organisation
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
        """Assign an exact-plan reusable or new seat to a membership."""
        membership = (
            OrganisationMembership.objects.select_for_update()
            .select_related("organisation", "user")
            .get(pk=membership.pk, status=OrganisationMembership.Status.ACTIVE)
        )
        self.ensure_can_manage(actor, membership.organisation)
        if membership.seat_assignments.filter(ended_at__isnull=True).exists():
            raise ValidationError(_("This member already has an assigned seat."))
        seat = self.find_available_seat(membership.organisation, offering)
        created_seat = seat is None
        if created_seat:
            seat = OrganisationSeat.objects.create(
                organisation=membership.organisation,
                product_offering=offering,
                status=(
                    OrganisationSeat.Status.ACTIVE
                    if membership.organisation.status == Organisation.Status.ACTIVE
                    else OrganisationSeat.Status.PROVISIONAL
                ),
                starts_on=(
                    timezone.localdate()
                    if membership.organisation.status == Organisation.Status.ACTIVE
                    else None
                ),
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
            created_seat=created_seat,
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
        membership.role = role
        membership.save(update_fields=["role"])
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
        current.role = OrganisationMembership.Role.ADMIN
        current.save(update_fields=["role"])
        new_owner.role = OrganisationMembership.Role.OWNER
        new_owner.save(update_fields=["role"])
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
            seat.product_offering = offering
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
        for seat in organisation.seats.select_for_update().filter(
            status=OrganisationSeat.Status.ACTIVE
        ):
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
        for seat in organisation.seats.select_for_update().filter(
            status=OrganisationSeat.Status.SUSPENDED
        ):
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
        organisation.notify_administrators(
            _("Your LawLibrary organisation is closing"),
            _(
                "Organisation-funded access for %(organisation)s has ended. "
                "Member accounts and private research have been preserved."
            )
            % {"organisation": organisation.name},
            include_billing_contacts=True,
        )
        self.suspend_organisation_entitlements(organisation=organisation, actor=actor)
        for assignment in OrganisationSeatAssignment.objects.select_for_update().filter(
            seat__organisation=organisation, ended_at__isnull=True
        ):
            self.release_assignment(assignment=assignment, actor=actor)
        organisation.seats.select_for_update().exclude(
            status=OrganisationSeat.Status.ENDED
        ).update(status=OrganisationSeat.Status.ENDED, ends_on=timezone.localdate())
        organisation.memberships.select_for_update().filter(
            status=OrganisationMembership.Status.ACTIVE
        ).update(
            status=OrganisationMembership.Status.ENDED,
            pending_end_on=None,
            ended_at=timezone.now(),
        )
        organisation.status = Organisation.Status.CLOSED
        organisation.closed_at = timezone.now()
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
            invitation.status = OrganisationInvitation.Status.EXPIRED
            invitation.save(update_fields=["status"])
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
        )
        count = 0
        for invitation in invitations:
            invitation.reminder_sent_at = now
            invitation.save(update_fields=["reminder_sent_at"])
            notify_invitation(invitation)
            count += 1
        return count

    @transaction.atomic
    def schedule_privacy_mode_change(
        self, *, organisation, privacy_mode, effective_on, actor
    ):
        """Schedule a staff-authorized privacy mode change."""
        organisation = Organisation.objects.select_for_update().get(pk=organisation.pk)
        if not actor or not actor.is_staff:
            raise PermissionDenied
        if privacy_mode == organisation.privacy_mode:
            return organisation
        organisation.pending_privacy_mode = privacy_mode
        organisation.privacy_change_on = effective_on
        organisation.save(update_fields=["pending_privacy_mode", "privacy_change_on"])
        for membership in organisation.memberships.filter(
            status=OrganisationMembership.Status.ACTIVE
        ).select_related("user"):
            notify_member(
                membership.user,
                _("Your organisation privacy setting is changing"),
                _(
                    "On %(date)s, %(organisation)s will change to %(privacy)s. "
                    "Research content and history are never visible to organisation administrators."
                )
                % {
                    "date": effective_on,
                    "organisation": organisation.name,
                    "privacy": organisation.get_pending_privacy_mode_display(),
                },
            )
        return organisation

    @transaction.atomic
    def apply_scheduled_privacy_changes(self, today=None):
        """Apply organisation privacy mode changes that are due."""
        today = today or timezone.localdate()
        for organisation in Organisation.objects.select_for_update().filter(
            pending_privacy_mode__isnull=False,
            privacy_change_on__lte=today,
        ):
            previous = organisation.privacy_mode
            organisation.privacy_mode = organisation.pending_privacy_mode
            organisation.pending_privacy_mode = None
            organisation.privacy_change_on = None
            organisation.save(
                update_fields=[
                    "privacy_mode",
                    "pending_privacy_mode",
                    "privacy_change_on",
                ]
            )
            OrganisationAuditEvent.objects.create(
                organisation=organisation,
                event_type=OrganisationAuditEvent.EventType.PRIVACY_CHANGED,
                message="Changed organisation privacy mode.",
                event_data={"before": previous, "after": organisation.privacy_mode},
            )

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
