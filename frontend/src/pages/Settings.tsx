import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  getApplicationSettings,
  getDeploymentConfig,
  type ApplicationSettings,
  type DeploymentConfig,
} from "../api/settings";

type WizardStep = "environment" | "trading" | "review";

interface CheckItem {
  key: "database_url" | "redis_url" | "secret_key_set";
  label: string;
  detail: string;
}

const requiredChecks: CheckItem[] = [
  {
    key: "database_url",
    label: "Database connection",
    detail: "A database URL is available to the application.",
  },
  {
    key: "redis_url",
    label: "Redis connection",
    detail: "A Redis URL is available for runtime services.",
  },
  {
    key: "secret_key_set",
    label: "Application secret",
    detail: "The default development secret has been replaced.",
  },
];

const stepLabels: Array<{ id: WizardStep; number: number; label: string }> = [
  { id: "environment", number: 1, label: "Verify environment" },
  { id: "trading", number: 2, label: "Review trading defaults" },
  { id: "review", number: 3, label: "Finish safely" },
];

function modeStyle(mode: string) {
  return mode.toLowerCase() === "live"
    ? "border-red-700 bg-red-950/50 text-red-300"
    : "border-amber-700 bg-amber-950/40 text-amber-300";
}

function formatValue(value: string | number) {
  return typeof value === "number" ? value.toLocaleString() : value || "Not configured";
}

function CheckStatus({ passed }: { passed: boolean }) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-semibold ${
        passed
          ? "border-emerald-700 bg-emerald-950/60 text-emerald-300"
          : "border-red-700 bg-red-950/60 text-red-300"
      }`}
    >
      {passed ? "Verified" : "Needs attention"}
    </span>
  );
}

function EnvironmentStep({ deployment }: { deployment: DeploymentConfig }) {
  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-lg font-semibold text-slate-100">Required environment checks</h3>
        <p className="mt-1 text-sm text-slate-400">
          Credentials and secret values are never shown in the terminal. This check only confirms whether the server has the required configuration.
        </p>
      </div>

      <div className="overflow-hidden rounded-lg border border-slate-700 bg-slate-900">
        {requiredChecks.map((check, index) => {
          const passed = deployment.checks[check.key];
          return (
            <div
              key={check.key}
              className={`flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between ${
                index < requiredChecks.length - 1 ? "border-b border-slate-800" : ""
              }`}
            >
              <div>
                <div className="flex items-center gap-2 text-sm font-medium text-slate-200">
                  <span className={passed ? "text-emerald-400" : "text-red-400"} aria-hidden="true">
                    {passed ? "✓" : "!"}
                  </span>
                  {check.label}
                </div>
                <p className="mt-1 text-xs text-slate-500">{check.detail}</p>
              </div>
              <CheckStatus passed={passed} />
            </div>
          );
        })}
      </div>

      {!deployment.valid && (
        <div className="rounded-lg border border-amber-700 bg-amber-950/40 p-4 text-sm text-amber-200">
          <span className="font-semibold">Configuration action required. </span>
          Update the missing environment variable in the deployment environment, then select Refresh validation. Do not paste credentials or secrets into this application.
        </div>
      )}
    </div>
  );
}

function TradingStep({ settings, deployment }: { settings: ApplicationSettings; deployment: DeploymentConfig }) {
  const defaultValidation = useMemo(
    () => [
      { label: "Default risk per trade", value: `${formatValue(settings.default_risk_percent)}%`, valid: settings.default_risk_percent > 0 && settings.default_risk_percent <= 100 },
      { label: "Minimum risk / reward", value: formatValue(settings.min_risk_reward), valid: settings.min_risk_reward > 0 },
      { label: "Maximum contracts", value: formatValue(settings.max_contracts), valid: Number.isInteger(settings.max_contracts) && settings.max_contracts > 0 },
      { label: "Maximum trades per day", value: formatValue(settings.max_trades_per_day), valid: Number.isInteger(settings.max_trades_per_day) && settings.max_trades_per_day > 0 },
      { label: "Maximum trades per session", value: formatValue(settings.max_trades_per_session), valid: Number.isInteger(settings.max_trades_per_session) && settings.max_trades_per_session > 0 },
    ],
    [settings],
  );

  return (
    <div className="space-y-5">
      <div>
        <h3 className="text-lg font-semibold text-slate-100">Trading defaults</h3>
        <p className="mt-1 text-sm text-slate-400">
          Review the server-managed defaults before trading. Risk controls remain enforced independently at execution time.
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="rounded-lg border border-slate-700 bg-slate-900 p-4">
          <div className="text-xs font-medium uppercase tracking-wide text-slate-500">Trading mode</div>
          <div className={`mt-2 inline-flex rounded border px-2.5 py-1 font-mono text-sm font-bold ${modeStyle(settings.trading_mode)}`}>
            {settings.trading_mode.toUpperCase()}
          </div>
          <p className="mt-3 text-xs text-slate-500">
            {settings.trading_mode.toLowerCase() === "live"
              ? "LIVE mode is configured. Live execution still requires explicit confirmation and applicable safety controls."
              : "PAPER mode is active. Orders are simulated until LIVE is explicitly enabled."}
          </p>
        </div>
        <div className="rounded-lg border border-slate-700 bg-slate-900 p-4">
          <div className="text-xs font-medium uppercase tracking-wide text-slate-500">Market data provider</div>
          <div className="mt-2 font-mono text-lg font-semibold text-slate-100">{settings.data_provider || "Not configured"}</div>
          <p className="mt-3 text-xs text-slate-500">Provider details and credentials stay on the server.</p>
        </div>
        <div className="rounded-lg border border-slate-700 bg-slate-900 p-4">
          <div className="text-xs font-medium uppercase tracking-wide text-slate-500">Live execution permission</div>
          <div className={`mt-2 text-lg font-semibold ${deployment.checks.live_allowed ? "text-red-300" : "text-emerald-300"}`}>
            {deployment.checks.live_allowed ? "Allowed" : "Blocked"}
          </div>
          <p className="mt-3 text-xs text-slate-500">This deployment setting does not bypass the explicit LIVE confirmation flow.</p>
        </div>
      </div>

      <div className="overflow-hidden rounded-lg border border-slate-700 bg-slate-900">
        <div className="border-b border-slate-800 px-4 py-3 text-sm font-semibold text-slate-200">Default validation</div>
        <div className="divide-y divide-slate-800">
          {defaultValidation.map((item) => (
            <div key={item.label} className="flex items-center justify-between gap-4 px-4 py-3">
              <span className="text-sm text-slate-400">{item.label}</span>
              <div className="flex items-center gap-3">
                <span className="font-mono text-sm text-slate-200">{item.value}</span>
                <CheckStatus passed={item.valid} />
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-lg border border-blue-800 bg-blue-950/30 p-4 text-sm text-blue-200">
        Need to tune runtime risk limits? Use the <Link to="/risk" className="font-semibold underline decoration-blue-500 underline-offset-2 hover:text-blue-100">Risk Center</Link>. Application defaults shown here are read-only to keep configuration changes auditable and secret-safe.
      </div>
    </div>
  );
}

function ReviewStep({ deployment, settings }: { deployment: DeploymentConfig; settings: ApplicationSettings }) {
  const isPaper = settings.trading_mode.toLowerCase() !== "live";
  return (
    <div className="space-y-5">
      <div>
        <h3 className="text-lg font-semibold text-slate-100">Safe configuration summary</h3>
        <p className="mt-1 text-sm text-slate-400">Confirm the environment and operational safeguards before proceeding to the trading workspace.</p>
      </div>

      <div className={`rounded-lg border p-5 ${deployment.valid ? "border-emerald-700 bg-emerald-950/30" : "border-amber-700 bg-amber-950/30"}`}>
        <div className="flex items-start gap-3">
          <span className="text-xl" aria-hidden="true">{deployment.valid ? "✓" : "!"}</span>
          <div>
            <h4 className={`font-semibold ${deployment.valid ? "text-emerald-300" : "text-amber-300"}`}>
              {deployment.valid ? "Required environment checks passed" : "Configuration is incomplete"}
            </h4>
            <p className="mt-1 text-sm text-slate-300">
              {deployment.valid
                ? "The API reports its required database, Redis, and application-secret checks as configured."
                : "Return to Verify environment, correct the missing deployment variable, and refresh validation before operating."}
            </p>
          </div>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-lg border border-slate-700 bg-slate-900 p-4">
          <div className="text-sm font-semibold text-slate-200">Mode protection</div>
          <p className="mt-2 text-sm text-slate-400">
            {isPaper
              ? "PAPER mode is configured, so orders are simulated by default."
              : "LIVE mode is configured. Confirm the Risk Center and execution controls before allowing real orders."}
          </p>
        </div>
        <div className="rounded-lg border border-slate-700 bg-slate-900 p-4">
          <div className="text-sm font-semibold text-slate-200">Secrets stay outside the UI</div>
          <p className="mt-2 text-sm text-slate-400">Broker, provider, database, and secret-key values are managed through deployment environment variables—not browser forms.</p>
        </div>
      </div>

      <div className="flex flex-wrap gap-3">
        <Link to="/risk" className="rounded bg-slate-700 px-4 py-2 text-sm font-medium text-slate-100 transition-colors hover:bg-slate-600">
          Review risk controls
        </Link>
        <Link to="/live-trading" className="rounded border border-amber-700 px-4 py-2 text-sm font-medium text-amber-300 transition-colors hover:bg-amber-950/50">
          Open trading mode controls
        </Link>
      </div>
    </div>
  );
}

export default function Settings() {
  const [settings, setSettings] = useState<ApplicationSettings | null>(null);
  const [deployment, setDeployment] = useState<DeploymentConfig | null>(null);
  const [activeStep, setActiveStep] = useState<WizardStep>("environment");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    try {
      const [nextSettings, nextDeployment] = await Promise.all([getApplicationSettings(), getDeploymentConfig()]);
      setSettings(nextSettings);
      setDeployment(nextDeployment);
      setError("");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unable to load configuration status");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  function handleRefresh() {
    setRefreshing(true);
    refresh();
  }

  const stepIndex = stepLabels.findIndex((step) => step.id === activeStep);

  if (loading && !settings && !deployment) {
    return <div className="flex h-64 items-center justify-center text-sm text-slate-400">Loading configuration workspace…</div>;
  }

  if ((!settings || !deployment) && error) {
    return (
      <div className="p-6">
        <div className="mx-auto max-w-xl rounded-lg border border-red-700 bg-red-950/50 p-6 text-center">
          <h2 className="text-lg font-semibold text-red-200">Configuration status unavailable</h2>
          <p className="mt-2 text-sm text-red-300">{error}</p>
          <button onClick={handleRefresh} className="mt-4 rounded bg-red-800 px-4 py-2 text-sm font-medium text-red-100 hover:bg-red-700">
            Retry connection
          </button>
        </div>
      </div>
    );
  }

  if (!settings || !deployment) return null;

  return (
    <div className="mx-auto max-w-6xl space-y-5 p-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-2xl font-bold text-slate-100">Configuration workspace</h2>
            <span className="rounded border border-slate-700 bg-slate-900 px-2 py-0.5 text-xs font-medium text-slate-400">Read-only</span>
          </div>
          <p className="mt-1 text-sm text-slate-400">Verify required environment configuration and review server-managed trading defaults.</p>
        </div>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="rounded border border-slate-600 bg-slate-800 px-3 py-1.5 text-sm font-medium text-slate-200 transition-colors hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {refreshing ? "Validating…" : "Refresh validation"}
        </button>
      </div>

      {error && (
        <div className="rounded border border-amber-700 bg-amber-950/50 px-4 py-3 text-sm text-amber-200">
          Last refresh failed: {error}. Showing the last successfully loaded configuration status.
        </div>
      )}

      <div className="grid gap-5 lg:grid-cols-[220px_minmax(0,1fr)]">
        <aside className="rounded-lg border border-slate-700 bg-slate-900 p-3 lg:h-fit">
          <div className="mb-3 px-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Setup checklist</div>
          <nav className="space-y-1" aria-label="Configuration setup steps">
            {stepLabels.map((step, index) => {
              const isActive = step.id === activeStep;
              const completed = index < stepIndex || (step.id === "environment" && deployment.valid);
              return (
                <button
                  key={step.id}
                  onClick={() => setActiveStep(step.id)}
                  className={`flex w-full items-center gap-3 rounded px-2 py-2.5 text-left text-sm transition-colors ${
                    isActive ? "bg-slate-800 text-slate-100" : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-200"
                  }`}
                >
                  <span className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-xs font-semibold ${
                    completed ? "border-emerald-700 bg-emerald-950 text-emerald-300" : isActive ? "border-blue-600 bg-blue-950 text-blue-300" : "border-slate-600 text-slate-400"
                  }`}>
                    {completed ? "✓" : step.number}
                  </span>
                  {step.label}
                </button>
              );
            })}
          </nav>
        </aside>

        <section className="rounded-lg border border-slate-700 bg-slate-950 p-5 sm:p-6">
          {activeStep === "environment" && <EnvironmentStep deployment={deployment} />}
          {activeStep === "trading" && <TradingStep settings={settings} deployment={deployment} />}
          {activeStep === "review" && <ReviewStep settings={settings} deployment={deployment} />}

          <div className="mt-8 flex items-center justify-between border-t border-slate-800 pt-4">
            <button
              onClick={() => setActiveStep(stepLabels[Math.max(stepIndex - 1, 0)].id)}
              disabled={stepIndex === 0}
              className="rounded px-3 py-2 text-sm text-slate-400 transition-colors hover:bg-slate-800 hover:text-slate-200 disabled:cursor-not-allowed disabled:opacity-30"
            >
              Back
            </button>
            <button
              onClick={() => setActiveStep(stepLabels[Math.min(stepIndex + 1, stepLabels.length - 1)].id)}
              disabled={stepIndex === stepLabels.length - 1}
              className="rounded bg-blue-700 px-4 py-2 text-sm font-medium text-blue-50 transition-colors hover:bg-blue-600 disabled:cursor-not-allowed disabled:opacity-30"
            >
              Continue
            </button>
          </div>
        </section>
      </div>
    </div>
  );
}
