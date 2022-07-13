from docpipe.html import BodyToDiv, SerialiseHtml, parse_and_clean
from docpipe.pipeline import Pipeline, PipelineContext
from docpipe.soffice import DocToHtml

DOC_MIMETYPES = [
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
]


class ImportContext(PipelineContext):
    source_file = None


word_pipeline = Pipeline(
    [
        DocToHtml(),
        parse_and_clean,
        BodyToDiv(),
        SerialiseHtml(),
    ]
)
