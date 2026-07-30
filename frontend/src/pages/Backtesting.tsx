import { useState, useEffect, useRef, useCallback } from "react";
import {
  runDryBacktest,
  type BacktestResult,
} from "../api/backtesting";
import { getInstruments, type Instrument } from "../api/market-data";
import { createChart, ColorType } from "lightweight-charts";

/* ─── Constants ─────────────────────────────────────── */

const STRATEGIES = [
  { value: "trend_following", label: "Trend Following" },
  { value: "mean_reversion", label: "Mean Reversion" },
  { value: "breakout", label: "Breakout" },
];

const TIMEFRAMES = ["5m", "15m", "1h"];

function defaultStart(): string {
  const d = new Date();
  d.setDate(d.getDate() - 30);
  return d.toISOString().slice(0, 16);
}

function defaultEnd(): string {
  return new Date().toISOString().slice(0, 16);
}

function generateSampleBars(
  symbol: string,
  timeframe: string,
  bars: number = 200,
): object[] {
  const now = new Date();
  const result: object[] = [];
  let price = symbol === "NQ" ? 20000 : symbol === "MNQ" ? 20000 : 5500;
  const stepMin =
    timeframe === "5m" ? 5 : timeframe === "15m" ? 15 : 60;
  for (let i = bars - 1; i >= 0; i--) {
    const t = new Date(now.getTime() - i * stepMin * 60 * 1000);
    const change = (Math.random() - 0.5) * price * 0.005;
    const open = price;
    price += change;
    const close = price;
    const high = Math.max(open, close) + Math.random() * price * 0.002;
    const low = Math.min(open, close) - Math.random() * price * 0.002;
    result.push({
      timestamp: t.toISOString(),
      open: +open.toFixed(2),
      high: +high.toFixed(2),
      low: +low.toFixed(2),
      close: +close.toFixed(2),
      volume: Math.floor(Math.random() * 1000 + 100),
    });
  }
  return result;
}

/* ─── Formatting ─────────────────────────────────────── */

function fmtNum(n: number, dec = 2): string {
  if (n === 0) return "0.00";
  const abs = Math.abs(n);
  if (abs >= 1_000_000) return (n / 1_000_000).toFixed(dec) + "M";
  if (abs >= 1_000) return (n / 1_000).toFixed(dec) + "K";
  return n.toFixed(dec);
}

function fmtPct(n: number): string {
  return n.toFixed(2) + "%";
}

function fmtRatio(n: number): string {
  return n.toFixed(4);
}

/* ─── Components ─────────────────────────────────────── */

function MetricCard({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color?: string;
}) {
  return (
    <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-4">
      <div className="text-xs text-slate-500 mb-1 uppercase tracking-wider">
        {label}
      </div>
      <div className={`text-lg font-bold font-mono ${color ?? "text-slate-200"}`}>
        {value}
      </div>
    </div>
  );
}

/* ─── Page ──────────────────────────────────────────── */

export default function Backtesting() {
  const [instruments, setInstruments] = useState<Instrument[]>([]);
  const [symbol, setSymbol] = useState("ES");
  const [timeframe, setTimeframe] = useState("5m");
  const [strategy, setStrategy] = useState("trend_following");
  const [startTime, setStartTime] = useState(defaultStart());
  const [endTime, setEndTime] = useState(defaultEnd());
  const [initialBalance, setInitialBalance] = useState(100000);
  const [commission, setCommission] = useState(2.5);
  const [slippage, setSlippage] = useState(1);
  const [barsCount, setBarsCount] = useState(200);

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<ReturnType<typeof createChart> | null>(null);

  /* ─── Load instruments ─────────────────────────────── */

  useEffect(() => {
    getInstruments("CME")
      .then((data: { instruments: Instrument[] }) => {
        const futures = data.instruments.filter((i: Instrument) =>
          ["ES", "NQ", "MNQ"].includes(i.symbol),
        );
        if (futures.length > 0) setInstruments(futures);
        else setInstruments(data.instruments.slice(0, 3));
      })
      .catch(() => {
        // Fallback instruments
        setInstruments([
          { id: 1, symbol: "ES", name: "E-mini S&P 500", exchange: "CME", tick_size: 0.25, tick_value: 12.5, multiplier: 50 },
          { id: 2, symbol: "NQ", name: "E-mini Nasdaq-100", exchange: "CME", tick_size: 0.25, tick_value: 5.0, multiplier: 20 },
          { id: 3, symbol: "MNQ", name: "Micro E-mini Nasdaq-100", exchange: "CME", tick_size: 0.25, tick_value: 0.5, multiplier: 2 },
        ]);
      });
  }, []);

  /* ─── Run backtest ─────────────────────────────────── */

  const handleRun = useCallback(async () => {
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const bars = generateSampleBars(symbol, timeframe, barsCount);
      const res = await runDryBacktest({
        instrument: symbol,
        timeframe,
        start_time: new Date(startTime).toISOString(),
        end_time: new Date(endTime).toISOString(),
        strategy,
        bars_json: JSON.stringify(bars),
        initial_balance: initialBalance,
        commission,
        slippage,
      });
      setResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [symbol, timeframe, strategy, startTime, endTime, initialBalance, commission, slippage, barsCount]);

  /* ─── Equity curve chart ───────────────────────────── */

  useEffect(() => {
    if (!chartRef.current) return;

    // Destroy previous
    if (chartInstance.current) {
      chartInstance.current.remove();
      chartInstance.current = null;
    }

    if (!result || result.equity_curve.length === 0) return;

    const chart = createChart(chartRef.current, {
      width: chartRef.current.clientWidth,
      height: 320,
      layout: {
        background: { type: ColorType.Solid, color: "#0f172a" },
        textColor: "#94a3b8",
      },
      grid: {
        vertLines: { color: "#1e293b" },
        horzLines: { color: "#1e293b" },
      },
      timeScale: {
        borderColor: "#334155",
        timeVisible: true,
      },
      rightPriceScale: {
        borderColor: "#334155",
      },
    });

    const data = result.equity_curve
      .filter((ep) => ep.timestamp)
      .map((ep) => ({
        time: (new Date(ep.timestamp!).getTime() / 1000) as unknown as number,
        value: ep.equity,
      }));

    if (data.length > 0) {
      const lineSeries = chart.addLineSeries({
        color: "#22c55e",
        lineWidth: 2,
        priceFormat: { type: "price", precision: 2, minMove: 0.01 },
      });
      lineSeries.setData(data as any);
      chart.timeScale().fitContent();
    }

    chartInstance.current = chart;

    const handleResize = () => {
      if (chartRef.current && chartInstance.current) {
        chartInstance.current.applyOptions({
          width: chartRef.current.clientWidth,
        });
      }
    };
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, [result]);

  /* ─── Render ───────────────────────────────────────── */

  const m = result?.metrics;

  return (
    <div className="p-6 space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-100">Backtesting</h2>
        <p className="text-sm text-slate-500 mt-1">
          Run strategy simulations over generated sample data.
        </p>
      </div>

      {/* ─── Configuration Panel ──────────────────────── */}
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-6">
        <h3 className="text-lg font-semibold text-slate-200 mb-4">
          Configuration
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Instrument */}
          <div>
            <label className="block text-sm text-slate-400 mb-1">Instrument</label>
            <select
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              className="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-slate-200 text-sm focus:outline-none focus:border-emerald-500"
            >
              {instruments.map((inst) => (
                <option key={inst.symbol} value={inst.symbol}>
                  {inst.symbol} — {inst.name}
                </option>
              ))}
            </select>
          </div>

          {/* Timeframe */}
          <div>
            <label className="block text-sm text-slate-400 mb-1">Timeframe</label>
            <div className="flex gap-1">
              {TIMEFRAMES.map((tf) => (
                <button
                  key={tf}
                  onClick={() => setTimeframe(tf)}
                  className={`px-3 py-2 text-sm rounded ${
                    timeframe === tf
                      ? "bg-emerald-600/30 text-emerald-400 border border-emerald-500/50"
                      : "bg-slate-800 text-slate-400 border border-slate-700 hover:border-slate-600"
                  }`}
                >
                  {tf}
                </button>
              ))}
            </div>
          </div>

          {/* Strategy */}
          <div>
            <label className="block text-sm text-slate-400 mb-1">Strategy</label>
            <select
              value={strategy}
              onChange={(e) => setStrategy(e.target.value)}
              className="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-slate-200 text-sm focus:outline-none focus:border-emerald-500"
            >
              {STRATEGIES.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
          </div>

          {/* Bars count */}
          <div>
            <label className="block text-sm text-slate-400 mb-1">Bars</label>
            <input
              type="number"
              value={barsCount}
              onChange={(e) => setBarsCount(+e.target.value)}
              min={30}
              max={1000}
              className="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-slate-200 text-sm focus:outline-none focus:border-emerald-500"
            />
          </div>

          {/* Start */}
          <div>
            <label className="block text-sm text-slate-400 mb-1">Start</label>
            <input
              type="datetime-local"
              value={startTime}
              onChange={(e) => setStartTime(e.target.value)}
              className="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-slate-200 text-sm focus:outline-none focus:border-emerald-500"
            />
          </div>

          {/* End */}
          <div>
            <label className="block text-sm text-slate-400 mb-1">End</label>
            <input
              type="datetime-local"
              value={endTime}
              onChange={(e) => setEndTime(e.target.value)}
              className="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-slate-200 text-sm focus:outline-none focus:border-emerald-500"
            />
          </div>

          {/* Initial Balance */}
          <div>
            <label className="block text-sm text-slate-400 mb-1">
              Initial Balance ($)
            </label>
            <input
              type="number"
              value={initialBalance}
              onChange={(e) => setInitialBalance(+e.target.value)}
              min={1000}
              step={10000}
              className="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-slate-200 text-sm focus:outline-none focus:border-emerald-500"
            />
          </div>

          {/* Commission */}
          <div>
            <label className="block text-sm text-slate-400 mb-1">
              Commission ($/contract)
            </label>
            <input
              type="number"
              value={commission}
              onChange={(e) => setCommission(+e.target.value)}
              min={0}
              step={0.25}
              className="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-slate-200 text-sm focus:outline-none focus:border-emerald-500"
            />
          </div>
        </div>

        <button
          onClick={handleRun}
          disabled={loading}
          className="mt-4 px-6 py-2.5 bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-700 disabled:text-slate-500 text-white font-medium rounded-lg transition-colors flex items-center gap-2"
        >
          {loading && (
            <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
              <circle
                className="opacity-25"
                cx="12" cy="12" r="10"
                stroke="currentColor" strokeWidth="4" fill="none"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
              />
            </svg>
          )}
          {loading ? "Running..." : "Run Backtest"}
        </button>
      </div>

      {/* ─── Error ────────────────────────────────────── */}
      {error && (
        <div className="bg-red-900/30 border border-red-800 rounded-lg p-4">
          <p className="text-red-400 font-medium">{error}</p>
        </div>
      )}

      {/* ─── Results ──────────────────────────────────── */}
      {result && m && (
        <div className="space-y-6">
          {/* Performance Metrics Grid */}
          <div>
            <h3 className="text-lg font-semibold text-slate-200 mb-3">
              Performance Metrics
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
              <MetricCard
                label="Net Profit"
                value={`$${fmtNum(m.net_profit)}`}
                color={m.net_profit >= 0 ? "text-emerald-400" : "text-red-400"}
              />
              <MetricCard
                label="Win Rate"
                value={fmtPct(m.win_rate * 100)}
                color={
                  m.win_rate >= 0.5 ? "text-emerald-400" : "text-amber-400"
                }
              />
              <MetricCard
                label="Profit Factor"
                value={fmtRatio(m.profit_factor)}
              />
              <MetricCard
                label="Sharpe Ratio"
                value={fmtRatio(m.sharpe_ratio)}
                color={
                  m.sharpe_ratio >= 1
                    ? "text-emerald-400"
                    : m.sharpe_ratio >= 0
                      ? "text-amber-400"
                      : "text-red-400"
                }
              />
              <MetricCard
                label="Sortino Ratio"
                value={m.sortino_ratio === Infinity ? "∞" : fmtRatio(m.sortino_ratio)}
              />
              <MetricCard
                label="Max Drawdown"
                value={`$${fmtNum(m.max_drawdown)}`}
                color="text-red-400"
              />
              <MetricCard
                label="Max DD %"
                value={fmtPct(m.max_drawdown_pct)}
                color="text-red-400"
              />
              <MetricCard label="Expectancy" value={`$${fmtNum(m.expectancy)}`} />
              <MetricCard
                label="Avg Win"
                value={`$${fmtNum(m.average_win)}`}
                color="text-emerald-400"
              />
              <MetricCard
                label="Avg Loss"
                value={`$${fmtNum(m.average_loss)}`}
                color="text-red-400"
              />
              <MetricCard
                label="Annual Return"
                value={fmtPct(m.annual_return_pct)}
              />
              <MetricCard
                label="Recovery Factor"
                value={fmtRatio(m.recovery_factor)}
              />
              <MetricCard
                label="Total Trades"
                value={`${m.total_trades}`}
              />
              <MetricCard
                label="Largest Winner"
                value={`$${fmtNum(m.largest_winner)}`}
                color="text-emerald-400"
              />
              <MetricCard
                label="Largest Loser"
                value={`$${fmtNum(m.largest_loser)}`}
                color="text-red-400"
              />
              <MetricCard
                label="Max Consec Wins"
                value={`${m.max_consecutive_wins}`}
              />
              <MetricCard
                label="Max Consec Losses"
                value={`${m.max_consecutive_losses}`}
              />
              <MetricCard
                label="Avg R"
                value={fmtRatio(m.average_r)}
              />
              <MetricCard
                label="Max DD Duration"
                value={`${m.max_drawdown_duration_days}d`}
              />
              <MetricCard
                label="Long PnL"
                value={`$${fmtNum(m.long_pnl)}`}
              />
              <MetricCard
                label="Short PnL"
                value={`$${fmtNum(m.short_pnl)}`}
              />
            </div>
          </div>

          {/* Monthly Returns Table */}
          {m.monthly_returns.length > 0 && (
            <div>
              <h3 className="text-lg font-semibold text-slate-200 mb-3">
                Monthly Returns
              </h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-700 text-slate-500 text-left">
                      <th className="py-2 px-3 font-medium">Month</th>
                      <th className="py-2 px-3 font-medium text-right">PnL ($)</th>
                      <th className="py-2 px-3 font-medium text-right">Return %</th>
                      <th className="py-2 px-3 font-medium text-right">Trades</th>
                    </tr>
                  </thead>
                  <tbody>
                    {m.monthly_returns.map((mr) => (
                      <tr
                        key={mr.month}
                        className="border-b border-slate-800 hover:bg-slate-800/50"
                      >
                        <td className="py-2 px-3 font-mono text-slate-300">
                          {mr.month}
                        </td>
                        <td
                          className={`py-2 px-3 text-right font-mono ${
                            mr.pnl >= 0 ? "text-emerald-400" : "text-red-400"
                          }`}
                        >
                          ${fmtNum(mr.pnl)}
                        </td>
                        <td
                          className={`py-2 px-3 text-right font-mono ${
                            mr.return_pct >= 0
                              ? "text-emerald-400"
                              : "text-red-400"
                          }`}
                        >
                          {fmtPct(mr.return_pct)}
                        </td>
                        <td className="py-2 px-3 text-right font-mono text-slate-400">
                          {mr.trades}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Equity Curve Chart */}
          {result.equity_curve.length > 0 && (
            <div>
              <h3 className="text-lg font-semibold text-slate-200 mb-3">
                Equity Curve
              </h3>
              <div
                ref={chartRef}
                className="w-full rounded-lg overflow-hidden border border-slate-800"
              />
            </div>
          )}
        </div>
      )}

      {/* ─── Empty State ──────────────────────────────── */}
      {!result && !error && !loading && (
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-12 text-center">
          <p className="text-slate-500 text-lg mb-2">
            No backtest results yet
          </p>
          <p className="text-slate-600 text-sm">
            Configure your strategy and instrument parameters above, then click
            "Run Backtest".
          </p>
        </div>
      )}
    </div>
  );
}
