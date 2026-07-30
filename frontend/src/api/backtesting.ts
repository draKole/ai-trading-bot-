/** Backtesting API client. */

const BASE = "/api/v1";

/* ─── Types ──────────────────────────────────────────── */

export interface BacktestMetrics {
  net_profit: number;
  gross_profit: number;
  gross_loss: number;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  breakeven_trades: number;
  win_rate: number;
  loss_rate: number;
  profit_factor: number;
  average_win: number;
  average_loss: number;
  average_r: number;
  expectancy: number;
  max_drawdown: number;
  max_drawdown_pct: number;
  max_consecutive_wins: number;
  max_consecutive_losses: number;
  average_trade_duration_seconds: number;
  long_trades: number;
  long_wins: number;
  long_pnl: number;
  short_trades: number;
  short_wins: number;
  short_pnl: number;
  largest_winner: number;
  largest_loser: number;
  // Sprint 3
  sharpe_ratio: number;
  sortino_ratio: number;
  annual_return_pct: number;
  monthly_returns: MonthlyReturn[];
  max_drawdown_duration_days: number;
  recovery_factor: number;
}

export interface MonthlyReturn {
  month: string;
  return_pct: number;
  trades: number;
  pnl: number;
}

export interface EquityPoint {
  trade_index: number;
  timestamp: string | null;
  account_balance: number;
  equity: number;
  drawdown: number;
  drawdown_pct: number;
  peak_equity: number;
}

export interface BacktestTrade {
  trade_id: string;
  entry_time: string | null;
  exit_time: string | null;
  direction: string;
  quantity: number;
  entry_price: number;
  exit_price: number;
  stop_price: number;
  risk: number;
  r_multiple: number;
  pnl: number;
  duration_seconds: number;
  exit_reason: string;
  strategy_version: string;
}

export interface BacktestConfig {
  instrument: string;
  timeframe: string;
  start_time: string | null;
  end_time: string | null;
  replay_mode: string;
  strategy: string;
  strategy_params: Record<string, unknown>;
  initial_balance: number;
  commission_per_contract: number;
  slippage_ticks: number;
}

export interface BacktestResult {
  run_id: string;
  config: BacktestConfig;
  trades: BacktestTrade[];
  equity_curve: EquityPoint[];
  metrics: BacktestMetrics;
  errors: string[];
}

export interface RunListItem {
  id: number;
  instrument: string;
  timeframe: string;
  start_time: string;
  end_time: string;
  status: string;
  created_at: string;
}

/* ─── Helpers ────────────────────────────────────────── */

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`HTTP ${res.status}: ${text || res.statusText}`);
  }
  return res.json();
}

/* ─── Run Backtest ───────────────────────────────────── */

export async function runBacktest(params: {
  instrument: string;
  timeframe: string;
  start_time: string;
  end_time: string;
  strategy: string;
  bars_json: string;
  initial_balance?: number;
  commission?: number;
  slippage?: number;
}): Promise<{
  run_id: number;
  status: string;
  metrics: BacktestMetrics;
  trade_count: number;
  equity_curve: EquityPoint[];
}> {
  const q = new URLSearchParams({
    instrument: params.instrument,
    timeframe: params.timeframe,
    start_time: params.start_time,
    end_time: params.end_time,
    strategy: params.strategy,
    bars_json: params.bars_json,
    initial_balance: String(params.initial_balance ?? 100000),
    commission: String(params.commission ?? 2.5),
    slippage: String(params.slippage ?? 1),
  });
  return fetchJson(`${BASE}/backtesting/run?${q}`, { method: "POST" });
}

/* ─── Run Dry Backtest ───────────────────────────────── */

export async function runDryBacktest(params: {
  instrument: string;
  timeframe: string;
  start_time: string;
  end_time: string;
  strategy: string;
  bars_json: string;
  initial_balance?: number;
  commission?: number;
  slippage?: number;
}): Promise<BacktestResult> {
  const q = new URLSearchParams({
    instrument: params.instrument,
    timeframe: params.timeframe,
    start_time: params.start_time,
    end_time: params.end_time,
    strategy: params.strategy,
    bars_json: params.bars_json,
    initial_balance: String(params.initial_balance ?? 100000),
    commission: String(params.commission ?? 2.5),
    slippage: String(params.slippage ?? 1),
  });
  return fetchJson(`${BASE}/backtesting/run-dry?${q}`, { method: "POST" });
}

/* ─── List Runs ──────────────────────────────────────── */

export async function listRuns(instrument?: string): Promise<{
  count: number;
  runs: RunListItem[];
}> {
  const params = instrument ? `?instrument=${instrument}` : "";
  return fetchJson(`${BASE}/backtesting/runs${params}`);
}

/* ─── Get Run ────────────────────────────────────────── */

export async function getRun(runId: number): Promise<{
  id: number;
  instrument: string;
  timeframe: string;
  start_time: string;
  end_time: string;
  status: string;
  total_bars: number;
  metrics_json: string;
  equity_curve_json: string;
  created_at: string;
}> {
  return fetchJson(`${BASE}/backtesting/runs/${runId}`);
}
