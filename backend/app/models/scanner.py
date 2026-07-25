"""Scanner ORM models — Watchlist, WatchlistSymbol, ScanRun, ScanResult, Opportunity."""

from datetime import datetime

from sqlalchemy import String, Float, Integer, DateTime, JSON, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Watchlist(Base):
    __tablename__ = "watchlists"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class WatchlistSymbol(Base):
    __tablename__ = "watchlist_symbols"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    watchlist_id: Mapped[int] = mapped_column(Integer, ForeignKey("watchlists.id"), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    timeframes: Mapped[str] = mapped_column(String(100), default="5m")
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class ScanRun(Base):
    __tablename__ = "scan_runs"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    watchlist_id: Mapped[int] = mapped_column(Integer, ForeignKey("watchlists.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    symbols_scanned: Mapped[int] = mapped_column(Integer, default=0)
    opportunities_found: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class ScanResult(Base):
    __tablename__ = "scan_results"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    scan_id: Mapped[int] = mapped_column(Integer, ForeignKey("scan_runs.id"), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[str] = mapped_column(String(20), default="Low")
    detail_json: Mapped[str] = mapped_column(String(2000), default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class Opportunity(Base):
    __tablename__ = "opportunities"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    scan_id: Mapped[int] = mapped_column(Integer, ForeignKey("scan_runs.id"), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False)
    direction: Mapped[str] = mapped_column(String(10), default="neutral")
    score: Mapped[float] = mapped_column(Float, default=0.0)
    rank: Mapped[int] = mapped_column(Integer, default=0)
    expected_reward: Mapped[float] = mapped_column(Float, default=0.0)
    risk: Mapped[float] = mapped_column(Float, default=0.0)
    metrics_json: Mapped[str | None] = mapped_column(String(3000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
