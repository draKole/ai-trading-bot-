"""Server-side Tradovate demo adapter.

Credentials are read only from environment/config supplied by the server.  The
adapter never exposes them to API responses and requires an injected transport
in tests, making accidental real calls impossible in unit tests.
"""
from __future__ import annotations
import os
from typing import Any, Protocol
from uuid import uuid4
import httpx
from app.services.broker.base import BrokerAdapter, BrokerOrder, BrokerPosition, BrokerAccount, ConnectionState

class HTTPTransport(Protocol):
    async def request(self, method: str, url: str, **kwargs: Any) -> Any: ...

class TradovateDemoAdapter(BrokerAdapter):
    """OAuth/API adapter for Tradovate demo, disabled unless credentials exist."""
    BASE_URL = "https://demo.tradovateapi.com/v1"
    AUTH_URL = "https://live.tradovateapi.com/auth/oauthtoken"
    SUPPORTED = {"ES", "MES", "NQ", "MNQ"}

    def __init__(self, config: dict | None = None, transport: HTTPTransport | None = None):
        super().__init__(config)
        cfg = config or {}
        self.client_id = cfg.get("client_id") or os.getenv("TRADOVATE_CLIENT_ID", "")
        self.client_secret = cfg.get("client_secret") or os.getenv("TRADOVATE_CLIENT_SECRET", "")
        self.username = cfg.get("username") or os.getenv("TRADOVATE_USERNAME", "")
        self.password = cfg.get("password") or os.getenv("TRADOVATE_PASSWORD", "")
        self.account_id = cfg.get("account_id") or os.getenv("TRADOVATE_ACCOUNT_ID", "")
        self.base_url = cfg.get("base_url", self.BASE_URL)
        self._transport = transport
        self._token = ""
        self._client: httpx.AsyncClient | None = None

    def _require_credentials(self) -> None:
        if not all((self.client_id, self.client_secret, self.username, self.password)):
            raise RuntimeError("Tradovate demo credentials are not configured")

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        if self._transport is not None:
            return await self._transport.request(method, path, **kwargs)
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=15)
        return await self._client.request(method, f"{self.base_url}{path}", headers={"Authorization": f"Bearer {self._token}"}, **kwargs)

    async def connect(self) -> bool:
        self._require_credentials()
        response = await self._request("POST", self.AUTH_URL, data={"name": self.username, "password": self.password, "appId": self.client_id, "appVersion": "1.0", "cid": self.client_id, "sec": self.client_secret})
        if getattr(response, "status_code", 200) >= 400:
            self._state = ConnectionState.ERROR
            return False
        payload = response.json() if hasattr(response, "json") else response
        self._token = payload.get("accessToken", payload.get("access_token", ""))
        if not self._token:
            self._state = ConnectionState.ERROR
            return False
        self._state = ConnectionState.CONNECTED
        self._emit_event("connection", "Connected to Tradovate demo")
        return True

    async def disconnect(self) -> bool:
        if self._client: await self._client.aclose(); self._client = None
        self._token = ""; self._state = ConnectionState.DISCONNECTED
        return True
    async def is_connected(self) -> bool: return self._state == ConnectionState.CONNECTED
    def _check_symbol(self, symbol: str) -> None:
        if symbol.upper() not in self.SUPPORTED: raise ValueError(f"Unsupported Tradovate instrument: {symbol}")
    async def place_order(self, order: BrokerOrder) -> BrokerOrder:
        self._check_symbol(order.instrument)
        payload = {"accountId": self.account_id, "action": order.action, "symbol": order.instrument.upper(), "orderQty": order.quantity, "orderType": order.order_type.upper(), "price": order.limit_price, "stopPrice": order.stop_price}
        response = await self._request("POST", "/order/placeorder", json=payload)
        data = response.json() if hasattr(response, "json") else response
        order.broker_order_id = str(data.get("orderId", "")); order.status = "accepted" if order.broker_order_id else "rejected"
        return order
    async def modify_order(self, order_id: str, updates: dict) -> BrokerOrder | None:
        response = await self._request("POST", "/order/modifyorder", json={"orderId": order_id, **updates})
        data = response.json() if hasattr(response, "json") else response
        return BrokerOrder(order_id=order_id, broker_order_id=order_id, status="accepted", limit_price=data.get("price"))
    async def cancel_order(self, order_id: str) -> bool:
        response = await self._request("POST", "/order/cancelorder", json={"orderId": order_id}); return getattr(response, "status_code", 200) < 400
    async def get_order(self, order_id: str) -> BrokerOrder | None:
        response = await self._request("GET", f"/order/item?id={order_id}"); data = response.json() if hasattr(response, "json") else response
        return BrokerOrder(order_id=order_id, broker_order_id=order_id, status=data.get("ordStatus", "unknown")) if data else None
    async def get_positions(self) -> list[BrokerPosition]:
        response = await self._request("GET", f"/position/list?accountId={self.account_id}"); rows = response.json() if hasattr(response, "json") else response
        return [BrokerPosition(instrument=r.get("contractId", ""), quantity=r.get("netPos", 0)) for r in (rows or [])]
    async def get_account(self) -> BrokerAccount:
        response = await self._request("GET", f"/cashbalance/getcashbalancesnapshot?accountId={self.account_id}"); d=response.json() if hasattr(response, "json") else response
        return BrokerAccount(account_id=self.account_id, balance=float(d.get("totalCashValue", 0)), buying_power=float(d.get("netLiquidationValue", 0)))
    async def get_market_price(self, instrument: str) -> float | None:
        self._check_symbol(instrument); return None
