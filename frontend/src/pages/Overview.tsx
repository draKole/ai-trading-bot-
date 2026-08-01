import { useEffect, useState, useCallback } from "react";
import {
  getHealth,
  type HealthData,
  type ComponentHealth,
} from "../api/health";
import { NoticeBanner, RefreshButton, TerminalPageHeader, TerminalState } from "../components/TerminalUI";

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

function MarketDataStatusCard({ component }: { component?: ComponentHealth }) {
  const metadata = component?.metadata;
  if (!component) return null;
  const instruments = metadata?.instruments ?? {};
  return (
    <div className={`rounded border ${statusBorder(component.status)} bg-slate-900 p-4`} data-testid="market-data-status">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-300">Market Data</h3>
        <span className={`text-xs font-bold uppercase ${statusTextColor(component.status)}`}>{component.status}</span>
      </div>
      <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-slate-400">
        <span>Provider: <b className="text-slate-200">{metadata?.provider ?? "unavailable"}</b></span>
        <span>Provider status: <b className="text-slate-200">{metadata?.provider_status ?? "unknown"}</b></span>
        <span>ES/MES/NQ/MNQ: <b className="text-slate-200">{Object.keys(instruments).filter((s) => (instruments[s] ?? 0) > 0).length}/4</b></span>
        <span>Last update: <b className="text-slate-200">{metadata?.last_successful_update ? new Date(metadata.last_successful_update).toLocaleString() : "none"}</b></span>
      </div>
      <div className="mt-2 text-xs text-slate-500">{component.latency_ms?.toFixed(1) ?? "—"} ms · {component.detail}</div>
    </div>
  );
}

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
    return <TerminalState kind="loading" title="Loading system status" detail="Checking platform health and execution services." />;
  }

  /* ── Error state ────────────────────────────────── */
  if (error && !data) {
    return (
      <TerminalState
        kind="error"
        title="System status unavailable"
        detail={error}
        onRetry={() => { setLoading(true); setError(""); refresh(); }}
      />
    );
  }

  /* ── Data state ─────────────────────────────────── */
  const overall = data?.health?.overall ?? "unknown";

  return (
    <div className="space-y-5">
      <TerminalPageHeader
        eyebrow="System operations"
        title="Overview"
        description={`Platform health and execution status · refreshes in ${countdown}s`}
        actions={<RefreshButton loading={loading} label="Refresh now" onClick={() => { setLoading(true); refresh().finally(() => setLoading(false)); }} />}
      />

      {/* Error banner (non-fatal) */}
      {error && data && (
        <NoticeBanner>Last refresh failed: {error} — showing cached data.</NoticeBanner>
      )}

      {/* Overall Status */}
      <OverallStatusCard
        overall={overall}
        mode={data?.mode ?? { mode: "PAPER", live_allowed: false, uptime_seconds: 0 }}
      />

      {/* Market data provider and historical bars */}
      <MarketDataStatusCard component={data?.health?.components?.market_data} />

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
