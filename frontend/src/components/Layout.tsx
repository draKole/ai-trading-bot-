import { NavLink, Outlet } from 'react-router-dom'

const navItems = [
  { path: '/', label: 'Overview', icon: '📊' },
  { path: '/accounts', label: 'Accounts', icon: '💼' },
  { path: '/monitor', label: 'Live Monitor', icon: '📡' },
  { path: '/signals', label: 'Signals', icon: '⚡' },
  { path: '/analytics', label: 'Analytics', icon: '📈' },
  { path: '/risk', label: 'Risk Center', icon: '🛡️' },
  { path: '/settings', label: 'Settings', icon: '⚙️' },
]

export default function Layout() {
  return (
    <div className="flex h-screen bg-slate-950 text-slate-100">
      <aside className="w-56 bg-slate-900 border-r border-slate-800 flex flex-col">
        <div className="p-4 border-b border-slate-800">
          <h1 className="text-lg font-bold text-green-500">Drake AI Trading</h1>
          <span className="text-xs text-slate-500">Phase 0 — Foundation</span>
        </div>
        <nav className="flex-1 p-2 space-y-1">
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
        <div className="p-4 border-t border-slate-800 text-xs text-slate-600">
          Mode: PAPER | Status: Offline
        </div>
      </aside>
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
