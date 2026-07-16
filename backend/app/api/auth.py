"""Authentication endpoints — placeholder for Phase 1+."""

from fastapi import APIRouter

router = APIRouter()


@router.post("/login")
async def login():
    """Placeholder: user login."""
    return {"message": "Authentication not yet implemented"}


@router.post("/logout")
async def logout():
    """Placeholder: user logout."""
    return {"message": "Authentication not yet implemented"}
