import argparse
import json
import sys

from django.core.management import BaseCommand
from django.db import transaction

from peachjam.models.taxonomies import Taxonomy


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "--root", type=str, help="Slug of the taxonomy to import or export"
        )
        parser.add_argument(
            "--import", action="store_true", help="Import the taxonomy tree"
        )
        parser.add_argument(
            "--export", action="store_true", help="Export the taxonomy tree"
        )
        parser.add_argument(
            "infile",
            nargs="?",
            type=argparse.FileType("r"),
            default=sys.stdin,
            help="File to import from (JSON)",
        )
        parser.add_argument(
            "outfile",
            nargs="?",
            type=argparse.FileType("w"),
            default=sys.stdout,
            help="File to export to (JSON)",
        )

    def handle(self, *args, **kwargs):
        if kwargs["import"] and kwargs["export"]:
            raise ValueError("Specify only one of --import or --export")

        with transaction.atomic():
            if kwargs["import"]:
                self.do_import(**kwargs)

            if kwargs["export"]:
                self.do_export(**kwargs)

    def do_import(self, **kwargs):
        root_node = None
        root = kwargs.get("root")
        if root:
            root_node = Taxonomy.objects.filter(slug=root).first()
            if not root_node:
                root_node = Taxonomy.add_root(name=root)
        data = json.load(kwargs["infile"])
        Taxonomy.load_bulk(data, parent=root_node)

    def do_export(self, **kwargs):
        root_node = None
        root = kwargs.get("root")
        if root:
            root_node = Taxonomy.objects.filter(slug=root).first()
            if not root_node:
                raise ValueError("Root node not found: " + root)
        data = Taxonomy.dump_bulk(root_node, keep_ids=False)

        # keep only the name and slug of the data
        def fixup(node):
            node["data"] = {
                k: v for k, v in node["data"].items() if k in ["name", "slug"]
            }
            for child in node.get("children", []):
                fixup(child)

        for node in data:
            fixup(node)

        json.dump(data, kwargs["outfile"])
