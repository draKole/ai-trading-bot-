/** Application settings and deployment configuration API client. */

const BASE = "/api/v1";

export interface ApplicationSettings {
  trading_mode: string;
  data_provider: string;
  default_risk_percent: number;
  min_risk_reward: number;
  max_contracts: number;
  max_trades_per_day: number;
  max_trades_per_session: number;
}

export interface DeploymentConfig {
  valid: boolean;
  checks: {
    database_url: boolean;
    redis_url: boolean;
    secret_key_set: boolean;
    trading_mode: string;
    live_allowed: boolean;
  };
}

async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) {
    const detail = await response.text().catch(() => "");
    throw new Error(`HTTP ${response.status}: ${detail || response.statusText}`);
  }
  return response.json() as Promise<T>;
}

/** Non-sensitive trading defaults. These values are server-managed and read-only. */
export function getApplicationSettings(): Promise<ApplicationSettings> {
  return fetchJson<ApplicationSettings>(`${BASE}/settings/`);
}

/** Required environment configuration validation. No secret values are returned. */
export function getDeploymentConfig(): Promise<DeploymentConfig> {
  return fetchJson<DeploymentConfig>(`${BASE}/infrastructure/deployment/config`);
}
