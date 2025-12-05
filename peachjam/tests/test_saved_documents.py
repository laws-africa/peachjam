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

        self.doc1 = SavedDocument.objects.create(
            user=self.user, work=CoreDocument.objects.get(pk=5389).work
        )
        self.doc2 = SavedDocument.objects.create(
            user=self.user, work=CoreDocument.objects.get(pk=3407).work
        )

        self.doc1.folders.set([self.folder])
        self.doc2.folders.set([self.folder])

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

    def test_cached_js_fragments(self):
        response = self.client.get(reverse("saved_document_fragments") + "?doc_id=4124")
        self.assertNotContains(response, "Saved")
        self.assertContains(response, "saved-document-star--4124")
        self.assertContains(response, "save-document-button--4124")
        self.assertContains(response, "saved-document-table-detail--4124")
        self.assert_no_recursive(response)

        sd = SavedDocument.objects.create(
            user=self.user, work=CoreDocument.objects.get(pk=4124).work
        )

        sd.folders.set([self.folder])

        response = self.client.get(reverse("saved_document_fragments") + "?doc_id=4124")
        self.assertContains(response, "Saved")
        self.assertContains(response, "saved-document-star--4124")
        self.assertContains(response, "save-document-button--4124")
        self.assertContains(response, "saved-document-table-detail--4124")
        self.assert_no_recursive(response)

    def test_new_fragment_format_only(self):
        saved_documents = [(self.doc1, 5389), (self.doc2, 3407)]

        response = self.client.get(
            reverse("saved_document_fragments") + "?doc_ids=5389,3407"
        )
        self.assertContains(response, "Saved")

        for doc, id in saved_documents:
            self.assertContains(response, f"saved-document-star--{id}")
            self.assertContains(response, f"save-document-button--{id}")
            self.assertContains(response, f"saved-document-table-detail--{id}")
            self.assert_no_recursive(response)

        self.assert_no_recursive(response)

    def test_hybrid_fragment_format(self):
        saved_documents = [(self.doc1, 5389), (self.doc2, 3407)]

        response = self.client.get(
            reverse("saved_document_fragments") + "?doc_id=5389&doc_ids=3407"
        )
        self.assertContains(response, "Saved")

        for doc, id in saved_documents:
            self.assertContains(response, f"saved-document-star--{id}")
            self.assertContains(response, f"save-document-button--{id}")
            self.assertContains(response, f"saved-document-table-detail--{id}")

        self.assert_no_recursive(response)

    def test_fragment_deduplication(self):
        response = self.client.get(
            reverse("saved_document_fragments")
            + "?doc_ids=5389,3407,5389,3407, 5389, 3407, 5389,3407"
        )

        self.assertContains(response, "Saved")

        self.assertContains(response, "saved-document-star--5389", 1)
        self.assertContains(
            response, "save-document-button save-document-button--5389", 1
        )
        self.assertContains(response, "saved-document-table-detail--5389", 1)

        self.assertContains(response, "saved-document-star--3407", 1)
        self.assertContains(
            response, "save-document-button save-document-button--3407", 1
        )
        self.assertContains(response, "saved-document-table-detail--3407", 1)

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
                user=self.user, work=CoreDocument.objects.get(pk=4124).work
            ).exists()
        )

    def test_modal(self):
        sd = SavedDocument.objects.create(
            user=self.user, work=CoreDocument.objects.get(pk=4124).work
        )
        sd.folders.set([self.folder])
        response = self.client.get(
            reverse("saved_document_modal", kwargs={"pk": sd.pk})
        )
        self.assertContains(response, "modal-content")
        self.assert_no_recursive(response)

    def test_update(self):
        sd = SavedDocument.objects.create(
            user=self.user, work=CoreDocument.objects.get(pk=4124).work
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
            user=self.user, work=CoreDocument.objects.get(pk=4124).work
        )
        sd.folders.set([self.folder])
        response = self.client.post(
            reverse("saved_document_delete", kwargs={"pk": sd.pk})
        )
        self.assertRedirects(
            response, reverse("saved_document_fragments") + "?doc_id=4124"
        )
