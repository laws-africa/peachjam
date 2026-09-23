from django.core.management import BaseCommand

from peachjam.models import PopularLegislation


class Command(BaseCommand):
    help = "Fill empty popular-legislation positions with ranked suggestions"

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=10,
            help="Maximum number of popular legislation entries",
        )

    def handle(self, *args, **options):
        added = PopularLegislation.add_suggestions(limit=options["limit"])
        self.stdout.write(self.style.SUCCESS(f"Added {added} suggestion(s)."))
