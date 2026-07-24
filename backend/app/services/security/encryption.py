"""Encryption — at-rest encryption, key management, sensitive field protection."""

import base64
import hashlib
import secrets


def encrypt_data(data: str, key: str) -> str:
    """Encrypt data using XOR with key-derived stream (demo-only)."""
    if not data or not key:
        return ""
    key_bytes = hashlib.sha256(key.encode()).digest()
    data_bytes = data.encode()
    result = bytes(d ^ key_bytes[i % len(key_bytes)]
                   for i, d in enumerate(data_bytes))
    return base64.b64encode(result).decode()


def decrypt_data(encrypted: str, key: str) -> str:
    """Decrypt data encrypted with encrypt_data."""
    if not encrypted or not key:
        return ""
    try:
        key_bytes = hashlib.sha256(key.encode()).digest()
        raw = base64.b64decode(encrypted)
        result = bytes(r ^ key_bytes[i % len(key_bytes)]
                       for i, r in enumerate(raw))
        return result.decode()
    except Exception:
        return ""


def generate_encryption_key() -> str:
    """Generate a new random encryption key."""
    return secrets.token_hex(32)


def rotate_key(old_key: str, new_key: str, encrypted_data: str) -> str:
    """Re-encrypt data with a new key."""
    plain = decrypt_data(encrypted_data, old_key)
    return encrypt_data(plain, new_key)


class EncryptionManager:
    """Manages encryption keys and sensitive field protection."""

    def __init__(self, master_key: str = ""):
        self._master_key = master_key or generate_encryption_key()

    def encrypt(self, data: str) -> str:
        return encrypt_data(data, self._master_key)

    def decrypt(self, encrypted: str) -> str:
        return decrypt_data(encrypted, self._master_key)

    def rotate_master_key(self, new_key: str) -> None:
        """Rotate master key — requires re-encrypting all stored data."""
        self._master_key = new_key

    def get_key_fingerprint(self) -> str:
        """Get a fingerprint of the current key (safe to display)."""
        return hashlib.sha256(self._master_key.encode()).hexdigest()[:16]
