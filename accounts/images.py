"""Profile photos: centred 400×400 square JPEG with all metadata (incl. GPS) removed."""
from core.images import MAX_UPLOAD_BYTES, process_photo  # noqa: F401


def process_avatar(upload):
    return process_photo(upload, field="avatar", max_side=400, square=True)
