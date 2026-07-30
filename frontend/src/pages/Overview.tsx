import { useEffect, useState } from 'react'
import { getHealth } from '../api/health'

export default function Overview() {
  const [health, setHealth] = useState<any>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch((err) => setError(err.message))
  }, [])

  return (
    <div className="p-6">
      <h2 className="text-2xl font-bold mb-4">Overview</h2>

      {error && (
        <div className="rounded border border-red-700 bg-red-950 p-4">
          Error: {error}
        </div>
      )}

      {health && (
        <div className="rounded border border-green-700 bg-slate-900 p-6 space-y-2">
          <p><strong>Overall:</strong> {health.overall}</p>

          <p>
            <strong>Database:</strong>{" "}
            {health.components?.database?.status ?? "Unknown"}
          </p>

          <p>
            <strong>Workers:</strong>{" "}
            {health.components?.workers?.status ?? "Unknown"}
          </p>

          <p>
            <strong>Broker:</strong>{" "}
            {health.components?.broker?.status ?? "Unknown"}
          </p>

          <p>
            <strong>Live Trading:</strong>{" "}
            {health.components?.live_trading?.status ?? "Unknown"}
          </p>

          <p>
            <strong>Paper Trading:</strong>{" "}
            {health.components?.paper_trading?.status ?? "Unknown"}
          </p>

          <p>
            <strong>Market Data:</strong>{" "}
            {health.components?.market_data?.status ?? "Unknown"}
          </p>
        </div>
      )}

    </div>
  )
}
