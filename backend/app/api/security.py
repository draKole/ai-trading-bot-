"""Security API — login, logout, sessions, API keys, security events."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.security import (
    SecurityService, AuthManager, SecurityMonitor,
    hash_password, hash_token, EnvSecretProvider,
)

router = APIRouter()

_auth_manager = AuthManager()
_monitor = SecurityMonitor()
_secrets = EnvSecretProvider()


@router.post("/login")
async def login(
    username: str = Query(...),
    password: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    service = SecurityService(db)
    user = await service.get_user_by_username(username)
    if user is None:
        await service.log_security_event("login_failed", detail=f"Unknown user: {username}")
        raise HTTPException(401, "Invalid credentials")

    token = _auth_manager.login(username, password, user["hashed_password"], user["role"])
    if token is None:
        _monitor.record_login_attempt(username, False)
        await service.log_security_event("login_failed", user_id=user["id"],
                                         detail="Invalid password")
        raise HTTPException(401, "Invalid credentials")

    token_hash = hash_token(token.access_token)
    refresh_hash = hash_token(token.refresh_token)
    expires = datetime.now(timezone.utc) + timedelta(seconds=3600)
    await service.create_session(user["id"], token_hash, refresh_hash, expires)
    await service.log_security_event("login_success", user_id=user["id"],
                                     detail="User logged in")

    return {**token.to_dict(), "role": user["role"]}


@router.post("/logout")
async def logout(
    access_token: str = Query(...),
    refresh_token: str = Query(""),
    db: AsyncSession = Depends(get_db),
):
    _auth_manager.logout(access_token, refresh_token)
    return {"status": "logged_out"}


@router.post("/refresh")
async def refresh_token(
    refresh_token: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    token = _auth_manager.refresh_token(refresh_token)
    if token is None:
        raise HTTPException(401, "Invalid or expired refresh token")
    return token.to_dict()


@router.post("/register")
async def register(
    username: str = Query(...),
    email: str = Query(...),
    password: str = Query(...),
    role: str = Query("ReadOnly"),
    db: AsyncSession = Depends(get_db),
):
    service = SecurityService(db)
    existing = await service.get_user_by_username(username)
    if existing:
        raise HTTPException(409, "Username already exists")
    hashed = hash_password(password)
    user = await service.create_user(username, email, hashed, role)
    return {"id": user["id"], "username": user["username"], "role": user["role"]}


@router.get("/profile")
async def get_profile(
    user_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
):
    service = SecurityService(db)
    user = await service.get_user(user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    return {"id": user["id"], "username": user["username"],
            "email": user["email"], "role": user["role"]}


@router.get("/sessions")
async def list_sessions():
    return {"sessions": [], "message": "Session listing requires DB"}


@router.get("/events")
async def list_security_events(
    event_type: Optional[str] = Query(None),
    limit: int = Query(200, le=1000),
    db: AsyncSession = Depends(get_db),
):
    service = SecurityService(db)
    events = await service.get_security_events(event_type=event_type, limit=limit)
    return {"count": len(events), "events": events}


@router.get("/alerts")
async def list_security_alerts(
    severity: Optional[str] = Query(None),
):
    return {"alerts": _monitor.get_alerts(severity=severity),
            "summary": _monitor.get_summary()}
