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
    pending_privacy_mode = models.CharField(
        max_length=20,
        choices=PrivacyMode.choices,
        null=True,
        blank=True,
    )
    privacy_change_on = models.DateField(null=True, blank=True)
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

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("organisation", "email"),
                condition=Q(status="pending"),
                name="one_pending_invitation_per_org_email",
            )
        ]

    @property
    def is_expired(self):
        return self.status == self.Status.PENDING and timezone.now() >= self.expires_at

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

    def __str__(self):
        return f"{self.seat} assigned to {self.membership.user}"


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
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.organisation}: {self.get_event_type_display()}"
