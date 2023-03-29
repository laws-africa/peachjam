from django_elasticsearch_dsl.management.commands.search_index import (
    Command as OriginalCommand,
)
from django_elasticsearch_dsl.registries import registry

from peachjam_search.tasks import search_model_saved


class Command(OriginalCommand):
    def add_arguments(self, parser):
        super().add_arguments(parser)

        parser.add_argument(
            "--background",
            action="store_true",
            default=False,
            dest="background",
            help="Run populate tasks in the background",
        )

    def _populate(self, models, options):
        if not options["background"]:
            return super()._populate(models, options)

        for doc in registry.get_documents(models):
            self.stdout.write(
                "Queuing up background tasks to index {} '{}' objects".format(
                    doc().get_queryset().count() if options["count"] else "all",
                    doc.django.model.__name__,
                )
            )
            qs = doc().get_indexing_queryset()

            for doc in qs:
                search_model_saved(doc._meta.label, doc.pk)
