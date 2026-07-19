"""Custom model fields for util app."""

# Django imports
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import models

# external imports
from cryptography.fernet import Fernet, InvalidToken


class EncryptedTextField(models.CharField):
    """CharField that transparently encrypts values at rest."""

    prefix = "enc1:"

    def __init__(self, *args, encryption_setting="API_KEY_ENCRYPTION_KEY", **kwargs):
        """Store the Django setting name that contains the Fernet key."""
        self.encryption_setting = encryption_setting
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        """Serialize field configuration into migrations."""
        name, path, args, kwargs = super().deconstruct()
        if self.encryption_setting != "API_KEY_ENCRYPTION_KEY":
            kwargs["encryption_setting"] = self.encryption_setting
        return name, path, args, kwargs

    def _get_cipher(self):
        """Build the configured symmetric cipher."""
        encryption_key = getattr(settings, self.encryption_setting, None)
        if not encryption_key:
            raise ImproperlyConfigured(f"{self.encryption_setting} must be configured for encrypted field storage")
        if isinstance(encryption_key, str):
            encryption_key = encryption_key.encode("utf-8")
        return Fernet(encryption_key)

    @classmethod
    def is_encrypted_value(cls, value):
        """Return whether the stored value uses the encrypted marker."""
        return isinstance(value, str) and value.startswith(cls.prefix)

    def encrypt_value(self, value):
        """Encrypt plaintext values for storage."""
        if value is None or self.is_encrypted_value(value):
            return value
        token = self._get_cipher().encrypt(str(value).encode("utf-8")).decode("utf-8")
        return f"{self.prefix}{token}"

    def decrypt_value(self, value):
        """Decrypt stored values, leaving legacy plaintext untouched."""
        if value is None or not self.is_encrypted_value(value):
            return value
        token = value[len(self.prefix) :].encode("utf-8")
        try:
            return self._get_cipher().decrypt(token).decode("utf-8")
        except InvalidToken as exc:
            raise ImproperlyConfigured(
                f"Stored encrypted value could not be decrypted with {self.encryption_setting}"
            ) from exc

    def from_db_value(self, value, expression, connection):
        """Convert database values to decrypted Python values."""
        return self.decrypt_value(value)

    def to_python(self, value):
        """Return decrypted Python values for model instances."""
        value = super().to_python(value)
        return self.decrypt_value(value)

    def get_prep_value(self, value):
        """Encrypt model values before writing them to the database."""
        value = super().get_prep_value(value)
        return self.encrypt_value(value)
