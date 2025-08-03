from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from PIL import Image
from io import BytesIO
import json
from contextlib import contextmanager
import os
import tempfile


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
def temp_blob(path, suffix):
    temp_file_path = None
    try:
        if not default_storage.exists(path):
            raise FileNotFoundError(f"Blob not found: {path}")

        temp_dir = os.environ.get("TEMP_DIR", "/tmp")

        os.makedirs(temp_dir, exist_ok=True)

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
