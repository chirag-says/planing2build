"""AI image provider adapters (Slice 3.1; INTEGRATION_ARCHITECTURE section 6).

- `demo`: deterministic placeholder images made locally from the request, zero cost, for
  development and tests. It runs the same queue, state, storage and gallery path as a real
  provider. Never allowed in production (settings guard).
- `none`: no provider configured; generation is unavailable. The production choice until a
  provider is selected and contracted (AQ-15).

A vendor adapter is added here behind the same interface once AQ-15 is decided.
"""

import hashlib
import io

from PIL import Image, ImageDraw

from p2b.core.config import Settings
from p2b.core.images import ImageProvider, ImageProviderError, ImageRequest, ImageResult


class DemoImageProvider:
    """Draws a deterministic picture from the request: the same request gives the same bytes."""

    name = "demo"
    model = "demo-placeholder-v1"
    configured = True

    async def generate(self, request: ImageRequest) -> ImageResult:
        digest = hashlib.sha256(f"{request.view}|{request.seed}|{request.prompt}".encode()).digest()
        sky = (150 + digest[0] % 80, 170 + digest[1] % 70, 200 + digest[2] % 55)
        wall = (180 + digest[3] % 60, 160 + digest[4] % 60, 130 + digest[5] % 60)
        image = Image.new("RGB", (request.width, request.height), sky)
        draw = ImageDraw.Draw(image)
        w, h = request.width, request.height
        draw.rectangle((0, int(h * 0.78), w, h), fill=(110, 140, 95))  # ground
        if request.view == "EXTERIOR":
            left, right = int(w * 0.2), int(w * 0.8)
            top = int(h * (0.25 + (digest[6] % 10) / 100))
            draw.rectangle((left, top, right, int(h * 0.78)), fill=wall)
            for i in range(3):
                x = left + int((right - left) * (0.15 + 0.3 * i))
                draw.rectangle((x, top + int(h * 0.12), x + int(w * 0.08), top + int(h * 0.24)),
                               fill=(70, 90, 110))  # fmt: skip
        else:
            draw.rectangle((0, 0, w, int(h * 0.78)), fill=wall)
            draw.rectangle((int(w * 0.1), int(h * 0.55), int(w * 0.6), int(h * 0.72)),
                           fill=(120, 95, 80))  # fmt: skip
        out = io.BytesIO()
        image.save(out, format="PNG")
        return ImageResult(content=out.getvalue(), mime="image/png", usage=None)


class UnconfiguredImageProvider:
    name = "none"
    model = "none"
    configured = False

    async def generate(self, request: ImageRequest) -> ImageResult:
        raise ImageProviderError("no image provider is configured", kind="UNAVAILABLE",
                                 retryable=False)  # fmt: skip


def build_image_provider(settings: Settings) -> ImageProvider:
    if settings.ai_image_provider == "demo":
        return DemoImageProvider()
    return UnconfiguredImageProvider()
