"""Accounts API."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_accounts():
    """Return all trading accounts."""

    return {
        "accounts": [
            {
                "id": "SIM-50000",
                "broker": "Paper",
                "name": "Paper Trading",
                "status": "Connected",
                "equity": 50000,
                "buying_power": 50000,
                "daily_pnl": 0,
            }
        ]
    }
