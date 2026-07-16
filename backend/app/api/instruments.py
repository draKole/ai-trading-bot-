"""Instrument endpoints."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_instruments():
    """List available trading instruments."""
    return {"instruments": ["MNQ", "NQ", "MES", "ES"]}
