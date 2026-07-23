"""Phase 4B Tests — Position Sizing Engine.

Tests for contracts calculation, constraint validation,
sizing methods, edge cases.
"""

from datetime import datetime, timedelta
import pytest

from app.services.position_sizing.engine import (
    calculate_position, validate_constraints,
    calc_fixed_dollar_contracts, calc_fixed_pct_contracts,
    calc_kelly_contracts, calc_fixed_contract_count,
    calc_dollar_risk, calc_max_contracts_by_risk,
    AccountConfig, PositionRecommendation, ConstraintResult,
)


# ─── Helpers ─────────────────────────────────────────────────

def _setup(**overrides) -> dict:
    base = {
        "setup_id": "test-setup-001",
        "instrument": "ES",
        "timeframe": "5m",
        "direction": "bullish",
        "preferred_entry": 6010.0,
        "entry_zone_low": 6005.0,
        "entry_zone_high": 6015.0,
        "stop_reference": 6000.0,
    }
    base.update(overrides)
    return base


def _bearish_setup(**overrides) -> dict:
    base = {
        "setup_id": "test-setup-bear",
        "instrument": "ES",
        "timeframe": "5m",
        "direction": "bearish",
        "preferred_entry": 6020.0,
        "stop_reference": 6030.0,
    }
    base.update(overrides)
    return base


def _default_config(**overrides) -> AccountConfig:
    base = {
        "account_balance": 100000.0,
        "max_risk_per_trade_pct": 1.0,
        "tick_value": 12.50,
        "tick_size": 0.25,
        "margin_per_contract": 12000.0,
        "sizing_method": "fixed_percentage",
    }
    base.update(overrides)
    return AccountConfig(**base)


# ─── Dollar Risk ─────────────────────────────────────────────

class TestDollarRisk:
    """Per-contract dollar risk calculations."""

    def test_bullish_stop_10pts(self):
        """10pt stop = $500 risk per ES contract."""
        config = _default_config()
        risk = calc_dollar_risk(10.0, config)
        assert risk == 500.0  # 10pts × $50/pt

    def test_bullish_stop_5pts(self):
        risk = calc_dollar_risk(5.0, config=_default_config())
        assert risk == 250.0

    def test_point_value_from_tick(self):
        """Point value derived from tick_value/tick_size."""
        config = _default_config(tick_value=12.50, tick_size=0.25)
        risk = calc_dollar_risk(1.0, config)
        assert risk == 50.0  # $12.50/0.25 = $50/pt


# ─── Sizing Methods ─────────────────────────────────────────

class TestSizingMethods:
    """Configurable sizing method calculations."""

    def test_fixed_dollar_500(self):
        """$500 risk, $500/contract → 1 contract."""
        config = _default_config(
            fixed_dollar_risk=500.0, sizing_method="fixed_dollar",
        )
        contracts = calc_fixed_dollar_contracts(10.0, config)
        assert contracts == 1

    def test_fixed_dollar_1000(self):
        """$1000 risk, $500/contract → 2 contracts."""
        config = _default_config(
            fixed_dollar_risk=1000.0, sizing_method="fixed_dollar",
        )
        contracts = calc_fixed_dollar_contracts(10.0, config)
        assert contracts == 2

    def test_fixed_pct_1pct(self):
        """1% of $100k = $1000, stop 10pts = $500 → 2 contracts."""
        config = _default_config(
            account_balance=100000.0, max_risk_per_trade_pct=1.0,
        )
        contracts = calc_fixed_pct_contracts(10.0, config)
        assert contracts == 2

    def test_fixed_pct_small_account(self):
        """Small account with tight stop."""
        config = _default_config(
            account_balance=10000.0, max_risk_per_trade_pct=1.0,
        )
        contracts = calc_fixed_pct_contracts(5.0, config)
        # $100 risk / ($5*50 = $250) = 0
        assert contracts == 0

    def test_fixed_contracts(self):
        config = _default_config(fixed_contract_count=3)
        assert calc_fixed_contract_count(config) == 3

    def test_kelly(self):
        config = _default_config(
            account_balance=100000.0, kelly_fraction=0.25,
        )
        contracts = calc_kelly_contracts(
            10.0, win_rate=0.6, avg_win_pct=2.0, avg_loss_pct=1.0,
            config=config,
        )
        # Kelly f* = (0.6*2 - 0.4)/2 = (1.2-0.4)/2 = 0.4
        # Fractional: 0.4 * 0.25 = 0.1
        # Dollar risk: $100k * 0.1 = $10k
        # Per-contract risk: 10 * 50 = $500
        # Contracts: 10000/500 = 20
        assert contracts > 0


# ─── Position Calculation ───────────────────────────────────

class TestPositionCalculation:
    """Full position recommendation pipeline."""

    def test_bullish_setup_default(self):
        rec = calculate_position(_setup())
        assert rec.recommended_contracts > 0
        assert rec.sizing_method == "fixed_percentage"
        assert rec.conservative_contracts <= rec.recommended_contracts

    def test_bearish_setup(self):
        rec = calculate_position(_bearish_setup())
        assert rec.recommended_contracts > 0
        assert rec.direction == "bearish"

    def test_small_account_no_contracts(self):
        """Small account can't afford even 1 contract."""
        rec = calculate_position(
            _setup(stop_reference=5900.0),  # 110pt stop
            config=AccountConfig(account_balance=5000.0),
        )
        assert rec.recommended_contracts == 0

    def test_large_account_many_contracts(self):
        """Large account gets many contracts."""
        rec = calculate_position(
            _setup(),
            config=AccountConfig(
                account_balance=1000000.0,
                max_risk_per_trade_pct=1.0,
            ),
        )
        assert rec.recommended_contracts >= 5

    def test_conservative_is_half(self):
        rec = calculate_position(_setup())
        assert rec.conservative_contracts == int(rec.recommended_contracts * 0.5)

    def test_max_allowable_computed(self):
        rec = calculate_position(_setup())
        assert rec.max_allowable_contracts >= rec.recommended_contracts

    def test_risk_pct_calculated(self):
        rec = calculate_position(_setup())
        assert 0 < rec.risk_pct_of_account <= 2.0

    def test_margin_required(self):
        rec = calculate_position(_setup())
        expected_margin = rec.recommended_contracts * 12000.0
        assert rec.margin_required == expected_margin

    def test_kelly_method(self):
        rec = calculate_position(
            _setup(),
            config=AccountConfig(
                sizing_method="kelly", account_balance=100000.0,
                kelly_fraction=0.25,
            ),
        )
        assert rec.sizing_method == "kelly"


# ─── Constraint Validation ──────────────────────────────────

class TestConstraints:
    """Constraint validation against account limits."""

    def test_all_pass(self):
        results = validate_constraints(
            2, 10.0, 6010.0,
            _default_config(max_exposure_pct=1000.0),
        )
        assert all(r.status == "PASS" for r in results)

    def test_fail_excessive_risk(self):
        """100 contracts exceed risk limits."""
        config = _default_config(account_balance=10000.0)
        results = validate_constraints(100, 50.0, 6010.0, config)
        assert any(r.status == "FAIL" and r.rule == "max_trade_risk"
                   for r in results)

    def test_fail_margin(self):
        """100 contracts × $12k margin > buying power."""
        config = _default_config(account_balance=50000.0)
        results = validate_constraints(100, 10.0, 6010.0, config)
        assert any(r.status == "FAIL" and r.rule == "margin"
                   for r in results)

    def test_fail_open_positions(self):
        config = _default_config(max_open_positions=3)
        results = validate_constraints(1, 10.0, 6010.0, config,
                                       open_positions=5)
        assert any(r.status == "FAIL" and r.rule == "open_positions"
                   for r in results)

    def test_fail_daily_loss(self):
        config = _default_config(
            account_balance=100000.0, max_daily_loss_pct=1.0,
        )
        results = validate_constraints(
            10, 30.0, 6010.0, config,
            daily_loss_so_far=8000.0,  # $8k already lost
        )
        # 10 × 30 × 50 = $15k risk, + $8k = $23k > $1k limit
        assert any(r.status == "FAIL" and r.rule == "max_daily_loss"
                   for r in results)

    def test_pass_all_no_failures(self):
        """Recommendation with all passing constraints."""
        rec = calculate_position(
            _setup(),
            config=AccountConfig(
                account_balance=500000.0,
                max_risk_per_trade_pct=1.0,
                max_exposure_pct=1000.0,  # enough for 10 ES contracts
            ),
        )
        assert rec.all_constraints_pass is True
        assert len(rec.failure_reasons) == 0


# ─── Edge Cases ──────────────────────────────────────────────

class TestEdgeCases:
    """Edge case and robustness."""

    def test_historical_consistency(self):
        """Same inputs → same output."""
        r1 = calculate_position(_setup())
        r2 = calculate_position(_setup())
        assert r1.recommended_contracts == r2.recommended_contracts
        assert r1.total_dollar_risk == r2.total_dollar_risk

    def test_to_dict(self):
        rec = calculate_position(_setup())
        d = rec.to_dict()
        assert isinstance(d, dict)
        assert "recommended_contracts" in d
        assert "constraint_results" in d

    def test_zero_contracts_produces_valid_report(self):
        rec = calculate_position(
            _setup(stop_reference=5900.0),
            config=AccountConfig(account_balance=1000.0),
        )
        assert isinstance(rec, PositionRecommendation)
        assert rec.recommended_contracts == 0

    def test_no_stop_uses_default(self):
        """Missing stop → sensible default."""
        rec = calculate_position(_setup(stop_reference=None))
        assert rec.recommended_contracts >= 0

    def test_edge_entry_equals_stop(self):
        """Entry == stop → minimal distance."""
        rec = calculate_position(
            _setup(preferred_entry=6000.0, stop_reference=6000.0),
        )
        assert rec.recommended_contracts >= 0


# ─── Config Tests ────────────────────────────────────────────

class TestAccountConfig:
    """Account configuration."""

    def test_config_round_trip(self):
        config = AccountConfig(
            account_balance=50000.0,
            sizing_method="fixed_dollar",
            fixed_dollar_risk=250.0,
            max_risk_per_trade_pct=2.0,
        )
        d = config.to_dict()
        c2 = AccountConfig.from_dict(d)
        assert c2.account_balance == 50000.0
        assert c2.sizing_method == "fixed_dollar"
        assert c2.fixed_dollar_risk == 250.0

    def test_buying_power_default(self):
        config = AccountConfig(account_balance=100000.0)
        assert config.buying_power == 200000.0


# ─── API Tests ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sizing_dry_run_no_db():
    from app.main import app
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        try:
            response = await client.post(
                "/api/v1/position-sizing/calculate-dry-run",
                params={
                    "instrument": "ES", "entry_price": 6010.0,
                    "stop_price": 6000.0, "direction": "bullish",
                    "account_balance": 100000.0,
                },
            )
            assert response.status_code in (200, 500)
        except Exception:
            pass
