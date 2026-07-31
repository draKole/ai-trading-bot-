import { useCallback, useEffect, useMemo, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { getMode, switchMode, killSwitch, type ModeState } from "../api/live-trading";
import { StatusPill } from "./TerminalUI";

type NavItem = { path: string; label: string; icon: string };
type NavGroup = { label: string; items: NavItem[] };

const navGroups: NavGroup[] = [
  {
    label: "Workspace",
    items: [
      { path: "/", label: "Overview", icon: "◫" },
      { path: "/charts", label: "Charts", icon: "⌁" },
      { path: "/instruments", label: "Instruments", icon: "≡" },
      { path: "/data-import", label: "Data Import", icon: "↓" },
      { path: "/backtesting", label: "Backtesting", icon: "⟲" },
    ],
  },
  {
    label: "Execution",
    items: [
      { path: "/paper-trading", label: "Paper Trading", icon: "▣" },
      { path: "/live-trading", label: "Live Trading", icon: "●" },
      { path: "/signals", label: "Signals", icon: "ϟ" },
      { path: "/accounts", label: "Accounts", icon: "▤" },
    ],
  },
  {
    label: "Oversight",
    items: [
      { path: "/monitor", label: "Live Monitor", icon: "◉" },
      { path: "/analytics", label: "Analytics", icon: "⌇" },
      { path: "/risk", label: "Risk Center", icon: "◇" },
      { path: "/audit", label: "Audit Log", icon: "≣" },
      { path: "/settings", label: "Settings", icon: "⚙" },
    ],
  },
];

export default function Layout() {
  const location = useLocation();
  const [modeState, setModeState] = useState<ModeState | null>(null);
  const [showConfirm, setShowConfirm] = useState(false);
  const [switchTarget, setSwitchTarget] = useState<string | null>(null);
  const [switchLoading, setSwitchLoading] = useState(false);
  const [error, setError] = useState("");

  const fetchMode = useCallback(async () => {
    try {
      const state = await getMode();
      setModeState(state);
      setError("");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to fetch mode");
    }
  }, []);

  useEffect(() => {
    fetchMode();
    const interval = setInterval(fetchMode, 10_000);
    return () => clearInterval(interval);
  }, [fetchMode]);

  const isKilled = modeState?.is_killed ?? false;
  const isLive = modeState?.is_live ?? false;
  const mode = modeState?.mode?.toUpperCase() ?? "PAPER";
  const currentPage = useMemo(
    () => navGroups.flatMap((group) => group.items).find((item) => item.path === location.pathname)?.label ?? "Trading Workspace",
    [location.pathname],
  );

  function handleSwitch(target: string) {
    setSwitchTarget(target);
    setShowConfirm(true);
  }

  async function handleConfirmSwitch() {
    if (!switchTarget) return;
    setSwitchLoading(true);
    setError("");
    try {
      await switchMode(switchTarget, true);
      await fetchMode();
      setShowConfirm(false);
      setSwitchTarget(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Switch failed");
    } finally {
      setSwitchLoading(false);
    }
  }

  async function handleKill() {
    if (!window.confirm("ACTIVATE GLOBAL KILL SWITCH?\n\nThis will halt ALL trading for this session. This action is IRREVERSIBLE.\n\nAre you sure?")) return;
    setSwitchLoading(true);
    setError("");
    try {
      await killSwitch();
      await fetchMode();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Kill switch failed");
    } finally {
      setSwitchLoading(false);
    }
  }

  return (
    <div className="flex h-screen min-w-[768px] overflow-hidden bg-slate-950 text-slate-100">
      <aside className="flex w-[72px] shrink-0 flex-col border-r border-slate-800 bg-slate-950 lg:w-64">
        <div className="flex h-[72px] items-center border-b border-slate-800 px-4">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-emerald-900 bg-emerald-950/60 font-mono text-sm font-bold text-emerald-400">D</div>
          <div className="ml-3 hidden min-w-0 lg:block">
            <h1 className="truncate text-sm font-semibold tracking-wide text-slate-100">DRAKE</h1>
            <p className="truncate text-[11px] uppercase tracking-[0.14em] text-slate-500">Trading Terminal</p>
          </div>
        </div>

        <nav className="flex-1 space-y-5 overflow-y-auto px-2 py-4 lg:px-3" aria-label="Main navigation">
          {navGroups.map((group) => (
            <div key={group.label}>
              <div className="mb-1 hidden px-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-600 lg:block">{group.label}</div>
              <div className="space-y-0.5">
                {group.items.map((item) => (
                  <NavLink
                    key={item.path}
                    to={item.path}
                    end={item.path === "/"}
                    title={item.label}
                    className={({ isActive }) =>
                      `group flex items-center rounded-md px-2.5 py-2.5 text-sm transition-colors lg:gap-3 ${
                        isActive
                          ? "bg-slate-800 text-slate-50 shadow-[inset_2px_0_0_0_rgb(16_185_129)]"
                          : "text-slate-500 hover:bg-slate-900 hover:text-slate-200"
                      }`
                    }
                  >
                    <span className="flex h-5 w-5 shrink-0 items-center justify-center font-mono text-base leading-none text-current" aria-hidden="true">{item.icon}</span>
                    <span className="hidden truncate lg:block">{item.label}</span>
                  </NavLink>
                ))}
              </div>
            </div>
          ))}
        </nav>

        <div className="border-t border-slate-800 p-2.5 lg:p-3">
          <div className="rounded-md border border-slate-800 bg-slate-900/60 p-2.5 lg:p-3">
            <div className="flex items-center justify-center gap-2 lg:justify-between">
              <span className="flex items-center gap-2">
                <span className={`h-2 w-2 rounded-full ${isKilled ? "bg-slate-500" : isLive ? "animate-pulse bg-red-500" : "bg-amber-400"}`} />
                <span className="hidden text-xs text-slate-400 lg:block">Execution</span>
              </span>
              <span className="hidden lg:block">
                <StatusPill tone={isKilled ? "neutral" : isLive ? "danger" : "warning"}>{isKilled ? "KILLED" : mode}</StatusPill>
              </span>
            </div>
            {!isKilled && (
              <div className="mt-2 flex flex-col gap-1 lg:hidden">
                <button
                  onClick={() => handleSwitch(isLive ? "paper" : "live")}
                  disabled={switchLoading}
                  title={isLive ? "Switch to PAPER mode" : "Switch to LIVE mode"}
                  className={`rounded border py-1.5 text-xs font-semibold transition-colors disabled:opacity-40 ${
                    isLive ? "border-amber-800 text-amber-300 hover:bg-amber-950/50" : "border-red-900 text-red-300 hover:bg-red-950/50"
                  }`}
                >
                  ↔
                </button>
                <button
                  onClick={handleKill}
                  disabled={switchLoading}
                  title="Activate global kill switch"
                  className="rounded border border-red-900 py-1.5 text-xs font-semibold text-red-400 transition-colors hover:bg-red-950/60 disabled:opacity-40"
                >
                  !
                </button>
              </div>
            )}
            <div className="mt-2 hidden space-y-2 lg:block">
              {!isKilled ? (
                <>
                  <button
                    onClick={() => handleSwitch(isLive ? "paper" : "live")}
                    disabled={switchLoading}
                    className={`w-full rounded border px-2 py-1.5 text-xs font-medium transition-colors disabled:opacity-40 ${
                      isLive ? "border-amber-800 text-amber-300 hover:bg-amber-950/50" : "border-red-900 text-red-300 hover:bg-red-950/50"
                    }`}
                  >
                    {isLive ? "Switch to PAPER" : "Switch to LIVE"}
                  </button>
                  <button
                    onClick={handleKill}
                    disabled={switchLoading}
                    className="w-full rounded border border-red-900 px-2 py-1.5 text-xs font-medium text-red-400 transition-colors hover:bg-red-950/60 disabled:opacity-40"
                  >
                    KILL SWITCH
                  </button>
                </>
              ) : (
                <p className="text-center text-[11px] leading-4 text-slate-500">Trading halted for this session.</p>
              )}
            </div>
          </div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <header className="flex h-[72px] shrink-0 items-center justify-between border-b border-slate-800 bg-slate-950/90 px-5 lg:px-7">
          <div>
            <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-600">Terminal / {currentPage}</div>
            <div className="mt-0.5 text-sm font-medium text-slate-200">{currentPage}</div>
          </div>
          <div className="flex items-center gap-3">
            {error && <span className="hidden max-w-xs truncate text-xs text-red-400 xl:block">Mode status unavailable</span>}
            <div className="hidden h-5 w-px bg-slate-800 sm:block" />
            <span className="font-mono text-[11px] text-slate-500">SYSTEM ONLINE</span>
            <StatusPill tone={isKilled ? "neutral" : isLive ? "danger" : "warning"}>{isKilled ? "KILLED" : mode}</StatusPill>
          </div>
        </header>
        <main className="min-w-0 flex-1 overflow-auto">
          <div className="mx-auto w-full max-w-[1600px] p-5 lg:p-7"><Outlet /></div>
        </main>
      </div>

      {showConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4 backdrop-blur-sm" role="dialog" aria-modal="true" aria-labelledby="mode-confirm-title">
          <div className="w-full max-w-md rounded-lg border border-slate-700 bg-slate-900 p-6 shadow-2xl">
            <div className="mb-1 text-[11px] font-semibold uppercase tracking-[0.15em] text-slate-500">Execution control</div>
            <h3 id="mode-confirm-title" className="text-lg font-semibold text-slate-100">
              {switchTarget === "live" ? "Switch to LIVE Trading" : "Switch to PAPER Trading"}
            </h3>
            <p className="mt-3 text-sm leading-6 text-slate-400">
              {switchTarget === "live"
                ? "This will enable LIVE broker connectivity. Real orders may be sent to the market. Confirm that risk controls are configured before proceeding."
                : "This will disable live broker connectivity. All orders will be simulated in PAPER mode."}
            </p>
            {error && <div className="mt-4 rounded border border-red-800 bg-red-950/40 px-3 py-2 text-xs text-red-300">{error}</div>}
            <div className="mt-6 flex gap-3">
              <button
                onClick={handleConfirmSwitch}
                disabled={switchLoading}
                className={`flex-1 rounded-md px-4 py-2.5 text-sm font-semibold transition-colors disabled:opacity-50 ${
                  switchTarget === "live" ? "bg-red-700 text-red-50 hover:bg-red-600" : "bg-amber-700 text-amber-50 hover:bg-amber-600"
                }`}
              >
                {switchLoading ? "Switching…" : `Confirm ${switchTarget === "live" ? "LIVE" : "PAPER"}`}
              </button>
              <button
                onClick={() => { setShowConfirm(false); setSwitchTarget(null); setError(""); }}
                disabled={switchLoading}
                className="flex-1 rounded-md border border-slate-600 px-4 py-2.5 text-sm font-medium text-slate-300 transition-colors hover:bg-slate-800 disabled:opacity-50"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
