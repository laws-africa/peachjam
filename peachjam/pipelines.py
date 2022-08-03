from docpipe.html import BodyToDiv, SerialiseHtml, parse_and_clean
from docpipe.pipeline import Pipeline, PipelineContext, Stage
from docpipe.soffice import DocToHtml
from docpipe.xmlutils import unwrap_element

DOC_MIMETYPES = [
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
]


class ImportContext(PipelineContext):
    source_file = None


class RemoveTags(Stage):
    """Unwraps certain tags.

    Reads: context.html
    Writes: context.html
    """

    tags = ["font"]

    def __call__(self, context):
        xpath = " | ".join(f"//{x}" for x in self.tags)
        for font in context.html.xpath(xpath):
            unwrap_element(font)


class CleanStyles(Stage):
    # styles we explicitly want to remove
    style_blacklist = {"p": set("line-height".split()), None: set()}

    def __call__(self, context):
        for elem in context.html.xpath(".//*[@style]"):
            style = self.clean_style_string(elem.tag, elem.get("style"))
            if not style:
                del elem.attrib["style"]
            else:
                elem.set("style", style)

    def clean_style_string(self, tag, s):
        blacklist = self.style_blacklist.get(tag, self.style_blacklist[None])

        # split style string into rules, and rules into pairs
        # color: red; margin: 0px -> {'color': 'red', 'margin': '0px'}
        pairs = [a.split(":") for a in s.split(";") if ":" in a]
        styles = {k.strip(): v.strip() for (k, v) in pairs}

        styles = "; ".join(f"{k}: {v}" for k, v in styles.items() if k not in blacklist)
        return styles


word_pipeline = Pipeline(
    [
        DocToHtml(),
        parse_and_clean,
        BodyToDiv(),
        RemoveTags(),
        CleanStyles(),
        SerialiseHtml(),
    ]
)
