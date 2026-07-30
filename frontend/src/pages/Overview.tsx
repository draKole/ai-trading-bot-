import { useEffect, useState, useCallback } from "react";
import {
  getHealth,
  type HealthData,
  type ComponentHealth,
} from "../api/health";

/* ─── Helpers ─────────────────────────────────────────── */

function statusColor(status: string): string {
  switch (status) {
    case "healthy":
      return "bg-emerald-500";
    case "degraded":
      return "bg-amber-500";
    case "unhealthy":
      return "bg-red-500";
    default:
      return "bg-slate-500";
  }
}

function statusTextColor(status: string): string {
  switch (status) {
    case "healthy":
      return "text-emerald-400";
    case "degraded":
      return "text-amber-400";
    case "unhealthy":
      return "text-red-400";
    default:
      return "text-slate-400";
  }
}

function statusBorder(status: string): string {
  switch (status) {
    case "healthy":
      return "border-emerald-700";
    case "degraded":
      return "border-amber-700";
    case "unhealthy":
      return "border-red-700";
    default:
      return "border-slate-700";
  }
}

function statusIcon(status: string): string {
  switch (status) {
    case "healthy":
      return "●";
    case "degraded":
      return "◐";
    case "unhealthy":
      return "○";
    default:
      return "?";
  }
}

/* ─── Sub-components ──────────────────────────────────── */

function ComponentHealthGrid({
  components,
}: {
  components: Record<string, ComponentHealth>;
}) {
  const order = [
    "database",
    "redis",
    "workers",
    "broker",
    "market_data",
    "api",
  ];
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
      {order.map((name) => {
        const c = components[name];
        if (!c) return null;
        const color = statusTextColor(c.status);
        return (
          <div
            key={name}
            className={`rounded border ${statusBorder(c.status)} bg-slate-900 p-3 flex items-center gap-3`}
          >
            <span className={`text-xl ${color}`}>{statusIcon(c.status)}</span>
            <div className="min-w-0 flex-1">
              <div className="text-sm font-semibold capitalize text-slate-200">
                {name.replace("_", " ")}
              </div>
              <div className="text-xs text-slate-400 truncate">
                {c.detail}
              </div>
              {c.latency_ms != null && (
                <div className="text-xs text-slate-500">
                  {c.latency_ms.toFixed(1)} ms
                </div>
              )}
            </div>
            <span
              className={`ml-auto text-xs font-medium uppercase ${color}`}
            >
              {c.status}
            </span>
          </div>
        );
      })}
    </div>
  );
}

function SystemMetricsCard({ system }: { system: HealthData["system"] }) {
  return (
    <div className="rounded border border-slate-700 bg-slate-900 p-4">
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-300">
        System Metrics
      </h3>
      <div className="grid grid-cols-3 gap-4">
        <div>
          <div className="text-2xl font-bold text-slate-100">
            {system.cpu_percent}%
          </div>
          <div className="text-xs text-slate-400">CPU</div>
        </div>
        <div>
          <div className="text-2xl font-bold text-slate-100">
            {system.memory_percent}%
          </div>
          <div className="text-xs text-slate-400">
            RAM ({system.memory_used_mb} / {system.memory_total_mb} MB)
          </div>
        </div>
        <div>
          <div className="text-2xl font-bold text-slate-100">
            {system.uptime_human}
          </div>
          <div className="text-xs text-slate-400">Uptime</div>
        </div>
      </div>
    </div>
  );
}

function TradingStatusCard({ trading }: { trading: HealthData["trading"] }) {
  const items = [
    { label: "Active Positions", value: trading.active_positions },
    { label: "Open Orders", value: trading.open_orders },
    { label: "Signals Today", value: trading.signals_today },
    { label: "Trades Today", value: trading.trades_today },
  ];
  return (
    <div className="rounded border border-slate-700 bg-slate-900 p-4">
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-300">
        Trading Status
      </h3>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {items.map(({ label, value }) => (
          <div key={label}>
            <div className="text-2xl font-bold text-slate-100">{value}</div>
            <div className="text-xs text-slate-400">{label}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function OverallStatusCard({
  overall,
  mode,
}: {
  overall: string;
  mode: HealthData["mode"];
}) {
  return (
    <div
      className={`rounded border ${statusBorder(overall)} bg-slate-900 p-4`}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className={`text-2xl ${statusTextColor(overall)}`}>
            {statusIcon(overall)}
          </span>
          <div>
            <div className="text-lg font-bold capitalize text-slate-100">
              System {overall}
            </div>
            <div className="text-xs text-slate-400">
              {new Date().toLocaleTimeString()}
            </div>
          </div>
        </div>
        <span
          className={`rounded-full px-3 py-1 text-xs font-bold uppercase ${
            mode.mode === "LIVE"
              ? "bg-red-900 text-red-300"
              : mode.mode === "PAPER"
                ? "bg-amber-900 text-amber-300"
                : "bg-slate-700 text-slate-300"
          }`}
        >
          {mode.mode}
        </span>
      </div>
    </div>
  );
}

/* ─── Main Overview ────────────────────────────────────── */

export default function Overview() {
  const [data, setData] = useState<HealthData | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [countdown, setCountdown] = useState(15);

  const refresh = useCallback(async () => {
    try {
      const d = await getHealth();
      setData(d);
      setError("");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, []);

  /* Initial fetch + 15-second auto-refresh */
  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 15_000);
    return () => clearInterval(interval);
  }, [refresh]);

  /* Countdown timer */
  useEffect(() => {
    const timer = setInterval(() => {
      setCountdown((prev) => (prev <= 1 ? 15 : prev - 1));
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  /* ── Loading state ──────────────────────────────── */
  if (loading && !data) {
    return (
      <div className="flex h-64 items-center justify-center p-6">
        <div className="flex flex-col items-center gap-3">
          <svg
            className="h-8 w-8 animate-spin text-slate-400"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
            />
          </svg>
          <span className="text-sm text-slate-400">
            Loading system status…
          </span>
        </div>
      </div>
    );
  }

  /* ── Error state ────────────────────────────────── */
  if (error && !data) {
    return (
      <div className="p-6">
        <div className="rounded border border-red-700 bg-red-950 p-6 text-center">
          <div className="mb-2 text-3xl">⚠</div>
          <div className="text-lg font-semibold text-red-300">
            Connection Error
          </div>
          <div className="mt-1 text-sm text-red-400">{error}</div>
          <button
            onClick={() => {
              setLoading(true);
              setError("");
              refresh();
            }}
            className="mt-4 rounded bg-red-800 px-4 py-2 text-sm text-red-100 hover:bg-red-700"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  /* ── Data state ─────────────────────────────────── */
  const overall = data?.health?.overall ?? "unknown";

  return (
    <div className="space-y-5 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-100">Overview</h2>
          <p className="text-sm text-slate-400">
            Auto-refreshes in {countdown}s
          </p>
        </div>
        <button
          onClick={() => {
            setLoading(true);
            refresh().finally(() => setLoading(false));
          }}
          disabled={loading}
          className="rounded bg-slate-700 px-3 py-1.5 text-sm text-slate-200 hover:bg-slate-600 disabled:opacity-50"
        >
          {loading ? "Refreshing…" : "Refresh Now"}
        </button>
      </div>

      {/* Error banner (non-fatal) */}
      {error && data && (
        <div className="rounded border border-amber-700 bg-amber-950 px-4 py-2 text-sm text-amber-300">
          Last refresh failed: {error} — showing cached data
        </div>
      )}

      {/* Overall Status */}
      <OverallStatusCard
        overall={overall}
        mode={data?.mode ?? { mode: "PAPER", live_allowed: false, uptime_seconds: 0 }}
      />

      {/* Component Health Grid */}
      <div>
        <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-300">
          Component Health
        </h3>
        <ComponentHealthGrid
          components={data?.health?.components ?? {}}
        />
      </div>

      {/* Metrics + Trading row */}
      <div className="grid gap-5 md:grid-cols-2">
        {data?.system && <SystemMetricsCard system={data.system} />}
        {data?.trading && <TradingStatusCard trading={data.trading} />}
      </div>

      {/* Timestamp */}
      {data?.timestamp && (
        <div className="text-right text-xs text-slate-500">
          Last updated: {new Date(data.timestamp).toLocaleString()}
        </div>
      )}
    </div>
  );
}
