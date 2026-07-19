"""Tests for util app security helpers."""

# Python imports
import hashlib
import hmac
import json

# Django imports
from django.db import connection

import pytest
from rest_framework.test import APIRequestFactory


@pytest.mark.django_db
@pytest.mark.unit
class TestAPIKeyStorage:
    """Test encrypted storage and HMAC compatibility for API keys."""

    def test_apikey_is_encrypted_at_rest(self):
        """Saving an API key should encrypt the stored database value."""
        # app imports
        from util.models import APIKey

        key = APIKey(key="a" * 128, comment="test key")
        key.save()
        key.refresh_from_db()

        assert key.key == "a" * 128
        assert key.identifier
        assert key.key_digest == hashlib.sha256(bytes.fromhex("a" * 128)).hexdigest()

        with connection.cursor() as cursor:
            cursor.execute("SELECT key FROM util_apikey WHERE id = %s", [key.pk])
            raw_key = cursor.fetchone()[0]
        assert raw_key.startswith("enc1:")
        assert raw_key != "a" * 128

    def test_hmac_auth_accepts_legacy_signature_format(self, sample_user):
        """Legacy HMAC headers without a key identifier should still authenticate."""
        # app imports
        from util.backend import HMACAuthentication
        from util.models import APIKey

        key = APIKey(key="b" * 128, comment="legacy key")
        key.save()
        payload = {"student": sample_user.username}
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        signature = hmac.new(key.key_bytes(), body, hashlib.sha256).hexdigest()
        request = APIRequestFactory().post(
            "/api/feedback/",
            data=body,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"HMAC {signature}",
        )

        user, _ = HMACAuthentication().authenticate(request)

        assert user.pk == sample_user.pk
        assert getattr(user, "hmac_authenticated", False) is True

    def test_hmac_auth_accepts_identifier_prefixed_signature_format(self, sample_user):
        """Identifier-prefixed HMAC headers should look up a single API key."""
        # app imports
        from util.backend import HMACAuthentication
        from util.models import APIKey

        key = APIKey(key="c" * 128, comment="identified key")
        key.save()
        payload = {"student": sample_user.username}
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        signature = hmac.new(key.key_bytes(), body, hashlib.sha256).hexdigest()
        request = APIRequestFactory().post(
            "/api/feedback/",
            data=body,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"HMAC {key.identifier}:{signature}",
        )

        user, _ = HMACAuthentication().authenticate(request)

        assert user.pk == sample_user.pk
        assert getattr(user, "hmac_authenticated", False) is True
