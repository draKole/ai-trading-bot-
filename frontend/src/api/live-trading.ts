/** Live Trading API — mode, audit log, risk controls. */

const BASE = "/api/v1";

/* ─── Helpers ──────────────────────────────────────────── */

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`HTTP ${res.status}: ${text || res.statusText}`);
  }
  return res.json();
}

/* ─── Types: Mode ──────────────────────────────────────── */

export interface ModeState {
  mode: string;
  is_live: boolean;
  is_paper: boolean;
  configured_at: string;
  last_switched_at: string | null;
  is_killed?: boolean;
}

export interface SwitchResult {
  status: string;
  message?: string;
  previous_mode?: string;
  current_mode?: string;
}

/* ─── Types: Audit ─────────────────────────────────────── */

export interface AuditLogEntry {
  id: number;
  event_type: string;
  client_order_id: string | null;
  broker_order_id: string | null;
  instrument: string | null;
  side: string | null;
  order_type: string | null;
  quantity: number | null;
  price: number | null;
  fill_price: number | null;
  commission: number | null;
  reason: string | null;
  mode: string | null;
  metadata_json: unknown;
  created_at: string;
}

export interface AuditLogResponse {
  total: number;
  limit: number;
  offset: number;
  entries: AuditLogEntry[];
}

/* ─── Types: Risk Controls ─────────────────────────────── */

export interface CircuitBreakerState {
  consecutive_losses: number;
  max_consecutive: number;
  window_seconds: number;
  triggered: boolean;
  losses_in_window: unknown[];
}

export interface DailyLossState {
  current_loss: number;
  limit: number;
  exceeded: boolean;
}

export interface RiskControlsState {
  is_killed: boolean;
  kill_switch_enabled: boolean;
  circuit_breaker: CircuitBreakerState;
  daily_loss: DailyLossState;
  daily_loss_limit_enabled: boolean;
  circuit_breaker_enabled: boolean;
  max_position_enabled: boolean;
  max_position_size: Record<string, number>;
  positions_current: Record<string, number>;
}

export interface RiskConfig {
  daily_loss_limit: number;
  circuit_breaker_consecutive_losses: number;
  circuit_breaker_window_seconds: number;
  kill_switch_enabled: boolean;
  circuit_breaker_enabled: boolean;
  daily_loss_limit_enabled: boolean;
  max_position_enabled: boolean;
  max_position_size: Record<string, number>;
}

/* ─── Mode API ─────────────────────────────────────────── */

export async function getMode(): Promise<ModeState> {
  return fetchJson<ModeState>(`${BASE}/mode`);
}

export async function switchMode(
  target: string,
  confirm: boolean,
): Promise<SwitchResult> {
  const params = new URLSearchParams({ target, confirm: String(confirm) });
  return fetchJson<SwitchResult>(`${BASE}/mode/switch?${params}`, { method: "POST" });
}

export async function killSwitch(): Promise<{ status: string }> {
  return fetchJson(`${BASE}/mode/kill`, { method: "POST" });
}

export async function canTrade(): Promise<{ allowed: boolean; reason: string }> {
  return fetchJson(`${BASE}/mode/can-trade`);
}

/* ─── Audit API ────────────────────────────────────────── */

export async function getAuditLogs(params?: {
  event_type?: string;
  client_order_id?: string;
  instrument?: string;
  mode?: string;
  limit?: number;
  offset?: number;
}): Promise<AuditLogResponse> {
  const q = new URLSearchParams();
  if (params?.event_type) q.set("event_type", params.event_type);
  if (params?.client_order_id) q.set("client_order_id", params.client_order_id);
  if (params?.instrument) q.set("instrument", params.instrument);
  if (params?.mode) q.set("mode", params.mode);
  if (params?.limit) q.set("limit", String(params.limit));
  if (params?.offset) q.set("offset", String(params.offset));
  const qs = q.toString();
  return fetchJson<AuditLogResponse>(`${BASE}/audit${qs ? "?" + qs : ""}`);
}

/* ─── Risk Controls API ────────────────────────────────── */

export async function getRiskControls(): Promise<RiskControlsState> {
  return fetchJson<RiskControlsState>(`${BASE}/risk/controls`);
}

export async function activateRiskKillSwitch(): Promise<{ status: string }> {
  return fetchJson(`${BASE}/risk/controls/kill`, { method: "POST" });
}

export async function updateRiskConfig(
  updates: Partial<RiskConfig>,
): Promise<{ status: string; config: RiskConfig }> {
  const q = new URLSearchParams();
  for (const [key, value] of Object.entries(updates)) {
    if (value !== undefined && value !== null) {
      if (typeof value === "object") {
        // Handle max_position_size as individual params
        for (const [inst, size] of Object.entries(value as Record<string, number>)) {
          const k = `max_pos_${inst.toLowerCase()}`;
          q.set(k, String(size));
        }
      } else {
        q.set(key, String(value));
      }
    }
  }
  return fetchJson(`${BASE}/risk/controls/config?${q}`, { method: "POST" });
}

export async function recordTradePnl(pnl: number): Promise<{
  status: string;
  pnl: number;
  circuit_breaker_losses: number;
  daily_loss: number;
  killed: boolean;
}> {
  return fetchJson(`${BASE}/risk/controls/record-trade?pnl=${pnl}`, { method: "POST" });
}
