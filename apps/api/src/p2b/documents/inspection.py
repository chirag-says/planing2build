"""Content checks a file must pass before it becomes AVAILABLE (ADR-011; INTEGRATION section 7;
SECURITY section 5, malicious uploads). Pure functions over bytes.

- Type: the first bytes must match the declared type (three types only, so a signature table
  is clearer than a libmagic dependency).
- Images: decoded and re-encoded, which drops EXIF including GPS and device data; the
  orientation is applied first so the photo still looks right.
- PDFs: opened with pikepdf; encrypted files and files carrying JavaScript or launch actions
  are rejected.
"""

import io
from dataclasses import dataclass

import pikepdf
from PIL import Image, ImageOps, UnidentifiedImageError

SIGNATURES: dict[str, tuple[bytes, ...]] = {
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "application/pdf": (b"%PDF-",),
}
# Pillow refuses images above this many pixels (decompression bombs).
MAX_PIXELS = 60_000_000
Image.MAX_IMAGE_PIXELS = MAX_PIXELS
FORBIDDEN_PDF_KEYS = ("/JS", "/JavaScript", "/Launch")


@dataclass(frozen=True)
class Inspected:
    ok: bool
    content: bytes = b""
    detected_mime: str | None = None
    reason: str | None = None


def sniff(data: bytes) -> str | None:
    for mime, prefixes in SIGNATURES.items():
        if any(data.startswith(prefix) for prefix in prefixes):
            return mime
    return None


def _reencode_image(data: bytes, mime: str) -> bytes:
    with Image.open(io.BytesIO(data)) as image:
        image.load()
        clean = ImageOps.exif_transpose(image)
        out = io.BytesIO()
        if mime == "image/jpeg":
            clean.convert("RGB").save(out, format="JPEG", quality=90, optimize=True)
        else:
            clean.save(out, format="PNG", optimize=True)
    return out.getvalue()


def _has_active_content(pdf: pikepdf.Pdf) -> bool:
    """Walk every object reachable from the trailer, direct ones included: an /OpenAction
    written inline in the catalogue is not in `pdf.objects`."""
    forbidden = set(FORBIDDEN_PDF_KEYS)
    stack: list[pikepdf.Object] = [pdf.trailer]
    seen: set[tuple[int, int]] = set()
    containers = (pikepdf.Dictionary, pikepdf.Array, pikepdf.Stream)
    while stack:
        obj = stack.pop()
        if not isinstance(obj, containers):  # scalars come back as Python values
            continue
        if obj.is_indirect:
            if obj.objgen in seen:
                continue
            seen.add(obj.objgen)
        if isinstance(obj, pikepdf.Stream):
            obj = obj.stream_dict
        if isinstance(obj, pikepdf.Dictionary):
            if set(obj.keys()) & forbidden:
                return True
            if obj.get("/S") in (pikepdf.Name.JavaScript, pikepdf.Name.Launch):
                return True
            stack.extend(obj.values())
        elif isinstance(obj, pikepdf.Array):
            stack.extend(obj)
    return False


def _pdf_problem(data: bytes) -> str | None:
    try:
        with pikepdf.open(io.BytesIO(data)) as pdf:
            if pdf.is_encrypted:
                return "PDF_ENCRYPTED"
            if _has_active_content(pdf):
                return "PDF_ACTIVE_CONTENT"
    except pikepdf.PasswordError:
        return "PDF_ENCRYPTED"
    except pikepdf.PdfError:
        return "PDF_UNREADABLE"
    return None


def inspect(data: bytes, declared_mime: str) -> Inspected:
    detected = sniff(data)
    if detected is None or detected != declared_mime:
        return Inspected(ok=False, detected_mime=detected, reason="TYPE_MISMATCH")
    if detected == "application/pdf":
        problem = _pdf_problem(data)
        if problem:
            return Inspected(ok=False, detected_mime=detected, reason=problem)
        return Inspected(ok=True, content=data, detected_mime=detected)
    try:
        return Inspected(ok=True, content=_reencode_image(data, detected), detected_mime=detected)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        return Inspected(ok=False, detected_mime=detected, reason="IMAGE_UNREADABLE")
