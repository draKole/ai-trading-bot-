import { useState, useEffect, useCallback } from "react";
import {
  startSession,
  getAccountSummary,
  placeOrder,
  listOrders,
  cancelOrder,
  listPositions,
  listTrades,
  type AccountSummary,
  type PaperOrder,
  type PaperPosition,
  type PaperTrade,
} from "../api/paper-trading";

/* ─── Constants ─────────────────────────────────────── */

const INSTRUMENTS = ["ES", "NQ", "MNQ"];
const ORDER_TYPES = ["market", "limit", "stop"];
const SIDES = ["buy", "sell"];

/* ─── Formatting ─────────────────────────────────────── */

function fmt(n: number, dec = 2): string {
  if (n === 0) return "0.00";
  const abs = Math.abs(n);
  if (abs >= 1_000_000) return (n / 1_000_000).toFixed(dec) + "M";
  if (abs >= 1_000) return (n / 1_000).toFixed(dec) + "K";
  return n.toFixed(dec);
}

function fmtPnl(n: number): string {
  const sign = n >= 0 ? "+" : "";
  return `${sign}$${fmt(n)}`;
}

function fmtPct(n: number): string {
  return (n >= 0 ? "+" : "") + n.toFixed(2) + "%";
}

function pnlColor(n: number): string {
  if (n > 0) return "text-emerald-400";
  if (n < 0) return "text-red-400";
  return "text-slate-400";
}

/* ─── Page ──────────────────────────────────────────── */

export default function PaperTrading() {
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [account, setAccount] = useState<AccountSummary | null>(null);
  const [positions, setPositions] = useState<PaperPosition[]>([]);
  const [orders, setOrders] = useState<PaperOrder[]>([]);
  const [trades, setTrades] = useState<PaperTrade[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Order entry form
  const [oeInstrument, setOeInstrument] = useState("ES");
  const [oeSide, setOeSide] = useState("buy");
  const [oeType, setOeType] = useState("market");
  const [oeQty, setOeQty] = useState(1);
  const [oePrice, setOePrice] = useState("");
  const [oeStopPrice, setOeStopPrice] = useState("");
  const [orderError, setOrderError] = useState<string | null>(null);

  /* ─── Auto-start session ──────────────────────── */

  useEffect(() => {
    async function init() {
      try {
        const sess = await startSession("Paper Account", 100000);
        setSessionId(sess.session_id);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to start session");
      }
    }
    init();
  }, []);

  /* ─── Poll data ────────────────────────────────── */

  const refresh = useCallback(async () => {
    if (!sessionId) return;
    try {
      const [acc, pos, ord, trd] = await Promise.all([
        getAccountSummary(sessionId),
        listPositions(sessionId),
        listOrders(sessionId),
        listTrades(sessionId),
      ]);
      setAccount(acc);
      setPositions(pos.positions);
      setOrders(ord.orders);
      setTrades(trd.trades);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Refresh failed");
    }
  }, [sessionId]);

  useEffect(() => {
    if (!sessionId) return;
    refresh();
    const interval = setInterval(refresh, 3000);
    return () => clearInterval(interval);
  }, [sessionId, refresh]);

  /* ─── Place order ──────────────────────────────── */

  const handlePlaceOrder = async () => {
    if (!sessionId) return;
    setOrderError(null);
    setLoading(true);
    try {
      await placeOrder({
        session_id: sessionId,
        order_type: oeType,
        side: oeSide,
        instrument: oeInstrument,
        quantity: oeQty,
        price: oePrice ? parseFloat(oePrice) : undefined,
        stop_price: oeStopPrice ? parseFloat(oeStopPrice) : undefined,
        // Use a simulated current price for market fills
        current_price: oeType === "market" ? (oeInstrument === "NQ" || oeInstrument === "MNQ" ? 20000 : 5500) : undefined,
      });
      await refresh();
    } catch (e) {
      setOrderError(e instanceof Error ? e.message : "Order failed");
    } finally {
      setLoading(false);
    }
  };

  /* ─── Cancel order ─────────────────────────────── */

  const handleCancel = async (orderId: number) => {
    if (!sessionId) return;
    try {
      await cancelOrder(orderId);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Cancel failed");
    }
  };

  /* ─── Render ───────────────────────────────────── */

  const openOrders = orders.filter((o) => o.status === "pending");
  const filledOrders = orders.filter((o) => o.status === "filled");
  const openPositions = positions.filter((p) => p.status === "open");

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-100">Paper Trading</h2>
          <p className="text-sm text-slate-500 mt-1">
            Simulated trading with real order execution logic.
          </p>
        </div>
        {account && (
          <div className="flex items-center gap-2">
            <span
              className={`inline-block h-2.5 w-2.5 rounded-full ${
                account.status === "running" ? "bg-emerald-500" : "bg-slate-500"
              }`}
            />
            <span className="text-sm text-slate-400">
              {account.status?.toUpperCase()}
            </span>
          </div>
        )}
      </div>

      {/* ─── Error ─────────────────────────────── */}
      {error && (
        <div className="bg-red-900/30 border border-red-800 rounded-lg p-3">
          <p className="text-red-400 text-sm">{error}</p>
        </div>
      )}

      {/* ─── Account Summary ───────────────────── */}
      {account && (
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
          <SummaryCard label="Balance" value={`$${fmt(account.balance)}`} />
          <SummaryCard
            label="Total P&L"
            value={fmtPnl(account.total_pnl)}
            color={pnlColor(account.total_pnl)}
          />
          <SummaryCard
            label="Return"
            value={fmtPct(account.total_return_pct)}
            color={pnlColor(account.total_return_pct)}
          />
          <SummaryCard
            label="Realized P&L"
            value={fmtPnl(account.realized_pnl)}
            color={pnlColor(account.realized_pnl)}
          />
          <SummaryCard
            label="Unrealized P&L"
            value={fmtPnl(account.unrealized_pnl)}
            color={pnlColor(account.unrealized_pnl)}
          />
          <SummaryCard
            label="Buying Power"
            value={`$${fmt(account.buying_power)}`}
          />
          <SummaryCard
            label="Open Positions"
            value={`${account.open_positions_count}`}
          />
          <SummaryCard
            label="Initial Balance"
            value={`$${fmt(account.initial_balance)}`}
          />
        </div>
      )}

      {/* ─── Order Entry ───────────────────────── */}
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-5">
        <h3 className="text-lg font-semibold text-slate-200 mb-4">
          Place Order
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3 items-end">
          <div>
            <label className="block text-xs text-slate-500 mb-1">Symbol</label>
            <div className="flex gap-1">
              {INSTRUMENTS.map((sym) => (
                <button
                  key={sym}
                  onClick={() => setOeInstrument(sym)}
                  className={`px-3 py-1.5 text-xs rounded font-mono ${
                    oeInstrument === sym
                      ? "bg-emerald-600/30 text-emerald-400 border border-emerald-500/50"
                      : "bg-slate-800 text-slate-400 border border-slate-700 hover:border-slate-600"
                  }`}
                >
                  {sym}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">Side</label>
            <div className="flex gap-1">
              {SIDES.map((s) => (
                <button
                  key={s}
                  onClick={() => setOeSide(s)}
                  className={`px-4 py-1.5 text-xs rounded uppercase font-medium ${
                    oeSide === s
                      ? s === "buy"
                        ? "bg-emerald-600/30 text-emerald-400 border border-emerald-500/50"
                        : "bg-red-600/30 text-red-400 border border-red-500/50"
                      : "bg-slate-800 text-slate-400 border border-slate-700 hover:border-slate-600"
                  }`}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">Type</label>
            <select
              value={oeType}
              onChange={(e) => setOeType(e.target.value)}
              className="w-full bg-slate-800 border border-slate-700 rounded px-2 py-1.5 text-sm text-slate-200"
            >
              {ORDER_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t.charAt(0).toUpperCase() + t.slice(1)}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">Qty</label>
            <input
              type="number"
              value={oeQty}
              onChange={(e) => setOeQty(Math.max(1, +e.target.value))}
              min={1}
              className="w-full bg-slate-800 border border-slate-700 rounded px-2 py-1.5 text-sm text-slate-200"
            />
          </div>
          {(oeType === "limit" || oeType === "stop") && (
            <div>
              <label className="block text-xs text-slate-500 mb-1">
                {oeType === "limit" ? "Limit $" : "Stop $"}
              </label>
              <input
                type="number"
                value={oeType === "limit" ? oePrice : oeStopPrice}
                onChange={(e) =>
                  oeType === "limit"
                    ? setOePrice(e.target.value)
                    : setOeStopPrice(e.target.value)
                }
                step={0.25}
                className="w-full bg-slate-800 border border-slate-700 rounded px-2 py-1.5 text-sm text-slate-200"
              />
            </div>
          )}
          <div>
            <button
              onClick={handlePlaceOrder}
              disabled={loading}
              className={`w-full px-4 py-1.5 rounded text-sm font-medium transition-colors ${
                oeSide === "buy"
                  ? "bg-emerald-600 hover:bg-emerald-500 text-white"
                  : "bg-red-600 hover:bg-red-500 text-white"
              } disabled:opacity-50 disabled:cursor-not-allowed`}
            >
              {loading ? "..." : oeSide === "buy" ? "Buy" : "Sell"}
            </button>
          </div>
        </div>
        {orderError && (
          <p className="mt-2 text-sm text-red-400">{orderError}</p>
        )}
      </div>

      {/* ─── Positions Table ────────────────────── */}
      <div>
        <h3 className="text-lg font-semibold text-slate-200 mb-3">
          Positions ({openPositions.length})
        </h3>
        {openPositions.length === 0 ? (
          <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 text-center text-slate-500 text-sm">
            No open positions
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-700 text-slate-500 text-left">
                  <th className="py-2 px-3 font-medium">Symbol</th>
                  <th className="py-2 px-3 font-medium">Side</th>
                  <th className="py-2 px-3 font-medium text-right">Size</th>
                  <th className="py-2 px-3 font-medium text-right">Entry</th>
                  <th className="py-2 px-3 font-medium text-right">Mark</th>
                  <th className="py-2 px-3 font-medium text-right">Unreal. P&L</th>
                  <th className="py-2 px-3 font-medium text-right">Real. P&L</th>
                </tr>
              </thead>
              <tbody>
                {openPositions.map((p) => (
                  <tr
                    key={p.id}
                    className="border-b border-slate-800 hover:bg-slate-800/50"
                  >
                    <td className="py-2 px-3 font-mono text-slate-200">
                      {p.instrument}
                    </td>
                    <td
                      className={`py-2 px-3 font-medium uppercase ${
                        p.direction === "long"
                          ? "text-emerald-400"
                          : "text-red-400"
                      }`}
                    >
                      {p.direction}
                    </td>
                    <td className="py-2 px-3 text-right font-mono text-slate-300">
                      {p.quantity}
                    </td>
                    <td className="py-2 px-3 text-right font-mono text-slate-300">
                      {fmt(p.avg_entry_price, 2)}
                    </td>
                    <td className="py-2 px-3 text-right font-mono text-slate-400">
                      {fmt(p.current_price, 2)}
                    </td>
                    <td
                      className={`py-2 px-3 text-right font-mono font-medium ${pnlColor(p.unrealized_pnl)}`}
                    >
                      {fmtPnl(p.unrealized_pnl)}
                    </td>
                    <td className="py-2 px-3 text-right font-mono text-slate-400">
                      {fmtPnl(p.realized_pnl)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ─── Open Orders Table ──────────────────── */}
      <div>
        <h3 className="text-lg font-semibold text-slate-200 mb-3">
          Open Orders ({openOrders.length})
        </h3>
        {openOrders.length === 0 ? (
          <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 text-center text-slate-500 text-sm">
            No open orders
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-700 text-slate-500 text-left">
                  <th className="py-2 px-3 font-medium">Type</th>
                  <th className="py-2 px-3 font-medium">Side</th>
                  <th className="py-2 px-3 font-medium">Symbol</th>
                  <th className="py-2 px-3 font-medium text-right">Qty</th>
                  <th className="py-2 px-3 font-medium text-right">Price</th>
                  <th className="py-2 px-3 font-medium">Status</th>
                  <th className="py-2 px-3 font-medium"></th>
                </tr>
              </thead>
              <tbody>
                {openOrders.map((o) => (
                  <tr
                    key={o.id}
                    className="border-b border-slate-800 hover:bg-slate-800/50"
                  >
                    <td className="py-2 px-3 text-slate-300 capitalize">
                      {o.order_type}
                    </td>
                    <td
                      className={`py-2 px-3 font-medium uppercase ${
                        o.side === "buy" ? "text-emerald-400" : "text-red-400"
                      }`}
                    >
                      {o.side}
                    </td>
                    <td className="py-2 px-3 font-mono text-slate-200">
                      {o.instrument}
                    </td>
                    <td className="py-2 px-3 text-right font-mono text-slate-300">
                      {o.quantity}
                    </td>
                    <td className="py-2 px-3 text-right font-mono text-slate-300">
                      {o.price ?? o.stop_price ?? "—"}
                    </td>
                    <td className="py-2 px-3">
                      <span className="inline-flex items-center gap-1 text-amber-400 text-xs">
                        <span className="inline-block h-1.5 w-1.5 rounded-full bg-amber-400" />
                        {o.status}
                      </span>
                    </td>
                    <td className="py-2 px-3">
                      <button
                        onClick={() => handleCancel(o.id)}
                        className="text-xs text-red-400 hover:text-red-300"
                      >
                        Cancel
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ─── Recent Trades ──────────────────────── */}
      <div>
        <h3 className="text-lg font-semibold text-slate-200 mb-3">
          Recent Trades ({trades.length})
        </h3>
        {trades.length === 0 ? (
          <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 text-center text-slate-500 text-sm">
            No trades yet
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-700 text-slate-500 text-left">
                  <th className="py-2 px-3 font-medium">Symbol</th>
                  <th className="py-2 px-3 font-medium">Side</th>
                  <th className="py-2 px-3 font-medium text-right">Qty</th>
                  <th className="py-2 px-3 font-medium text-right">Fill $</th>
                  <th className="py-2 px-3 font-medium text-right">Comm.</th>
                  <th className="py-2 px-3 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {trades.slice(0, 50).map((t) => (
                  <tr
                    key={t.id}
                    className="border-b border-slate-800 hover:bg-slate-800/50"
                  >
                    <td className="py-2 px-3 font-mono text-slate-200">
                      {t.instrument}
                    </td>
                    <td
                      className={`py-2 px-3 font-medium uppercase ${
                        t.side === "buy" ? "text-emerald-400" : "text-red-400"
                      }`}
                    >
                      {t.side}
                    </td>
                    <td className="py-2 px-3 text-right font-mono text-slate-300">
                      {t.filled_qty || t.quantity}
                    </td>
                    <td className="py-2 px-3 text-right font-mono text-slate-300">
                      {t.fill_price ? fmt(t.fill_price, 2) : "—"}
                    </td>
                    <td className="py-2 px-3 text-right font-mono text-slate-500">
                      ${fmt(t.commission)}
                    </td>
                    <td className="py-2 px-3">
                      <span
                        className={`text-xs ${
                          t.status === "filled"
                            ? "text-emerald-400"
                            : "text-slate-500"
                        }`}
                      >
                        {t.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

/* ─── Summary Card ────────────────────────────────── */

function SummaryCard({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color?: string;
}) {
  return (
    <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-3">
      <div className="text-xs text-slate-500 mb-0.5 uppercase tracking-wider">
        {label}
      </div>
      <div
        className={`text-base font-bold font-mono ${color ?? "text-slate-200"}`}
      >
        {value}
      </div>
    </div>
  );
}
