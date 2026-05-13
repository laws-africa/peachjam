from django.db import migrations, models


class Migration(migrations.Migration):
    """Move arbitration models from peachjam to peachjam-pro (arbitration_hub).

    Drops the tables here; peachjam-pro's 0002 migration recreates them.
    Both apps share the same DB so the net result is identical tables,
    just tracked under arbitration_hub's migration state.
    """

    dependencies = [
        ("peachjam", "0298_remove_judgmentoffence_judgment_and_more"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel("ArbitrationAward"),
                migrations.DeleteModel("ArbitrationSeat"),
                migrations.DeleteModel("ArbitralInstitution"),
                migrations.AlterField(
                    model_name="coredocument",
                    name="doc_type",
                    field=models.CharField(
                        choices=[
                            ("core_document", "Core Document"),
                            ("bill", "Bill"),
                            ("gazette", "Gazette"),
                            ("generic_document", "Generic Document"),
                            ("judgment", "Judgment"),
                            ("legal_instrument", "Legal Instrument"),
                            ("legislation", "Legislation"),
                            ("book", "Book"),
                            ("journal_article", "Journal Article"),
                            ("causelist", "Cause List"),
                        ],
                        default="core_document",
                        max_length=255,
                        verbose_name="document type",
                    ),
                ),
            ],
            database_operations=[
                # Drop in FK-safe order: award first (references institution + seat)
                migrations.DeleteModel("ArbitrationAward"),
                migrations.DeleteModel("ArbitrationSeat"),
                migrations.DeleteModel("ArbitralInstitution"),
            ],
        ),
    ]
