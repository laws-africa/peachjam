from django.core.management import BaseCommand, call_command
from languages_plus.utils import associate_countries_and_languages


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        call_command("update_countries_plus")
        call_command("loaddata", "languages_data.json.gz")
        associate_countries_and_languages()
