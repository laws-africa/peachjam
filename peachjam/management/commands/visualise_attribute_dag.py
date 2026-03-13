import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from peachjam.models.lifecycle import attribute_dag


class Command(BaseCommand):
    help = "Export the attribute DAG for visualisation."

    def add_arguments(self, parser):
        parser.add_argument(
            "output",
            nargs="?",
            default=None,
            help="Optional output file path. If omitted, output is written to stdout.",
        )
        parser.add_argument(
            "--igraph-format",
            default=None,
            help="Optional igraph format override. If omitted, igraph infers the format from the filename.",
        )
        parser.add_argument(
            "--format",
            choices=["auto", "json", "text", "igraph"],
            default="auto",
            help="Export mode. 'auto' infers from the filename extension.",
        )

    def handle(self, *args, **options):
        output_arg = options["output"]
        output = Path(output_arg) if output_arg else None
        export_format = options["igraph_format"]
        mode = options["format"]

        if mode == "auto":
            suffix = output.suffix.lower() if output else ""
            if suffix == ".json":
                mode = "json"
            elif suffix in {".txt", ".text"}:
                mode = "text"
            elif output is None:
                mode = "text"
            else:
                mode = "igraph"

        if mode == "json":
            rendered = (
                json.dumps(attribute_dag.as_dict(), indent=2, sort_keys=True) + "\n"
            )
            if output:
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(rendered)
                self.stdout.write(
                    self.style.SUCCESS(f"Exported attribute DAG JSON to {output}.")
                )
            else:
                self.stdout.write(rendered, ending="")
            return

        if mode == "text":
            rendered = self.render_text()
            if output:
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(rendered)
                self.stdout.write(
                    self.style.SUCCESS(f"Exported attribute DAG text to {output}.")
                )
            else:
                self.stdout.write(rendered, ending="")
            return

        if output is None:
            raise CommandError(
                "An output file is required for igraph exports. Use --format text or --format json for stdout."
            )

        graph = attribute_dag.to_igraph()
        output.parent.mkdir(parents=True, exist_ok=True)

        try:
            if (export_format or output.suffix.lstrip(".")).lower() == "svg":
                graph.write(str(output), format=export_format, layout="auto")
            else:
                graph.write(str(output), format=export_format)
        except (IOError, OSError, ValueError) as exc:
            raise CommandError(f"Could not export attribute DAG: {exc}") from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"Exported attribute DAG with {graph.vcount()} nodes and {graph.ecount()} edges to {output}."
            )
        )

    def render_text(self):
        lines = []
        for edge, metadata in sorted(attribute_dag.edges().items()):
            source, target = edge
            lines.append(f"{source} -> {target}")
            for item in metadata:
                lines.append(
                    f"  - {item.function_name} [{item.timing}] "
                    f"{item.declaration_mode} owner={item.owner_class}"
                )
        if not lines:
            lines.append("(attribute DAG is empty)")
        return "\n".join(lines) + "\n"
