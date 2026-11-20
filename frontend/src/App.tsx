import { lazy, Suspense, useState, type ComponentType } from 'react'
import { usePoll } from './ui'

const P = (f: () => Promise<{ default: ComponentType }>) => lazy(f)
const NAV: { name: string; page: ComponentType }[] = [
  { name: 'Overview', page: P(() => import('./pages/Overview')) },
  { name: 'AI Command Centre', page: P(() => import('./pages/Command')) },
  { name: 'Market Scanner', page: P(() => import('./pages/Overview')) },
  { name: 'Market Data', page: P(() => import('./pages/MarketData')) },
  { name: 'Strategy Lab', page: P(() => import('./pages/Strategy')) },
  { name: 'Backtesting', page: P(() => import('./pages/Backtesting')) },
  { name: 'AI Quant Research', page: P(() => import('./pages/Research')) },
  { name: 'Paper Trading', page: P(() => import('./pages/Paper')) },
  { name: 'Live Trading', page: P(() => import('./pages/Live')) },
  { name: 'Portfolio', page: P(() => import('./pages/Paper')) },
  { name: 'Broker Connections', page: P(() => import('./pages/Brokers')) },
  { name: 'Wallet & Funds', page: P(() => import('./pages/Wallet')) },
  { name: 'Profit Manager', page: P(() => import('./pages/Profit')) },
  { name: 'Survival Engine', page: P(() => import('./pages/Survival')) },
  { name: 'Agent Management', page: P(() => import('./pages/Agents')) },
  { name: 'Reports', page: P(() => import('./pages/Reports')) },
  { name: 'Security & Audit', page: P(() => import('./pages/Security')) },
  { name: 'Settings', page: P(() => import('./pages/Settings')) },
]

export default function App() {
  const [active, setActive] = useState('Overview')
  const [open, setOpen] = useState(false)
  const status = usePoll<{ kill_switch: boolean; live_trading_allowed: boolean }>('/api/system/status', 5000)
  const Page = NAV.find(n => n.name === active)!.page
  const signedIn = !!sessionStorage.getItem('clab_token')
  return (
    <div className="flex min-h-screen">
      <aside className={`${open ? 'block' : 'hidden'} fixed inset-y-0 z-20 w-64 shrink-0 overflow-y-auto border-r border-edge bg-panel p-4 md:static md:block`}>
        <div className="mb-6"><div className="text-lg font-bold text-white">Cloudisoft</div><div className="text-xs text-slate-400">AI Trading Lab</div></div>
        <nav className="space-y-0.5">{NAV.map(n => (
          <button key={n.name} onClick={() => { setActive(n.name); setOpen(false) }} className={`block w-full rounded-lg px-3 py-1.5 text-left text-sm ${active === n.name ? 'bg-accent/20 text-white' : 'text-slate-400 hover:bg-edge/60'}`}>{n.name}</button>))}</nav>
      </aside>
      <main className="min-w-0 flex-1 p-4 md:p-6">
        <header className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2"><button className="rounded border border-edge px-2 md:hidden" onClick={() => setOpen(!open)}>☰</button><h1 className="text-xl font-semibold text-white">{active}</h1></div>
          <div className="flex flex-wrap gap-2 text-xs">
            <span className="rounded-full bg-accent/20 px-3 py-1 font-semibold text-accent">MODE: PAPER</span>
            <span className={`rounded-full px-3 py-1 font-semibold ${status.data?.live_trading_allowed ? 'bg-loss/20 text-loss' : 'bg-edge text-slate-400'}`}>LIVE: {status.data?.live_trading_allowed ? 'ENABLED' : 'DISABLED'}</span>
            {status.data?.kill_switch && <span className="rounded-full bg-loss px-3 py-1 font-semibold text-white">KILL SWITCH ENGAGED</span>}
            {!signedIn && <button onClick={() => setActive('Security & Audit')} className="rounded-full border border-warn/50 px-3 py-1 text-warn">Owner sign-in →</button>}
          </div>
        </header>
        <Suspense fallback={<p className="text-slate-500">Loading…</p>}><Page /></Suspense>
      </main>
    </div>
  )
}
