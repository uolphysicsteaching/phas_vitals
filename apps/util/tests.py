"""Tests for util app security helpers."""

# Python imports
import hashlib
import hmac
import json

# Django imports
from django.db import connection

# external imports
import pandas as pd
import pytest
from rest_framework.test import APIRequestFactory


@pytest.mark.django_db
class TestGradebookImport:
    """Tests for the bulk Gradebook result importer."""

    def test_bulk_import_filters_students_and_recalculates_scores(self, sample_status_code, sample_user, sample_test):
        """Only enrolled students are imported and their best score is retained."""
        # external imports
        from minerva.models import ModuleEnrollment, Test_Attempt, Test_Score
        from util.wizard import GradebookImport

        ModuleEnrollment.objects.create(
            module=sample_test.module,
            student=sample_user,
            status=sample_status_code,
        )
        frame = pd.DataFrame(
            {
                "Result": [40.0, 75.0, 99.0],
                "Attempt date": ["2026-01-01", "2026-01-02", "2026-01-03"],
            },
            index=[sample_user.number, sample_user.number, 999999],
        )

        result = GradebookImport._bulk_process_attempts(
            frame,
            sample_test.module,
            {"Result": sample_test},
            "Attempt date",
        )

        score = Test_Score.objects.get(user=sample_user, test=sample_test)
        assert result == {"rows": 3, "attempts": 2, "students": 1, "scores": 1}
        assert Test_Attempt.objects.filter(test_entry=score).count() == 2
        assert score.score == 75.0
        assert score.passed is True


@pytest.mark.django_db
@pytest.mark.unit
class TestAPIKeyStorage:
    """Test encrypted storage and HMAC compatibility for API keys."""

    def test_apikey_is_encrypted_at_rest(self):
        """Saving an API key should encrypt the stored database value."""
        # external imports
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
        # external imports
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
        # external imports
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
