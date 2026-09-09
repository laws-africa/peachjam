from datetime import timedelta

from allauth.account.models import EmailAddress
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from peachjam_subs.models import (
    OffboardingFeedback,
    Organisation,
    OrganisationMembership,
    OrganisationSeat,
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
        self.organisation = organisation_service.create_organisation(
            name="Example Chambers",
            billing_period=PricingPlan.Period.MONTHLY,
            privacy_mode=Organisation.PrivacyMode.BILLING_ONLY,
            actor=self.staff,
            owner=self.owner,
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

    def test_release_assignment_restores_default_subscription(self):
        settings = subscription_settings()
        settings.default_product_offering = ProductOffering.objects.get(pk=2)
        settings.save()
        self.organisation.status = Organisation.Status.ACTIVE
        self.organisation.save(update_fields=["status"])
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
        organisation_service.close_organisation(
            organisation=self.organisation, actor=self.staff
        )

        self.organisation.refresh_from_db()
        membership = OrganisationMembership.objects.get(
            organisation=self.organisation, user=self.owner
        )
        self.assertEqual(Organisation.Status.CLOSED, self.organisation.status)
        self.assertEqual(OrganisationMembership.Status.ENDED, membership.status)
