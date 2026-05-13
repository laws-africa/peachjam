from django.db import migrations, models


class Migration(migrations.Migration):
    """Remove arbitration models from peachjam's migration state.

    Tables are kept in the database — ownership moves to peachjam-pro,
    which must supply a matching SeparateDatabaseAndState migration that
    adds the models to its own state without recreating the tables.
    """

    dependencies = [
        ("peachjam", "0297_alter_offencecategory_options_remove_flynote_slug_and_more"),
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
            database_operations=[],
        ),
    ]
