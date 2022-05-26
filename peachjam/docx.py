import logging
import subprocess
from os.path import basename
from shutil import copyfileobj
from tempfile import NamedTemporaryFile, TemporaryDirectory

logger = logging.getLogger(__name__)


def convert_docx_to_pdf(docx_file):
    f = docx_file.open()

    temp_file = NamedTemporaryFile(suffix=".docx")
    temp_dir = TemporaryDirectory()

    copyfileobj(f, temp_file)
    f.close()

    process_args = [
        "soffice",
        "--headless",
        "--convert-to",
        "pdf",
        "--outdir",
        temp_dir.name,
        temp_file.name,
    ]

    try:
        process = subprocess.run(
            process_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            encoding="utf-8",
        )
        logger.info(
            f"soffice subprocess: {process.stdout} Exit Code: {process.returncode}"
        )
    except subprocess.CalledProcessError as e:
        logger.error(f"soffice subprocess: {e.stdout} Exit Code: {e.returncode}")
        raise

    filename = basename(temp_file.name).replace(".docx", ".pdf")

    return temp_dir, filename
