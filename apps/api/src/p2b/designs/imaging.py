"""Output validation for provider images (Slice 3.1). The image is decoded, checked, re-encoded
without metadata and marked "Illustrative" in the picture itself (ADR-013), so the mark travels
with every copy and nothing the provider embedded survives."""

import io

from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError

FORMATS = frozenset({"PNG", "JPEG", "WEBP"})
MIN_SIDE, MAX_SIDE = 256, 4096
MAX_BYTES = 20 * 1024 * 1024
MARK = "Illustrative concept"
OUTPUT_MIME = "image/jpeg"


class InvalidImage(Exception):
    pass


def finalise(content: bytes) -> bytes:
    if not content or len(content) > MAX_BYTES:
        raise InvalidImage("empty or too large")
    try:
        with Image.open(io.BytesIO(content)) as source:
            if source.format not in FORMATS:
                raise InvalidImage(f"unexpected format {source.format}")
            width, height = source.size
            if not (MIN_SIDE <= width <= MAX_SIDE and MIN_SIDE <= height <= MAX_SIDE):
                raise InvalidImage(f"unexpected size {width}x{height}")
            image = source.convert("RGB")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise InvalidImage("not a readable image") from exc

    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = ImageFont.load_default(size=max(16, width // 36))
    left, top, right, bottom = draw.textbbox((0, 0), MARK, font=font)
    pad = max(8, width // 120)
    x, y = pad * 2, height - (bottom - top) - pad * 4
    draw.rectangle((x - pad, y - pad, x + right - left + pad, y + bottom - top + pad * 2),
                   fill=(0, 0, 0, 170))  # fmt: skip
    draw.text((x - left, y - top), MARK, font=font, fill=(255, 255, 255, 255))
    marked = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
    out = io.BytesIO()
    marked.save(out, format="JPEG", quality=88, optimize=True)
    return out.getvalue()
