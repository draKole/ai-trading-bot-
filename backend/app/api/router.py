"""API Router — aggregates all resource routers."""

from fastapi import APIRouter

from app.api import (
    health,
    auth,
    instruments,
    market_data,
    market_structure,
    liquidity,
    fvg,
    order_blocks,
    smt,
    confluence,
    strategy,
    risk,
    position_sizing,
    trade_management,
    signals,
    trades,
    backtesting,
    analytics,
    dashboard,
    settings as settings_router,
    replay,
    paper_trading,
    live_trading,
    monitoring,
)

api_router = APIRouter()

api_router.include_router(health.router, tags=["Health"])
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(instruments.router, prefix="/instruments", tags=["Instruments"])
api_router.include_router(market_data.router, prefix="/market-data", tags=["Market Data"])
api_router.include_router(market_structure.router, prefix="/market-structure", tags=["Market Structure"])
api_router.include_router(liquidity.router, prefix="/liquidity", tags=["Liquidity"])
api_router.include_router(fvg.router, prefix="/fvg", tags=["FVG"])
api_router.include_router(order_blocks.router, prefix="/order-blocks", tags=["Order Blocks"])
api_router.include_router(smt.router, prefix="/smt", tags=["SMT Divergence"])
api_router.include_router(confluence.router, prefix="/confluence", tags=["Confluence"])
api_router.include_router(strategy.router, prefix="/strategy", tags=["Strategy"])
api_router.include_router(risk.router, prefix="/risk", tags=["Risk"])
api_router.include_router(position_sizing.router, prefix="/position-sizing", tags=["Position Sizing"])
api_router.include_router(trade_management.router, prefix="/trade-management", tags=["Trade Management"])
api_router.include_router(signals.router, prefix="/signals", tags=["Signals"])
api_router.include_router(trades.router, prefix="/trades", tags=["Trades"])
api_router.include_router(backtesting.router, prefix="/backtesting", tags=["Backtesting"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
api_router.include_router(settings_router.router, prefix="/settings", tags=["Settings"])
api_router.include_router(replay.router, prefix="/replay", tags=["Replay"])
api_router.include_router(paper_trading.router, prefix="/paper", tags=["Paper Trading"])
api_router.include_router(live_trading.router, prefix="/live", tags=["Live Trading"])
api_router.include_router(monitoring.router, prefix="/monitoring", tags=["Monitoring"])
