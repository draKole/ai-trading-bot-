import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getInstruments, type Instrument } from "../api/market-data";

export default function Instruments() {
  const [instruments, setInstruments] = useState<Instrument[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    getInstruments()
      .then((res) => {
        setInstruments(res.instruments);
        setError("");
      })
      .catch((err: unknown) =>
        setError(err instanceof Error ? err.message : "Unknown error"),
      )
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center p-6">
        <div className="flex flex-col items-center gap-3">
          <svg className="h-8 w-8 animate-spin text-slate-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          <span className="text-sm text-slate-400">Loading instruments…</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="rounded border border-red-700 bg-red-950 p-6 text-center">
          <div className="mb-2 text-3xl">⚠</div>
          <div className="text-lg font-semibold text-red-300">Failed to Load</div>
          <div className="mt-1 text-sm text-red-400">{error}</div>
          <button
            onClick={() => window.location.reload()}
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
      <div>
        <h2 className="text-2xl font-bold text-slate-100">Instruments</h2>
        <p className="text-sm text-slate-400">
          Available futures contracts
        </p>
      </div>

      <div className="overflow-x-auto rounded-lg border border-slate-700">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-800 text-xs uppercase text-slate-400">
            <tr>
              <th className="px-4 py-3">Symbol</th>
              <th className="px-4 py-3">Name</th>
              <th className="px-4 py-3">Exchange</th>
              <th className="px-4 py-3">Tick Size</th>
              <th className="px-4 py-3">Tick Value</th>
              <th className="px-4 py-3">Multiplier</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {instruments.map((inst) => (
              <tr
                key={inst.symbol}
                onClick={() => navigate(`/charts?symbol=${inst.symbol}`)}
                className="cursor-pointer transition-colors hover:bg-slate-800/50"
              >
                <td className="px-4 py-3 font-mono font-bold text-green-400">
                  {inst.symbol}
                </td>
                <td className="px-4 py-3 text-slate-200">{inst.name}</td>
                <td className="px-4 py-3 text-slate-400">{inst.exchange}</td>
                <td className="px-4 py-3 font-mono text-slate-300">{inst.tick_size}</td>
                <td className="px-4 py-3 font-mono text-slate-300">
                  ${inst.tick_value.toFixed(2)}
                </td>
                <td className="px-4 py-3 font-mono text-slate-300">{inst.multiplier}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
