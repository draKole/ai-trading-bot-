import { useEffect, useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'

const navItems = [
  { path: '/', label: 'Overview', icon: '📊' },
  { path: '/charts', label: 'Charts', icon: '📈' },
  { path: '/instruments', label: 'Instruments', icon: '📋' },
  { path: '/data-import', label: 'Data Import', icon: '📥' },
  { path: '/backtesting', label: 'Backtesting', icon: '🧪' },
  { path: '/monitor', label: 'Live Monitor', icon: '📡' },
  { path: '/signals', label: 'Signals', icon: '⚡' },
  { path: '/accounts', label: 'Accounts', icon: '💼' },
  { path: '/analytics', label: 'Analytics', icon: '📉' },
  { path: '/risk', label: 'Risk Center', icon: '🛡️' },
  { path: '/settings', label: 'Settings', icon: '⚙️' },
]

async function fetchMode(): Promise<string> {
  try {
    const res = await fetch('/api/v1/monitoring/health');
    const data = await res.json();
    return data?.mode?.mode || 'PAPER';
  } catch {
    return 'PAPER';
  }
}

export default function Layout() {
  const [mode, setMode] = useState('PAPER');

  useEffect(() => {
    fetchMode().then(setMode);
  }, []);

  return (
    <div className="flex h-screen bg-slate-950 text-slate-100">
      <aside className="w-56 bg-slate-900 border-r border-slate-800 flex flex-col">
        <div className="p-4 border-b border-slate-800">
          <h1 className="text-lg font-bold text-green-500">Drake AI Trading</h1>
          <span className="text-xs text-slate-500">Sprint 3 — Backtesting</span>
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
        <div className="p-4 border-t border-slate-800 text-xs">
          <div className="flex items-center gap-2">
            <span
              className={`inline-block h-2 w-2 rounded-full ${
                mode === 'LIVE'
                  ? 'bg-red-500'
                  : mode === 'PAPER'
                    ? 'bg-amber-500'
                    : 'bg-slate-500'
              }`}
            />
            <span className="text-slate-400">
              Mode: <span className="font-medium text-slate-300">{mode}</span>
            </span>
          </div>
        </div>
      </aside>
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
