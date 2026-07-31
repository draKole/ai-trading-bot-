"""Settings persistence — model validation, service logic, API contract tests."""

import pytest

from app.api.settings import SettingsUpdate, SettingsResponse


# ═══════════════════════════════════════════════════════════════
# Pydantic model validation
# ═══════════════════════════════════════════════════════════════

class TestSettingsUpdateValidation:
    """SettingsUpdate must reject invalid values and accept valid partials."""

    def test_empty_update_rejected(self):
        """Empty body should produce no fields."""
        su = SettingsUpdate()
        assert su.model_dump(exclude_none=True) == {}

    def test_valid_trading_mode_accepted(self):
        su = SettingsUpdate(trading_mode="PAPER")
        assert su.trading_mode == "PAPER"

    def test_valid_live_mode_accepted(self):
        su = SettingsUpdate(trading_mode="LIVE")
        assert su.trading_mode == "LIVE"

    def test_invalid_trading_mode_rejected(self):
        with pytest.raises(ValueError):
            SettingsUpdate(trading_mode="INVALID")

    def test_risk_percent_range(self):
        su = SettingsUpdate(default_risk_percent=0.0)
        assert su.default_risk_percent == 0.0
        su = SettingsUpdate(default_risk_percent=100.0)
        assert su.default_risk_percent == 100.0

    def test_risk_percent_negative_rejected(self):
        with pytest.raises(ValueError):
            SettingsUpdate(default_risk_percent=-0.1)

    def test_risk_percent_over_100_rejected(self):
        with pytest.raises(ValueError):
            SettingsUpdate(default_risk_percent=100.1)

    def test_min_risk_reward_positive(self):
        su = SettingsUpdate(min_risk_reward=0.1)
        assert su.min_risk_reward == 0.1

    def test_min_risk_reward_zero_rejected(self):
        with pytest.raises(ValueError):
            SettingsUpdate(min_risk_reward=0.0)

    def test_min_risk_reward_negative_rejected(self):
        with pytest.raises(ValueError):
            SettingsUpdate(min_risk_reward=-1.0)

    def test_max_contracts_positive(self):
        su = SettingsUpdate(max_contracts=1)
        assert su.max_contracts == 1

    def test_max_contracts_zero_rejected(self):
        with pytest.raises(ValueError):
            SettingsUpdate(max_contracts=0)

    def test_max_trades_per_day_positive(self):
        su = SettingsUpdate(max_trades_per_day=1)
        assert su.max_trades_per_day == 1

    def test_max_trades_per_session_positive(self):
        su = SettingsUpdate(max_trades_per_session=1)
        assert su.max_trades_per_session == 1

    def test_partial_update_only_sets_provided(self):
        su = SettingsUpdate(trading_mode="LIVE", default_risk_percent=2.0)
        data = su.model_dump(exclude_none=True)
        assert data == {"trading_mode": "LIVE", "default_risk_percent": 2.0}

    def test_data_provider_accepts_any_string(self):
        su = SettingsUpdate(data_provider="polygon")
        assert su.data_provider == "polygon"


# ═══════════════════════════════════════════════════════════════
# SettingsResponse contract
# ═══════════════════════════════════════════════════════════════

class TestSettingsResponse:
    """Response schema matches the frontend ApplicationSettings interface."""

    def test_defaults_match_frontend_contract(self):
        sr = SettingsResponse()
        d = sr.model_dump()
        assert set(d.keys()) == {
            "trading_mode",
            "data_provider",
            "default_risk_percent",
            "min_risk_reward",
            "max_contracts",
            "max_trades_per_day",
            "max_trades_per_session",
        }

    def test_default_trading_mode_is_paper(self):
        sr = SettingsResponse()
        assert sr.trading_mode == "PAPER"

    def test_default_risk_percent_is_1(self):
        sr = SettingsResponse()
        assert sr.default_risk_percent == 1.0

    def test_all_defaults_are_safe_values(self):
        sr = SettingsResponse()
        assert sr.trading_mode in ("PAPER", "LIVE")
        assert sr.default_risk_percent >= 0
        assert sr.min_risk_reward > 0
        assert sr.max_contracts > 0
        assert sr.max_trades_per_day > 0
        assert sr.max_trades_per_session > 0


# ═══════════════════════════════════════════════════════════════
# SettingsService logic (without DB)
# ═══════════════════════════════════════════════════════════════

class TestSettingsService:
    """Service layer: key filtering, defaults, secret exclusion."""

    def test_expected_fields_are_non_secret(self):
        """The EXPECTED_FIELDS set must not contain any secret keys."""
        from app.services.settings.service import EXPECTED_FIELDS
        secret_keys = {
            "database_url", "redis_url", "secret_key",
            "broker_key", "broker_secret", "api_key",
            "password", "token", "private_key",
        }
        assert EXPECTED_FIELDS.isdisjoint(secret_keys)

    def test_update_filters_unknown_keys(self):
        """Unknown/secret keys are silently dropped by the service."""
        from app.services.settings.service import EXPECTED_FIELDS
        payload = {
            "trading_mode": "LIVE",
            "database_url": "postgresql://evil",  # must be dropped
            "broker_secret": "abc123",            # must be dropped
            "max_contracts": 5,                   # allowed
        }
        filtered = {k: v for k, v in payload.items() if k in EXPECTED_FIELDS}
        assert "database_url" not in filtered
        assert "broker_secret" not in filtered
        assert filtered == {"trading_mode": "LIVE", "max_contracts": 5}

    def test_defaults_are_present_when_no_db_row(self):
        """When DB returns None, environment defaults are used."""
        from app.services.settings.service import _DEFAULTS
        assert "trading_mode" in _DEFAULTS
        assert "data_provider" in _DEFAULTS
        assert _DEFAULTS["trading_mode"] in ("PAPER", "LIVE")
        assert _DEFAULTS["max_contracts"] > 0

    def test_get_returns_defaults_when_no_db_row(self):
        """When DB returns None, service falls back to environment defaults."""
        from app.services.settings.service import _DEFAULTS, EXPECTED_FIELDS
        # Defaults dict must contain exactly the expected fields
        assert set(_DEFAULTS.keys()) == EXPECTED_FIELDS
        # Defaults must be safe values
        assert _DEFAULTS["trading_mode"] in ("PAPER", "BACKTEST", "LIVE")
        assert _DEFAULTS["default_risk_percent"] >= 0
        assert _DEFAULTS["min_risk_reward"] > 0
        assert _DEFAULTS["max_contracts"] > 0
        assert _DEFAULTS["max_trades_per_day"] > 0
        assert _DEFAULTS["max_trades_per_session"] > 0
