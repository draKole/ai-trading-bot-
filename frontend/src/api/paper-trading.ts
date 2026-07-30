/** Paper Trading API client. */

const BASE = "/api/v1";

/* ─── Types ──────────────────────────────────────────── */

export interface AccountSummary {
  session_id: number;
  account_id: string;
  name: string;
  balance: number;
  buying_power: number;
  initial_balance: number;
  realized_pnl: number;
  unrealized_pnl: number;
  total_pnl: number;
  total_return_pct: number;
  open_positions_count: number;
  status: string;
}

export interface PaperOrder {
  id: number;
  session_id: number;
  order_type: string;
  side: string;
  instrument: string;
  quantity: number;
  price: number | null;
  stop_price: number | null;
  status: string;
  filled_qty: number;
  fill_price: number | null;
  slippage: number;
  commission: number;
  created_at?: string;
}

export interface PaperPosition {
  id: number;
  session_id: number;
  instrument: string;
  direction: string;
  quantity: number;
  avg_entry_price: number;
  current_price: number;
  unrealized_pnl: number;
  realized_pnl: number;
  status: string;
  opened_at: string | null;
  closed_at?: string | null;
}

export interface PaperTrade {
  id: number;
  instrument: string;
  side: string;
  order_type: string;
  quantity: number;
  filled_qty: number;
  price: number | null;
  fill_price: number | null;
  status: string;
  commission: number;
  slippage: number;
}

export interface PlaceOrderResult {
  order_id: number;
  status: string;
  fill_price: number | null;
  filled_qty: number;
  slippage: number;
  commission: number;
}

export interface ListResponse<T> {
  count: number;
  [key: string]: T[] | number;
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

/* ─── Sessions ───────────────────────────────────────── */

export async function startSession(
  name: string,
  initialBalance: number,
): Promise<{ session_id: number; account_id: string; status: string }> {
  const params = new URLSearchParams({ name, initial_balance: String(initialBalance) });
  return fetchJson(`${BASE}/paper/start?${params}`, { method: "POST" });
}

/* ─── Account ────────────────────────────────────────── */

export async function getAccountSummary(sessionId: number): Promise<AccountSummary> {
  return fetchJson(`${BASE}/paper/account/${sessionId}`);
}

/* ─── Orders ─────────────────────────────────────────── */

export async function placeOrder(params: {
  session_id: number;
  order_type: string;
  side: string;
  instrument: string;
  quantity: number;
  price?: number;
  stop_price?: number;
  current_price?: number;
  current_high?: number;
  current_low?: number;
}): Promise<PlaceOrderResult> {
  const q = new URLSearchParams({
    session_id: String(params.session_id),
    order_type: params.order_type,
    side: params.side,
    instrument: params.instrument,
    quantity: String(params.quantity),
  });
  if (params.price !== undefined) q.set("price", String(params.price));
  if (params.stop_price !== undefined) q.set("stop_price", String(params.stop_price));
  if (params.current_price !== undefined) q.set("current_price", String(params.current_price));
  if (params.current_high !== undefined) q.set("current_high", String(params.current_high));
  if (params.current_low !== undefined) q.set("current_low", String(params.current_low));
  return fetchJson(`${BASE}/paper/orders/place?${q}`, { method: "POST" });
}

export async function listOrders(
  sessionId: number,
  status?: string,
): Promise<{ count: number; orders: PaperOrder[] }> {
  const params = new URLSearchParams({ session_id: String(sessionId) });
  if (status) params.set("status", status);
  return fetchJson(`${BASE}/paper/orders?${params}`);
}

export async function cancelOrder(orderId: number): Promise<{ order_id: number; status: string }> {
  return fetchJson(`${BASE}/paper/orders/${orderId}`, { method: "DELETE" });
}

export async function modifyOrder(
  orderId: number,
  updates: { quantity?: number; price?: number; stop_price?: number },
): Promise<{ order_id: number; status: string }> {
  const q = new URLSearchParams();
  if (updates.quantity !== undefined) q.set("quantity", String(updates.quantity));
  if (updates.price !== undefined) q.set("price", String(updates.price));
  if (updates.stop_price !== undefined) q.set("stop_price", String(updates.stop_price));
  return fetchJson(`${BASE}/paper/orders/${orderId}?${q}`, { method: "PATCH" });
}

/* ─── Positions ──────────────────────────────────────── */

export async function listPositions(
  sessionId: number,
  status?: string,
): Promise<{ count: number; positions: PaperPosition[] }> {
  const params = new URLSearchParams({ session_id: String(sessionId) });
  if (status) params.set("status", status);
  return fetchJson(`${BASE}/paper/positions?${params}`);
}

/* ─── Trades ─────────────────────────────────────────── */

export async function listTrades(
  sessionId: number,
): Promise<{ count: number; trades: PaperTrade[] }> {
  return fetchJson(`${BASE}/paper/trades?session_id=${sessionId}`);
}
