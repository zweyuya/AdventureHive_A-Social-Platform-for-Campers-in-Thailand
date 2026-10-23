"""
EncryptedTextField — application-layer encryption with Fernet (AES-128-CBC + HMAC).

Values are encrypted before they reach PostgreSQL and decrypted when loaded,
so the database (and anyone with only DB access, including the Django admin's
raw SQL views) sees ciphertext. Anyone holding FIELD_ENCRYPTION_KEY can decrypt,
so the key lives only in the server environment.

Encrypted columns cannot be filtered or sorted in SQL — by design.
"""
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import models


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    key = getattr(settings, "FIELD_ENCRYPTION_KEY", None)
    if not key:
        raise ImproperlyConfigured("FIELD_ENCRYPTION_KEY is not set.")
    return Fernet(key.encode() if isinstance(key, str) else key)


class EncryptedTextField(models.TextField):
    description = "Text encrypted at rest with Fernet"

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if value is None or value == "":
            return value
        return _fernet().encrypt(str(value).encode()).decode()

    def from_db_value(self, value, expression, connection):
        if value is None or value == "":
            return value
        try:
            return _fernet().decrypt(value.encode()).decode()
        except InvalidToken as exc:  # wrong key or corrupted data — fail loudly
            raise ValueError("Could not decrypt field; check FIELD_ENCRYPTION_KEY.") from exc

    def get_lookup(self, lookup_name):
        # Equality on ciphertext is meaningless (Fernet is randomized); block it.
        if lookup_name not in ("isnull",):
            return None
        return super().get_lookup(lookup_name)
