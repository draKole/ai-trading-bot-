import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Overview from './pages/Overview'
import Accounts from './pages/Accounts'
import LiveMonitor from './pages/LiveMonitor'
import Signals from './pages/Signals'
import Analytics from './pages/Analytics'
import RiskCenter from './pages/RiskCenter'
import Settings from './pages/Settings'
import Charts from './pages/Charts'
import DataImport from './pages/DataImport'
import Instruments from './pages/Instruments'
import Backtesting from './pages/Backtesting'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Overview />} />
        <Route path="/accounts" element={<Accounts />} />
        <Route path="/monitor" element={<LiveMonitor />} />
        <Route path="/signals" element={<Signals />} />
        <Route path="/analytics" element={<Analytics />} />
        <Route path="/risk" element={<RiskCenter />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/charts" element={<Charts />} />
        <Route path="/data-import" element={<DataImport />} />
        <Route path="/instruments" element={<Instruments />} />
        <Route path="/backtesting" element={<Backtesting />} />
      </Route>
    </Routes>
  )
}
