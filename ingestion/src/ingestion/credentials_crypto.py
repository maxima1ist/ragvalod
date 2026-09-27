"""Fernet helpers for encrypting source credentials at rest."""

from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import Mapping

from cryptography.fernet import Fernet, InvalidToken


class CredentialsCryptoError(ValueError):
    """Raised when encryption key is missing/invalid or ciphertext cannot be decrypted."""


class CredentialsCrypto:
    """Encrypt/decrypt credential maps. Empty key disables crypto (no-cred schedules only)."""

    def __init__(self, key: str) -> None:
        self._raw_key = (key or "").strip()
        self._fernet: Fernet | None = None
        if self._raw_key:
            self._fernet = Fernet(self._normalize_key(self._raw_key))

    @property
    def enabled(self) -> bool:
        return self._fernet is not None

    @staticmethod
    def _normalize_key(key: str) -> bytes:
        """Accept a Fernet key or derive one from an arbitrary secret string."""
        raw = key.encode("utf-8")
        try:
            Fernet(raw)
            return raw
        except (ValueError, TypeError):
            digest = hashlib.sha256(raw).digest()
            return base64.urlsafe_b64encode(digest)

    def require_enabled(self) -> None:
        if not self.enabled:
            raise CredentialsCryptoError(
                "INGESTION_CREDENTIALS_ENCRYPTION_KEY is required to store "
                'credentials for scheduled ingest (python -c "from cryptography.fernet '
                'import Fernet; print(Fernet.generate_key().decode())")'
            )

    def encrypt_mapping(self, credentials: Mapping[str, str]) -> str:
        if not credentials:
            return ""
        self.require_enabled()
        assert self._fernet is not None
        payload = json.dumps(dict(credentials), separators=(",", ":"), sort_keys=True)
        return self._fernet.encrypt(payload.encode("utf-8")).decode("utf-8")

    def decrypt_mapping(self, token: str) -> dict[str, str]:
        if not token:
            return {}
        self.require_enabled()
        assert self._fernet is not None
        try:
            raw = self._fernet.decrypt(token.encode("utf-8"))
        except InvalidToken as exc:
            raise CredentialsCryptoError(
                "failed to decrypt stored credentials (wrong encryption key?)"
            ) from exc
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise CredentialsCryptoError("decrypted credentials must be a JSON object")
        return {str(k): str(v) for k, v in data.items()}
