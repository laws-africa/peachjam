import io
import logging
import re
from tempfile import NamedTemporaryFile

import requests
from django.conf import settings
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

logger = logging.getLogger(__name__)


def download_source_file(url):
    # check if the url is a Google doc url
    google_regex = re.compile(r"google")
    if google_regex.search(url):
        pattern = r"(?<=document\/d\/)(?P<google_id>.*)(?=\/)"
        regex = re.compile(pattern)
        match = regex.search(url)
        if match:
            return download_file_from_google(match.group("google_id"))
    else:
        return download_with_urllib(url)


def download_file_from_google(file_id):
    try:
        scopes = ["https://www.googleapis.com/auth/drive"]
        creds = service_account.Credentials.from_service_account_info(
            settings.GOOGLE_SERVICE_ACCOUNT_CREDENTIALS, scopes=scopes
        )
        service = build("drive", "v3", credentials=creds)
        request = service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fd=fh, request=request)

        done = False
        while done is False:
            status, done = downloader.next_chunk()
            logger.info("Download %d%%." % int(status.progress() * 100))

        fh.seek(0)

    except HttpError as e:
        logger.error(e)
        return None

    else:
        f = NamedTemporaryFile()
        f.write(fh.read())
        return f


def download_with_urllib(url):
    f = NamedTemporaryFile()
    r = requests.get(url)
    r.raise_for_status()
    f.write(r.content)
    return f
