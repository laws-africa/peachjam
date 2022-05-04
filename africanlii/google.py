import io
import re
from tempfile import NamedTemporaryFile

from django.conf import settings
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload


def download_source_file(url):
    google_pattern = re.compile(r"google")
    if google_pattern.search(url):
        pattern = r"(?<=document\/d\/)(?P<google_id>.*)(?=\/)"
        regex = re.compile(pattern)
        match = regex.search(url)
        if match:
            return download_file_from_google(match.group("google_id"))
    else:
        return None


def download_file_from_google(file_id):
    try:
        scopes = ["https://www.googleapis.com/auth/drive"]
        creds = service_account.Credentials.from_service_account_file(
            settings.GOOGLE_CREDENTIALS_JSON_FILE, scopes=scopes
        )
        service = build("drive", "v3", credentials=creds)
        request = service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fd=fh, request=request)

        done = False
        while done is False:
            status, done = downloader.next_chunk()
            print("Download %d%%." % int(status.progress() * 100))

        fh.seek(0)

    except HttpError as e:
        print(e)
        return None

    else:
        f = NamedTemporaryFile()
        f.write(fh.read())
        return f
