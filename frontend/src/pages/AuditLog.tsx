import { useEffect, useState, useCallback } from "react";
import {
  getAuditLogs,
  type AuditLogEntry,
  type AuditLogResponse,
} from "../api/live-trading";
import { NoticeBanner, RefreshButton, TerminalPageHeader, TerminalState } from "../components/TerminalUI";

/* ─── Helpers ─────────────────────────────────────────── */

function eventBadge(eventType: string): { bg: string; text: string; label: string } {
  const t = eventType.toLowerCase();
  if (t.includes("order") || t.includes("fill")) return { bg: "bg-blue-900/50 border-blue-700", text: "text-blue-300", label: eventType };
  if (t.includes("kill") || t.includes("halt")) return { bg: "bg-red-900/50 border-red-700", text: "text-red-300", label: eventType };
  if (t.includes("mode") || t.includes("switch")) return { bg: "bg-amber-900/50 border-amber-700", text: "text-amber-300", label: eventType };
  if (t.includes("risk") || t.includes("circuit") || t.includes("loss")) return { bg: "bg-orange-900/50 border-orange-700", text: "text-orange-300", label: eventType };
  if (t.includes("config") || t.includes("setting")) return { bg: "bg-purple-900/50 border-purple-700", text: "text-purple-300", label: eventType };
  return { bg: "bg-slate-800 border-slate-600", text: "text-slate-300", label: eventType };
}

function formatDateTime(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString();
  } catch {
    return iso;
  }
}

function fmtNum(n: number | null | undefined): string {
  if (n == null) return "—";
  if (Number.isInteger(n)) return String(n);
  return n.toFixed(2);
}

/* ─── AuditLogEntryRow ────────────────────────────────── */

function AuditLogEntryRow({ entry }: { entry: AuditLogEntry }) {
  const badge = eventBadge(entry.event_type);
  return (
    <div className={`rounded border ${badge.bg} p-3 text-sm`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          {/* Event type + timestamp */}
          <div className="flex items-center gap-2 mb-1">
            <span className={`text-xs font-bold uppercase px-1.5 py-0.5 rounded ${badge.bg} ${badge.text} border`}>
              {badge.label}
            </span>
            <span className="text-xs text-slate-500">
              {formatDateTime(entry.created_at)}
            </span>
          </div>

          {/* Core details row */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-x-4 gap-y-1 mt-1">
            {entry.instrument && (
              <div>
                <span className="text-xs text-slate-500">Instrument</span>
                <div className="font-mono text-slate-200">{entry.instrument}</div>
              </div>
            )}
            {entry.side && (
              <div>
                <span className="text-xs text-slate-500">Side</span>
                <div className={`font-mono font-bold ${entry.side === "BUY" ? "text-emerald-400" : "text-red-400"}`}>
                  {entry.side}
                </div>
              </div>
            )}
            {entry.order_type && (
              <div>
                <span className="text-xs text-slate-500">Type</span>
                <div className="font-mono text-slate-200 capitalize">{entry.order_type}</div>
              </div>
            )}
            {entry.quantity != null && (
              <div>
                <span className="text-xs text-slate-500">Quantity</span>
                <div className="font-mono text-slate-200">{entry.quantity}</div>
              </div>
            )}
          </div>

          {/* Price + fill details */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-x-4 gap-y-1 mt-1">
            {entry.price != null && (
              <div>
                <span className="text-xs text-slate-500">Price</span>
                <div className="font-mono text-slate-200">{fmtNum(entry.price)}</div>
              </div>
            )}
            {entry.fill_price != null && (
              <div>
                <span className="text-xs text-slate-500">Fill</span>
                <div className="font-mono text-slate-200">{fmtNum(entry.fill_price)}</div>
              </div>
            )}
            {entry.commission != null && (
              <div>
                <span className="text-xs text-slate-500">Comm</span>
                <div className="font-mono text-slate-300">${fmtNum(entry.commission)}</div>
              </div>
            )}
            {entry.reason && (
              <div>
                <span className="text-xs text-slate-500">Reason</span>
                <div className="text-slate-300 text-xs truncate max-w-[200px]" title={entry.reason}>
                  {entry.reason}
                </div>
              </div>
            )}
          </div>

          {/* Client/broker order IDs */}
          {(entry.client_order_id || entry.broker_order_id) && (
            <div className="flex gap-4 mt-1 text-xs text-slate-600 font-mono">
              {entry.client_order_id && <span>CL: {entry.client_order_id}</span>}
              {entry.broker_order_id && <span>BR: {entry.broker_order_id}</span>}
            </div>
          )}
        </div>

        {/* Mode badge */}
        {entry.mode && (
          <span
            className={`shrink-0 text-xs font-bold uppercase px-1.5 py-0.5 rounded ${
              entry.mode === "live"
                ? "bg-red-900/50 text-red-400 border border-red-700"
                : "bg-amber-900/50 text-amber-400 border border-amber-700"
            }`}
          >
            {entry.mode}
          </span>
        )}
      </div>
    </div>
  );
}

/* ─── Filters ─────────────────────────────────────────── */

const EVENT_TYPES = [
  "order_placed",
  "order_filled",
  "order_cancelled",
  "order_rejected",
  "mode_switch",
  "kill_switch",
  "circuit_breaker",
  "daily_loss",
  "risk_config",
  "position_update",
];

/* ─── Main AuditLog ───────────────────────────────────── */

export default function AuditLog() {
  const [data, setData] = useState<AuditLogResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Filters
  const [eventFilter, setEventFilter] = useState("");
  const [instrumentFilter, setInstrumentFilter] = useState("");
  const [modeFilter, setModeFilter] = useState("");
  const [page, setPage] = useState(0);
  const pageSize = 50;

  const fetchLogs = useCallback(async () => {
    try {
      const result = await getAuditLogs({
        event_type: eventFilter || undefined,
        instrument: instrumentFilter || undefined,
        mode: modeFilter || undefined,
        limit: pageSize,
        offset: page * pageSize,
      });
      setData(result);
      setError("");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load audit logs");
    } finally {
      setLoading(false);
    }
  }, [eventFilter, instrumentFilter, modeFilter, page]);

  useEffect(() => {
    fetchLogs();
    const interval = setInterval(fetchLogs, 10_000);
    return () => clearInterval(interval);
  }, [fetchLogs]);

  const totalPages = data ? Math.ceil(data.total / pageSize) : 0;
  const entries = data?.entries ?? [];

  if (loading && !data) {
    return <TerminalState kind="loading" title="Loading audit history" detail="Retrieving immutable execution and risk events." />;
  }

  if (error && !data) {
    return <TerminalState kind="error" title="Audit history unavailable" detail={error} onRetry={() => { setLoading(true); fetchLogs(); }} />;
  }

  return (
    <div className="space-y-4">
      <TerminalPageHeader
        eyebrow="Compliance & oversight"
        title="Audit Log"
        description={`Immutable event history — ${data?.total ?? 0} entries`}
        actions={<RefreshButton loading={loading} onClick={() => { setLoading(true); fetchLogs().finally(() => setLoading(false)); }} />}
      />

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <select
          value={eventFilter}
          onChange={(e) => { setEventFilter(e.target.value); setPage(0); }}
          className="rounded bg-slate-800 border border-slate-600 px-3 py-1.5 text-sm text-slate-200"
        >
          <option value="">All Event Types</option>
          {EVENT_TYPES.map((et) => (
            <option key={et} value={et}>{et.replace(/_/g, " ")}</option>
          ))}
        </select>
        <input
          type="text"
          value={instrumentFilter}
          onChange={(e) => { setInstrumentFilter(e.target.value); setPage(0); }}
          placeholder="Instrument (e.g. ES)"
          className="rounded bg-slate-800 border border-slate-600 px-3 py-1.5 text-sm text-slate-200 placeholder-slate-600 w-40"
        />
        <select
          value={modeFilter}
          onChange={(e) => { setModeFilter(e.target.value); setPage(0); }}
          className="rounded bg-slate-800 border border-slate-600 px-3 py-1.5 text-sm text-slate-200"
        >
          <option value="">All Modes</option>
          <option value="paper">Paper</option>
          <option value="live">Live</option>
        </select>
        {(eventFilter || instrumentFilter || modeFilter) && (
          <button
            onClick={() => { setEventFilter(""); setInstrumentFilter(""); setModeFilter(""); setPage(0); }}
            className="rounded border border-slate-600 px-3 py-1.5 text-sm text-slate-400 hover:text-slate-200 hover:bg-slate-700"
          >
            Clear Filters
          </button>
        )}
      </div>

      {/* Error */}
      {error && <NoticeBanner tone="error">Last refresh failed: {error}. Showing the last successfully loaded event history.</NoticeBanner>}

      {/* Entries */}
      {!loading && entries.length === 0 && (
        <TerminalState kind="empty" title="No audit log entries found" detail="Events will appear here as trading activity occurs." />
      )}

      <div className="space-y-2">
        {entries.map((entry) => (
          <AuditLogEntryRow key={entry.id} entry={entry} />
        ))}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between pt-2">
          <span className="text-xs text-slate-500">
            Page {page + 1} of {totalPages} ({data?.total} total)
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
              className="rounded bg-slate-800 border border-slate-600 px-3 py-1 text-sm text-slate-300 hover:bg-slate-700 disabled:opacity-40"
            >
              ← Previous
            </button>
            <button
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
              disabled={page >= totalPages - 1}
              className="rounded bg-slate-800 border border-slate-600 px-3 py-1 text-sm text-slate-300 hover:bg-slate-700 disabled:opacity-40"
            >
              Next →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
