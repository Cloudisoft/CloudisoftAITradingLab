import { useState, type ReactElement } from 'react'
import Backtesting from './pages/Backtesting'
import Overview from './pages/Overview'
import Paper from './pages/Paper'
import Security from './pages/Security'
import Survival from './pages/Survival'
import { usePoll } from './ui'

const NAV: { name: string; page?: () => ReactElement; milestone?: number }[] = [
  { name: 'Overview', page: Overview }, { name: 'AI Command Centre', milestone: 7 }, { name: 'Market Scanner', page: Overview },
  { name: 'Market Data', milestone: 6 }, { name: 'Strategy Lab', milestone: 8 }, { name: 'Backtesting', page: Backtesting },
  { name: 'AI Quant Research', milestone: 7 }, { name: 'Paper Trading', page: Paper }, { name: 'Live Trading', milestone: 10 },
  { name: 'Portfolio', page: Paper }, { name: 'Broker Connections', milestone: 10 }, { name: 'Wallet & Funds', milestone: 11 },
  { name: 'Profit Manager', milestone: 12 }, { name: 'Survival Engine', page: Survival }, { name: 'Agent Management', milestone: 13 },
  { name: 'Reports', milestone: 12 }, { name: 'Security & Audit', page: Security }, { name: 'Settings', milestone: 5 },
]

export default function App() {
  const [active, setActive] = useState('Overview')
  const [open, setOpen] = useState(false)
  const status = usePoll<{ kill_switch: boolean; live_trading_allowed: boolean }>('/api/system/status', 5000)
  const item = NAV.find(n => n.name === active)!
  const Page = item.page
  return (
    <div className="flex min-h-screen">
      <aside className={`${open ? 'block' : 'hidden'} fixed inset-y-0 z-20 w-64 shrink-0 overflow-y-auto border-r border-edge bg-panel p-4 md:static md:block`}>
        <div className="mb-6"><div className="text-lg font-bold text-white">Cloudisoft</div><div className="text-xs text-slate-400">AI Trading Lab</div></div>
        <nav className="space-y-0.5">{NAV.map(n => (
          <button key={n.name} onClick={() => { setActive(n.name); setOpen(false) }} className={`block w-full rounded-lg px-3 py-1.5 text-left text-sm ${active === n.name ? 'bg-accent/20 text-white' : 'text-slate-400 hover:bg-edge/60'}`}>
            {n.name}{!n.page && <span className="ml-1 text-[10px] text-slate-600">M{n.milestone}</span>}
          </button>))}</nav>
      </aside>
      <main className="min-w-0 flex-1 p-4 md:p-6">
        <header className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2"><button className="rounded border border-edge px-2 md:hidden" onClick={() => setOpen(!open)}>☰</button><h1 className="text-xl font-semibold text-white">{active}</h1></div>
          <div className="flex gap-2 text-xs">
            <span className="rounded-full bg-accent/20 px-3 py-1 font-semibold text-accent">MODE: PAPER</span>
            <span className={`rounded-full px-3 py-1 font-semibold ${status.data?.live_trading_allowed ? 'bg-loss/20 text-loss' : 'bg-edge text-slate-400'}`}>LIVE: {status.data?.live_trading_allowed ? 'ENABLED' : 'DISABLED'}</span>
            {status.data?.kill_switch && <span className="rounded-full bg-loss px-3 py-1 font-semibold text-white">KILL SWITCH ENGAGED</span>}
          </div>
        </header>
        {Page ? <Page /> : <div className="rounded-xl border border-dashed border-edge p-10 text-center text-slate-400">{active} is scheduled for Milestone {item.milestone}. See IMPLEMENTATION_ROADMAP.md.</div>}
      </main>
    </div>
  )
}
