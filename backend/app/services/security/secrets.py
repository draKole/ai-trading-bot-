"""Secrets Management — provider interface for broker creds, keys, etc.

Never logs, serializes, or commits secrets. Provider interface for
future Vault/KMS integration.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


@dataclass
class SecretEntry:
    """Metadata about a secret — NEVER contains the secret value."""
    name: str
    provider: str = "env"
    rotated_at: datetime | None = None
    expires_at: datetime | None = None

    def to_dict(self) -> dict:
        return {
            "name": self.name, "provider": self.provider,
            "rotated_at": self.rotated_at.isoformat() if self.rotated_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }


class SecretProvider:
    """Abstract interface for secret retrieval. Future: Vault, KMS, etc."""

    def get_secret(self, name: str) -> str | None:
        """Get a secret value. Never logged or serialized."""
        raise NotImplementedError

    def set_secret(self, name: str, value: str) -> None:
        """Set a secret value."""
        raise NotImplementedError


class EnvSecretProvider(SecretProvider):
    """Environment variable-based secret provider."""

    def __init__(self, prefix: str = "DRAKE_"):
        self._prefix = prefix
        self._cache: dict[str, str] = {}
        self._metadata: dict[str, SecretEntry] = {}

    def get_secret(self, name: str) -> str | None:
        import os
        if name in self._cache:
            return self._cache[name]
        env_key = f"{self._prefix}{name.upper()}"
        value = os.getenv(env_key)
        if value:
            self._cache[name] = value
            self._metadata[name] = SecretEntry(name=name, provider="env")
            return value
        return None

    def set_secret(self, name: str, value: str) -> None:
        self._cache[name] = value
        self._metadata[name] = SecretEntry(name=name, provider="env")

    def list_secrets(self) -> list[SecretEntry]:
        """List secret metadata (names only, never values)."""
        return list(self._metadata.values())

    def rotate_secret(self, name: str, new_value: str) -> bool:
        """Rotate a secret to a new value."""
        if name not in self._cache:
            return False
        self._cache[name] = new_value
        if name in self._metadata:
            self._metadata[name].rotated_at = datetime.now(timezone.utc)
        return True
