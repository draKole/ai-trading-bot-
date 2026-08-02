"""Mock-only tests for the server-side Tradovate demo adapter."""
import pytest
from app.services.broker.base import BrokerOrder
from app.services.broker.secure_tradovate import TradovateDemoAdapter

class Response:
    def __init__(self, payload, status_code=200): self._payload, self.status_code = payload, status_code
    def json(self): return self._payload

class Transport:
    def __init__(self): self.calls=[]
    async def request(self, method, url, **kwargs):
        self.calls.append((method,url,kwargs))
        if "oauthtoken" in url: return Response({"accessToken":"mock-token"})
        if "placeorder" in url: return Response({"orderId":123})
        if "cashbalance" in url: return Response({"totalCashValue":1000,"netLiquidationValue":900})
        return Response([])

@pytest.mark.asyncio
async def test_demo_adapter_uses_mock_transport_and_never_exposes_secret():
    transport=Transport()
    adapter=TradovateDemoAdapter({"client_id":"id","client_secret":"secret","username":"user","password":"pass","account_id":"acct"}, transport)
    assert await adapter.connect()
    order=await adapter.place_order(BrokerOrder(instrument="ES", quantity=1))
    assert order.status == "accepted" and order.broker_order_id == "123"
    assert (await adapter.get_account()).balance == 1000
    assert all("secret" not in repr(call) for call in transport.calls)

@pytest.mark.asyncio
async def test_missing_credentials_fail_before_transport():
    adapter=TradovateDemoAdapter({}, Transport())
    with pytest.raises(RuntimeError, match="not configured"):
        await adapter.connect()

@pytest.mark.asyncio
async def test_supported_symbols_are_enforced():
    adapter=TradovateDemoAdapter({"client_id":"i","client_secret":"s","username":"u","password":"p"}, Transport())
    with pytest.raises(ValueError): await adapter.get_market_price("CL")
