import { useEffect, useState } from "react";
import {
  getInstruments,
  importBars,
  type Instrument,
  type ImportResult,
} from "../api/market-data";

/* ─── Constants ──────────────────────────────────────── */

const TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h", "1d"];

function generateTemplate(symbol: string, timeframe: string): string {
  const now = new Date();
  const bars = Array.from({ length: 3 }, (_, i) => {
    const ts = new Date(now.getTime() - (2 - i) * 60_000 * 5);
    const base = 5000 + i * 2;
    return {
      instrument: symbol,
      timeframe,
      timestamp: ts.toISOString(),
      open: base,
      high: base + 5,
      low: base - 3,
      close: base + 2,
      volume: 1000 + i * 200,
      vwap: base + 1.5,
      session: "RTH",
      provider: "manual",
    };
  });
  return JSON.stringify(bars, null, 2);
}

/* ─── Helpers ────────────────────────────────────────── */

function validateBarArray(data: unknown): { valid: boolean; error?: string } {
  if (!Array.isArray(data)) {
    return { valid: false, error: "Data must be a JSON array of bar objects" };
  }
  if (data.length === 0) {
    return { valid: false, error: "Array is empty — provide at least one bar" };
  }
  for (let i = 0; i < data.length; i++) {
    const bar = data[i];
    if (!bar || typeof bar !== "object") {
      return { valid: false, error: `Bar at index ${i} is not an object` };
    }
    if (!bar.instrument || typeof bar.instrument !== "string") {
      return { valid: false, error: `Bar at index ${i} missing 'instrument' field` };
    }
    if (!bar.timeframe || typeof bar.timeframe !== "string") {
      return { valid: false, error: `Bar at index ${i} missing 'timeframe' field` };
    }
    if (!bar.timestamp) {
      return { valid: false, error: `Bar at index ${i} missing 'timestamp' field` };
    }
    const o = bar.open, h = bar.high, l = bar.low, c = bar.close;
    if (typeof o !== "number" || typeof h !== "number" || typeof l !== "number" || typeof c !== "number") {
      return { valid: false, error: `Bar at index ${i} has invalid OHLC values` };
    }
  }
  return { valid: true };
}

/* ─── Main DataImport Page ───────────────────────────── */

export default function DataImport() {
  const [instruments, setInstruments] = useState<Instrument[]>([]);
  const [symbol, setSymbol] = useState("ES");
  const [timeframe, setTimeframe] = useState("5m");
  const [jsonText, setJsonText] = useState("");
  const [validationError, setValidationError] = useState("");
  const [importing, setImporting] = useState(false);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [apiError, setApiError] = useState("");

  useEffect(() => {
    getInstruments()
      .then((res) => setInstruments(res.instruments))
      .catch(() => {});
  }, []);

  /* Populate template */
  useEffect(() => {
    setJsonText(generateTemplate(symbol, timeframe));
  }, [symbol, timeframe]);

  /* Validate on text change */
  useEffect(() => {
    if (!jsonText.trim()) {
      setValidationError("");
      return;
    }
    try {
      const parsed = JSON.parse(jsonText);
      const { valid, error } = validateBarArray(parsed);
      setValidationError(valid ? "" : (error || "Invalid"));
    } catch {
      setValidationError("Invalid JSON — check syntax");
    }
  }, [jsonText]);

  /* Import handler */
  const handleImport = async () => {
    if (validationError || !jsonText.trim()) return;
    setImporting(true);
    setApiError("");
    setResult(null);
    try {
      const bars = JSON.parse(jsonText);
      const res = await importBars(bars);
      setResult(res);
    } catch (err: unknown) {
      setApiError(err instanceof Error ? err.message : "Import failed");
    } finally {
      setImporting(false);
    }
  };

  return (
    <div className="space-y-5 p-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-100">Import Market Data</h2>
        <p className="text-sm text-slate-400">
          Paste OHLCV bar data in JSON format to import into the historical database
        </p>
      </div>

      {/* Controls */}
      <div className="flex flex-wrap items-end gap-4">
        <div>
          <label className="mb-1 block text-xs font-medium text-slate-400">Symbol</label>
          <select
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            className="rounded border border-slate-700 bg-slate-800 px-3 py-1.5 text-sm text-slate-100 focus:border-green-500 focus:outline-none"
          >
            {instruments.map((i) => (
              <option key={i.symbol} value={i.symbol}>
                {i.symbol} — {i.name}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="mb-1 block text-xs font-medium text-slate-400">Default Timeframe</label>
          <div className="flex gap-1 rounded bg-slate-800 p-1">
            {TIMEFRAMES.map((tf) => (
              <button
                key={tf}
                onClick={() => setTimeframe(tf)}
                className={`rounded px-3 py-1 text-xs font-medium transition-colors ${
                  tf === timeframe
                    ? "bg-green-600 text-white"
                    : "text-slate-400 hover:bg-slate-700 hover:text-slate-200"
                }`}
              >
                {tf}
              </button>
            ))}
          </div>
        </div>

        <button
          onClick={() => setJsonText(generateTemplate(symbol, timeframe))}
          className="rounded border border-slate-600 bg-slate-800 px-3 py-1.5 text-xs text-slate-300 hover:bg-slate-700"
        >
          Generate Template
        </button>
      </div>

      {/* JSON textarea */}
      <div>
        <label className="mb-2 block text-sm font-medium text-slate-300">
          Bar Data (JSON)
        </label>
        <textarea
          value={jsonText}
          onChange={(e) => setJsonText(e.target.value)}
          rows={16}
          className="w-full rounded-lg border border-slate-700 bg-slate-900 p-4 font-mono text-xs text-slate-200 placeholder-slate-600 focus:border-green-500 focus:outline-none focus:ring-1 focus:ring-green-500"
          placeholder='[{"instrument": "ES", "timeframe": "5m", ...}]'
        />
        {validationError && (
          <p className="mt-1 text-xs text-amber-400">{validationError}</p>
        )}
      </div>

      {/* Import button */}
      <div className="flex items-center gap-4">
        <button
          onClick={handleImport}
          disabled={!!validationError || !jsonText.trim() || importing}
          className="rounded bg-green-600 px-6 py-2 text-sm font-semibold text-white hover:bg-green-500 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {importing ? (
            <span className="flex items-center gap-2">
              <svg className="h-4 w-4 animate-spin" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              Importing…
            </span>
          ) : (
            "Import Bars"
          )}
        </button>
      </div>

      {/* API Error */}
      {apiError && (
        <div className="rounded border border-red-700 bg-red-950 px-4 py-3 text-sm text-red-300">
          {apiError}
        </div>
      )}

      {/* Import Result */}
      {result && (
        <div className="rounded border border-emerald-700 bg-emerald-950 p-4">
          <h3 className="mb-3 text-sm font-semibold text-emerald-300">Import Complete</h3>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <div className="text-2xl font-bold text-emerald-200">{result.submitted}</div>
              <div className="text-xs text-emerald-400">Submitted</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-emerald-200">{result.inserted}</div>
              <div className="text-xs text-emerald-400">Inserted</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-amber-200">{result.skipped}</div>
              <div className="text-xs text-amber-400">Skipped</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
