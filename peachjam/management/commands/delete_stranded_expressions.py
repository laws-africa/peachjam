import logging

from django.core.management import BaseCommand
from django.db import transaction

from peachjam.models import Legislation

log = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Deletes legislation objects whose dates aren't included in their own points_in_time. "
        "Add --dry-run to see a list first."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        if dry_run:
            log.info("Dry run, won't actually make changes.")
        with transaction.atomic():
            for expression in (
                Legislation.objects.all().only("date", "metadata_json").iterator()
            ):
                point_in_time_dates = [
                    point_in_time["date"]
                    for point_in_time in expression.metadata_json.get(
                        "points_in_time", []
                    )
                ]
                if expression.date.strftime("%Y-%m-%d") not in point_in_time_dates:
                    log.info(
                        f"Deleting expression {expression.expression_frbr_uri} for not being in {point_in_time_dates}"
                    )
                    expression.delete()
            if dry_run:
                raise Exception("Forcing rollback on dry run.")
