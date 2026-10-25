"""
Safe processing for user-uploaded photos.

Every upload is opened with Pillow (only real JPEG/PNG/WebP images get through),
rotated according to its EXIF orientation, resized, and re-encoded as JPEG.
Re-encoding drops ALL metadata — including GPS coordinates from phone cameras.
"""
import io
from uuid import uuid4

from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError
from rest_framework.exceptions import ValidationError

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


def process_photo(upload, *, field: str, max_side: int = 1600, square: bool = False) -> ContentFile:
    if upload.size > MAX_UPLOAD_BYTES:
        raise ValidationError({field: "The photo must be 5 MB or smaller."})
    try:
        image = Image.open(upload)
        image.verify()               # detects truncated / fake files
        upload.seek(0)
        image = Image.open(upload)
    except (UnidentifiedImageError, OSError, SyntaxError) as exc:
        raise ValidationError({field: "That file isn't a valid image."}) from exc
    if image.format not in ALLOWED_FORMATS:
        raise ValidationError({field: "Use a JPEG, PNG or WebP image."})
    if image.width * image.height > 40_000_000:  # decompression-bomb guard
        raise ValidationError({field: "That image is too large."})

    image = ImageOps.exif_transpose(image).convert("RGB")
    if square:
        image = ImageOps.fit(image, (max_side, max_side), Image.Resampling.LANCZOS)
    else:
        image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    out = io.BytesIO()
    image.save(out, "JPEG", quality=85, optimize=True)  # no exif= → metadata removed
    return ContentFile(out.getvalue(), name=f"{uuid4().hex}.jpg")
