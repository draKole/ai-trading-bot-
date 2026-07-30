/** Market Data API client. */

const BASE = "/api/v1";

/* ─── Types ──────────────────────────────────────────── */

export interface Instrument {
  id: number;
  symbol: string;
  name: string;
  exchange: string;
  tick_size: number;
  tick_value: number;
  multiplier: number;
  min_contracts?: number;
  max_contracts?: number;
  is_active?: boolean;
  created_at?: string;
}

export interface InstrumentsResponse {
  instruments: Instrument[];
  pagination?: {
    page: number;
    page_size: number;
    total: number;
    total_pages: number;
  };
}

export interface BarData {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  vwap: number;
  session: string;
  provider: string;
}

export interface BarsResponse {
  instrument: string;
  timeframe: string;
  session: string | null;
  count: number;
  bars: BarData[];
}

export interface ImportResult {
  submitted: number;
  inserted: number;
  skipped: number;
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

/* ─── Instruments ────────────────────────────────────── */

/** List all instruments with optional exchange filter. */
export async function getInstruments(exchange?: string): Promise<InstrumentsResponse> {
  const params = exchange ? `?exchange=${exchange}` : "";
  return fetchJson<InstrumentsResponse>(`${BASE}/instruments/${params}`);
}

/** Get a single instrument by symbol. */
export async function getInstrument(symbol: string): Promise<Instrument> {
  return fetchJson<Instrument>(`${BASE}/instruments/${symbol}`);
}

/* ─── Bars ───────────────────────────────────────────── */

/** Query historical bars with optional session filter. */
export async function getBars(
  instrument: string,
  timeframe: string,
  start?: string,
  end?: string,
  session?: string,
): Promise<BarsResponse> {
  const params = new URLSearchParams({ instrument, timeframe });
  if (start) params.set("start", start);
  if (end) params.set("end", end);
  if (session && session !== "all") params.set("session", session);
  return fetchJson<BarsResponse>(`${BASE}/market-data/bars?${params}`);
}

/** Get the most recent bar for an instrument/timeframe. */
export async function getLatestBar(
  instrument: string,
  timeframe: string,
): Promise<{ instrument: string; timeframe: string; bar: BarData }> {
  const params = new URLSearchParams({ instrument, timeframe });
  return fetchJson(`${BASE}/market-data/bars/latest?${params}`);
}

/** Get bar count for an instrument/timeframe. */
export async function getBarCount(
  instrument: string,
  timeframe: string,
): Promise<{ instrument: string; timeframe: string; count: number }> {
  const params = new URLSearchParams({ instrument, timeframe });
  return fetchJson(`${BASE}/market-data/bars/count?${params}`);
}

/* ─── Import ─────────────────────────────────────────── */

/** Import OHLCV bars from a JSON array. */
export async function importBars(bars: Partial<BarData>[]): Promise<ImportResult> {
  return fetchJson<ImportResult>(`${BASE}/market-data/import`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(bars),
  });
}
