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
            choices=["auto", "json", "text", "mermaid", "igraph"],
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
            elif suffix in {".mmd", ".mermaid"}:
                mode = "mermaid"
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

        if mode == "mermaid":
            rendered = self.render_mermaid()
            if output:
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(rendered)
                self.stdout.write(
                    self.style.SUCCESS(f"Exported attribute DAG Mermaid to {output}.")
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
                function_label = item.function_name
                if item.declaration_mode == "on-class":
                    function_label = f"{item.owner_class}.{item.function_name}"
                lines.append(
                    f"  - {function_label} [{item.timing}] {item.declaration_mode}"
                )
                lines.append("")
        if not lines:
            lines.append("(attribute DAG is empty)")
        return "\n".join(lines) + "\n"

    def render_mermaid(self):
        lines = ["flowchart TD"]
        edges = attribute_dag.edges()
        node_ids = {}

        def node_id(name):
            if name not in node_ids:
                node_ids[name] = f"N{len(node_ids)}"
            return node_ids[name]

        for source, target in sorted(edges):
            src_id = node_id(source)
            tgt_id = node_id(target)
            lines.append(f'  {src_id}["{source}"] --> {tgt_id}["{target}"]')

        if len(lines) == 1:
            lines.append("  Empty[attribute DAG is empty]")

        return "\n".join(lines) + "\n"
