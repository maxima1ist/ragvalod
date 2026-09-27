"""Unit tests for credentials crypto and schedule store."""

from __future__ import annotations

from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from ingestion.credentials_crypto import CredentialsCrypto, CredentialsCryptoError
from ingestion.schedule_store import ScheduleStore


def test_fernet_roundtrip() -> None:
    key = Fernet.generate_key().decode()
    crypto = CredentialsCrypto(key)
    token = crypto.encrypt_mapping({"token": "secret", "extra": "1"})
    assert token
    assert "secret" not in token
    assert crypto.decrypt_mapping(token) == {"extra": "1", "token": "secret"}


def test_derived_key_from_passphrase() -> None:
    crypto = CredentialsCrypto("not-a-fernet-key-but-ok")
    token = crypto.encrypt_mapping({"a": "b"})
    assert crypto.decrypt_mapping(token) == {"a": "b"}


def test_empty_credentials_no_key_needed() -> None:
    crypto = CredentialsCrypto("")
    assert crypto.encrypt_mapping({}) == ""
    assert crypto.decrypt_mapping("") == {}


def test_encrypt_requires_key() -> None:
    crypto = CredentialsCrypto("")
    with pytest.raises(CredentialsCryptoError):
        crypto.encrypt_mapping({"token": "x"})


def test_schedule_store_encrypts_and_lists(tmp_path: Path) -> None:
    key = Fernet.generate_key().decode()
    crypto = CredentialsCrypto(key)
    store = ScheduleStore(tmp_path / "schedules.json", crypto)

    record = store.upsert(
        schedule_id=None,
        name="hourly-notion",
        cron="0 * * * *",
        enabled=True,
        sources=[("notion", {"integration_token": "ntn_secret"}, {"max_pages": "5"})],
        all_with_credentials=False,
    )
    assert record.schedule_id
    assert record.sources[0].credentials_encrypted
    assert "ntn_secret" not in record.sources[0].credentials_encrypted
    assert "ntn_secret" not in (tmp_path / "schedules.json").read_text(encoding="utf-8")

    public = store.list()[0].to_public_dict()
    assert public["source_names"] == ["notion"]
    assert "credentials" not in public

    decrypted = store.decrypt_sources(record)
    assert decrypted[0][1]["integration_token"] == "ntn_secret"

    reloaded = ScheduleStore(tmp_path / "schedules.json", crypto)
    assert len(reloaded.list()) == 1
    assert reloaded.decrypt_sources(reloaded.list()[0])[0][1]["integration_token"] == "ntn_secret"


def test_schedule_store_rejects_bad_cron(tmp_path: Path) -> None:
    store = ScheduleStore(tmp_path / "schedules.json", CredentialsCrypto(""))
    with pytest.raises(ValueError, match="cron"):
        store.upsert(
            schedule_id=None,
            name="bad",
            cron="not-cron",
            enabled=True,
            sources=[("local_files", {}, {})],
            all_with_credentials=False,
        )


def test_schedule_without_creds_works_without_key(tmp_path: Path) -> None:
    store = ScheduleStore(tmp_path / "schedules.json", CredentialsCrypto(""))
    record = store.upsert(
        schedule_id=None,
        name="local-daily",
        cron="0 3 * * *",
        enabled=True,
        sources=[("local_files", {}, {"path": "/test_data"})],
        all_with_credentials=False,
    )
    assert record.sources[0].credentials_encrypted == ""
