import { lazy, Suspense, useEffect, useState } from 'react'
import { BotScreen, Coin, Home, Markets, More, Orders } from './simple/Screens'

const ProApp = lazy(() => import('./ProApp'))

type Route = { tab: string; coin?: string }
const parse = (): Route => {
  const [, tab = 'home', coin] = window.location.hash.replace(/^#/, '').split('/')
  return { tab, coin }
}

const TABS = [
  { id: 'home', label: 'Home', icon: 'M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z' },
  { id: 'markets', label: 'Markets', icon: 'M4 19V9m6 10V5m6 14v-7m4 7H2' },
  { id: 'orders', label: 'Orders', icon: 'M7 4h10M7 9h10M7 14h6M5 2h14a1 1 0 0 1 1 1v18l-4-2-4 2-4-2-4 2V3a1 1 0 0 1 1-1z' },
  { id: 'bot', label: 'Bot', icon: 'M9 3h6m-3 0v3M5 8h14a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2zm4 5h.01M15 13h.01' },
  { id: 'more', label: 'More', icon: 'M5 12h.01M12 12h.01M19 12h.01' },
]

function Icon({ d }: { d: string }) {
  return <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d={d} /></svg>
}

export default function App() {
  const [route, setRoute] = useState<Route>(parse())
  useEffect(() => {
    const on = () => { setRoute(parse()); window.scrollTo(0, 0) }
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])
  const go = (tab: string, coin?: string) => { window.location.hash = coin ? `/${tab}/${coin}` : `/${tab}` }
  const open = (symbol: string) => go('coin', symbol)

  if (route.tab === 'pro') return <Suspense fallback={<p className="p-6">Loading Pro tools…</p>}><ProApp onExit={() => go('more')} /></Suspense>

  const active = route.tab === 'coin' ? 'markets' : route.tab
  let screen
  switch (route.tab) {
    case 'markets': screen = <Markets open={open} />; break
    case 'coin': screen = route.coin ? <Coin key={route.coin} symbol={route.coin} back={() => history.back()} /> : <Markets open={open} />; break
    case 'orders': screen = <Orders />; break
    case 'bot': screen = <BotScreen />; break
    case 'more': screen = <More openPro={() => go('pro')} />; break
    default: screen = <Home open={open} go={t => go(t)} />
  }
  return (
    <div className="simple md:flex">
      <nav aria-label="Main" className="fixed inset-x-0 bottom-0 z-40 border-t border-line bg-card md:sticky md:top-0 md:h-screen md:w-60 md:shrink-0 md:border-t-0 md:border-r md:p-5">
        <a href="#/home" className="mb-8 hidden items-center gap-2 md:flex" aria-label="Cloudisoft home">
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-violet text-white" style={{ fontFamily: 'var(--font-display)' }}>C</span>
          <span className="text-lg font-semibold" style={{ fontFamily: 'var(--font-display)' }}>Cloudisoft</span>
        </a>
        <ul className="flex md:flex-col md:gap-1">
          {TABS.map(t => (
            <li key={t.id} className="flex-1">
              <a href={`#/${t.id}`} aria-current={active === t.id ? 'page' : undefined}
                className={`flex flex-col items-center gap-0.5 py-2 text-[11px] font-semibold md:flex-row md:gap-3 md:rounded-xl md:px-3 md:py-2.5 md:text-sm ${active === t.id ? 'text-violet md:bg-violet-soft' : 'text-muted hover:text-navy'}`}>
                <Icon d={t.icon} />{t.label}
              </a>
            </li>))}
        </ul>
      </nav>
      <main className="mx-auto w-full max-w-5xl px-4 pt-5 pb-24 md:px-8 md:pt-8 md:pb-10">
        <header className="mb-4 flex items-center justify-between md:hidden">
          <span className="flex items-center gap-2"><span className="grid h-8 w-8 place-items-center rounded-lg bg-violet text-sm text-white" style={{ fontFamily: 'var(--font-display)' }}>C</span>
            <span className="font-semibold" style={{ fontFamily: 'var(--font-display)' }}>Cloudisoft</span></span>
          <span className="rounded-full bg-violet-soft px-3 py-1 text-xs font-semibold text-violet">Practice</span>
        </header>
        {screen}
      </main>
    </div>
  )
}
