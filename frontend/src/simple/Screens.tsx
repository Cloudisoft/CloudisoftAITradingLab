import { useState } from 'react'
import { api, isSignedIn, logout } from '../api'
import TradeSheet from './Trade'
import { CandleChart, CoinBadge, SignIn, Spark, pct, refreshAll, tone, usd, useData, type Candle } from './kit'

export type Market = { symbol: string; name: string; price: number; change_24h: number | null; spark: number[]; holding_qty: string | null }
type Overview = { account_value: string; available_capital: string; realised_pnl: string; unrealised_pnl: string; equity_curve: [string, number][] }
type Bot = { headline: string; enabled: boolean; paused: boolean; kill_switch: boolean; health: string; state: string; strategy: string | null; strategy_plain: string | null; checks_every_minutes: number; last_trade: { side: string; name: string; price: string; qty: string } | null; per_trade_usd: number }
type Act = { status: string; side: string; name: string; qty: string; price: string | null; fees: string; reason: string | null; ref: string | null }

const H = ({ children }: { children: React.ReactNode }) => <h2 className="mb-3 text-base font-semibold" style={{ fontFamily: 'var(--font-display)' }}>{children}</h2>
const Panel = ({ children, className = '' }: { children: React.ReactNode; className?: string }) => <section className={`rounded-3xl bg-card p-5 ${className}`}>{children}</section>

export function PracticeNote() {
  return <p className="rounded-2xl bg-violet-soft px-4 py-2.5 text-sm text-violet">Practice mode: simulated prices and practice money. Nothing here uses real funds.</p>
}

function MarketRow({ m, onOpen }: { m: Market; onOpen: (s: string) => void }) {
  const up = (m.change_24h ?? 0) >= 0
  return (
    <button onClick={() => onOpen(m.symbol)} data-coin={m.symbol} aria-label={`${m.name}, ${usd(m.price)}`}
      className="flex w-full items-center gap-3 rounded-2xl px-2 py-3 text-left hover:bg-canvas">
      <CoinBadge name={m.name} />
      <span className="min-w-0 flex-1">
        <span className="block truncate font-semibold">{m.name}</span>
        <span className="flex items-center gap-1.5 text-xs text-muted">{m.symbol.replace('USDT', '')}
          {m.holding_qty && <span className="rounded-full bg-violet-soft px-1.5 py-0.5 text-[10px] font-semibold text-violet">Owned</span>}</span>
      </span>
      <span className="hidden min-[400px]:block"><Spark data={m.spark} up={up} w={72} /></span>
      <span className="w-28 text-right"><span className="num block font-semibold">{usd(m.price)}</span><span className={`num block text-xs ${tone(m.change_24h)}`}>{pct(m.change_24h)}</span></span>
    </button>
  )
}

export function BotCard({ compact = false, onOpen }: { compact?: boolean; onOpen?: () => void }) {
  const b = useData<Bot>('/api/bot', 10000)
  if (!b.data) return null
  const d = b.data
  return (
    <section className="rounded-3xl bg-violet p-5 text-white">
      <div className="mb-2 flex items-center gap-2 text-sm text-white/80">
        <span className={`inline-block h-2.5 w-2.5 rounded-full ${d.enabled ? 'bg-emerald-300' : 'bg-amber-300'}`} aria-hidden />
        {d.enabled ? 'Your bot is on' : 'Your bot is off'}
      </div>
      <p className="text-xl leading-snug font-semibold md:text-2xl" style={{ fontFamily: 'var(--font-display)' }}>{d.headline}</p>
      {!compact && <p className="mt-2 text-sm text-white/80">{d.health} Checks prices every {d.checks_every_minutes} minutes.</p>}
      {onOpen && <button onClick={onOpen} className="mt-4 rounded-full bg-white/15 px-4 py-2 text-sm font-semibold hover:bg-white/25">See what it's doing</button>}
    </section>
  )
}

export function Home({ open, go }: { open: (s: string) => void; go: (t: string) => void }) {
  const ov = useData<Overview>('/api/overview', 10000)
  const mk = useData<{ markets: Market[] }>('/api/markets', 10000)
  const acts = useData<{ items: Act[] }>('/api/activity?limit=3', 15000)
  const o = ov.data
  const curve = (o?.equity_curve ?? []).map(([, v]) => v)
  const first = curve[0] ?? Number(o?.account_value ?? 0)
  const change = o ? Number(o.account_value) - first : 0
  const pnl = o ? Number(o.realised_pnl) + Number(o.unrealised_pnl) : 0
  return (
    <div className="space-y-4">
      <PracticeNote />
      <Panel>
        <p className="text-sm text-muted">Your practice balance</p>
        <p className="num mt-1 text-4xl font-semibold md:text-5xl">{usd(o?.account_value)}</p>
        <p className={`num mt-1 text-sm ${tone(change)}`}>{change > 0 ? '+' : ''}{usd(change)} since the bot started</p>
        {curve.length > 1 && <div className="mt-3"><Spark data={curve.slice(-200)} up={change >= 0} w={600} h={64} fluid /></div>}
        <div className="mt-4 grid grid-cols-3 gap-2 text-sm">
          <div><p className="text-muted">Cash</p><p className="num font-semibold">{usd(o?.available_capital)}</p></div>
          <div><p className="text-muted">In coins</p><p className="num font-semibold">{usd(o ? Number(o.account_value) - Number(o.available_capital) : null)}</p></div>
          <div><p className="text-muted">Profit / loss</p><p className={`num font-semibold ${tone(pnl)}`}>{usd(pnl)}</p></div>
        </div>
      </Panel>
      <BotCard compact onOpen={() => go('bot')} />
      <Panel>
        <div className="mb-3 flex items-center justify-between [&_h2]:mb-0"><H>Watchlist</H><button onClick={() => go('markets')} className="text-sm font-semibold text-violet">See all</button></div>
        {(mk.data?.markets ?? []).map(m => <MarketRow key={m.symbol} m={m} onOpen={open} />)}
      </Panel>
      <Panel>
        <div className="mb-3 flex items-center justify-between [&_h2]:mb-0"><H>Recent activity</H><button onClick={() => go('orders')} className="text-sm font-semibold text-violet">All orders</button></div>
        <ActivityList items={acts.data?.items ?? []} />
      </Panel>
    </div>
  )
}

export function Markets({ open }: { open: (s: string) => void }) {
  const mk = useData<{ markets: Market[]; label: string }>('/api/markets', 10000)
  return (
    <div className="space-y-4">
      <Panel>
        <H>Markets</H>
        <p className="mb-2 text-xs text-muted">{mk.data?.label}</p>
        {(mk.data?.markets ?? []).map(m => <MarketRow key={m.symbol} m={m} onOpen={open} />)}
        {mk.error && <p className="text-sm text-down">Prices are unavailable right now. They refresh automatically.</p>}
      </Panel>
      <p className="px-2 text-sm text-muted">More coins and live exchange prices arrive when a broker or exchange is connected.</p>
    </div>
  )
}

type Detail = { name: string; symbol: string; price: number; change_24h: number | null; high_24h: number; low_24h: number; candles: Candle[]; insights: { tone: string; text: string }[]; holding: { qty: string; avg_price: number; value: number; pnl: number; pnl_pct: number } | null; available_cash: number; label: string }

export function Coin({ symbol, back }: { symbol: string; back: () => void }) {
  const [tf, setTf] = useState<'1h' | '4h' | '1d'>('1h')
  const d = useData<Detail>(`/api/markets/${symbol}?tf=${tf}`, 15000)
  const [side, setSide] = useState<'buy' | 'sell' | null>(null)
  const x = d.data
  const dot = { up: 'bg-up', down: 'bg-down', caution: 'bg-amber-500', neutral: 'bg-muted' } as Record<string, string>
  return (
    <div className="space-y-4 pb-24 md:pb-0">
      <button onClick={back} className="text-sm font-semibold text-violet">Back</button>
      <div className="flex items-center gap-3">
        <CoinBadge name={x?.name ?? '?'} size={48} />
        <div><h1 className="text-xl font-semibold" style={{ fontFamily: 'var(--font-display)' }}>{x?.name ?? symbol}</h1><p className="text-sm text-muted">{symbol.replace('USDT', '')} · priced in US dollars</p></div>
      </div>
      <div>
        <p className="num text-4xl font-semibold">{usd(x?.price)}</p>
        <p className={`num text-sm ${tone(x?.change_24h)}`}>{pct(x?.change_24h)} today</p>
      </div>
      <div className="grid gap-4 lg:grid-cols-[1fr_340px]">
        <div className="space-y-4">
          <section className="rounded-3xl bg-card p-3">
            <div className="mb-2 flex items-center justify-between px-2">
              <div role="tablist" aria-label="Candle size" className="flex gap-1 rounded-full bg-canvas p-1">
                {(['1h', '4h', '1d'] as const).map(t => (
                  <button key={t} role="tab" aria-selected={tf === t} onClick={() => setTf(t)}
                    className={`rounded-full px-3 py-1 text-sm font-semibold ${tf === t ? 'bg-card shadow-sm' : 'text-muted'}`}>{t === '1d' ? '1D' : t.toUpperCase()}</button>))}
              </div>
              <span className="text-xs text-muted">Simulated prices</span>
            </div>
            {x && <CandleChart candles={x.candles} />}
            <p className="px-2 pt-2 text-xs text-muted">Each candle shows one {tf === '1d' ? 'day' : tf === '4h' ? '4-hour period' : 'hour'}: green if the price rose, red if it fell. The thin lines show the highest and lowest prices. Bars at the bottom show how much was traded.</p>
          </section>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <Panel><p className="text-muted">24h high</p><p className="num font-semibold">{usd(x?.high_24h)}</p></Panel>
            <Panel><p className="text-muted">24h low</p><p className="num font-semibold">{usd(x?.low_24h)}</p></Panel>
          </div>
        </div>
        <div className="space-y-4">
          <Panel>
            <H>What the AI sees</H>
            <ul className="space-y-2.5">{(x?.insights ?? []).map(i => (
              <li key={i.text} className="flex gap-2.5 text-sm"><span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${dot[i.tone]}`} aria-hidden /><span>{i.text}</span></li>))}</ul>
            <p className="mt-3 text-xs text-muted">This is analysis, not advice. Past prices don't predict the future.</p>
          </Panel>
          <Panel>
            <H>Your {x?.name}</H>
            {x?.holding ? (<div className="space-y-1 text-sm">
              <div className="flex justify-between"><span className="text-muted">Worth now</span><span className="num font-semibold">{usd(x.holding.value)}</span></div>
              <div className="flex justify-between"><span className="text-muted">Amount</span><span className="num">{x.holding.qty}</span></div>
              <div className="flex justify-between"><span className="text-muted">Bought at (avg)</span><span className="num">{usd(x.holding.avg_price)}</span></div>
              <div className="flex justify-between"><span className="text-muted">Profit / loss</span><span className={`num font-semibold ${tone(x.holding.pnl)}`}>{usd(x.holding.pnl)} ({pct(x.holding.pnl_pct)})</span></div>
            </div>) : <p className="text-sm text-muted">You don't own any yet.</p>}
          </Panel>
          <div className="fixed inset-x-0 bottom-16 z-30 flex gap-3 bg-canvas/95 p-3 backdrop-blur md:static md:bg-transparent md:p-0">
            <button onClick={() => setSide('buy')} className="flex-1 rounded-2xl bg-up py-3.5 font-semibold text-white">Buy</button>
            <button onClick={() => setSide('sell')} disabled={!x?.holding} className="flex-1 rounded-2xl bg-down py-3.5 font-semibold text-white disabled:opacity-40">Sell</button>
          </div>
        </div>
      </div>
      {x && side && <TradeSheet open symbol={symbol} name={x.name} side={side} onClose={() => setSide(null)} cash={x.available_cash}
        holdingQty={Number(x.holding?.qty ?? 0)} price={x.price} />}
    </div>
  )
}

function ActivityList({ items }: { items: Act[] }) {
  if (!items.length) return <p className="py-4 text-sm text-muted">No trades yet. When you or your bot buy or sell, it shows up here.</p>
  return (
    <ul className="divide-y divide-line">{items.map((a, i) => (
      <li key={(a.ref ?? '') + i} className="flex items-center gap-3 py-3">
        <span className={`grid h-9 w-9 place-items-center rounded-full text-sm font-bold ${a.side === 'buy' ? 'bg-up/10 text-up' : 'bg-down/10 text-down'}`} aria-hidden>{a.side === 'buy' ? 'B' : 'S'}</span>
        <span className="min-w-0 flex-1">
          <span className="block font-semibold">{a.side === 'buy' ? 'Bought' : 'Sold'} {a.name}</span>
          <span className="block truncate text-xs text-muted">{a.status === 'filled' ? `${a.qty} at ${usd(a.price)} · fee ${usd(a.fees, 4)}` : a.reason ?? 'Not placed'}</span>
        </span>
        <span className={`text-xs font-semibold ${a.status === 'filled' ? 'text-up' : 'text-down'}`}>{a.status === 'filled' ? 'Done' : 'Not placed'}</span>
      </li>))}</ul>
  )
}

export function Orders() {
  const acts = useData<{ items: Act[]; label: string }>('/api/activity?limit=100', 10000)
  return <Panel><H>Orders</H><p className="mb-1 text-xs text-muted">{acts.data?.label}</p><ActivityList items={acts.data?.items ?? []} /></Panel>
}

export function BotScreen() {
  const b = useData<Bot>('/api/bot', 8000)
  const [msg, setMsg] = useState<string | null>(null)
  const d = b.data
  const toggle = async () => {
    if (!d) return
    try { await api('/api/bot', { method: 'POST', body: JSON.stringify({ enabled: !d.enabled }) }); refreshAll(); setMsg(null) }
    catch { setMsg('Sign in (More tab) to switch the bot on or off.') }
  }
  return (
    <div className="space-y-4">
      <BotCard />
      {d && !d.kill_switch && (
        <button onClick={toggle} className={`w-full rounded-2xl py-3.5 font-semibold ${d.enabled ? 'bg-card text-navy' : 'bg-up text-white'}`}>
          {d.enabled ? 'Pause the bot' : 'Turn the bot on'}</button>)}
      {msg && <p className="text-sm text-down">{msg}</p>}
      <Panel>
        <H>How it decides</H>
        <p className="text-sm">{d?.strategy_plain ?? 'No strategy is active. Pick one in Pro tools → Strategy Lab.'}</p>
        <p className="mt-2 text-xs text-muted">Every order, the bot's or yours, passes an independent safety check first: no borrowing, at most half your money in one coin, a daily loss limit, and no bigger bets after a loss.</p>
      </Panel>
      <Panel>
        <H>Latest</H>
        {d?.last_trade ? <p className="text-sm">{d.last_trade.side === 'buy' ? 'Bought' : 'Sold'} {d.last_trade.qty} {d.last_trade.name} at {usd(d.last_trade.price)}.</p> : <p className="text-sm text-muted">No trades yet.</p>}
        <p className="mt-1 text-sm text-muted">Each bot trade uses about {usd(d?.per_trade_usd)} of your cash.</p>
      </Panel>
    </div>
  )
}

export function More({ openPro }: { openPro: () => void }) {
  const [signed, setSigned] = useState(isSignedIn())
  const [amt, setAmt] = useState('25')
  const [msg, setMsg] = useState<string | null>(null)
  const deposit = async () => {
    try { await api('/api/paper/deposit', { method: 'POST', body: JSON.stringify({ amount: amt }) }); setMsg(`Added $${amt} of practice money.`); refreshAll() }
    catch { setMsg('Only the owner can add practice money. Sign in first.') }
  }
  return (
    <div className="space-y-4">
      <Panel>
        <H>Account</H>
        {signed ? (<div className="flex items-center justify-between"><p className="text-sm">You're signed in.</p>
          <button onClick={() => { logout(); setSigned(false); refreshAll() }} className="text-sm font-semibold text-violet">Sign out</button></div>)
          : <SignIn onDone={() => setSigned(true)} />}
      </Panel>
      <Panel>
        <H>Add practice money</H>
        <p className="mb-3 text-sm text-muted">Top up your practice balance to see how trading works. This is not real money.</p>
        <div className="flex gap-2">
          <div className="flex flex-1 items-center rounded-xl border border-line bg-canvas px-3"><span className="text-muted">$</span>
            <input value={amt} inputMode="decimal" onChange={e => setAmt(e.target.value.replace(/[^\d.]/g, ''))} className="num w-full bg-transparent px-2 py-2.5 outline-none" /></div>
          <button onClick={deposit} className="rounded-xl bg-violet px-5 font-semibold text-white">Add</button>
        </div>
        {msg && <p className="mt-2 text-sm">{msg}</p>}
      </Panel>
      <Panel>
        <H>Pro tools</H>
        <p className="mb-3 text-sm text-muted">Advanced screens: strategy lab, backtesting, AI research, survival engine, reports, wallet and withdrawals, agents, security and settings (including 2FA).</p>
        <button onClick={openPro} className="w-full rounded-xl bg-navy py-3 font-semibold text-white">Open Pro tools</button>
      </Panel>
      <Panel>
        <H>Words you'll see</H>
        <dl className="space-y-2 text-sm">
          <div><dt className="font-semibold">Candle</dt><dd className="text-muted">One bar on the chart covering a period of time: where the price opened, closed, and its highest and lowest points.</dd></div>
          <div><dt className="font-semibold">Profit / loss</dt><dd className="text-muted">How much your coins are worth now compared with what you paid, after fees.</dd></div>
          <div><dt className="font-semibold">Fee</dt><dd className="text-muted">What an exchange charges per trade (simulated here at 0.1%).</dd></div>
          <div><dt className="font-semibold">Practice mode</dt><dd className="text-muted">Everything works like real trading, but with simulated prices and practice money.</dd></div>
        </dl>
      </Panel>
    </div>
  )
}
