from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from peachjam.adapters.gazettes import GazetteAPIAdapter


class GazetteAdapterSourceURLTests(SimpleTestCase):
    def test_imports_s3_reference_without_setting_source_url(self):
        uri = "/akn/za/officialGazette/government-gazette/2026-11-20/1/eng@2026-11-20"
        payload = {
            "expression_frbr_uri": uri,
            "jurisdiction": "za",
            "language": "en",
            "date": "2026-11-20",
            "name": "Gazette 1",
            "publication": "Government Gazette",
            "sub_publication": None,
            "supplement": False,
            "supplement_number": None,
            "part": None,
            "key": "test.pdf",
            "created_at": "2026-11-20T00:00:00Z",
            "updated_at": "2026-11-20T00:00:00Z",
            "s3_location": "lawsafrica-gazettes-archive/archive/za/test.pdf",
            "size": 123,
        }
        for created, include_download_url in (
            (True, True),
            (False, True),
            (True, False),
        ):
            with self.subTest(created=created, download_url=include_download_url):
                document = dict(payload)
                if include_download_url:
                    document["download_url"] = f"https://gazettes.africa{uri}/source"
                adapter = GazetteAPIAdapter(
                    Mock(), {"api_url": "https://api.example.org", "token": "test"}
                )
                gazette = Mock(expression_frbr_uri=uri)
                source = Mock()
                with (
                    patch.object(
                        adapter, "client_get", return_value=Mock(json=lambda: document)
                    ),
                    patch(
                        "peachjam.adapters.gazettes.get_country_and_locality",
                        return_value=(Mock(), None),
                    ),
                    patch("peachjam.adapters.gazettes.Language.objects.get"),
                    patch(
                        "peachjam.adapters.gazettes.Gazette.objects.update_or_create",
                        return_value=(gazette, created),
                    ),
                    patch(
                        "peachjam.adapters.gazettes.SourceFile.objects.update_or_create",
                        return_value=(source, created),
                    ) as update,
                    patch(
                        "peachjam.adapters.gazettes.SourceFile.objects.filter"
                    ) as rows,
                ):
                    adapter.update_document("https://api.example.org/gazettes/1")
                defaults = update.call_args.kwargs["defaults"]
                self.assertNotIn("source_url", defaults)
                self.assertEqual(
                    defaults["file"],
                    "s3:lawsafrica-gazettes-archive:archive/za/test.pdf",
                )
                rows.return_value.update.assert_called_once_with(file=defaults["file"])
                source.refresh_from_db.assert_called_once()
                source.file_changed.assert_called_once()
