import uuid
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .subscriptions import PricingPlan, ProductOffering, Subscription


def organisation_invitation_expiry():
    return timezone.now() + timedelta(days=14)


class Organisation(models.Model):
    """A customer organisation that can sponsor subscriptions for its members."""

    MAX_DUNNING_RECIPIENTS = 15

    class Status(models.TextChoices):
        PROVISIONAL = "provisional", _("Provisional")
        ACTIVE = "active", _("Active")
        CLOSING = "closing", _("Closing")
        CLOSED = "closed", _("Closed")

    class PrivacyMode(models.TextChoices):
        MANAGED_USAGE = "managed-usage", _("Managed usage")
        BILLING_ONLY = "billing-only", _("Private / billing only")

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    name = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PROVISIONAL
    )
    billing_period = models.CharField(max_length=50, choices=PricingPlan.Period.choices)
    privacy_mode = models.CharField(
        max_length=20,
        choices=PrivacyMode.choices,
        default=PrivacyMode.BILLING_ONLY,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    closing_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("name", "pk")

    @property
    def owner(self):
        membership = self.memberships.filter(
            status=OrganisationMembership.Status.ACTIVE,
            role=OrganisationMembership.Role.OWNER,
        ).first()
        return membership.user if membership else None

    def administrator_emails(self, include_billing_contacts=False):
        """Return active owner and administrator email addresses."""
        emails = list(
            self.memberships.filter(
                status=OrganisationMembership.Status.ACTIVE,
                role__in=[
                    OrganisationMembership.Role.OWNER,
                    OrganisationMembership.Role.ADMIN,
                ],
            ).values_list("user__email", flat=True)
        )
        if include_billing_contacts:
            try:
                details = self.billing_details
            except (AttributeError, ObjectDoesNotExist):
                details = None
            if details:
                emails.append(details.email)
                emails.extend(details.billing_contacts or [])
        return emails

    def dunning_recipient_emails(self, billing_email=None, billing_contacts=None):
        """Return normalized owner, administrator, and billing contact emails."""
        emails = self.administrator_emails()
        if billing_email is None and billing_contacts is None:
            try:
                details = self.billing_details
            except (AttributeError, ObjectDoesNotExist):
                details = None
            if details:
                billing_email = details.email
                billing_contacts = details.billing_contacts
        emails.extend([billing_email, *(billing_contacts or [])])
        recipients = {}
        for email in emails:
            if email:
                normalized = email.strip().lower()
                recipients.setdefault(normalized.casefold(), normalized)
        return list(recipients.values())

    def validate_dunning_recipient_limit(
        self, billing_email=None, billing_contacts=None, additional_emails=None
    ):
        """Raise when Customer.io cannot address all billing recipients."""
        recipients = self.dunning_recipient_emails(
            billing_email=billing_email,
            billing_contacts=billing_contacts,
        )
        existing = {email.casefold() for email in recipients}
        for email in additional_emails or []:
            if email and email.strip().casefold() not in existing:
                recipients.append(email.strip().lower())
                existing.add(email.strip().casefold())
        if len(recipients) > self.MAX_DUNNING_RECIPIENTS:
            raise ValidationError(
                _(
                    "An organisation can have at most %(limit)s owners, "
                    "administrators, and billing contacts in total."
                )
                % {"limit": self.MAX_DUNNING_RECIPIENTS}
            )
        return recipients

    def notify_administrators(self, subject, body, include_billing_contacts=False):
        """Email active administrators and, optionally, billing contacts."""
        from peachjam_subs.organisations.notifications import send_email

        send_email(
            subject,
            body,
            self.administrator_emails(include_billing_contacts),
        )

    def clean(self):
        if self.pk:
            previous = Organisation.objects.filter(pk=self.pk).first()
            if (
                previous
                and previous.status != self.Status.PROVISIONAL
                and previous.billing_period != self.billing_period
            ):
                raise ValidationError(
                    {"billing_period": _("Billing period can only change at renewal.")}
                )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class OrganisationMembership(models.Model):
    """A user's current or historical relationship with an organisation."""

    class Role(models.TextChoices):
        OWNER = "owner", _("Owner")
        ADMIN = "admin", _("Administrator")
        MEMBER = "member", _("Member")

    class Status(models.TextChoices):
        ACTIVE = "active", _("Active")
        ENDED = "ended", _("Ended")

    organisation = models.ForeignKey(
        Organisation, on_delete=models.CASCADE, related_name="memberships"
    )
    user = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="organisation_memberships"
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.MEMBER)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE
    )
    joined_at = models.DateTimeField(default=timezone.now)
    pending_end_on = models.DateField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("user__last_name", "user__first_name", "pk")
        constraints = [
            models.UniqueConstraint(
                fields=("user",),
                condition=Q(status="active"),
                name="one_active_organisation_per_user",
            ),
            models.UniqueConstraint(
                fields=("organisation",),
                condition=Q(status="active", role="owner"),
                name="one_active_owner_per_organisation",
            ),
        ]

    @property
    def can_manage(self):
        return self.status == self.Status.ACTIVE and self.role in {
            self.Role.OWNER,
            self.Role.ADMIN,
        }

    def __str__(self):
        return f"{self.user} in {self.organisation} ({self.get_role_display()})"


class OrganisationInvitation(models.Model):
    """A time-limited invitation to join an organisation."""

    class Status(models.TextChoices):
        AWAITING_PAYMENT = "awaiting-payment", _("Awaiting payment")
        PENDING = "pending", _("Pending")
        ACCEPTED = "accepted", _("Accepted")
        EXPIRED = "expired", _("Expired")
        CANCELLED = "cancelled", _("Cancelled")

    organisation = models.ForeignKey(
        Organisation, on_delete=models.CASCADE, related_name="invitations"
    )
    email = models.EmailField()
    role = models.CharField(
        max_length=20,
        choices=OrganisationMembership.Role.choices,
        default=OrganisationMembership.Role.MEMBER,
    )
    requested_product_offering = models.ForeignKey(
        ProductOffering,
        on_delete=models.PROTECT,
        related_name="organisation_invitations",
        null=True,
        blank=True,
    )
    invited_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="sent_organisation_invitations",
        null=True,
        blank=True,
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=organisation_invitation_expiry)
    accepted_at = models.DateTimeField(null=True, blank=True)
    reminder_sent_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    accepted_membership = models.OneToOneField(
        OrganisationMembership,
        on_delete=models.SET_NULL,
        related_name="accepted_invitation",
        null=True,
        blank=True,
    )
    reserved_seat = models.OneToOneField(
        "OrganisationSeat",
        on_delete=models.SET_NULL,
        related_name="reserved_invitation",
        null=True,
        blank=True,
    )
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("organisation", "email"),
                condition=Q(status__in=["awaiting-payment", "pending"]),
                name="one_pending_invitation_per_org_email",
            )
        ]

    @property
    def is_expired(self):
        return self.status == self.Status.PENDING and timezone.now() >= self.expires_at

    def mark_sent(self, now=None):
        """Mark a paid-seat invitation as sent and start its expiry period."""
        now = now or timezone.now()
        self.status = self.Status.PENDING
        self.sent_at = now
        self.expires_at = now + timezone.timedelta(days=14)
        self.save(update_fields=["status", "sent_at", "expires_at"])

    def accept(self, membership, now=None):
        """Mark this invitation as accepted by the supplied membership."""
        self.status = self.Status.ACCEPTED
        self.accepted_at = now or timezone.now()
        self.accepted_membership = membership
        self.reserved_seat = None
        self.save(
            update_fields=[
                "status",
                "accepted_at",
                "accepted_membership",
                "reserved_seat",
            ]
        )

    def expire(self):
        """Mark this invitation as expired and release its reserved seat."""
        self.status = self.Status.EXPIRED
        self.reserved_seat = None
        self.save(update_fields=["status", "reserved_seat"])

    def cancel(self, now=None):
        """Mark this invitation as cancelled and release its reserved seat."""
        self.status = self.Status.CANCELLED
        self.cancelled_at = now or timezone.now()
        self.reserved_seat = None
        self.save(update_fields=["status", "cancelled_at", "reserved_seat"])

    def resend(self, now=None):
        """Restart this invitation's expiry period after resending it."""
        now = now or timezone.now()
        self.expires_at = now + timezone.timedelta(days=14)
        self.reminder_sent_at = now
        self.save(update_fields=["expires_at", "reminder_sent_at"])

    def mark_reminder_sent(self, now=None):
        """Record that this invitation's expiry reminder has been sent."""
        self.reminder_sent_at = now or timezone.now()
        self.save(update_fields=["reminder_sent_at"])

    def clean(self):
        self.email = self.email.strip().lower()
        if (
            self.requested_product_offering
            and self.requested_product_offering.pricing_plan.period
            != self.organisation.billing_period
        ):
            raise ValidationError(
                {
                    "requested_product_offering": _(
                        "The plan must use the organisation's billing period."
                    )
                }
            )

    def save(self, *args, **kwargs):
        self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.email} invited to {self.organisation}"


class OrganisationSeat(models.Model):
    """One committed, plan-specific subscription funded by an organisation."""

    class Status(models.TextChoices):
        PROVISIONAL = "provisional", _("Provisional")
        ACTIVE = "active", _("Active")
        SUSPENDED = "suspended", _("Suspended")
        ENDED = "ended", _("Ended")

    organisation = models.ForeignKey(
        Organisation, on_delete=models.CASCADE, related_name="seats"
    )
    product_offering = models.ForeignKey(
        ProductOffering, on_delete=models.PROTECT, related_name="organisation_seats"
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PROVISIONAL
    )
    starts_on = models.DateField(null=True, blank=True)
    ends_on = models.DateField(null=True, blank=True)
    pending_product_offering = models.ForeignKey(
        ProductOffering,
        on_delete=models.PROTECT,
        related_name="pending_organisation_seats",
        null=True,
        blank=True,
    )
    pending_change_on = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("product_offering__product__tier", "pk")

    @property
    def active_assignment(self):
        return self.assignments.filter(ended_at__isnull=True).first()

    def clean(self):
        if (
            self.product_offering.pricing_plan.period
            != self.organisation.billing_period
        ):
            raise ValidationError(
                {
                    "product_offering": _(
                        "The plan must use the organisation's billing period."
                    )
                }
            )

        if (
            self.pending_product_offering
            and self.pending_product_offering.pricing_plan.period
            != self.organisation.billing_period
        ):
            raise ValidationError(
                {
                    "pending_product_offering": _(
                        "The pending plan must use the organisation's billing period."
                    )
                }
            )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.organisation}: {self.product_offering}"


class OrganisationSeatAssignment(models.Model):
    """Historical assignment of an organisation seat to a member."""

    seat = models.ForeignKey(
        OrganisationSeat, on_delete=models.CASCADE, related_name="assignments"
    )
    membership = models.ForeignKey(
        OrganisationMembership,
        on_delete=models.PROTECT,
        related_name="seat_assignments",
    )
    subscription = models.OneToOneField(
        Subscription,
        on_delete=models.SET_NULL,
        related_name="organisation_seat_assignment",
        null=True,
        blank=True,
    )
    started_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-started_at", "-pk")
        constraints = [
            models.UniqueConstraint(
                fields=("seat",),
                condition=Q(ended_at__isnull=True),
                name="one_active_assignment_per_org_seat",
            ),
            models.UniqueConstraint(
                fields=("membership",),
                condition=Q(ended_at__isnull=True),
                name="one_active_org_seat_per_membership",
            ),
        ]

    def clean(self):
        errors = {}
        if (
            self.seat_id
            and self.membership_id
            and self.seat.organisation_id != self.membership.organisation_id
        ):
            errors.setdefault("membership", []).append(
                _("The seat and membership must belong to the same organisation.")
            )
        if (
            self.subscription_id
            and self.membership_id
            and self.subscription.user_id != self.membership.user_id
        ):
            errors.setdefault("subscription", []).append(
                _("The subscription must belong to the assigned member.")
            )
        if self.ended_at is None and self.membership_id:
            if self.membership.status != OrganisationMembership.Status.ACTIVE:
                errors.setdefault("membership", []).append(
                    _("An active assignment requires an active membership.")
                )
        if self.ended_at is None and self.seat_id:
            if self.seat.status == OrganisationSeat.Status.ENDED:
                errors.setdefault("seat", []).append(
                    _("An ended seat cannot have an active assignment.")
                )
        if (
            self.ended_at is None
            and self.subscription_id
            and self.seat_id
            and self.subscription.product_offering_id != self.seat.product_offering_id
        ):
            errors.setdefault("subscription", []).append(
                _("The subscription plan must match the assigned seat.")
            )
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.seat} assigned to {self.membership.user}"


class OrganisationSeatChange(models.Model):
    """A change to the seats for an organisation. Changes that require payment must be settled before the change is
    applied and the seats are allocated."""

    class Status(models.TextChoices):
        AWAITING_SETTLEMENT = "awaiting-settlement", _("Awaiting settlement")
        APPLIED = "applied", _("Applied")
        CANCELLED = "cancelled", _("Cancelled")

    organisation = models.ForeignKey(
        Organisation, on_delete=models.CASCADE, related_name="seat_changes"
    )
    requested_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="requested_organisation_seat_changes",
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=24, choices=Status.choices, default=Status.AWAITING_SETTLEMENT
    )
    created_at = models.DateTimeField(auto_now_add=True)
    applied_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at", "-pk")
        constraints = [
            models.UniqueConstraint(
                fields=("organisation",),
                condition=Q(status="awaiting-settlement"),
                name="one_awaiting_org_seat_change",
            )
        ]

    def __str__(self):
        return f"{self.organisation}: {self.get_status_display()}"


class OrganisationSeatChangeItem(models.Model):
    """A single change to organisation seats as part of a seat change request."""

    class Action(models.TextChoices):
        ADD = "add", _("Add seat")
        UPGRADE = "upgrade", _("Upgrade seat")
        REASSIGN = "reassign", _("Reassign seat")

    change = models.ForeignKey(
        OrganisationSeatChange, on_delete=models.CASCADE, related_name="items"
    )
    action = models.CharField(max_length=16, choices=Action.choices)
    seat = models.ForeignKey(
        OrganisationSeat, on_delete=models.PROTECT, related_name="pending_change_items"
    )
    previous_offering = models.ForeignKey(
        ProductOffering,
        on_delete=models.PROTECT,
        related_name="previous_organisation_seat_change_items",
        null=True,
        blank=True,
    )
    requested_offering = models.ForeignKey(
        ProductOffering,
        on_delete=models.PROTECT,
        related_name="requested_organisation_seat_change_items",
    )
    previous_membership = models.ForeignKey(
        OrganisationMembership,
        on_delete=models.PROTECT,
        related_name="outgoing_organisation_seat_change_items",
        null=True,
        blank=True,
    )
    requested_membership = models.ForeignKey(
        OrganisationMembership,
        on_delete=models.PROTECT,
        related_name="incoming_organisation_seat_change_items",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ("pk",)
        constraints = [
            models.UniqueConstraint(
                fields=("change", "seat"), name="one_item_per_seat_change"
            )
        ]

    def clean(self):
        errors = {}
        if self.seat_id and self.change_id:
            if self.seat.organisation_id != self.change.organisation_id:
                errors["seat"] = _("The seat must belong to the change's organisation.")

        if self.requested_offering_id and self.change_id:
            if (
                self.requested_offering.pricing_plan.period
                != self.change.organisation.billing_period
            ):
                errors["requested_offering"] = _(
                    "The requested plan must use the organisation's billing period."
                )

        for field_name in ("previous_membership", "requested_membership"):
            membership = getattr(self, field_name, None)
            if (
                membership
                and self.change_id
                and membership.organisation_id != self.change.organisation_id
            ):
                errors[field_name] = _(
                    "The member must belong to the change's organisation."
                )

        if self.action == self.Action.UPGRADE and not self.previous_offering_id:
            errors["previous_offering"] = _("An upgrade must record the current plan.")

        if self.action == self.Action.REASSIGN:
            if not self.previous_membership_id:
                errors["previous_membership"] = _(
                    "A reassignment must record the current member."
                )
            if not self.requested_membership_id:
                errors["requested_membership"] = _(
                    "A reassignment must identify the replacement member."
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.clean()
        return super().save(*args, **kwargs)


class OrganisationAuditEvent(models.Model):
    """Append-only record of an organisation lifecycle decision."""

    class EventType(models.TextChoices):
        CREATED = "created", _("Created")
        ACTIVATED = "activated", _("Activated")
        INVITATION_SENT = "invitation-sent", _("Invitation sent")
        INVITATION_ACCEPTED = "invitation-accepted", _("Invitation accepted")
        INVITATION_CANCELLED = "invitation-cancelled", _("Invitation cancelled")
        INVITATION_EXPIRED = "invitation-expired", _("Invitation expired")
        ROLE_CHANGED = "role-changed", _("Role changed")
        OWNERSHIP_TRANSFERRED = "ownership-transferred", _("Ownership transferred")
        SEAT_ASSIGNED = "seat-assigned", _("Subscription assigned")
        SEAT_RELEASED = "seat-released", _("Subscription released")
        PLAN_CHANGED = "plan-changed", _("Plan changed")
        SEAT_CHANGE_REQUESTED = "seat-change-requested", _("Seat change requested")
        SEAT_CHANGE_APPLIED = "seat-change-applied", _("Seat change applied")
        SEAT_CHANGE_CANCELLED = "seat-change-cancelled", _("Seat change cancelled")
        MEMBER_REMOVED = "member-removed", _("Member removed")
        MEMBER_LEFT = "member-left", _("Member left")
        PRIVACY_CHANGED = "privacy-changed", _("Privacy changed")
        SUSPENDED = "suspended", _("Suspended")
        RESTORED = "restored", _("Restored")
        CLOSURE_REQUESTED = "closure-requested", _("Closure requested")
        CLOSED = "closed", _("Closed")

    organisation = models.ForeignKey(
        Organisation, on_delete=models.CASCADE, related_name="audit_events"
    )
    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="organisation_audit_events",
        null=True,
        blank=True,
    )
    membership = models.ForeignKey(
        OrganisationMembership,
        on_delete=models.SET_NULL,
        related_name="audit_events",
        null=True,
        blank=True,
    )
    invitation = models.ForeignKey(
        OrganisationInvitation,
        on_delete=models.SET_NULL,
        related_name="audit_events",
        null=True,
        blank=True,
    )
    seat = models.ForeignKey(
        OrganisationSeat,
        on_delete=models.SET_NULL,
        related_name="audit_events",
        null=True,
        blank=True,
    )
    event_type = models.CharField(max_length=40, choices=EventType.choices)
    message = models.CharField(max_length=1024)
    event_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-pk")
        indexes = [models.Index(fields=("organisation", "-created_at"))]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError(_("Organisation audit events are append-only."))
        related_objects = {
            "membership": self.membership if self.membership_id else None,
            "invitation": self.invitation if self.invitation_id else None,
            "seat": self.seat if self.seat_id else None,
        }
        errors = {
            field: _("This object must belong to the audit event's organisation.")
            for field, related_object in related_objects.items()
            if related_object and related_object.organisation_id != self.organisation_id
        }
        if errors:
            raise ValidationError(errors)
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.organisation}: {self.get_event_type_display()}"
