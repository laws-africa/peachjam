import hashlib
import hmac
import logging
import re
from datetime import date
from functools import cached_property

import magic
import yaml
from cobalt import FrbrUri
from django.conf import settings
from django.core.files.base import ContentFile
from github import Github
from jinja2 import Environment, nodes
from jinja2.ext import Extension
from lxml import etree

from peachjam.adapters.base import Adapter
from peachjam.analysis.html import generate_toc_json_from_html
from peachjam.helpers import markdownify
from peachjam.models import Book, Image, Language, get_country_and_locality
from peachjam.plugins import plugins
from peachjam.tasks import run_ingestor
from peachjam.xmlutils import parse_html_str

logger = logging.getLogger(__name__)


@plugins.register("ingestor-adapter")
class GitbookAdapter(Adapter):
    """Imports markdown content from a GitHub repo, that has been authored with GitBook.

    The GitHub repository must contain a `peachjam.yaml` file at the root, which contains the details of the documents
    included in the repo:

    - documents:
      - expression_frbr_uri: /akn/...
      - title: The title of the document
      - path: The path to the directory containing the SUMMARY.md file and other markdown files

    For each document, the ingestor will fetch the `SUMMARY.md` file and all linked markdown files, and
    combine them into on HTML file.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.repo_name = self.settings.get("repo_name")
        access_token = self.settings.get("access_token")
        if not self.repo_name or not access_token:
            raise ValueError(
                "GitHub repository details or credentials are missing in settings."
            )

        self.github = Github(access_token)

        # Set up Jinja2 environment
        self.jinja_env = Environment()
        self.jinja_env.add_extension(HintExtension)
        self.jinja_env.add_extension(TabsExtension)

    def check_for_updates(self, last_refreshed):
        """Checks for documents updated since last_refreshed (which may be None), and returns a list
        of urls which must be updated.
        """
        docs = self.get_updated_docs(last_refreshed)
        existing = self.get_local_documents().values_list(
            "expression_frbr_uri", flat=True
        )
        to_delete = list(set(existing) - set(docs))
        return docs, to_delete

    def get_updated_docs(self, last_refreshed):
        documents = self.get_repo_documents()

        if last_refreshed:
            # filter documents based on last_refreshed
            documents = [d for d in documents if d["updated_at"] > last_refreshed]

        return [d["expression_frbr_uri"] for d in documents]

    def update_document(self, expression_frbr_uri):
        logger.info(f"Updating ... {expression_frbr_uri}")

        # get the document details
        document = self.get_repo_document(expression_frbr_uri)
        if not document:
            return

        frbr_uri = FrbrUri.parse(expression_frbr_uri)
        country, locality = get_country_and_locality(frbr_uri.place)
        language = Language.objects.get(iso_639_3__iexact=frbr_uri.language)

        data = {
            "jurisdiction": country,
            "locality": locality,
            "frbr_uri_doctype": frbr_uri.doctype,
            "frbr_uri_subtype": frbr_uri.subtype,
            "frbr_uri_actor": frbr_uri.actor,
            "frbr_uri_number": frbr_uri.number,
            "frbr_uri_date": frbr_uri.date,
            "language": language,
            "date": date.fromisoformat(frbr_uri.expression_date[1:]),
            "title": document["title"],
        }
        book, new = Book.objects.update_or_create(
            expression_frbr_uri=frbr_uri.expression_uri(),
            defaults={**data},
        )

        if frbr_uri.expression_uri() != book.expression_frbr_uri:
            raise Exception(
                f"FRBR URIs do not match: {frbr_uri.expression_uri()} != {book.expression_frbr_uri}"
            )

        self.compile_book(book, document["path"])
        book.save()

        logger.info(f"Updated book {book.expression_frbr_uri}")

    def delete_document(self, frbr_uri):
        documents = self.get_repo_documents()
        if frbr_uri not in [d["expression_frbr_uri"] for d in documents]:
            Book.objects.filter(expression_frbr_uri=frbr_uri).delete()

    def handle_webhook(self, request, data):
        if not verify_github_signature(
            request.body,
            settings.PEACHJAM["GITHUB_WEBHOOK_SECRET"],
            request.headers.get("x-hub-signature-256", ""),
        ):
            logger.warning("Invalid GitHub webhook signature")
            return

        logger.info(f"Ingestor {self.ingestor} handling webhook {data}")
        if data.get("repository", {}).get("full_name", None) == self.repo_name:
            logger.info("Will run ingestor to update documents")
            run_ingestor(self.ingestor.pk)

    def get_repo_documents(self):
        """
        Fetches the peachjam.yaml file from the root of the GitHub repository,
        parses it, and returns the list of documents from the 'documents' key.
        """
        yaml_content = yaml.safe_load(self.get_repo_file("peachjam.yaml"))
        documents = yaml_content.get("documents", [])

        # attach timestamp information
        for doc in documents:
            logger.info(f"Getting latest commit date for {doc['path']}")
            commits = self.repo.get_commits(path=doc["path"])
            doc["updated_at"] = commits[0].commit.author.date

        return documents

    def get_repo_document(self, expression_frbr_uri):
        for doc in self.get_repo_documents():
            if doc["expression_frbr_uri"] == expression_frbr_uri:
                return doc

    def get_local_documents(self):
        return self.ingestor.document_set.all()

    @cached_property
    def repo(self):
        return self.github.get_repo(self.repo_name)

    def get_repo_file(self, file_path) -> bytes:
        logger.info(f"Fetching file: {file_path}")
        file_content = self.repo.get_contents(file_path)
        return file_content.decoded_content

    def compile_book(self, book, repo_path):
        """
        Compiles a book by fetching the SUMMARY.md file and using it to build a TOC, which then drives
        the creation of a single nested HTML file with all the TOC pages combined.
        """
        summary_html = markdownify(
            self.get_repo_file(f"{repo_path}/SUMMARY.md").decode("utf-8")
        )
        toc = self.build_toc(summary_html)
        self.compile_pages(book, toc, repo_path)
        self.clean_toc(toc)
        book.toc_json = toc
        self.fetch_images(book, repo_path)

    def compile_pages(self, book, toc, repo_path):
        def process_entry(entry):
            # html for this page
            entry_html = self.compile_page(
                self.get_repo_file(f"{repo_path}/{entry['path']}").decode("utf-8")
            )

            # html for all its children
            entry_html += "\n".join(process_entry(kid) for kid in entry["children"])

            root = parse_html_str(entry_html)
            # adjust the HTML to update ids
            self.munge_page_html(entry, root)

            # use HTML headings to generate TOC children for this entry
            if not entry["children"]:
                sub_toc = generate_toc_json_from_html(root)
                if sub_toc:
                    # the very first item will be a repetition of this entry's title, so we hoist its children
                    # up to replace it
                    sub_toc = sub_toc[0]["children"] + sub_toc[1:]
                entry["children"] = sub_toc

            entry_html = etree.tostring(root, encoding="unicode")

            # combined html for this entry
            return f'<div id="{entry["id"]}">\n{entry_html}\n</div>'

        book.content_html = "\n".join(process_entry(e) for e in toc)

    def compile_page(self, markdown_text):
        # preprocess with jinja
        template = self.jinja_env.from_string(markdown_text)
        markdown_text = template.render()
        return markdownify(markdown_text)

    def build_toc(self, toc_html):
        """Build a TOC structure from the provided markdown content."""
        # for ensuring unique simplified IDs
        ids = set()

        def make_id(href):
            href = href.lower()
            if "/" in href:
                prefix, id_ = href.rsplit("/", 1)
                prefix = re.sub(r"/", "--", prefix + "/")
            else:
                prefix = ""
                id_ = href

            # dir1/dir2/page.md -> dir1--dir2--page
            id_ = prefix + id_.split(".", 1)[0][:10]

            # ensure it's unique
            if id_ in ids:
                i = 1
                while f"{id_}-{i}" in ids:
                    i += 1
                id_ = f"{id_}-{i}"
            ids.add(id_)
            return id_

        # walk the ULs
        def walk(ul):
            items = []

            for li in ul.iterchildren("li"):
                a = li.find("a[@href]")
                if a is not None:
                    href = a.get("href")
                    ul = li.find("ul")
                    items.append(
                        {
                            "id": make_id(href),
                            "title": a.text.strip() if a.text else "",
                            "path": href,
                            "children": walk(ul) if ul is not None else [],
                        }
                    )

            return items

        root = parse_html_str(toc_html)
        toc = []
        for ul in root.iter("ul"):
            toc.extend(walk(ul))

        return toc

    def clean_toc(self, toc):
        # remove "path" from the TOC items
        def clean(entry):
            if "path" in entry:
                del entry["path"]
            for child in entry["children"]:
                clean(child)

        for item in toc:
            clean(item)

    def munge_page_html(self, page, root):
        # scope all ids
        ids = {}
        for el in root.xpath("//*[@id]"):
            ids[el.attrib["id"]] = new_id = f"{page['id']}--{el.attrib['id']}"
            el.attrib["id"] = new_id

        # rewrite all hrefs to point to the correct entry, and remove broken footnote refs
        for el in root.xpath("//a[starts-with(@href, '#')]"):
            href = el.attrib["href"]

            if href.startswith("#user-content-fn-"):
                # gitbook inserts two types of footnotes: ones like this (which pandoc doesn't understand)
                # and the usual "[^1]" style which pandoc handles correctly. We remove the first type.
                el.getparent().remove(el)
                continue

            if href[1:] in ids:
                el.attrib["href"] = f"#{ids[href[1:]]}"

        # rewrite image paths from [../...]gitbook/assets/foo.png to /media/foo.png
        for el in root.xpath("//img[@src]"):
            src = el.attrib["src"]
            if ".gitbook/assets/" in src:
                src = src.rsplit("/", 1)[1]
                el.attrib["src"] = f"media/{src}"

    def fetch_images(self, book, repo_path):
        root = parse_html_str(book.content_html)
        images = set(
            img.attrib["src"][6:]
            for img in root.xpath("//img[@src]")
            if img.attrib["src"].startswith("media/")
        )

        Image.objects.filter(document=book).delete()

        for image in images:
            logger.info(f"fetching image {image}")
            image_data = self.get_repo_file(f"{repo_path}/.gitbook/assets/{image}")
            Image.objects.create(
                document=book,
                filename=image,
                file=ContentFile(image_data, name=image),
                mimetype=magic.from_buffer(image_data, mime=True),
                size=len(image_data),
            )


def parse_kv_pairs(parser):
    kwargs = []
    while parser.stream.current.type != "block_end":
        key_token = parser.stream.expect("name")
        parser.stream.expect("assign")
        value_expr = parser.parse_expression()
        kwargs.append(nodes.Keyword(key_token.value, value_expr))

    return kwargs


class HintExtension(Extension):
    # Define the tags this extension handles
    tags = {"hint"}

    def parse(self, parser):
        lineno = next(parser.stream).lineno
        kwargs = parse_kv_pairs(parser)

        # Parse the content inside the block
        body = parser.parse_statements(["name:endhint"], drop_needle=True)

        return nodes.CallBlock(
            self.call_method("_render_hint", kwargs), [], [], body
        ).set_lineno(lineno)

    def _render_hint(self, caller, **kwargs):
        style = kwargs.get("style", "info")
        if style == "info":
            style = "primary"
        return f'<div class="alert alert-{style}">{caller()}</div>'


class TabsExtension(Extension):
    tags = {"tabs", "tab"}

    n_tabs = 0

    def __init__(self, environment):
        super().__init__(environment)
        self._tabs_stack = []

    def parse(self, parser):
        token = next(parser.stream)
        lineno = token.lineno

        if token.value == "tabs":
            # Entering a new tabs block
            self._tabs_stack.append([])

            # Parse everything up to {% endtabs %}
            body = parser.parse_statements(["name:endtabs"], drop_needle=True)

            tabs = self._tabs_stack.pop()

            return nodes.CallBlock(
                self.call_method("_render_tabs", [nodes.List(tabs)]), [], [], body
            ).set_lineno(lineno)

        elif token.value == "tab":
            # Parse tab title
            kwargs = parse_kv_pairs(parser)

            # Parse tab body until {% endtab %}
            body = parser.parse_statements(["name:endtab"], drop_needle=True)

            # Add tab info to the current tab stack
            title_node = next((kw.value for kw in kwargs if kw.key == "title"), None)
            if title_node is None:
                parser.fail("Missing 'title' attribute in 'tab'", lineno)

            self._tabs_stack[-1].append(
                nodes.Tuple([title_node, body[0].nodes[0]], None, lineno=lineno)
            )

            # We don’t render tab blocks directly
            return nodes.Output([], lineno=lineno)

    def _render_tabs(self, tabs, caller=None):
        # tabs is a list of (title, body) pairs
        output = ['<ul class="nav nav-tabs" role="tablist">']

        for i, (title, _) in enumerate(tabs):
            tab_i = self.__class__.n_tabs + i
            active = "active" if i == 0 else ""
            output.append(
                f'<a class="nav-link {active}" data-bs-toggle="tab" href="#tab-pane-{tab_i}" role="tab">{title}</a>'
            )
        output.append("</ul>")
        output.append('<div class="tab-content">')
        for i, (_, content) in enumerate(tabs):
            tab_i = self.__class__.n_tabs + i
            active = "show active" if i == 0 else ""
            output.append(
                f'<div class="tab-pane {active}" id="tab-pane-{tab_i}" tabindex="0">{content}</div>'
            )

        output.append("</div></div>")
        self.__class__.n_tabs += len(tabs)
        return "".join(output)


def verify_github_signature(payload_body, secret_token, signature_header):
    """Verify that the payload was sent from GitHub by validating SHA256.
    Args:
        payload_body: original request body to verify (request.body())
        secret_token: GitHub app webhook token (WEBHOOK_SECRET)
        signature_header: header received from GitHub (x-hub-signature-256)
    """
    hash_object = hmac.new(
        secret_token.encode("utf-8"), msg=payload_body, digestmod=hashlib.sha256
    )
    expected_signature = "sha256=" + hash_object.hexdigest()
    return hmac.compare_digest(expected_signature, signature_header)
