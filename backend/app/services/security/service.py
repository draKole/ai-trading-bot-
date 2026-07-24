"""Security Service — user/session/API key management."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select, and_, desc

from app.models.security import (
    User, Role, UserSession, ApiKey, SecurityEvent, SecretMetadata,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()


class SecurityService:
    """Persistence service for security entities."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_user(self, username: str, email: str,
                          hashed_password: str, role: str = "ReadOnly") -> dict:
        user = User(username=username, email=email,
                    hashed_password=hashed_password, role=role)
        self.session.add(user)
        await self.session.flush()
        return {"id": user.id, "username": user.username, "role": user.role}

    async def get_user(self, user_id: int) -> dict | None:
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        u = result.scalar_one_or_none()
        if u is None:
            return None
        return {"id": u.id, "username": u.username, "email": u.email,
                "role": u.role, "hashed_password": u.hashed_password,
                "is_active": u.is_active}

    async def get_user_by_username(self, username: str) -> dict | None:
        result = await self.session.execute(
            select(User).where(User.username == username)
        )
        u = result.scalar_one_or_none()
        if u is None:
            return None
        return {"id": u.id, "username": u.username, "email": u.email,
                "role": u.role, "hashed_password": u.hashed_password,
                "is_active": u.is_active}

    async def create_session(self, user_id: int, token_hash: str,
                             refresh_hash: str, expires_at) -> int:
        s = UserSession(user_id=user_id, token_hash=token_hash,
                        refresh_token_hash=refresh_hash,
                        expires_at=expires_at, status="active")
        self.session.add(s)
        await self.session.flush()
        return s.id

    async def revoke_session(self, session_id: int) -> bool:
        result = await self.session.execute(
            select(UserSession).where(UserSession.id == session_id)
        )
        s = result.scalar_one_or_none()
        if s is None:
            return False
        s.status = "revoked"
        from datetime import datetime, timezone
        s.revoked_at = datetime.now(timezone.utc)
        await self.session.flush()
        return True

    async def create_api_key(self, user_id: int, key_hash: str,
                             name: str = "Default") -> int:
        k = ApiKey(user_id=user_id, key_hash=key_hash, name=name)
        self.session.add(k)
        await self.session.flush()
        return k.id

    async def revoke_api_key(self, key_id: int) -> bool:
        result = await self.session.execute(
            select(ApiKey).where(ApiKey.id == key_id)
        )
        k = result.scalar_one_or_none()
        if k is None:
            return False
        k.is_active = False
        await self.session.flush()
        return True

    async def log_security_event(self, event_type: str, user_id: int | None = None,
                                 detail: str = "", ip_address: str = "",
                                 severity: str = "info") -> int:
        e = SecurityEvent(event_type=event_type, user_id=user_id,
                          detail=detail, ip_address=ip_address,
                          severity=severity)
        self.session.add(e)
        await self.session.flush()
        return e.id

    async def get_security_events(self, event_type: str | None = None,
                                  limit: int = 200) -> list[dict]:
        conditions = []
        if event_type:
            conditions.append(SecurityEvent.event_type == event_type)
        query = select(SecurityEvent).order_by(desc(SecurityEvent.timestamp)).limit(limit)
        if conditions:
            query = query.where(and_(*conditions))
        result = await self.session.execute(query)
        return [
            {"id": e.id, "event_type": e.event_type, "user_id": e.user_id,
             "detail": e.detail, "severity": e.severity,
             "timestamp": e.timestamp.isoformat() if e.timestamp else None}
            for e in result.scalars().all()
        ]
