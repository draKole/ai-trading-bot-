import { useEffect, useState, useCallback } from "react";
import {
  getRiskControls,
  activateRiskKillSwitch,
  updateRiskConfig,
  type RiskControlsState,
} from "../api/live-trading";

/* ─── Helpers ─────────────────────────────────────────── */

function statusColor(triggered: boolean): string {
  return triggered ? "text-red-400" : "text-emerald-400";
}

function statusBg(triggered: boolean): string {
  return triggered ? "bg-red-900/40 border-red-700" : "bg-emerald-900/40 border-emerald-700";
}

function statusDot(triggered: boolean): string {
  return triggered ? "bg-red-500" : "bg-emerald-500";
}

/* ─── Sub-components ──────────────────────────────────── */

function KillSwitchPanel({
  isKilled,
  onKill,
  loading,
}: {
  isKilled: boolean;
  onKill: () => void;
  loading: boolean;
}) {
  return (
    <div
      className={`rounded-lg border p-5 ${isKilled ? "border-red-700 bg-red-950/50" : "border-slate-700 bg-slate-900"}`}
    >
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-bold text-slate-100">Execution Kill Switch</h3>
          <p className="text-xs text-slate-400 mt-1">
            {isKilled
              ? "Trading halted — all execution blocked for this session"
              : "Halts all order execution immediately and irreversibly"}
          </p>
        </div>
        <button
          onClick={onKill}
          disabled={loading || isKilled}
          className={`px-4 py-2 rounded-lg text-sm font-bold transition-colors disabled:opacity-40 ${
            isKilled
              ? "bg-slate-700 text-slate-400 cursor-not-allowed"
              : "bg-red-700 text-red-100 hover:bg-red-600 active:bg-red-800"
          }`}
        >
          {isKilled ? "KILLED" : "⚠ ACTIVATE"}
        </button>
      </div>
      {isKilled && (
        <div className="mt-3 rounded border border-red-800 bg-red-950 px-3 py-2 text-xs text-red-400">
          Kill switch is active. All order placement is blocked. Reload the application to restore.
        </div>
      )}
    </div>
  );
}

function CircuitBreakerCard({ cb }: { cb: RiskControlsState["circuit_breaker"] | null | undefined }) {
  const triggered = cb?.triggered ?? false;
  const consecutiveLosses = cb?.consecutive_losses ?? 0;
  const maxConsecutive = cb?.max_consecutive ?? 0;
  const windowSeconds = cb?.window_seconds ?? 0;
  return (
    <div className={`rounded-lg border p-4 ${statusBg(triggered)}`}>
      <div className="flex items-center gap-2 mb-2">
        <span className={`inline-block h-2 w-2 rounded-full ${statusDot(triggered)}`} />
        <h4 className="text-sm font-semibold text-slate-200">Circuit Breaker</h4>
      </div>
      <div className="space-y-1.5 text-sm">
        <div className="flex justify-between">
          <span className="text-slate-400">Consecutive Losses</span>
          <span className={`font-mono font-bold ${statusColor(triggered)}`}>
            {consecutiveLosses} / {maxConsecutive}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-slate-400">Window</span>
          <span className="font-mono text-slate-300">{windowSeconds}s</span>
        </div>
        <div className="flex justify-between">
          <span className="text-slate-400">Status</span>
          <span className={`font-bold uppercase text-xs ${statusColor(triggered)}`}>
            {triggered ? "TRIGGERED" : "OK"}
          </span>
        </div>
      </div>
    </div>
  );
}

function DailyLossCard({ dl }: { dl: RiskControlsState["daily_loss"] | null | undefined }) {
  const exceeded = dl?.exceeded ?? false;
  const currentLoss = dl?.current_loss ?? 0;
  const limit = dl?.limit ?? 0;
  const pct = limit > 0 ? Math.min((currentLoss / limit) * 100, 100) : 0;
  return (
    <div className={`rounded-lg border p-4 ${statusBg(exceeded)}`}>
      <div className="flex items-center gap-2 mb-2">
        <span className={`inline-block h-2 w-2 rounded-full ${statusDot(exceeded)}`} />
        <h4 className="text-sm font-semibold text-slate-200">Daily Loss Limit</h4>
      </div>
      <div className="space-y-2 text-sm">
        <div className="flex justify-between">
          <span className="text-slate-400">Current Loss</span>
          <span className={`font-mono font-bold ${statusColor(exceeded)}`}>
            ${currentLoss.toLocaleString()}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-slate-400">Limit</span>
          <span className="font-mono text-slate-300">
            ${limit.toLocaleString()}
          </span>
        </div>
        {/* Progress bar */}
        <div className="h-1.5 bg-slate-700 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all ${exceeded ? "bg-red-500" : "bg-amber-500"}`}
            style={{ width: `${pct}%` }}
          />
        </div>
        <div className="flex justify-between text-xs">
          <span className="text-slate-500">0%</span>
          <span className={`font-mono ${statusColor(exceeded)}`}>{pct.toFixed(1)}%</span>
          <span className="text-slate-500">100%</span>
        </div>
      </div>
    </div>
  );
}

function PositionLimitsCard({
  limits,
  current,
}: {
  limits: Record<string, number> | null | undefined;
  current: Record<string, number> | null | undefined;
}) {
  const safeLimits = limits ?? {};
  const safeCurrent = current ?? {};
  const instruments = ["ES", "NQ", "MNQ"];
  return (
    <div className="rounded-lg border border-slate-700 bg-slate-900 p-4">
      <h4 className="text-sm font-semibold text-slate-200 mb-3">Max Position Limits</h4>
      <div className="space-y-2">
        {instruments.map((inst) => {
          const limit = safeLimits[inst] ?? 0;
          const cur = safeCurrent[inst] ?? 0;
          const atLimit = limit > 0 && cur >= limit;
          return (
            <div key={inst} className="flex items-center justify-between text-sm">
              <span className="text-slate-400 font-mono w-8">{inst}</span>
              <div className="flex-1 mx-3 h-1.5 bg-slate-700 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full ${atLimit ? "bg-red-500" : "bg-blue-500"}`}
                  style={{ width: limit > 0 ? `${Math.min((cur / limit) * 100, 100)}%` : "0%" }}
                />
              </div>
              <span className={`font-mono text-xs ${atLimit ? "text-red-400" : "text-slate-300"}`}>
                {cur} / {limit}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function ConfigPanel({
  onConfigUpdate,
  loading,
}: {
  onConfigUpdate: (key: string, value: number | boolean) => Promise<void>;
  loading: boolean;
}) {
  const [dailyLossLimit, setDailyLossLimit] = useState("");
  const [cbLosses, setCbLosses] = useState("");
  const [cbWindow, setCbWindow] = useState("");
  const [status, setStatus] = useState("");

  async function handleUpdate(field: string, value: string) {
    const num = parseFloat(value);
    if (isNaN(num) || num < 0) return;
    setStatus(`Updating ${field}…`);
    try {
      await onConfigUpdate(field, ["cb_window", "cb_losses"].includes(field) ? Math.round(num) : num);
      setStatus(`✓ Updated ${field}`);
      setTimeout(() => setStatus(""), 2000);
    } catch (err: unknown) {
      setStatus(`✗ Failed: ${err instanceof Error ? err.message : "Unknown error"}`);
    }
  }

  return (
    <div className="rounded-lg border border-slate-700 bg-slate-900 p-4">
      <h4 className="text-sm font-semibold text-slate-200 mb-3">Runtime Config</h4>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div>
          <label className="text-xs text-slate-400 block mb-1">Daily Loss Limit ($)</label>
          <div className="flex gap-2">
            <input
              type="number"
              min="0"
              step="100"
              value={dailyLossLimit}
              onChange={(e) => setDailyLossLimit(e.target.value)}
              placeholder="e.g. 5000"
              className="flex-1 rounded bg-slate-800 border border-slate-600 px-2 py-1 text-sm text-slate-200 placeholder-slate-600"
            />
            <button
              onClick={() => handleUpdate("daily_loss_limit", dailyLossLimit)}
              disabled={loading || !dailyLossLimit}
              className="rounded bg-blue-700 px-2 py-1 text-xs text-blue-100 hover:bg-blue-600 disabled:opacity-40"
            >
              Set
            </button>
          </div>
        </div>
        <div>
          <label className="text-xs text-slate-400 block mb-1">CB Max Losses</label>
          <div className="flex gap-2">
            <input
              type="number"
              min="1"
              step="1"
              value={cbLosses}
              onChange={(e) => setCbLosses(e.target.value)}
              placeholder="e.g. 3"
              className="flex-1 rounded bg-slate-800 border border-slate-600 px-2 py-1 text-sm text-slate-200 placeholder-slate-600"
            />
            <button
              onClick={() => handleUpdate("cb_losses", cbLosses)}
              disabled={loading || !cbLosses}
              className="rounded bg-blue-700 px-2 py-1 text-xs text-blue-100 hover:bg-blue-600 disabled:opacity-40"
            >
              Set
            </button>
          </div>
        </div>
        <div>
          <label className="text-xs text-slate-400 block mb-1">CB Window (s)</label>
          <div className="flex gap-2">
            <input
              type="number"
              min="10"
              step="10"
              value={cbWindow}
              onChange={(e) => setCbWindow(e.target.value)}
              placeholder="e.g. 300"
              className="flex-1 rounded bg-slate-800 border border-slate-600 px-2 py-1 text-sm text-slate-200 placeholder-slate-600"
            />
            <button
              onClick={() => handleUpdate("cb_window", cbWindow)}
              disabled={loading || !cbWindow}
              className="rounded bg-blue-700 px-2 py-1 text-xs text-blue-100 hover:bg-blue-600 disabled:opacity-40"
            >
              Set
            </button>
          </div>
        </div>
      </div>
      {status && (
        <div className={`mt-2 text-xs ${status.startsWith("✓") ? "text-emerald-400" : status.startsWith("✗") ? "text-red-400" : "text-slate-400"}`}>
          {status}
        </div>
      )}
    </div>
  );
}

/* ─── Main Risk Center ────────────────────────────────── */

export default function RiskCenter() {
  const [data, setData] = useState<RiskControlsState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionLoading, setActionLoading] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const d = await getRiskControls();
      setData(d);
      setError("");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load risk controls");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 5_000);
    return () => clearInterval(interval);
  }, [refresh]);

  async function handleKill() {
    if (!window.confirm("⚠️ ACTIVATE EXECUTION KILL SWITCH?\n\nThis will halt ALL order execution for this session.\nThis action is IRREVERSIBLE.\n\nAre you sure?"))
      return;
    setActionLoading(true);
    try {
      await activateRiskKillSwitch();
      await refresh();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Kill switch activation failed");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleConfigUpdate(key: string, value: number | boolean) {
    const updates: Record<string, number | boolean> = {};
    if (key === "daily_loss_limit") updates.daily_loss_limit = value as number;
    if (key === "cb_losses") updates.circuit_breaker_consecutive_losses = value as number;
    if (key === "cb_window") updates.circuit_breaker_window_seconds = value as number;
    await updateRiskConfig(updates);
    await refresh();
  }

  if (loading && !data) {
    return (
      <div className="flex h-64 items-center justify-center">
        <span className="text-sm text-slate-400">Loading risk controls…</span>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="p-6">
        <div className="rounded border border-red-700 bg-red-950 p-6 text-center">
          <div className="text-lg font-semibold text-red-300">Connection Error</div>
          <div className="mt-1 text-sm text-red-400">{error}</div>
          <button
            onClick={() => { setLoading(true); refresh(); }}
            className="mt-4 rounded bg-red-800 px-4 py-2 text-sm text-red-100 hover:bg-red-700"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-5 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-100">Risk Center</h2>
          <p className="text-sm text-slate-400">
            Execution kill switch, circuit breaker, daily loss limit, position limits
          </p>
        </div>
        <button
          onClick={() => { setLoading(true); refresh().finally(() => setLoading(false)); }}
          disabled={loading}
          className="rounded bg-slate-700 px-3 py-1.5 text-sm text-slate-200 hover:bg-slate-600 disabled:opacity-50"
        >
          {loading ? "Refreshing…" : "Refresh"}
        </button>
      </div>

      {error && data && (
        <div className="rounded border border-amber-700 bg-amber-950 px-4 py-2 text-sm text-amber-300">
          Last refresh failed: {error} — showing cached data
        </div>
      )}

      {/* Kill Switch */}
      <KillSwitchPanel
        isKilled={data?.is_killed ?? false}
        onKill={handleKill}
        loading={actionLoading}
      />

      {/* Circuit Breaker + Daily Loss side by side */}
      {data && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <CircuitBreakerCard cb={data.circuit_breaker} />
          <DailyLossCard dl={data.daily_loss} />
        </div>
      )}

      {/* Position Limits */}
      {data && (
        <PositionLimitsCard
          limits={data.max_position_size}
          current={data.positions_current}
        />
      )}

      {/* Runtime Config */}
      <ConfigPanel onConfigUpdate={handleConfigUpdate} loading={actionLoading} />

      {/* Enabled toggles summary */}
      <div className="rounded-lg border border-slate-700 bg-slate-900 p-4">
        <h4 className="text-sm font-semibold text-slate-200 mb-2">Enabled Controls</h4>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
          {[
            { label: "Kill Switch", val: data?.kill_switch_enabled ?? false },
            { label: "Circuit Breaker", val: data?.circuit_breaker_enabled ?? false },
            { label: "Daily Loss Limit", val: data?.daily_loss_limit_enabled ?? false },
            { label: "Max Position", val: data?.max_position_enabled ?? false },
          ].map(({ label, val }) => (
              <div key={label} className="flex items-center gap-2">
                <span
                  className={`inline-block h-2 w-2 rounded-full ${val ? "bg-emerald-500" : "bg-slate-600"}`}
                />
                <span className={val ? "text-slate-200" : "text-slate-500"}>
                  {label}
                </span>
              </div>
            ))}
          </div>
        </div>
    </div>
  );
}
