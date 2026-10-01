"""Extension + libmagic + parser checks, followed by a mandatory ClamAV scan."""
import io
import socket
import struct
import warnings
from pathlib import PurePosixPath

import magic
from PIL import Image, UnidentifiedImageError

MAX_FILE = 5 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = 12_000_000
TYPES = {".pdf": "application/pdf", ".jpg": "image/jpeg",
         ".jpeg": "image/jpeg", ".png": "image/png", ".txt": "text/plain"}


class InvalidFile(ValueError):
    pass


class ScannerUnavailable(Exception):
    pass


def scan(data, socket_path):
    """ClamAV INSTREAM: no executable uploads, public paths or shell commands."""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(15)
            client.connect(socket_path)
            client.sendall(b"zINSTREAM\0")
            for start in range(0, len(data), 65536):
                chunk = data[start:start + 65536]
                client.sendall(struct.pack("!I", len(chunk)) + chunk)
            client.sendall(b"\0\0\0\0")
            result = b""
            while b"\0" not in result and len(result) < 4096:
                chunk = client.recv(1024)
                if not chunk:
                    break
                result += chunk
    except OSError as exc:
        raise ScannerUnavailable() from exc
    reply = result.split(b"\0", 1)[0]
    if reply.endswith(b" FOUND"):
        raise InvalidFile("The document did not pass the security scan.")
    if reply != b"stream: OK":
        raise ScannerUnavailable()


def read_upload(upload):
    if upload is None or not upload.filename:
        return None
    suffix = PurePosixPath(upload.filename.replace("\\", "/")).suffix.lower()
    if suffix not in TYPES:
        raise InvalidFile("Use PDF, JPG, PNG or UTF-8 TXT files only.")
    data = upload.stream.read(MAX_FILE + 1)
    if not data or len(data) > MAX_FILE:
        raise InvalidFile("The document must be non-empty and no larger than 5 MB.")
    if magic.from_buffer(data, mime=True) != TYPES[suffix]:
        raise InvalidFile("The document content does not match its file extension.")
    if suffix == ".pdf" and (not data.startswith(b"%PDF-") or b"%%EOF" not in data[-2048:]):
        raise InvalidFile("The PDF document is incomplete or invalid.")
    if suffix == ".txt":
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise InvalidFile("Save text documents as UTF-8.") from exc
        if any(ord(c) < 32 and c not in "\n\r\t" for c in text):
            raise InvalidFile("The text document contains invalid characters.")
    return data, suffix


def prepare_upload(raw, socket_path):
    if raw is None:
        return None
    data, suffix = raw
    scan(data, socket_path)
    if suffix in {".jpg", ".jpeg", ".png"}:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(data)) as picture:
                    if picture.format != ("PNG" if suffix == ".png" else "JPEG"):
                        raise InvalidFile("The image format is invalid.")
                    picture.verify()
                with Image.open(io.BytesIO(data)) as picture:
                    picture.load()
                    # Re-encode pixels into a new file; omit EXIF and trailing payloads.
                    pixels = picture.convert("RGBA" if suffix == ".png" else "RGB")
                    clean = Image.new(pixels.mode, pixels.size)
                    clean.paste(pixels)
                    output = io.BytesIO()
                    clean.save(output, format="PNG" if suffix == ".png" else "JPEG")
                    data = output.getvalue()
        except (UnidentifiedImageError, OSError, ValueError,
                Image.DecompressionBombWarning, Image.DecompressionBombError) as exc:
            raise InvalidFile("The image is invalid or too large to process.") from exc
        if len(data) > MAX_FILE:
            raise InvalidFile("Please upload a smaller image.")
    # Client-supplied names never become filesystem paths or mail headers.
    return data, "cargo-document" + suffix, TYPES[suffix]
