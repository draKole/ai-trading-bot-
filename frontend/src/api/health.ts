/** Consolidated monitoring API client. */

const BASE = "/api/v1/monitoring";

export interface ComponentHealth {
  status: string; // healthy, degraded, unhealthy, unknown
  detail: string;
  latency_ms?: number | null;
  metadata?: {
    ok?: boolean;
    provider?: string | null;
    provider_status?: string;
    instruments?: Record<string, number>;
    complete_instruments?: boolean;
    last_successful_update?: string | null;
    latency_ms?: number;
  };
}

export interface SystemMetrics {
  cpu_percent: number;
  memory_percent: number;
  memory_used_mb: number;
  memory_total_mb: number;
  uptime_seconds: number;
  uptime_human: string;
}

export interface TradingStatus {
  active_positions: number;
  open_orders: number;
  signals_today: number;
  trades_today: number;
}

export interface ModeInfo {
  mode: string;
  live_allowed: boolean;
  uptime_seconds: number;
}

export interface HealthData {
  health: {
    overall: string;
    components: Record<string, ComponentHealth>;
  };
  metrics: Record<string, unknown>;
  system: SystemMetrics;
  mode: ModeInfo;
  trading: TradingStatus;
  timestamp: string;
}

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
  return res.json();
}

/** Full dashboard/health status with all fields. */
export async function getHealth(): Promise<HealthData> {
  return fetchJson<HealthData>(`${BASE}/health`);
}

/** Consolidated monitoring status. */
export async function getMonitoringStatus(): Promise<HealthData> {
  return fetchJson<HealthData>(`${BASE}/status`);
}

/** Single-component health: database. */
export async function getDatabaseHealth(): Promise<ComponentHealth> {
  return fetchJson<ComponentHealth>(`${BASE}/health/database`);
}

/** Single-component health: redis. */
export async function getRedisHealth(): Promise<ComponentHealth> {
  return fetchJson<ComponentHealth>(`${BASE}/health/redis`);
}

/** Single-component health: broker. */
export async function getBrokerHealth(): Promise<ComponentHealth> {
  return fetchJson<ComponentHealth>(`${BASE}/health/broker`);
}

/** Single-component health: market data. */
export async function getMarketDataHealth(): Promise<ComponentHealth> {
  return fetchJson<ComponentHealth>(`${BASE}/health/market-data`);
}

/** Single-component health: workers. */
export async function getWorkersHealth(): Promise<ComponentHealth> {
  return fetchJson<ComponentHealth>(`${BASE}/health/workers`);
}

/** Trigger a full health check run. */
export async function runAllHealthChecks(): Promise<unknown> {
  return fetchJson(`${BASE}/health/run-all`);
}
