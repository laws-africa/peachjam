from django.db import migrations, models


def backfill_selectable_offerings(apps, schema_editor):
    Product = apps.get_model("peachjam_subs", "Product")
    for product in Product.objects.exclude(default_offering__isnull=True).iterator():
        product.selectable_offerings.add(product.default_offering_id)


def reverse_backfill_selectable_offerings(apps, schema_editor):
    Product = apps.get_model("peachjam_subs", "Product")
    for product in Product.objects.all().iterator():
        first_selectable = (
            product.selectable_offerings.order_by("id")
            .values_list("id", flat=True)
            .first()
        )
        if first_selectable:
            product.default_offering_id = first_selectable
            product.save(update_fields=["default_offering"])
        product.selectable_offerings.clear()


class Migration(migrations.Migration):
    dependencies = [
        ("peachjam_subs", "0015_document_chat_limit"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="selectable_offerings",
            field=models.ManyToManyField(
                blank=True,
                help_text="Offerings explicitly available to users for this product (for example monthly and annual).",
                related_name="selectable_for_products",
                to="peachjam_subs.productoffering",
            ),
        ),
        migrations.RunPython(
            backfill_selectable_offerings,
            reverse_backfill_selectable_offerings,
        ),
        migrations.RemoveField(
            model_name="product",
            name="default_offering",
        ),
    ]
