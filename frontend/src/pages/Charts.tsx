import { useEffect, useState, useRef, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import { createChart, type IChartApi, type ISeriesApi, ColorType } from "lightweight-charts";
import {
  getInstruments,
  getBars,
  type Instrument,
  type BarData,
} from "../api/market-data";

/* ─── Constants ──────────────────────────────────────── */

const TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h", "1d"];
const SESSIONS = [
  { value: "all", label: "All" },
  { value: "RTH", label: "RTH" },
  { value: "ETH", label: "ETH" },
];

/* ─── Helpers ────────────────────────────────────────── */

function formatBarCount(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
}

function isoDate(d: Date): string {
  return d.toISOString().slice(0, 10);
}

/* ─── Sub-components ─────────────────────────────────── */

function TimeframeSelector({
  value,
  onChange,
}: {
  value: string;
  onChange: (tf: string) => void;
}) {
  return (
    <div className="flex gap-1 rounded bg-slate-800 p-1">
      {TIMEFRAMES.map((tf) => (
        <button
          key={tf}
          onClick={() => onChange(tf)}
          className={`rounded px-3 py-1 text-xs font-medium transition-colors ${
            tf === value
              ? "bg-green-600 text-white"
              : "text-slate-400 hover:bg-slate-700 hover:text-slate-200"
          }`}
        >
          {tf}
        </button>
      ))}
    </div>
  );
}

/* ─── Main Charts Page ───────────────────────────────── */

export default function Charts() {
  const [searchParams, setSearchParams] = useSearchParams();

  const [instruments, setInstruments] = useState<Instrument[]>([]);
  const [symbol, setSymbol] = useState(searchParams.get("symbol") || "ES");
  const [timeframe, setTimeframe] = useState("5m");
  const [session, setSession] = useState("all");
  const [startDate, setStartDate] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() - 7);
    return isoDate(d);
  });
  const [endDate, setEndDate] = useState(() => isoDate(new Date()));

  const [bars, setBars] = useState<BarData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const chartRef = useRef<HTMLDivElement>(null);
  const chartApiRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const vwapSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);

  /* ── Fetch instruments ───────────────────────────── */
  useEffect(() => {
    getInstruments()
      .then((res) => setInstruments(res.instruments))
      .catch(() => {});
  }, []);

  /* ── Sync URL param on symbol change ─────────────── */
  useEffect(() => {
    setSearchParams({ symbol }, { replace: true });
  }, [symbol, setSearchParams]);

  /* ── Fetch bars ──────────────────────────────────── */
  const fetchBars = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const start = startDate ? `${startDate}T00:00:00` : undefined;
      const end = endDate ? `${endDate}T23:59:59` : undefined;
      const res = await getBars(symbol, timeframe, start, end, session);
      setBars(res.bars);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [symbol, timeframe, session, startDate, endDate]);

  useEffect(() => {
    fetchBars();
  }, [fetchBars]);

  /* ── Chart ───────────────────────────────────────── */
  useEffect(() => {
    if (!chartRef.current || bars.length === 0) return;

    /* Clean up previous chart */
    if (chartApiRef.current) {
      chartApiRef.current.remove();
      chartApiRef.current = null;
    }

    const chart = createChart(chartRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "#0f172a" },
        textColor: "#94a3b8",
      },
      grid: {
        vertLines: { color: "#1e293b" },
        horzLines: { color: "#1e293b" },
      },
      crosshair: {
        vertLine: { color: "#475569", labelBackgroundColor: "#334155" },
        horzLine: { color: "#475569", labelBackgroundColor: "#334155" },
      },
      timeScale: {
        borderColor: "#334155",
        timeVisible: true,
      },
      rightPriceScale: {
        borderColor: "#334155",
      },
    });

    chartApiRef.current = chart;

    /* Candlestick */
    const candleSeries = chart.addCandlestickSeries({
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderUpColor: "#22c55e",
      borderDownColor: "#ef4444",
      wickUpColor: "#22c55e",
      wickDownColor: "#ef4444",
    });
    candleSeriesRef.current = candleSeries;

    /* Volume */
    const volumeSeries = chart.addHistogramSeries({
      color: "#475569",
      priceFormat: { type: "volume" },
      priceScaleId: "volume",
    });
    volumeSeriesRef.current = volumeSeries;

    chart.priceScale("volume").applyOptions({
      scaleMargins: { top: 0.82, bottom: 0 },
    });

    /* VWAP overlay */
    const vwapSeries = chart.addLineSeries({
      color: "#f59e0b",
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    vwapSeriesRef.current = vwapSeries;

    /* Set data */
    const candleData = bars.map((b) => ({
      time: (new Date(b.timestamp).getTime() / 1000) as import("lightweight-charts").UTCTimestamp,
      open: b.open,
      high: b.high,
      low: b.low,
      close: b.close,
    }));
    candleSeries.setData(candleData);

    const volData = bars.map((b) => ({
      time: (new Date(b.timestamp).getTime() / 1000) as import("lightweight-charts").UTCTimestamp,
      value: b.volume,
      color: b.close >= b.open ? "rgba(34,197,94,0.3)" : "rgba(239,68,68,0.3)",
    }));
    volumeSeries.setData(volData);

    const vwapData = bars
      .filter((b) => b.vwap > 0)
      .map((b) => ({
        time: (new Date(b.timestamp).getTime() / 1000) as import("lightweight-charts").UTCTimestamp,
        value: b.vwap,
      }));
    if (vwapData.length > 0) {
      vwapSeries.setData(vwapData);
    }

    chart.timeScale().fitContent();

    return () => {
      chart.remove();
      chartApiRef.current = null;
    };
  }, [bars]);

  /* ── Bar info ────────────────────────────────────── */
  const firstBar = bars[0];
  const lastBar = bars[bars.length - 1];
  const dateRange =
    firstBar && lastBar
      ? `${new Date(firstBar.timestamp).toLocaleDateString()} — ${new Date(lastBar.timestamp).toLocaleDateString()}`
      : null;

  return (
    <div className="flex h-full flex-col">
      {/* Controls */}
      <div className="flex flex-wrap items-center gap-4 border-b border-slate-800 p-4">
        {/* Symbol */}
        <div>
          <label className="mb-1 block text-xs font-medium text-slate-400">Symbol</label>
          <select
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            className="rounded border border-slate-700 bg-slate-800 px-3 py-1.5 text-sm text-slate-100 focus:border-green-500 focus:outline-none"
          >
            {instruments.map((i) => (
              <option key={i.symbol} value={i.symbol}>
                {i.symbol} — {i.name}
              </option>
            ))}
          </select>
        </div>

        {/* Timeframe */}
        <div>
          <label className="mb-1 block text-xs font-medium text-slate-400">Timeframe</label>
          <TimeframeSelector value={timeframe} onChange={setTimeframe} />
        </div>

        {/* Session */}
        <div>
          <label className="mb-1 block text-xs font-medium text-slate-400">Session</label>
          <div className="flex gap-1 rounded bg-slate-800 p-1">
            {SESSIONS.map((s) => (
              <button
                key={s.value}
                onClick={() => setSession(s.value)}
                className={`rounded px-3 py-1 text-xs font-medium transition-colors ${
                  session === s.value
                    ? "bg-green-600 text-white"
                    : "text-slate-400 hover:bg-slate-700 hover:text-slate-200"
                }`}
              >
                {s.label}
              </button>
            ))}
          </div>
        </div>

        {/* Date Range */}
        <div className="flex items-end gap-2">
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-400">Start</label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="rounded border border-slate-700 bg-slate-800 px-2 py-1.5 text-xs text-slate-100"
            />
          </div>
          <span className="pb-1.5 text-slate-500">—</span>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-400">End</label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="rounded border border-slate-700 bg-slate-800 px-2 py-1.5 text-xs text-slate-100"
            />
          </div>
        </div>
      </div>

      {/* Chart area */}
      <div className="relative flex-1">
        {/* Loading */}
        {loading && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-slate-950/80">
            <div className="flex flex-col items-center gap-3">
              <svg className="h-8 w-8 animate-spin text-slate-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              <span className="text-sm text-slate-400">Loading {symbol} {timeframe}…</span>
            </div>
          </div>
        )}

        {/* Error */}
        {error && !loading && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-slate-950/90">
            <div className="rounded border border-red-700 bg-red-950 p-6 text-center">
              <div className="mb-2 text-3xl">⚠</div>
              <div className="text-lg font-semibold text-red-300">Error Loading Data</div>
              <div className="mt-1 text-sm text-red-400">{error}</div>
              <button
                onClick={fetchBars}
                className="mt-4 rounded bg-red-800 px-4 py-2 text-sm text-red-100 hover:bg-red-700"
              >
                Retry
              </button>
            </div>
          </div>
        )}

        {/* Empty */}
        {!loading && !error && bars.length === 0 && (
          <div className="absolute inset-0 z-10 flex items-center justify-center">
            <div className="text-center text-slate-500">
              <div className="mb-2 text-4xl">📊</div>
              <div className="text-lg">No data for {symbol} {timeframe}</div>
              <div className="mt-1 text-sm">Try adjusting the date range or session filter</div>
            </div>
          </div>
        )}

        {/* Chart container */}
        <div ref={chartRef} className="h-full w-full" />
      </div>

      {/* Info bar */}
      {!loading && !error && bars.length > 0 && (
        <div className="flex items-center gap-6 border-t border-slate-800 px-4 py-2 text-xs text-slate-400">
          <span>
            <span className="font-mono text-slate-200">{formatBarCount(bars.length)}</span> bars
          </span>
          <span>
            <span className="text-slate-200">{symbol}</span> {timeframe}
          </span>
          {dateRange && <span>{dateRange}</span>}
          <span>
            Session: <span className="text-slate-200">{session === "all" ? "All" : session}</span>
          </span>
          <span className="ml-auto flex items-center gap-3">
            <span className="flex items-center gap-1">
              <span className="inline-block h-2 w-2 rounded-full bg-amber-500" />
              VWAP overlay
            </span>
          </span>
        </div>
      )}
    </div>
  );
}
