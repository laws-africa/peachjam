import logging

import yaml
from cobalt import FrbrUri
from github import Github
from jinja2 import Environment, nodes
from jinja2.ext import Extension
from martor.utils import markdownify

from peachjam.adapters.base import RequestsAdapter
from peachjam.models import Book, get_country_and_locality
from peachjam.plugins import plugins
from peachjam.xmlutils import parse_html_str

logger = logging.getLogger(__name__)


@plugins.register("ingestor-adapter")
class GitbookAdapter(RequestsAdapter):
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
        self.access_token = self.settings.get("access_token")

        if not self.repo_name or not self.access_token:
            raise ValueError(
                "GitHub repository details or credentials are missing in settings."
            )

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
        # TODO: handle last_refreshed timestamp
        documents = self.get_repo_documents()
        return [d["expression_frbr_uri"] for d in documents]

    def update_document(self, expression_frbr_uri):
        logger.info(f"Updating ... {expression_frbr_uri}")

        # get the document details
        document = self.get_repo_document(expression_frbr_uri)
        if not document:
            return

        frbr_uri = FrbrUri.parse(expression_frbr_uri)
        country, locality = get_country_and_locality(frbr_uri.place)

        # TODO: check for existing
        book = Book(
            country=country,
            locality=locality,
            date=frbr_uri.expression_date[1:],
            expression_frbr_uri=expression_frbr_uri,
            title=document["title"],
        )

        self.compile_book(book, document["path"])

    def delete_document(self, frbr_uri):
        documents = self.get_repo_documents()
        if frbr_uri not in [d["expression_frbr_uri"] for d in documents]:
            document = Book.objects.filter(expression_frbr_uri=frbr_uri).first()
            if document:
                document.delete()

    def handle_webhook(self, data):
        # TODO:
        logger.info(f"Ingestor {self.ingestor} handling webhook {data}")

    def get_repo_documents(self):
        """
        Fetches the peachjam.yaml file from the root of the GitHub repository,
        parses it, and returns the list of documents from the 'documents' key.
        """
        # Authenticate with GitHub
        github = Github(self.access_token)
        repo = github.get_repo(self.repo_name)

        # Fetch the peachjam.yaml file from the root of the repository
        file_content = repo.get_contents("peachjam.yaml")
        yaml_content = yaml.safe_load(file_content.decoded_content)

        # Extract and return the list of documents
        documents = yaml_content.get("documents", [])
        return documents

    def get_repo_document(self, expression_frbr_uri):
        for doc in self.get_repo_documents():
            if doc.expression_frbr_uri == expression_frbr_uri:
                return doc

    def get_local_documents(self):
        return self.ingestor.document_set.all()

    def compile_book(self, book, repo_path):
        """
        Compiles a book by fetching the SUMMARY.md file, parsing its structure,
        fetching referenced files, converting them to HTML, and combining them.
        """
        # Authenticate with GitHub
        github = Github(self.access_token)
        repo = github.get_repo(self.repo_name)

        # Step 1: Fetch the SUMMARY.md file
        path = f"{repo_path}/SUMMARY.md"
        logger.info(f"Fetching file: {path}")
        summary_file = repo.get_contents(path)
        summary_content = markdownify(summary_file.decoded_content.decode("utf-8"))

        # Step 2: Parse the HTML structure of the summary
        root = parse_html_str(summary_content)
        links = root.xpath("//a")

        # Step 3: Fetch each linked file and convert to HTML
        combined_html = ""
        for link in links:
            href = link.get("href")
            if not href:
                continue

            # Fetch the file content
            logger.info(f"Fetching file: {href}")
            file_path = f"{repo_path}/{href}"
            file_content = repo.get_contents(file_path)
            file_html = self.compile_page(file_content.decoded_content.decode("utf-8"))

            # Wrap the content in a div and append to combined_html
            # TODO: better ID
            combined_html += f'<div id="{href}">{file_html}</div>\n'

        # Step 4: Save the combined HTML to the book object
        book.content_html = combined_html
        book.save()

    def compile_page(self, markdown_text):
        # preprocess with jinja
        template = self.jinja_env.from_string(markdown_text)
        markdown_text = template.render()
        # TODO: is markdownify using pandoc?
        return markdownify(markdown_text)


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
        output = ['<ul class="nav nav-underline" role="tablist">']

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
