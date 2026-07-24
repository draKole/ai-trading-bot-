# Security & Secrets Management

## Overview

Comprehensive security layer for authentication, authorization, secrets management, encryption, and security monitoring. Protects the platform without modifying trading logic.

## Architecture

```
Request → Auth Middleware → Role Check → Business Logic
                 ↓
          AuthManager (JWT tokens, bcrypt passwords)
          SecurityMonitor (brute force, rate limiting)
          EnvSecretProvider (secrets, never logged)
          EncryptionManager (at-rest encryption)
                 ↓
          SecurityService (persistence)
          Audit Events (immutable timestamped)
```

---

## 1. Authentication

`AuthManager` token lifecycle:

- **Login**: verify password → issue access (1h) + refresh (24h) tokens
- **Validate**: decode token, check expiration, check revocation
- **Refresh**: new access token from valid refresh token
- **Logout**: revoke both tokens
- **Brute force detection**: 5 failed attempts → account locked

### JWT-like tokens
`generate_token(subject, secret, expires_delta)` — produces signed tokens
`decode_token(token, secret)` — validates and extracts claims

### Password hashing
`hash_password(password)` — SHA-256 + random 16-byte salt
`verify_password(password, hash)` — constant-time comparison

---

## 2. Authorization — Roles

| Role | Level | Access |
|------|-------|--------|
| `Administrator` | 4 | Full system access |
| `Trader` | 3 | Trading + monitoring |
| `ReadOnly` | 2 | Read-only views |
| `ServiceAccount` | 1 | API access only |

`check_permission(role, required)` — hierarchical role comparison.

---

## 3. Secrets Management

`SecretProvider` — abstract interface for future Vault/KMS.
`EnvSecretProvider` — environment variable based (current).

- Never logs, serializes, or commits secret values
- `list_secrets()` returns metadata only (names, no values)
- `rotate_secret(name, new_value)` — key rotation support
- Prefix-based: `DRAKE_` prefix for env vars

---

## 4. Encryption

`EncryptionManager` with XOR-stream encryption (demo):

- `encrypt_data(data, key)` / `decrypt_data(encrypted, key)`
- `generate_encryption_key()` — 32-byte random hex
- `rotate_key(old, new, encrypted)` — re-encryption
- `get_key_fingerprint()` — safe-to-display key fingerprint

---

## 5. Security Monitoring

`SecurityMonitor`:

- Brute force detection (failed login counter per username)
- Rate limiting (request count per IP)
- IP blocking
- Security alerts with severity (critical/warning/info)
- Alert summary (total, critical, blocked IPs)

---

## 6. Database Schema

| Table | Purpose |
|-------|---------|
| `users` | User accounts (username, email, hashed password, role) |
| `roles` | Role definitions with permissions |
| `user_sessions` | Active/revoked sessions with token hashes |
| `api_keys` | Service account API keys (hashed) |
| `security_events` | Immutable audit events |
| `secret_metadata` | Secret metadata (names only, never values) |

---

## 7. API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/auth/login` | Authenticate → JWT tokens |
| `POST` | `/auth/logout` | Revoke tokens |
| `POST` | `/auth/refresh` | Refresh access token |
| `POST` | `/auth/register` | Create user |
| `GET` | `/auth/profile` | User profile |
| `GET` | `/auth/sessions` | Session list |
| `GET` | `/auth/events` | Security events |
| `GET` | `/auth/alerts` | Security alerts |

---

## 8. Limitations

1. JWT-like tokens (not standard JWT) — production should use python-jose
2. XOR encryption is demo-only — production needs AES-GCM
3. No OAuth2/SAML — only username/password
4. In-memory brute force and rate limiting (no Redis/Distributed)
5. Secret rotation requires application restart for env vars
6. No MFA or password policies
