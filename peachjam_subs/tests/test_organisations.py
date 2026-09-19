from datetime import timedelta
from unittest.mock import patch

from allauth.account.models import EmailAddress
from django.contrib.auth.models import User
from django.core import mail
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from guardian.shortcuts import assign_perm
from templated_email import get_templated_mail

from peachjam_subs.models import (
    OffboardingFeedback,
    Organisation,
    OrganisationAuditEvent,
    OrganisationInvitation,
    OrganisationMembership,
    OrganisationSeat,
    OrganisationSeatAssignment,
    OrganisationSeatChange,
    PricingPlan,
    ProductOffering,
    Subscription,
    subscription_settings,
)
from peachjam_subs.organisations.services import organisation_service


class OrganisationServiceTests(TestCase):
    fixtures = ["tests/countries", "tests/users", "tests/products"]

    def setUp(self):
        self.staff = User.objects.create_superuser(
            username="staff@example.com", email="staff@example.com", password="password"
        )
        self.owner = User.objects.create_user(
            username="owner@example.com", email="owner@example.com"
        )
        self.member = User.objects.create_user(
            username="member@example.com", email="member@example.com"
        )
        EmailAddress.objects.create(
            user=self.owner, email=self.owner.email, verified=True, primary=True
        )
        EmailAddress.objects.create(
            user=self.member, email=self.member.email, verified=True, primary=True
        )
        self.offering = ProductOffering.objects.get(pk=1)
        assign_perm("peachjam_subs.can_subscribe", self.owner, self.offering)
        self.organisation = organisation_service.create_organisation(
            name="Example Chambers",
            billing_period=PricingPlan.Period.MONTHLY,
            privacy_mode=Organisation.PrivacyMode.BILLING_ONLY,
            actor=self.staff,
            owner=self.owner,
        )

    def test_private_free_offering_is_available_through_owner_permission(self):
        self.organisation.billing_period = PricingPlan.Period.ANNUALLY
        self.organisation.save(update_fields=["billing_period"])
        staff_offering = ProductOffering.objects.get(pk=2)

        self.assertNotIn(
            staff_offering,
            organisation_service.offerings_available_to_organisation(self.organisation),
        )

        assign_perm("peachjam_subs.can_subscribe", self.owner, staff_offering)

        self.assertIn(
            staff_offering,
            organisation_service.offerings_available_to_organisation(self.organisation),
        )

    def test_invited_owner_can_accept_private_free_offering(self):
        staff_offering = ProductOffering.objects.get(pk=2)
        organisation = organisation_service.create_organisation(
            name="Staff Organisation",
            billing_period=PricingPlan.Period.ANNUALLY,
            privacy_mode=Organisation.PrivacyMode.MANAGED_USAGE,
            actor=self.staff,
        )
        invitation = organisation_service.send_invitation(
            organisation=organisation,
            email=self.member.email,
            role=OrganisationMembership.Role.OWNER,
            requested_product_offering=staff_offering,
            actor=self.staff,
        )

        membership = organisation_service.accept_invitation(
            token=invitation.token,
            user=self.member,
        )

        self.assertEqual(OrganisationMembership.Role.OWNER, membership.role)
        self.assertEqual(self.member, organisation.owner)
        self.assertEqual(
            staff_offering,
            membership.seat_assignments.get().seat.product_offering,
        )
        self.assertIn(
            staff_offering,
            organisation_service.offerings_available_to_organisation(organisation),
        )

    def test_duplicate_open_invitation_is_rejected(self):
        organisation_service.send_invitation(
            organisation=self.organisation,
            email=self.member.email,
            role=OrganisationMembership.Role.MEMBER,
            actor=self.owner,
        )

        with self.assertRaisesMessage(
            ValidationError, "already has an open invitation"
        ):
            organisation_service.send_invitation(
                organisation=self.organisation,
                email=self.member.email.upper(),
                role=OrganisationMembership.Role.MEMBER,
                actor=self.owner,
            )

    def test_invitation_to_existing_member_with_seat_is_rejected(self):
        membership = OrganisationMembership.objects.create(
            organisation=self.organisation,
            user=self.member,
            role=OrganisationMembership.Role.MEMBER,
        )
        seat = OrganisationSeat.objects.create(
            organisation=self.organisation,
            product_offering=self.offering,
            status=OrganisationSeat.Status.ACTIVE,
        )
        OrganisationSeatAssignment.objects.create(seat=seat, membership=membership)

        with self.assertRaisesMessage(ValidationError, "already a member"):
            organisation_service.send_invitation(
                organisation=self.organisation,
                email=self.member.email,
                role=OrganisationMembership.Role.MEMBER,
                actor=self.owner,
            )

    def test_ownership_transfer_copies_private_offering_permissions(self):
        new_owner_membership = OrganisationMembership.objects.create(
            organisation=self.organisation,
            user=self.member,
            role=OrganisationMembership.Role.ADMIN,
        )

        organisation_service.transfer_ownership(
            organisation=self.organisation,
            new_owner_membership=new_owner_membership,
            actor=self.owner,
        )

        self.assertIn(
            self.offering,
            organisation_service.offerings_available_to_organisation(self.organisation),
        )

    def test_one_active_organisation_per_user(self):
        other = Organisation.objects.create(
            name="Other", billing_period=PricingPlan.Period.MONTHLY
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            OrganisationMembership.objects.create(
                organisation=other,
                user=self.owner,
                role=OrganisationMembership.Role.MEMBER,
            )

    def test_organisation_administrator_emails_excludes_members(self):
        administrator = User.objects.create_user(
            username="administrator@example.com", email="administrator@example.com"
        )
        OrganisationMembership.objects.create(
            organisation=self.organisation,
            user=administrator,
            role=OrganisationMembership.Role.ADMIN,
        )
        OrganisationMembership.objects.create(
            organisation=self.organisation,
            user=self.member,
            role=OrganisationMembership.Role.MEMBER,
        )

        self.assertCountEqual(
            [self.owner.email, administrator.email],
            self.organisation.administrator_emails(),
        )

    def test_dunning_recipients_are_normalized_and_deduplicated(self):
        administrator = User.objects.create_user(
            username="Admin@Example.com", email="Admin@Example.com"
        )
        OrganisationMembership.objects.create(
            organisation=self.organisation,
            user=administrator,
            role=OrganisationMembership.Role.ADMIN,
        )

        recipients = self.organisation.dunning_recipient_emails(
            billing_email="OWNER@example.com",
            billing_contacts=[" finance@example.com ", "ADMIN@example.com"],
        )

        self.assertEqual(
            ["owner@example.com", "admin@example.com", "finance@example.com"],
            recipients,
        )

    def test_sixteenth_dunning_recipient_is_rejected(self):
        for index in range(14):
            user = User.objects.create_user(
                username=f"admin-{index}@example.com",
                email=f"admin-{index}@example.com",
            )
            OrganisationMembership.objects.create(
                organisation=self.organisation,
                user=user,
                role=OrganisationMembership.Role.ADMIN,
            )

        with self.assertRaisesMessage(
            ValidationError,
            "at most 15 owners, administrators, and billing contacts",
        ):
            organisation_service.send_invitation(
                organisation=self.organisation,
                email="sixteenth@example.com",
                role=OrganisationMembership.Role.ADMIN,
                actor=self.owner,
            )

    @patch("peachjam_subs.organisations.notifications.send_templated_mail")
    def test_invitation_uses_templated_email_backend(self, send_templated_mail):
        with self.captureOnCommitCallbacks(execute=True):
            invitation = organisation_service.send_invitation(
                organisation=self.organisation,
                email=self.member.email,
                role=OrganisationMembership.Role.MEMBER,
                actor=self.owner,
            )

        send_templated_mail.assert_called_once()
        kwargs = send_templated_mail.call_args.kwargs
        self.assertEqual("organisation/invitation", kwargs["template_name"])
        self.assertEqual([self.member.email], kwargs["recipient_list"])
        self.assertEqual(self.organisation.name, kwargs["context"]["organisation"])
        self.assertIn(str(invitation.token), kwargs["context"]["invitation_url"])

    @patch("peachjam_subs.organisations.notifications.send_templated_mail")
    def test_administrator_email_uses_shared_notification_template(
        self, send_templated_mail
    ):
        with self.captureOnCommitCallbacks(execute=True):
            self.organisation.notify_administrators("Subject", "Message")

        send_templated_mail.assert_called_once_with(
            template_name="organisation/notification",
            from_email=send_templated_mail.call_args.kwargs["from_email"],
            recipient_list=[self.owner.email],
            context={"subject": "Subject", "body": "Message"},
        )

    def test_organisation_invitation_template_uses_shared_email_layout(self):
        message = get_templated_mail(
            template_name="organisation/invitation",
            from_email="sender@example.com",
            to=[self.member.email],
            context={
                "organisation": self.organisation.name,
                "expiry": timezone.localdate() + timedelta(days=14),
                "invitation_url": "https://example.com/invitation/abc/",
            },
        )
        html = message.alternatives[0][0]

        self.assertIn("You have been invited", message.subject)
        self.assertIn(self.organisation.name, html)
        self.assertIn('href="https://example.com/invitation/abc/"', html)
        self.assertIn("Accept invitation", html)

    def test_staff_changes_privacy_mode_immediately_without_notifying_members(self):
        organisation_service.change_privacy_mode(
            organisation=self.organisation,
            privacy_mode=Organisation.PrivacyMode.MANAGED_USAGE,
            actor=self.staff,
        )

        self.organisation.refresh_from_db()
        self.assertEqual(
            Organisation.PrivacyMode.MANAGED_USAGE, self.organisation.privacy_mode
        )
        event = self.organisation.audit_events.latest("created_at")
        self.assertEqual(
            OrganisationAuditEvent.EventType.PRIVACY_CHANGED, event.event_type
        )
        self.assertEqual(self.staff, event.actor)
        self.assertEqual(
            {
                "before": Organisation.PrivacyMode.BILLING_ONLY,
                "after": Organisation.PrivacyMode.MANAGED_USAGE,
            },
            event.event_data,
        )
        self.assertEqual([], mail.outbox)

    def test_organisation_admin_cannot_change_privacy_mode(self):
        with self.assertRaises(PermissionDenied):
            organisation_service.change_privacy_mode(
                organisation=self.organisation,
                privacy_mode=Organisation.PrivacyMode.MANAGED_USAGE,
                actor=self.owner,
            )

    def test_accept_invitation_creates_provisional_assignment_without_trial(self):
        invitation = organisation_service.send_invitation(
            organisation=self.organisation,
            email=self.member.email,
            role=OrganisationMembership.Role.MEMBER,
            requested_product_offering=self.offering,
            actor=self.owner,
        )

        membership = organisation_service.accept_invitation(
            token=invitation.token, user=self.member
        )

        assignment = membership.seat_assignments.get()
        self.assertEqual(OrganisationSeat.Status.PROVISIONAL, assignment.seat.status)
        self.assertIsNone(assignment.subscription)

        organisation_service.activate_organisation(
            organisation=self.organisation, actor=self.staff
        )
        assignment.refresh_from_db()
        self.assertEqual(Subscription.Status.ACTIVE, assignment.subscription.status)
        self.assertFalse(assignment.subscription.is_trial)

    def test_subscription_state_distinguishes_pending_managed_and_suspended(self):
        invitation = organisation_service.send_invitation(
            organisation=self.organisation,
            email=self.member.email,
            role=OrganisationMembership.Role.MEMBER,
            requested_product_offering=self.offering,
            actor=self.owner,
        )
        membership = organisation_service.accept_invitation(
            token=invitation.token, user=self.member
        )

        state = organisation_service.subscription_state_for_user(self.member)
        self.assertEqual(membership, state.membership)
        self.assertTrue(state.is_pending)
        self.assertFalse(state.is_managed)

        organisation_service.activate_organisation(
            organisation=self.organisation, actor=self.staff
        )
        state = organisation_service.subscription_state_for_user(self.member)
        self.assertFalse(state.is_pending)
        self.assertTrue(state.is_managed)

        assignment = membership.seat_assignments.get(ended_at__isnull=True)
        assignment.seat.status = OrganisationSeat.Status.SUSPENDED
        assignment.seat.save(update_fields=["status"])
        assignment.subscription.status = Subscription.Status.CLOSED
        assignment.subscription.save(update_fields=["status"])

        state = organisation_service.subscription_state_for_user(self.member)
        self.assertTrue(state.is_managed)

    def test_accept_invitation_is_idempotent_for_same_user(self):
        invitation = organisation_service.send_invitation(
            organisation=self.organisation,
            email=self.member.email,
            role=OrganisationMembership.Role.MEMBER,
            actor=self.owner,
        )
        first = organisation_service.accept_invitation(
            token=invitation.token, user=self.member
        )
        second = organisation_service.accept_invitation(
            token=invitation.token, user=self.member
        )
        self.assertEqual(first, second)
        self.assertEqual(
            1, OrganisationMembership.objects.filter(user=self.member).count()
        )

    def test_expired_invitation_is_rejected(self):
        invitation = organisation_service.send_invitation(
            organisation=self.organisation,
            email=self.member.email,
            role=OrganisationMembership.Role.MEMBER,
            actor=self.owner,
        )
        invitation.expires_at = timezone.now() - timedelta(seconds=1)
        invitation.save(update_fields=["expires_at"])

        with self.assertRaisesMessage(ValidationError, "expired"):
            organisation_service.accept_invitation(
                token=invitation.token, user=self.member
            )

        invitation.refresh_from_db()
        self.assertEqual(OrganisationInvitation.Status.EXPIRED, invitation.status)
        self.assertEqual(
            1,
            invitation.audit_events.filter(
                event_type=OrganisationAuditEvent.EventType.INVITATION_EXPIRED
            ).count(),
        )

    def test_closed_organisation_rejects_pending_invitation(self):
        invitation = organisation_service.send_invitation(
            organisation=self.organisation,
            email=self.member.email,
            role=OrganisationMembership.Role.MEMBER,
            actor=self.owner,
        )
        self.organisation.status = Organisation.Status.CLOSED
        self.organisation.save(update_fields=["status"])

        with self.assertRaisesMessage(ValidationError, "no longer accepting"):
            organisation_service.accept_invitation(
                token=invitation.token, user=self.member
            )

        self.assertFalse(
            OrganisationMembership.objects.filter(user=self.member).exists()
        )

    def test_assignment_must_remain_within_one_organisation(self):
        other = Organisation.objects.create(
            name="Other Chambers", billing_period=PricingPlan.Period.MONTHLY
        )
        other_membership = OrganisationMembership.objects.create(
            organisation=other,
            user=self.member,
            role=OrganisationMembership.Role.MEMBER,
        )
        seat = OrganisationSeat.objects.create(
            organisation=self.organisation,
            product_offering=self.offering,
        )
        assignment = OrganisationSeatAssignment(seat=seat, membership=other_membership)

        with self.assertRaisesMessage(ValidationError, "same organisation"):
            assignment.save()

        OrganisationSeatAssignment.objects.bulk_create([assignment])
        self.organisation.status = Organisation.Status.ACTIVE
        self.organisation.save(update_fields=["status"])
        seat.status = OrganisationSeat.Status.ACTIVE
        seat.save(update_fields=["status"])
        with self.assertRaisesMessage(ValidationError, "same organisation"):
            organisation_service.activate_assignment(assignment)

    def test_assignment_subscription_must_belong_to_member(self):
        membership = OrganisationMembership.objects.get(
            organisation=self.organisation, user=self.owner
        )
        seat = OrganisationSeat.objects.create(
            organisation=self.organisation,
            product_offering=self.offering,
        )
        member_subscription = Subscription.objects.active_for_user(self.member).get()

        with self.assertRaisesMessage(ValidationError, "assigned member"):
            OrganisationSeatAssignment.objects.create(
                seat=seat,
                membership=membership,
                subscription=member_subscription,
            )

    def test_audit_event_relations_must_belong_to_organisation(self):
        other = Organisation.objects.create(
            name="Other Chambers", billing_period=PricingPlan.Period.MONTHLY
        )
        other_membership = OrganisationMembership.objects.create(
            organisation=other,
            user=self.member,
            role=OrganisationMembership.Role.MEMBER,
        )

        with self.assertRaisesMessage(ValidationError, "audit event's organisation"):
            OrganisationAuditEvent.objects.create(
                organisation=self.organisation,
                membership=other_membership,
                event_type=OrganisationAuditEvent.EventType.MEMBER_REMOVED,
                message="Invalid event.",
            )

    def test_suspended_seat_upgrade_does_not_restore_access(self):
        upgraded_offering = ProductOffering.objects.get(pk=3)
        assign_perm("peachjam_subs.can_subscribe", self.owner, upgraded_offering)
        invitation = organisation_service.send_invitation(
            organisation=self.organisation,
            email=self.member.email,
            role=OrganisationMembership.Role.MEMBER,
            requested_product_offering=self.offering,
            actor=self.owner,
        )
        membership = organisation_service.accept_invitation(
            token=invitation.token, user=self.member
        )
        organisation_service.activate_organisation(
            organisation=self.organisation, actor=self.staff
        )
        organisation_service.suspend_organisation_entitlements(
            organisation=self.organisation, actor=self.staff
        )
        assignment = membership.seat_assignments.get(ended_at__isnull=True)

        change = organisation_service.stage_seat_upgrade(
            seat=assignment.seat,
            offering=upgraded_offering,
            actor=self.owner,
        )
        organisation_service.apply_seat_change(change=change, actor=self.owner)

        assignment.refresh_from_db()
        assignment.seat.refresh_from_db()
        self.assertEqual(OrganisationSeat.Status.SUSPENDED, assignment.seat.status)
        self.assertEqual(upgraded_offering, assignment.seat.product_offering)
        self.assertIsNone(assignment.subscription)

    def test_available_exact_plan_seat_is_reused(self):
        self.organisation.status = Organisation.Status.ACTIVE
        self.organisation.save(update_fields=["status"])
        seat = OrganisationSeat.objects.create(
            organisation=self.organisation,
            product_offering=self.offering,
            status=OrganisationSeat.Status.ACTIVE,
            starts_on=timezone.localdate(),
        )
        invitation = organisation_service.send_invitation(
            organisation=self.organisation,
            email=self.member.email,
            role=OrganisationMembership.Role.MEMBER,
            requested_product_offering=self.offering,
            actor=self.owner,
        )

        membership = organisation_service.accept_invitation(
            token=invitation.token, user=self.member
        )

        self.assertEqual(seat, membership.seat_assignments.get().seat)
        self.assertEqual(1, self.organisation.seats.count())

    def test_active_invitation_reserves_new_seat_until_change_is_applied(self):
        self.organisation.status = Organisation.Status.ACTIVE
        self.organisation.save(update_fields=["status"])

        invitation = organisation_service.send_invitation(
            organisation=self.organisation,
            email=self.member.email,
            role=OrganisationMembership.Role.MEMBER,
            requested_product_offering=self.offering,
            actor=self.owner,
        )

        self.assertEqual(
            OrganisationInvitation.Status.AWAITING_PAYMENT, invitation.status
        )
        self.assertEqual(
            OrganisationSeat.Status.PROVISIONAL, invitation.reserved_seat.status
        )
        change = self.organisation.seat_changes.get(
            status=OrganisationSeatChange.Status.AWAITING_SETTLEMENT
        )
        organisation_service.apply_seat_change(change=change, actor=self.owner)
        invitation.refresh_from_db()
        self.assertEqual(OrganisationInvitation.Status.PENDING, invitation.status)
        self.assertEqual(
            OrganisationSeat.Status.ACTIVE, invitation.reserved_seat.status
        )

        membership = organisation_service.accept_invitation(
            token=invitation.token, user=self.member
        )

        self.assertEqual(1, self.organisation.seats.count())
        self.assertEqual(
            invitation.reserved_seat_id,
            membership.seat_assignments.get().seat_id,
        )

    def test_cancelling_unpaid_invitation_ends_only_provisional_seat(self):
        self.organisation.status = Organisation.Status.ACTIVE
        self.organisation.save(update_fields=["status"])
        invitation = organisation_service.send_invitation(
            organisation=self.organisation,
            email=self.member.email,
            role=OrganisationMembership.Role.MEMBER,
            requested_product_offering=self.offering,
            actor=self.owner,
        )
        seat = invitation.reserved_seat

        organisation_service.cancel_invitation(invitation=invitation, actor=self.owner)

        seat.refresh_from_db()
        invitation.refresh_from_db()
        self.assertEqual(OrganisationSeat.Status.ENDED, seat.status)
        self.assertEqual(OrganisationInvitation.Status.CANCELLED, invitation.status)
        self.assertFalse(
            self.organisation.seat_changes.filter(
                status=OrganisationSeatChange.Status.AWAITING_SETTLEMENT
            ).exists()
        )

    def test_stale_reassignment_does_not_replace_the_current_seat_holder(self):
        self.organisation.status = Organisation.Status.ACTIVE
        self.organisation.save(update_fields=["status"])
        previous_member = OrganisationMembership.objects.create(
            organisation=self.organisation,
            user=self.member,
            role=OrganisationMembership.Role.MEMBER,
        )
        replacement_user = User.objects.create_user(
            username="replacement@example.com", email="replacement@example.com"
        )
        replacement_member = OrganisationMembership.objects.create(
            organisation=self.organisation,
            user=replacement_user,
            role=OrganisationMembership.Role.MEMBER,
        )
        current_user = User.objects.create_user(
            username="current@example.com", email="current@example.com"
        )
        current_member = OrganisationMembership.objects.create(
            organisation=self.organisation,
            user=current_user,
            role=OrganisationMembership.Role.MEMBER,
        )
        seat = OrganisationSeat.objects.create(
            organisation=self.organisation,
            product_offering=self.offering,
            status=OrganisationSeat.Status.ACTIVE,
            starts_on=timezone.localdate(),
        )
        previous_assignment = OrganisationSeatAssignment.objects.create(
            seat=seat, membership=previous_member
        )
        organisation_service.activate_assignment(previous_assignment)
        change = organisation_service.stage_seat_reassignment(
            seat=seat, membership=replacement_member, actor=self.owner
        )
        organisation_service.release_assignment(
            assignment=previous_assignment, actor=self.owner
        )
        current_assignment = organisation_service.assign_subscription(
            membership=current_member, offering=self.offering, actor=self.owner
        )
        current_assignment.refresh_from_db()
        current_subscription_id = current_assignment.subscription_id

        with self.assertRaisesMessage(
            ValidationError, "seat assignment changed while this change"
        ):
            organisation_service.apply_seat_change(change=change, actor=self.owner)

        current_assignment.refresh_from_db()
        change.refresh_from_db()
        self.assertIsNone(current_assignment.ended_at)
        self.assertEqual(current_subscription_id, current_assignment.subscription_id)
        self.assertEqual(
            OrganisationSeatChange.Status.AWAITING_SETTLEMENT, change.status
        )
        self.assertFalse(
            replacement_member.seat_assignments.filter(ended_at__isnull=True).exists()
        )

    def test_assign_subscription_requires_unused_exact_plan_seat(self):
        self.organisation.status = Organisation.Status.ACTIVE
        self.organisation.save(update_fields=["status"])
        membership = OrganisationMembership.objects.create(
            organisation=self.organisation,
            user=self.member,
            role=OrganisationMembership.Role.MEMBER,
        )

        with self.assertRaisesMessage(ValidationError, "Add a seat first"):
            organisation_service.assign_subscription(
                membership=membership, offering=self.offering, actor=self.owner
            )

    def test_unused_free_seat_can_end_immediately(self):
        free_plan = PricingPlan.objects.create(
            name="Test monthly free plan",
            price=0,
            period=self.organisation.billing_period,
        )
        free_offering = ProductOffering.objects.create(
            product=self.offering.product, pricing_plan=free_plan
        )
        seat = OrganisationSeat.objects.create(
            organisation=self.organisation,
            product_offering=free_offering,
            status=OrganisationSeat.Status.ACTIVE,
        )

        organisation_service.end_unused_free_seat(seat=seat, actor=self.owner)

        seat.refresh_from_db()
        self.assertEqual(OrganisationSeat.Status.ENDED, seat.status)
        self.assertEqual(timezone.localdate(), seat.ends_on)
        self.assertTrue(
            self.organisation.audit_events.filter(
                seat=seat, message="Ended unused free organisation seat."
            ).exists()
        )

    def test_paid_seat_cannot_end_immediately(self):
        seat = OrganisationSeat.objects.create(
            organisation=self.organisation,
            product_offering=self.offering,
            status=OrganisationSeat.Status.ACTIVE,
        )

        with self.assertRaisesMessage(
            ValidationError, "Paid seats can only end at renewal."
        ):
            organisation_service.end_unused_free_seat(seat=seat, actor=self.owner)

    def test_active_organisation_does_not_reuse_an_unsettled_provisional_seat(self):
        self.organisation.status = Organisation.Status.ACTIVE
        self.organisation.save(update_fields=["status"])
        OrganisationSeat.objects.create(
            organisation=self.organisation,
            product_offering=self.offering,
            status=OrganisationSeat.Status.PROVISIONAL,
        )

        seat = organisation_service.find_available_seat(
            self.organisation, self.offering
        )

        self.assertIsNone(seat)

    def test_expired_invitation_releases_its_paid_seat(self):
        self.organisation.status = Organisation.Status.ACTIVE
        self.organisation.save(update_fields=["status"])
        seat = OrganisationSeat.objects.create(
            organisation=self.organisation,
            product_offering=self.offering,
            status=OrganisationSeat.Status.ACTIVE,
        )
        invitation = organisation_service.send_invitation(
            organisation=self.organisation,
            email=self.member.email,
            role=OrganisationMembership.Role.MEMBER,
            requested_product_offering=self.offering,
            actor=self.owner,
        )
        invitation.expires_at = timezone.now() - timezone.timedelta(seconds=1)
        invitation.save(update_fields=["expires_at"])

        self.assertTrue(organisation_service.expire_invitation(token=invitation.token))

        invitation.refresh_from_db()
        self.assertIsNone(invitation.reserved_seat)
        self.assertEqual(
            seat,
            organisation_service.find_available_seat(self.organisation, self.offering),
        )

    def test_release_assignment_restores_default_subscription(self):
        settings = subscription_settings()
        settings.default_product_offering = ProductOffering.objects.get(pk=2)
        settings.save()
        self.organisation.status = Organisation.Status.ACTIVE
        self.organisation.save(update_fields=["status"])
        OrganisationSeat.objects.create(
            organisation=self.organisation,
            product_offering=self.offering,
            status=OrganisationSeat.Status.ACTIVE,
            starts_on=timezone.localdate(),
        )
        invitation = organisation_service.send_invitation(
            organisation=self.organisation,
            email=self.member.email,
            role=OrganisationMembership.Role.MEMBER,
            requested_product_offering=self.offering,
            actor=self.owner,
        )
        membership = organisation_service.accept_invitation(
            token=invitation.token, user=self.member
        )

        organisation_service.release_assignment(
            assignment=membership.seat_assignments.get(), actor=self.owner
        )

        self.assertEqual(
            settings.default_product_offering,
            Subscription.objects.active_for_user(self.member).first().product_offering,
        )

    def test_cancel_scheduled_membership_removal(self):
        membership = OrganisationMembership.objects.create(
            organisation=self.organisation,
            user=self.member,
            role=OrganisationMembership.Role.MEMBER,
            pending_end_on=timezone.localdate() + timedelta(days=10),
        )

        organisation_service.cancel_scheduled_membership_removal(
            membership=membership, actor=self.owner
        )

        membership.refresh_from_db()
        self.assertIsNone(membership.pending_end_on)
        event = membership.audit_events.latest("created_at")
        self.assertEqual(
            "Cancelled scheduled organisation membership removal.", event.message
        )

    def test_transfer_ownership_demotes_previous_owner(self):
        new_owner = OrganisationMembership.objects.create(
            organisation=self.organisation,
            user=self.member,
            role=OrganisationMembership.Role.ADMIN,
        )

        organisation_service.transfer_ownership(
            organisation=self.organisation,
            new_owner_membership=new_owner,
            actor=self.owner,
        )

        new_owner.refresh_from_db()
        previous = OrganisationMembership.objects.get(user=self.owner)
        self.assertEqual(OrganisationMembership.Role.OWNER, new_owner.role)
        self.assertEqual(OrganisationMembership.Role.ADMIN, previous.role)

    def test_transfer_ownership_cannot_exceed_dunning_recipient_limit(self):
        new_owner = OrganisationMembership.objects.create(
            organisation=self.organisation,
            user=self.member,
            role=OrganisationMembership.Role.MEMBER,
        )
        for index in range(14):
            user = User.objects.create_user(
                username=f"transfer-admin-{index}@example.com",
                email=f"transfer-admin-{index}@example.com",
            )
            OrganisationMembership.objects.create(
                organisation=self.organisation,
                user=user,
                role=OrganisationMembership.Role.ADMIN,
            )

        with self.assertRaisesMessage(
            ValidationError,
            "at most 15 owners, administrators, and billing contacts",
        ):
            organisation_service.transfer_ownership(
                organisation=self.organisation,
                new_owner_membership=new_owner,
                actor=self.owner,
            )

    def test_billing_period_is_immutable_after_activation(self):
        self.organisation.status = Organisation.Status.ACTIVE
        self.organisation.save(update_fields=["status"])
        self.organisation.billing_period = PricingPlan.Period.ANNUALLY

        with self.assertRaisesMessage(ValidationError, "only change at renewal"):
            self.organisation.save(update_fields=["billing_period"])

    def test_only_owner_or_staff_can_transfer_ownership(self):
        administrator = User.objects.create_user(
            username="administrator@example.com", email="administrator@example.com"
        )
        admin_membership = OrganisationMembership.objects.create(
            organisation=self.organisation,
            user=administrator,
            role=OrganisationMembership.Role.ADMIN,
        )
        new_owner = OrganisationMembership.objects.create(
            organisation=self.organisation,
            user=self.member,
            role=OrganisationMembership.Role.ADMIN,
        )

        with self.assertRaises(PermissionDenied):
            organisation_service.transfer_ownership(
                organisation=self.organisation,
                new_owner_membership=new_owner,
                actor=admin_membership.user,
            )

    def test_member_leaves_organisation_when_deleting_account(self):
        membership = OrganisationMembership.objects.create(
            organisation=self.organisation,
            user=self.member,
            role=OrganisationMembership.Role.MEMBER,
        )
        self.client.force_login(self.member)

        response = self.client.post(
            reverse("delete_account"),
            {
                "confirm_delete": True,
                "reason": OffboardingFeedback.Reason.NOT_USING_ENOUGH,
                "comment": "No longer needed",
            },
        )

        self.assertRedirects(response, reverse("account_logged_out"))
        membership.refresh_from_db()
        self.member.refresh_from_db()
        self.assertEqual(OrganisationMembership.Status.ENDED, membership.status)
        self.assertFalse(self.member.is_active)

    def test_paid_member_is_not_removed_when_account_deletion_is_blocked(self):
        membership = OrganisationMembership.objects.create(
            organisation=self.organisation,
            user=self.member,
            role=OrganisationMembership.Role.MEMBER,
        )
        current = Subscription.get_or_create_active_for_user(self.member)
        current.close()
        Subscription.objects.create(
            user=self.member,
            product_offering=self.offering,
            status=Subscription.Status.ACTIVE,
            active_at=timezone.now(),
        )
        self.client.force_login(self.member)

        response = self.client.post(
            reverse("delete_account"),
            {
                "confirm_delete": True,
                "reason": OffboardingFeedback.Reason.NOT_USING_ENOUGH,
                "comment": "No longer needed",
            },
        )

        self.assertRedirects(response, reverse("delete_account"))
        membership.refresh_from_db()
        self.member.refresh_from_db()
        self.assertEqual(OrganisationMembership.Status.ACTIVE, membership.status)
        self.assertTrue(self.member.is_active)

    def test_owner_must_transfer_before_deleting_account(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("delete_account"),
            {
                "confirm_delete": True,
                "reason": OffboardingFeedback.Reason.NOT_USING_ENOUGH,
                "comment": "No longer needed",
            },
        )

        self.assertRedirects(response, reverse("delete_account"))
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.is_active)

    def test_closing_organisation_ends_memberships(self):
        invitation = organisation_service.send_invitation(
            organisation=self.organisation,
            email="invitee@example.com",
            role=OrganisationMembership.Role.MEMBER,
            actor=self.owner,
        )
        organisation_service.close_organisation(
            organisation=self.organisation, actor=self.staff
        )

        self.organisation.refresh_from_db()
        membership = OrganisationMembership.objects.get(
            organisation=self.organisation, user=self.owner
        )
        self.assertEqual(Organisation.Status.CLOSED, self.organisation.status)
        self.assertEqual(OrganisationMembership.Status.ENDED, membership.status)
        invitation.refresh_from_db()
        self.assertEqual(OrganisationInvitation.Status.CANCELLED, invitation.status)
        self.assertIsNotNone(invitation.cancelled_at)
        self.assertTrue(
            invitation.audit_events.filter(
                event_type=OrganisationAuditEvent.EventType.INVITATION_CANCELLED
            ).exists()
        )
        self.assertTrue(
            membership.audit_events.filter(
                message="Ended organisation membership during organisation closure."
            ).exists()
        )

    def test_closing_organisation_cancels_unsettled_seat_addition(self):
        self.organisation.status = Organisation.Status.ACTIVE
        self.organisation.save(update_fields=["status"])
        invitation = organisation_service.send_invitation(
            organisation=self.organisation,
            email=self.member.email,
            role=OrganisationMembership.Role.MEMBER,
            requested_product_offering=self.offering,
            actor=self.owner,
        )
        seat = invitation.reserved_seat
        change = self.organisation.seat_changes.get(
            status=OrganisationSeatChange.Status.AWAITING_SETTLEMENT
        )

        organisation_service.close_organisation(
            organisation=self.organisation, actor=self.staff
        )

        invitation.refresh_from_db()
        seat.refresh_from_db()
        change.refresh_from_db()
        self.assertEqual(OrganisationInvitation.Status.CANCELLED, invitation.status)
        self.assertEqual(OrganisationSeat.Status.ENDED, seat.status)
        self.assertEqual(OrganisationSeatChange.Status.CANCELLED, change.status)
        with self.assertRaisesMessage(ValidationError, "can no longer be applied"):
            organisation_service.apply_seat_change(change=change, actor=self.staff)
        seat.refresh_from_db()
        self.assertEqual(OrganisationSeat.Status.ENDED, seat.status)

    def test_closing_organisation_is_idempotent(self):
        organisation_service.close_organisation(
            organisation=self.organisation, actor=self.staff
        )
        audit_count = self.organisation.audit_events.count()

        organisation_service.close_organisation(
            organisation=self.organisation, actor=self.staff
        )

        self.assertEqual(audit_count, self.organisation.audit_events.count())

    def test_closed_organisation_rejects_new_and_resent_invitations(self):
        invitation = organisation_service.send_invitation(
            organisation=self.organisation,
            email=self.member.email,
            role=OrganisationMembership.Role.MEMBER,
            actor=self.owner,
        )
        organisation_service.close_organisation(
            organisation=self.organisation, actor=self.staff
        )

        with self.assertRaisesMessage(ValidationError, "no longer accepting"):
            organisation_service.send_invitation(
                organisation=self.organisation,
                email="another@example.com",
                role=OrganisationMembership.Role.MEMBER,
                actor=self.staff,
            )
        with self.assertRaisesMessage(ValidationError, "no longer accepting"):
            organisation_service.resend_invitation(
                invitation=invitation, actor=self.staff
            )

    def test_closed_organisation_cannot_be_reactivated(self):
        organisation_service.close_organisation(
            organisation=self.organisation, actor=self.staff
        )

        with self.assertRaisesMessage(ValidationError, "cannot be activated"):
            organisation_service.activate_organisation(
                organisation=self.organisation, actor=self.staff
            )
