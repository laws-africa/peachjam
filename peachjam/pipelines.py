import cssutils
from docpipe.html import BodyToDiv, SerialiseHtml, parse_and_clean
from docpipe.pipeline import Pipeline, PipelineContext, Stage
from docpipe.soffice import DocToHtml
from docpipe.xmlutils import unwrap_element

DOC_MIMETYPES = [
    "application/vnd.oasis.opendocument.text",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "application/rtf",
    "text/rtf",
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
    style_blacklist = {
        "p": set("line-height".split()),
        # disallow "position: *" everywhere as it can move content outside of the document borders
        None: set("position".split()),
    }

    def __call__(self, context):
        for elem in context.html.xpath(".//*[@style]"):
            style = self.clean_style_string(elem.tag, elem.get("style"))
            if not style:
                del elem.attrib["style"]
            else:
                elem.set("style", style)

    def clean_style_string(self, tag, s):
        blacklist = self.style_blacklist.get(tag, self.style_blacklist[None])

        style = cssutils.parseStyle(s)
        if style and s:
            for k in blacklist:
                style.removeProperty(k)

        if style.getCssText():
            return style.cssText.replace("\n", " ")


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
