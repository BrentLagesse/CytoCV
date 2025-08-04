from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from storages.backends.azure_storage import AzureStorage
from azure.storage.blob import generate_blob_sas, BlobSasPermissions
from datetime import datetime, timedelta
from PIL import Image
from io import BytesIO
import json
from contextlib import contextmanager
import os
import tempfile
import matplotlib.pyplot as plt
from matplotlib.figure import Figure


class CustomStorage(AzureStorage):
    def __init__(self, **settings):
        self.account_name = settings.get("account_name")
        self.account_key = settings.get("account_key")
        self.azure_container = settings.get("azure_container", "media")
        super().__init__(**settings)

    def url(self, name, expire=3600):
        sas_token = generate_blob_sas(
            account_name=self.account_name,
            account_key=self.account_key,
            blob_name=name,
            container_name="media",
            permission=BlobSasPermissions(read=True),
            expiry=datetime.utcnow() + timedelta(seconds=expire),
        )
        return f"https://{self.account_name}.blob.core.windows.net/media/{name}?{sas_token}"


def read_blob_file(path):
    try:
        if default_storage.exists(path):
            with default_storage.open(path, "rb") as file:
                content = file.read()
                return content
        else:
            print(f"File {path} not exist")

    except Exception as e:
        print("Error reading")
        return None


def upload_config(config, path):
    json_bytes = json.dumps(config).encode("utf-8")
    content = ContentFile(json_bytes)

    default_storage.save(path, content)


def upload_figure(figure: Figure, path):
    buffer = BytesIO()
    figure.savefig(buffer, format="png", dpi=600, bbox_inches="tight", pad_inches=0)
    buffer.seek(0)

    content = ContentFile(buffer.read())
    saved_path = default_storage.save(path, content)

    return saved_path


def upload_image(image: Image.Image, path):
    buffer = BytesIO()
    extension = os.path.splitext(path)[1][1:]
    if extension == "tif":
        extension = "TIFF"
    image.save(buffer, format=extension)
    buffer.seek(0)

    content = ContentFile(buffer.read())
    saved_path = default_storage.save(path, content)

    return saved_path


@contextmanager
def temp_blob(path, suffix, text=False):
    temp_file_path = None
    try:
        if not default_storage.exists(path):
            raise FileNotFoundError(f"Blob not found: {path}")

        temp_dir = os.environ.get("TEMP_DIR", "/tmp")

        os.makedirs(temp_dir, exist_ok=True)

        if text:
            with default_storage.open(path, "r") as file:
                content = file.read()

                if isinstance(content, bytes):
                    content = content.decode("utf-8")

            # Create temp file
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=suffix, dir=temp_dir, mode="w"
            ) as temp_file:
                temp_file.write(content)
                temp_file_path = temp_file.name
        else:
            with default_storage.open(path, "rb") as file:
                content = file.read()

            # Create temp file
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=suffix, dir=temp_dir
            ) as temp_file:
                temp_file.write(content)
                temp_file_path = temp_file.name

        yield temp_file_path

    except Exception as e:
        print(f"Error {e}")
        raise

    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except Exception as e:
                print(f"Cant delete {temp_file_path}: {e}")
