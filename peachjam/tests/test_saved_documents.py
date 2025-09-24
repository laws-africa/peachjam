from django.contrib.auth.models import Permission, User
from django.test import TestCase
from django.urls import reverse

from peachjam.models import CoreDocument, Folder, SavedDocument, pj_settings
from peachjam_subs.models import Subscription


class SavedDocumentViewsTest(TestCase):
    fixtures = [
        "tests/countries",
        "documents/sample_documents",
        "tests/users",
        "tests/products",
    ]

    def setUp(self):
        pjs = pj_settings()
        pjs.allow_save_documents = True
        pjs.save()

        self.user = User.objects.first()
        self.client._login(self.user, "django.contrib.auth.backends.ModelBackend")
        self.user.user_permissions.add(
            Permission.objects.get(codename="add_saveddocument")
        )
        self.user.user_permissions.add(
            Permission.objects.get(codename="change_saveddocument")
        )
        self.user.user_permissions.add(
            Permission.objects.get(codename="delete_saveddocument")
        )
        self.folder = Folder.objects.create(user=self.user, name="test")
        Subscription.get_or_create_active_for_user(self.user)

    def assert_no_recursive(self, response):
        self.assertNotContains(
            response,
            "[data-document-id]",
            200,
            "Cannot contain [data-document-id] to prevent recursion with loadSavedDocuments javascript",
        )

    def test_fragments_not_allowed(self):
        # no saved documents
        pjs = pj_settings()
        pjs.allow_save_documents = False
        pjs.save()

        self.assertEqual(
            404,
            self.client.get(
                reverse("saved_document_fragments") + "?doc_id=4124"
            ).status_code,
        )

    def test_fragments(self):
        response = self.client.get(reverse("saved_document_fragments") + "?doc_id=4124")
        self.assertNotContains(response, "Saved")
        self.assertContains(response, "saved-document-star--4124")
        self.assertContains(response, "save-document-button--4124")
        self.assertContains(response, "saved-document-table-detail--4124")
        self.assert_no_recursive(response)

        sd = SavedDocument.objects.create(
            user=self.user, document=CoreDocument.objects.get(pk=4124)
        )
        sd.folders.set([self.folder])

        response = self.client.get(reverse("saved_document_fragments") + "?doc_id=4124")
        self.assertContains(response, "Saved")
        self.assertContains(response, "saved-document-star--4124")
        self.assertContains(response, "save-document-button--4124")
        self.assertContains(response, "saved-document-table-detail--4124")
        self.assert_no_recursive(response)

    def test_create(self):
        response = self.client.post(reverse("saved_document_create") + "?doc_id=4124")
        self.assertContains(response, "Saved")
        self.assertContains(response, "saved-document-star--4124")
        self.assertContains(response, "save-document-button--4124")
        self.assertContains(response, "saved-document-table-detail--4124")
        self.assertContains(response, "modal-content")
        self.assert_no_recursive(response)

        self.assertTrue(
            SavedDocument.objects.filter(
                user=self.user, document=CoreDocument.objects.get(pk=4124)
            ).exists()
        )

    def test_modal(self):
        sd = SavedDocument.objects.create(
            user=self.user, document=CoreDocument.objects.get(pk=4124)
        )
        sd.folders.set([self.folder])
        response = self.client.get(
            reverse("saved_document_modal", kwargs={"pk": sd.pk})
        )
        self.assertContains(response, "modal-content")
        self.assert_no_recursive(response)

    def test_update(self):
        sd = SavedDocument.objects.create(
            user=self.user, document=CoreDocument.objects.get(pk=4124)
        )
        sd.folders.set([self.folder])
        response = self.client.post(
            reverse("saved_document_update", kwargs={"pk": sd.pk}), {"note": "my note"}
        )
        self.assertRedirects(
            response, reverse("saved_document_fragments") + "?doc_id=4124"
        )

    def test_delete(self):
        sd = SavedDocument.objects.create(
            user=self.user, document=CoreDocument.objects.get(pk=4124)
        )
        sd.folders.set([self.folder])
        response = self.client.post(
            reverse("saved_document_delete", kwargs={"pk": sd.pk})
        )
        self.assertRedirects(
            response, reverse("saved_document_fragments") + "?doc_id=4124"
        )
