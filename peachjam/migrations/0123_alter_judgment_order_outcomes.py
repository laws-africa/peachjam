# Generated by Django 3.2.20 on 2024-03-06 10:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("peachjam", "0122_lower_court_judges"),
    ]

    operations = [
        migrations.AlterField(
            model_name="judgment",
            name="order_outcomes",
            field=models.ManyToManyField(
                blank=True, related_name="judgments", to="peachjam.OrderOutcome"
            ),
        ),
    ]
