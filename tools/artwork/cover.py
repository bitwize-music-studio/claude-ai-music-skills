"""Turn a chosen image into the cover files an album needs.

Distributors want a square cover of at least 3000x3000 pixels. An image made
by Codex's built-in image tool is 1254x1254 (measured, whatever size
was asked for), so the chosen image is enlarged here.

Pillow is imported on first use, not when this module is imported. The MCP
server imports the artwork code when it starts, and a venv with a broken Pillow
must not stop every other tool from loading.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from PIL.Image import Image as PILImage

# The side, in pixels, a cover must have for distribution.
COVER_SIZE = 3000
# Generators round: 1254x1255 is a square image, 1254x900 is not.
_SQUARE_TOLERANCE = 2


def _pillow() -> Any:
    """Pillow's ``Image`` module, imported the first time an image is read."""
    try:
        from PIL import Image
    except ImportError as exc:
        raise ValueError(
            "Pillow is not installed, so images cannot be read. Run /bitwize-music:setup."
        ) from exc
    return Image


def image_size(path: Path) -> tuple[int, int]:
    """Width and height of the image at *path*.

    Raises:
        ValueError: when the file is missing or is not an image Pillow can read.
    """
    if not path.is_file():
        raise ValueError(f"Image not found: {path}")
    image_module = _pillow()
    try:
        with image_module.open(path) as probe:
            probe.verify()
        with image_module.open(path) as image:
            width, height = image.size
    except (OSError, SyntaxError, ValueError) as exc:  # UnidentifiedImageError is an OSError
        raise ValueError(f"{path.name} is not an image: {exc}") from exc
    return int(width), int(height)


def _flattened(image: PILImage) -> PILImage:
    """*image* as opaque RGB; anything transparent shows white, not black."""
    if image.mode in ("RGBA", "LA") or "transparency" in image.info:
        rgba = image.convert("RGBA")
        background: PILImage = _pillow().new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    return image.convert("RGB")


def _save_png(image: PILImage, dest: Path) -> None:
    """Write *image* to *dest* as a PNG, leaving no half-written file behind."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_name(dest.name + ".part")
    try:
        image.save(partial, "PNG")
        os.replace(partial, dest)
    finally:
        partial.unlink(missing_ok=True)


def write_cover(source: Path, dest: Path, size: int = COVER_SIZE) -> dict[str, Any]:
    """Write *source* to *dest* as a square, opaque PNG of at least *size* pixels.

    A smaller image is enlarged to exactly *size* with Lanczos resampling; a
    larger one keeps its own size. Enlarging adds no detail, so the result
    reports whether it happened.

    Raises:
        ValueError: when *source* is not an image, or is not square.
    """
    width, height = image_size(source)
    if abs(width - height) > _SQUARE_TOLERANCE:
        raise ValueError(
            f"{source.name} is not square ({width}x{height}); a cover must be 1:1. "
            "Crop it, or generate it again as a square."
        )
    image_module = _pillow()
    with image_module.open(source) as opened:
        image = _flattened(opened)
    side = min(width, height)
    if side < size:
        image = image.resize((size, size), image_module.Resampling.LANCZOS)
        enlarged = True
    else:
        if width != height:
            image = image.crop((0, 0, side, side))
        enlarged = False

    _save_png(image, dest)
    return {
        "size": [image.width, image.height],
        "source_size": [width, height],
        "enlarged": enlarged,
    }


def write_png(source: Path, dest: Path) -> None:
    """Write *source* to *dest* as a PNG at its own size.

    A PNG is copied byte for byte; anything else is converted.

    Raises:
        ValueError: when *source* is not an image.
    """
    image_size(source)
    with _pillow().open(source) as opened:
        if opened.format == "PNG":
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, dest)
            return
        keeps_alpha = opened.mode in ("RGBA", "LA", "P")
        converted = opened.convert("RGBA" if keeps_alpha else "RGB")
    _save_png(converted, dest)
