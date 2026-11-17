from django.db import migrations

FEATURE_NAME = "Leading authorities"
PERMISSION_CODENAME = "view_leadingauthority"


def add_leading_authorities_feature(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    Feature = apps.get_model("peachjam_subs", "Feature")
    Permission = apps.get_model("auth", "Permission")
    db_alias = schema_editor.connection.alias

    content_type, _ = ContentType.objects.using(db_alias).get_or_create(
        app_label="peachjam",
        model="leadingauthority",
    )
    permission, _ = Permission.objects.using(db_alias).get_or_create(
        content_type=content_type,
        codename=PERMISSION_CODENAME,
        defaults={"name": "Can view leading authority"},
    )
    feature, _ = Feature.objects.using(db_alias).get_or_create(
        name=FEATURE_NAME,
        defaults={"name_en": FEATURE_NAME, "ordering": 16},
    )
    feature.permissions.add(permission)


def remove_leading_authorities_feature(apps, schema_editor):
    Feature = apps.get_model("peachjam_subs", "Feature")
    Feature.objects.using(schema_editor.connection.alias).filter(
        name=FEATURE_NAME
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("peachjam", "0328_legalsubject_leadingauthority_and_more"),
        ("peachjam_subs", "0023_subscription_billing_anchor_on"),
    ]

    operations = [
        migrations.RunPython(
            add_leading_authorities_feature,
            remove_leading_authorities_feature,
        ),
    ]
