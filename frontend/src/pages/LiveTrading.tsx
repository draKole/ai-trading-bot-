import { useEffect, useState, useCallback } from "react";
import {
  getMode,
  switchMode,
  killSwitch,
  canTrade,
  getRiskControls,
  type ModeState,
  type RiskControlsState,
} from "../api/live-trading";
import { NoticeBanner, RefreshButton, TerminalPageHeader, TerminalState } from "../components/TerminalUI";

/* ─── ModePanel ───────────────────────────────────────── */

function ModePanel({
  mode,
  onSwitch,
  onKill,
  loading,
}: {
  mode: ModeState | null;
  onSwitch: (target: string) => void;
  onKill: () => void;
  loading: boolean;
}) {
  const isLive = mode?.is_live ?? false;
  const isKilled = mode?.is_killed ?? false;
  const currentMode = mode?.mode ?? "unknown";

  return (
    <div className="rounded-lg border border-slate-700 bg-slate-900 p-5">
      <h3 className="text-lg font-bold text-slate-100 mb-4">Trading Mode</h3>

      {/* Current mode display */}
      <div className="grid grid-cols-2 gap-4 mb-4">
        <div
          className={`rounded-lg border p-4 text-center transition-all ${
            !isLive && !isKilled
              ? "border-amber-500 bg-amber-900/20"
              : "border-slate-700 bg-slate-800/50"
          }`}
        >
          <div className="text-3xl mb-1">📝</div>
          <div className={`text-sm font-bold ${!isLive && !isKilled ? "text-amber-400" : "text-slate-500"}`}>
            PAPER
          </div>
          <div className="text-xs text-slate-500 mt-1">Simulated trading</div>
        </div>
        <div
          className={`rounded-lg border p-4 text-center transition-all ${
            isLive && !isKilled
              ? "border-red-500 bg-red-900/20"
              : "border-slate-700 bg-slate-800/50"
          }`}
        >
          <div className="text-3xl mb-1">🔴</div>
          <div className={`text-sm font-bold ${isLive && !isKilled ? "text-red-400" : "text-slate-500"}`}>
            LIVE
          </div>
          <div className="text-xs text-slate-500 mt-1">Real broker orders</div>
        </div>
      </div>

      {/* Kill switch status */}
      {isKilled && (
        <div className="rounded border-2 border-red-700 bg-red-950 p-4 mb-4 text-center">
          <div className="text-2xl mb-1">☠️</div>
          <div className="text-lg font-bold text-red-400">KILL SWITCH ACTIVE</div>
          <div className="text-sm text-red-300 mt-1">
            All trading halted for this session. Reload to restore.
          </div>
        </div>
      )}

      {/* Action buttons */}
      {!isKilled && (
        <div className="flex gap-3">
          <button
            onClick={() => onSwitch(isLive ? "paper" : "live")}
            disabled={loading}
            className={`flex-1 rounded-lg px-4 py-3 text-sm font-bold transition-colors disabled:opacity-40 ${
              isLive
                ? "bg-amber-700 text-amber-100 hover:bg-amber-600"
                : "bg-red-700 text-red-100 hover:bg-red-600"
            }`}
          >
            {isLive ? "🟡 Switch to PAPER" : "🔴 Switch to LIVE"}
          </button>
          <button
            onClick={onKill}
            disabled={loading}
            className="rounded-lg bg-red-900 border border-red-700 px-4 py-3 text-sm font-bold text-red-300 hover:bg-red-800 transition-colors disabled:opacity-40"
          >
            ⚠ KILL
          </button>
        </div>
      )}

      {/* Config info */}
      {mode && (
        <div className="mt-4 pt-3 border-t border-slate-700 grid grid-cols-2 gap-2 text-xs text-slate-400">
          <div>
            Configured:{" "}
            <span className="text-slate-300">
              {new Date(mode.configured_at).toLocaleString()}
            </span>
          </div>
          {mode.last_switched_at && (
            <div>
              Last switch:{" "}
              <span className="text-slate-300">
                {new Date(mode.last_switched_at).toLocaleString()}
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* ─── BrokerStatusCard ────────────────────────────────── */

function BrokerStatusCard() {
  const [status, setStatus] = useState<string>("unknown");
  const [detail, setDetail] = useState("Not connected");
  const [loading, setLoading] = useState(true);

  const checkBroker = useCallback(async () => {
    try {
      const res = await fetch("/api/v1/monitoring/health/broker");
      const data = await res.json();
      setStatus(data.status ?? "unknown");
      setDetail(data.detail ?? "");
    } catch {
      setStatus("unhealthy");
      setDetail("Cannot reach broker endpoint");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    checkBroker();
    const interval = setInterval(checkBroker, 10_000);
    return () => clearInterval(interval);
  }, [checkBroker]);

  return (
    <div className="rounded-lg border border-slate-700 bg-slate-900 p-5">
      <h3 className="text-lg font-bold text-slate-100 mb-3">Broker Connection</h3>
      <div className="flex items-center gap-3">
        <span
          className={`inline-block h-3 w-3 rounded-full ${
            status === "healthy"
              ? "bg-emerald-500"
              : status === "degraded"
                ? "bg-amber-500"
                : "bg-red-500"
          }`}
        />
        <div>
          <div className="font-bold text-slate-200 capitalize">
            {loading ? "Checking…" : status}
          </div>
          <div className="text-xs text-slate-400">{loading ? "..." : detail}</div>
        </div>
      </div>
    </div>
  );
}

/* ─── TradingPermissionCard ───────────────────────────── */

function TradingPermissionCard() {
  const [allowed, setAllowed] = useState<boolean>(true);
  const [reason, setReason] = useState("No restrictions");
  const [loading, setLoading] = useState(true);

  const check = useCallback(async () => {
    try {
      const result = await canTrade();
      setAllowed(result.allowed);
      setReason(result.reason);
    } catch {
      setAllowed(false);
      setReason("Cannot reach mode endpoint");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    check();
    const interval = setInterval(check, 5_000);
    return () => clearInterval(interval);
  }, [check]);

  return (
    <div
      className={`rounded-lg border p-5 ${
        allowed ? "border-emerald-700 bg-emerald-950/30" : "border-red-700 bg-red-950/30"
      }`}
    >
      <div className="flex items-center gap-3">
        <span className="text-2xl">{allowed ? "✅" : "🚫"}</span>
        <div>
          <div className={`font-bold ${allowed ? "text-emerald-400" : "text-red-400"}`}>
            {loading ? "Checking…" : allowed ? "Trading Allowed" : "Trading Blocked"}
          </div>
          <div className="text-xs text-slate-400">{loading ? "..." : reason}</div>
        </div>
      </div>
    </div>
  );
}

/* ─── Risk Summary Card ───────────────────────────────── */

function RiskSummaryCard() {
  const [data, setData] = useState<RiskControlsState | null>(null);

  useEffect(() => {
    getRiskControls().then(setData).catch(() => {});
    const interval = setInterval(() => {
      getRiskControls().then(setData).catch(() => {});
    }, 5_000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="rounded-lg border border-slate-700 bg-slate-900 p-5">
      <h3 className="text-lg font-bold text-slate-100 mb-3">Risk Controls Status</h3>
      {!data ? (
        <div className="text-sm text-slate-400">Loading…</div>
      ) : (
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div className="flex justify-between">
            <span className="text-slate-400">Execution Kill Switch</span>
            <span className={data.is_killed ? "text-red-400 font-bold" : "text-emerald-400"}>
              {data.is_killed ? "ACTIVE" : "Inactive"}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-400">Circuit Breaker</span>
            <span className={data.circuit_breaker.triggered ? "text-red-400 font-bold" : "text-emerald-400"}>
              {data.circuit_breaker.triggered ? "TRIGGERED" : "OK"}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-400">Daily Loss</span>
            <span className={data.daily_loss.exceeded ? "text-red-400 font-bold" : "text-emerald-400"}>
              ${data.daily_loss.current_loss.toLocaleString()} / ${data.daily_loss.limit.toLocaleString()}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-400">CB Losses</span>
            <span className={data.circuit_breaker.triggered ? "text-red-400" : "text-slate-300"}>
              {data.circuit_breaker.consecutive_losses} / {data.circuit_breaker.max_consecutive}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

/* ─── Confirmation Dialog ─────────────────────────────── */

function ConfirmDialog({
  target,
  onConfirm,
  onCancel,
  loading,
  error,
}: {
  target: string;
  onConfirm: () => void;
  onCancel: () => void;
  loading: boolean;
  error: string;
}) {
  const isLive = target === "live";
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="bg-slate-800 border border-slate-700 rounded-lg p-6 max-w-sm w-full mx-4 shadow-2xl">
        <h3 className="text-lg font-semibold text-slate-100 mb-2">
          {isLive ? "🔴 Switch to LIVE Trading" : "🟡 Switch to PAPER Trading"}
        </h3>
        <p className="text-sm text-slate-400 mb-4">
          {isLive
            ? "This will enable LIVE broker connectivity. Real orders will be sent to the market. Ensure risk controls are configured before proceeding."
            : "This will disable live broker connectivity. All orders will be simulated. Safe mode."}
        </p>
        {error && (
          <div className="mb-4 rounded border border-red-700 bg-red-950 px-3 py-2 text-xs text-red-400">
            {error}
          </div>
        )}
        <div className="flex gap-3">
          <button
            onClick={onConfirm}
            disabled={loading}
            className={`flex-1 rounded px-4 py-2 text-sm font-medium transition-colors disabled:opacity-50 ${
              isLive
                ? "bg-red-700 text-red-100 hover:bg-red-600"
                : "bg-amber-700 text-amber-100 hover:bg-amber-600"
            }`}
          >
            {loading ? "Switching…" : `Confirm ${isLive ? "LIVE" : "PAPER"}`}
          </button>
          <button
            onClick={onCancel}
            disabled={loading}
            className="flex-1 rounded border border-slate-600 px-4 py-2 text-sm text-slate-300 hover:bg-slate-700 transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

/* ─── Main LiveTrading ────────────────────────────────── */

export default function LiveTrading() {
  const [mode, setMode] = useState<ModeState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionLoading, setActionLoading] = useState(false);
  const [confirmTarget, setConfirmTarget] = useState<string | null>(null);

  const fetchMode = useCallback(async () => {
    try {
      const m = await getMode();
      setMode(m);
      setError("");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to fetch mode");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchMode();
    const interval = setInterval(fetchMode, 5_000);
    return () => clearInterval(interval);
  }, [fetchMode]);

  async function handleSwitch(target: string) {
    setConfirmTarget(target);
  }

  async function handleConfirmSwitch() {
    if (!confirmTarget) return;
    setActionLoading(true);
    setError("");
    try {
      await switchMode(confirmTarget, true);
      await fetchMode();
      setConfirmTarget(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Switch failed");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleKill() {
    if (!window.confirm("⚠️ ACTIVATE GLOBAL KILL SWITCH?\n\nThis will halt ALL trading for this session. This action is IRREVERSIBLE.\n\nAre you sure?"))
      return;
    setActionLoading(true);
    setError("");
    try {
      await killSwitch();
      await fetchMode();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Kill switch failed");
    } finally {
      setActionLoading(false);
    }
  }

  if (loading && !mode) {
    return <TerminalState kind="loading" title="Loading execution controls" detail="Verifying the current trading mode and safety status." />;
  }

  if (error && !mode) {
    return <TerminalState kind="error" title="Execution controls unavailable" detail={error} onRetry={() => { setLoading(true); fetchMode(); }} />;
  }

  return (
    <div className="space-y-5">
      <TerminalPageHeader
        eyebrow="Execution controls"
        title="Live Trading"
        description="Config-driven PAPER/LIVE mode switching with enforced safety controls."
        actions={<RefreshButton loading={loading} onClick={() => { setLoading(true); fetchMode().finally(() => setLoading(false)); }} />}
      />

      {error && <NoticeBanner tone="error">{error}</NoticeBanner>}

      {/* Mode Panel */}
      <ModePanel
        mode={mode}
        onSwitch={handleSwitch}
        onKill={handleKill}
        loading={actionLoading}
      />

      {/* Broker + Permission + Risk row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <BrokerStatusCard />
        <TradingPermissionCard />
        <RiskSummaryCard />
      </div>

      {/* Confirmation Dialog */}
      {confirmTarget && (
        <ConfirmDialog
          target={confirmTarget}
          onConfirm={handleConfirmSwitch}
          onCancel={() => { setConfirmTarget(null); setError(""); }}
          loading={actionLoading}
          error={error}
        />
      )}
    </div>
  );
}
