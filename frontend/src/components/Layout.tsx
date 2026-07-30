import { useEffect, useState, useCallback } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { getMode, switchMode, killSwitch, type ModeState } from '../api/live-trading'

const navItems = [
  { path: '/', label: 'Overview', icon: '📊' },
  { path: '/charts', label: 'Charts', icon: '📈' },
  { path: '/instruments', label: 'Instruments', icon: '📋' },
  { path: '/data-import', label: 'Data Import', icon: '📥' },
  { path: '/backtesting', label: 'Backtesting', icon: '🧪' },
  { path: '/paper-trading', label: 'Paper Trading', icon: '📝' },
  { path: '/live-trading', label: 'Live Trading', icon: '🔴' },
  { path: '/monitor', label: 'Live Monitor', icon: '📡' },
  { path: '/signals', label: 'Signals', icon: '⚡' },
  { path: '/accounts', label: 'Accounts', icon: '💼' },
  { path: '/analytics', label: 'Analytics', icon: '📉' },
  { path: '/risk', label: 'Risk Center', icon: '🛡️' },
  { path: '/audit', label: 'Audit Log', icon: '📜' },
  { path: '/settings', label: 'Settings', icon: '⚙️' },
]

export default function Layout() {
  const [modeState, setModeState] = useState<ModeState | null>(null)
  const [isKilled, setIsKilled] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)
  const [switchTarget, setSwitchTarget] = useState<string | null>(null)
  const [switchLoading, setSwitchLoading] = useState(false)
  const [error, setError] = useState('')

  const fetchMode = useCallback(async () => {
    try {
      const state = await getMode()
      setModeState(state)
      setIsKilled(state.is_killed ?? false)
      setError('')
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to fetch mode')
    }
  }, [])

  useEffect(() => {
    fetchMode()
    const interval = setInterval(fetchMode, 10_000)
    return () => clearInterval(interval)
  }, [fetchMode])

  const mode = modeState?.mode ?? 'PAPER'
  const isLive = mode === 'live'

  async function handleSwitch(target: string) {
    setSwitchTarget(target)
    setShowConfirm(true)
  }

  async function handleConfirmSwitch() {
    if (!switchTarget) return
    setSwitchLoading(true)
    setError('')
    try {
      await switchMode(switchTarget, true)
      await fetchMode()
      setShowConfirm(false)
      setSwitchTarget(null)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Switch failed')
    } finally {
      setSwitchLoading(false)
    }
  }

  async function handleKill() {
    if (!window.confirm('⚠️ ACTIVATE GLOBAL KILL SWITCH?\n\nThis will halt ALL trading for this session. This action is IRREVERSIBLE.\n\nAre you sure?')) return
    setSwitchLoading(true)
    setError('')
    try {
      await killSwitch()
      await fetchMode()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Kill switch failed')
    } finally {
      setSwitchLoading(false)
    }
  }

  return (
    <div className="flex h-screen bg-slate-950 text-slate-100">
      {/* Sidebar */}
      <aside className="w-56 bg-slate-900 border-r border-slate-800 flex flex-col">
        <div className="p-4 border-b border-slate-800">
          <h1 className="text-lg font-bold text-green-500">Drake AI Trading</h1>
          <span className="text-xs text-slate-500">Sprint 5 — Live Trading</span>
        </div>

        <nav className="flex-1 p-2 space-y-1 overflow-y-auto">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded text-sm transition-colors ${
                  isActive
                    ? 'bg-slate-800 text-green-400 font-medium'
                    : 'text-slate-400 hover:bg-slate-800/50 hover:text-slate-200'
                }`
              }
            >
              <span>{item.icon}</span>
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        {/* Mode indicator footer */}
        <div className="p-3 border-t border-slate-800 space-y-2">
          {/* Mode badge with toggle */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span
                className={`inline-block h-2.5 w-2.5 rounded-full ${
                  isKilled
                    ? 'bg-gray-500'
                    : isLive
                      ? 'bg-red-500 animate-pulse'
                      : 'bg-amber-500'
                }`}
              />
              <span className="text-xs text-slate-400">
                {isKilled ? (
                  <span className="text-gray-400 font-medium">KILLED</span>
                ) : (
                  <>
                    Mode:{' '}
                    <span
                      className={`font-medium ${
                        isLive ? 'text-red-400' : 'text-amber-400'
                      }`}
                    >
                      {mode.toUpperCase()}
                    </span>
                  </>
                )}
              </span>
            </div>
            {!isKilled && (
              <button
                onClick={() => handleSwitch(isLive ? 'paper' : 'live')}
                disabled={switchLoading}
                className={`text-xs px-2 py-0.5 rounded border transition-colors disabled:opacity-40 ${
                  isLive
                    ? 'border-amber-700 text-amber-400 hover:bg-amber-900/40'
                    : 'border-red-700 text-red-400 hover:bg-red-900/40'
                }`}
                title={isLive ? 'Switch to PAPER mode' : 'Switch to LIVE mode'}
              >
                {isLive ? '↓ PAPER' : '↑ LIVE'}
              </button>
            )}
          </div>

          {/* Kill switch button */}
          {!isKilled && (
            <button
              onClick={handleKill}
              disabled={switchLoading}
              className="w-full text-xs px-2 py-1 rounded border border-red-800 text-red-500 hover:bg-red-950 transition-colors disabled:opacity-40"
            >
              ⚠ KILL SWITCH
            </button>
          )}

          {isKilled && (
            <div className="text-xs text-gray-500 text-center italic">
              Trading halted — reload to restore
            </div>
          )}
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        {/* Confirmation dialog */}
        {showConfirm && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
            <div className="bg-slate-800 border border-slate-700 rounded-lg p-6 max-w-sm w-full mx-4 shadow-2xl">
              <h3 className="text-lg font-semibold text-slate-100 mb-2">
                {switchTarget === 'live' ? '🔴 Switch to LIVE Trading' : '🟡 Switch to PAPER Trading'}
              </h3>
              <p className="text-sm text-slate-400 mb-4">
                {switchTarget === 'live'
                  ? 'This will enable LIVE broker connectivity. Real orders will be sent to the market. Proceed?'
                  : 'This will disable live broker connectivity. All orders will be simulated. Proceed?'}
              </p>
              {error && (
                <div className="mb-4 rounded border border-red-700 bg-red-950 px-3 py-2 text-xs text-red-400">
                  {error}
                </div>
              )}
              <div className="flex gap-3">
                <button
                  onClick={handleConfirmSwitch}
                  disabled={switchLoading}
                  className={`flex-1 rounded px-4 py-2 text-sm font-medium transition-colors disabled:opacity-50 ${
                    switchTarget === 'live'
                      ? 'bg-red-700 text-red-100 hover:bg-red-600'
                      : 'bg-amber-700 text-amber-100 hover:bg-amber-600'
                  }`}
                >
                  {switchLoading ? 'Switching…' : `Confirm ${switchTarget === 'live' ? 'LIVE' : 'PAPER'}`}
                </button>
                <button
                  onClick={() => {
                    setShowConfirm(false)
                    setSwitchTarget(null)
                    setError('')
                  }}
                  disabled={switchLoading}
                  className="flex-1 rounded border border-slate-600 px-4 py-2 text-sm text-slate-300 hover:bg-slate-700 transition-colors disabled:opacity-50"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}

        <Outlet />
      </main>
    </div>
  )
}
