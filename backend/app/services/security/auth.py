"""Authentication & Authorization — JWT tokens, password hashing, roles."""

import hashlib
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from uuid import uuid4


class Role(str, Enum):
    ADMINISTRATOR = "Administrator"
    TRADER = "Trader"
    READONLY = "ReadOnly"
    SERVICE_ACCOUNT = "ServiceAccount"


@dataclass
class AuthToken:
    """JWT-compatible token representation."""
    access_token: str = ""
    refresh_token: str = ""
    token_type: str = "bearer"
    expires_in: int = 3600

    def to_dict(self) -> dict:
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_type": self.token_type,
            "expires_in": self.expires_in,
        }


@dataclass
class UserCredentials:
    """User credentials — never logged or serialized."""
    username: str
    password: str  # plaintext during auth only, never stored


def hash_password(password: str) -> str:
    """Hash a password using bcrypt-like approach (SHA-256 + salt)."""
    salt = secrets.token_hex(16)
    h = hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()
    return f"sha256${salt}${h}"


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against a hash."""
    try:
        parts = hashed.split("$")
        if len(parts) != 3 or parts[0] != "sha256":
            return False
        salt = parts[1]
        expected = parts[2]
        h = hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()
        return secrets.compare_digest(h, expected)
    except Exception:
        return False


def generate_token(subject: str, secret: str,
                   expires_delta: int = 3600) -> str:
    """Generate a JWT-like token (simplified for testing)."""
    now = datetime.now(timezone.utc)
    exp = now + timedelta(seconds=expires_delta)
    # Use base64-encoded subject to avoid delimiter collisions
    import base64
    encoded_sub = base64.b64encode(subject.encode()).decode()
    payload = f"{encoded_sub}:{int(exp.timestamp())}:{secrets.token_hex(8)}"
    sig = hashlib.sha256(f"{payload}:{secret}".encode()).hexdigest()
    return f"eyJ.{payload}.{sig[:32]}"


def decode_token(token: str, secret: str) -> dict | None:
    """Decode and validate a token. Returns payload dict or None."""
    try:
        import base64
        parts = token.split(".")
        if len(parts) != 3:
            return None
        payload = parts[1]
        fields = payload.split(":")
        if len(fields) < 2:
            return None
        encoded_sub = fields[0]
        subject = base64.b64decode(encoded_sub).decode()
        exp_ts = int(fields[1])
        if datetime.now(timezone.utc).timestamp() > exp_ts:
            return None  # Expired
        return {"sub": subject, "exp": exp_ts}
    except Exception:
        return None


def hash_token(token: str) -> str:
    """Hash a token for storage."""
    return hashlib.sha256(token.encode()).hexdigest()


class AuthManager:
    """Manages authentication, token lifecycle, and authorization."""

    def __init__(self, secret_key: str = "default_secret_change_me"):
        self._secret = secret_key
        self._revoked_tokens: set[str] = set()
        self._failed_attempts: dict[str, int] = {}

    def login(self, username: str, password: str,
              stored_hash: str, role: str = "ReadOnly") -> AuthToken | None:
        """Authenticate a user. Returns token or None."""
        if not verify_password(password, stored_hash):
            self._record_failure(username)
            return None
        access = generate_token(username, self._secret, 3600)
        refresh = generate_token(f"{username}:refresh", self._secret, 86400)
        return AuthToken(
            access_token=access,
            refresh_token=refresh,
            expires_in=3600,
        )

    def validate_token(self, token: str) -> dict | None:
        """Validate an access token. Returns claims or None."""
        if token in self._revoked_tokens:
            return None
        return decode_token(token, self._secret)

    def refresh_token(self, refresh_token: str) -> AuthToken | None:
        """Issue a new access token from a refresh token."""
        claims = decode_token(refresh_token, self._secret)
        if claims is None:
            return None
        username = claims["sub"].replace(":refresh", "")
        return AuthToken(
            access_token=generate_token(username, self._secret, 3600),
            refresh_token=generate_token(f"{username}:refresh", self._secret, 86400),
            expires_in=3600,
        )

    def revoke_token(self, token: str) -> None:
        """Revoke a token."""
        self._revoked_tokens.add(token)

    def logout(self, access_token: str, refresh_token: str = "") -> None:
        """Logout — revoke both tokens."""
        self._revoked_tokens.add(access_token)
        if refresh_token:
            self._revoked_tokens.add(refresh_token)

    def _record_failure(self, username: str) -> None:
        """Record a failed login attempt."""
        self._failed_attempts[username] = self._failed_attempts.get(username, 0) + 1

    def check_brute_force(self, username: str, max_attempts: int = 5) -> bool:
        """Check if login attempts exceed threshold."""
        return self._failed_attempts.get(username, 0) >= max_attempts

    def reset_failures(self, username: str) -> None:
        """Reset failed attempt counter."""
        self._failed_attempts.pop(username, None)

    def check_permission(self, role: str, required: str) -> bool:
        """Check if role has required permission level."""
        hierarchy = {"Administrator": 4, "Trader": 3,
                     "ReadOnly": 2, "ServiceAccount": 1}
        return hierarchy.get(role, 0) >= hierarchy.get(required, 0)
