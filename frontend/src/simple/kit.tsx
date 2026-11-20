import { useEffect, useRef, useState, type ReactNode } from 'react'
import { createChart, CandlestickSeries, HistogramSeries, type IChartApi, type UTCTimestamp } from 'lightweight-charts'
import { api, isSignedIn, login } from '../api'

export const usd = (v: number | string | null | undefined, _max = 2) => {
  if (v === null || v === undefined || v === '') return '—'
  const n = Number(v)
  if (!isFinite(n)) return '—'
  const a = Math.abs(n)
  const d = a === 0 || a >= 1 ? 2 : a >= 0.01 ? 4 : 6
  return (n < 0 ? '-$' : '$') + a.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: d })
}
export const pct = (v: number | null | undefined) => (v === null || v === undefined ? '—' : `${v >= 0 ? '+' : ''}${(v * 100).toFixed(2)}%`)
export const tone = (v: number | null | undefined) => (v === null || v === undefined || v === 0 ? 'text-muted' : v > 0 ? 'text-up' : 'text-down')

export function useData<T>(path: string | null, ms = 15000) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    if (!path) return
    let live = true
    const load = () => api<T>(path).then(d => { if (live) { setData(d); setError(null) } }).catch(e => live && setError(String(e)))
    load()
    const id = setInterval(load, ms)
    window.addEventListener('clab:refresh', load)
    return () => { live = false; clearInterval(id); window.removeEventListener('clab:refresh', load) }
  }, [path, ms])
  return { data, error }
}
export const refreshAll = () => window.dispatchEvent(new Event('clab:refresh'))

export function CoinBadge({ name, size = 40 }: { name: string; size?: number }) {
  const hues: Record<string, string> = { Bitcoin: '#f2a33a', Ethereum: '#6273e8', Solana: '#14a38b', BNB: '#e0b130' }
  return (
    <span aria-hidden className="grid shrink-0 place-items-center rounded-full font-semibold text-white"
      style={{ width: size, height: size, background: hues[name] ?? '#5b47e0', fontFamily: 'var(--font-display)', fontSize: size * 0.4 }}>
      {name.slice(0, 1)}
    </span>
  )
}

export function Spark({ data, up, w = 84, h = 32, fluid = false }: { data: number[]; up: boolean; w?: number; h?: number; fluid?: boolean }) {
  if (data.length < 2) return null
  const min = Math.min(...data), max = Math.max(...data), r = max - min || 1
  const pts = data.map((v, i) => `${(i / (data.length - 1)) * w},${h - ((v - min) / r) * (h - 4) - 2}`).join(' ')
  return (
    <svg width={fluid ? '100%' : w} height={h} viewBox={`0 0 ${w} ${h}`} preserveAspectRatio={fluid ? 'none' : undefined} aria-hidden className="block">
      <polyline fill="none" strokeWidth="1.8" strokeLinejoin="round" vectorEffect="non-scaling-stroke" stroke={up ? 'var(--color-up)' : 'var(--color-down)'} points={pts} />
    </svg>)
}

export type Candle = { time: number; open: number; high: number; low: number; close: number; volume: number }

export function CandleChart({ candles, height = 360 }: { candles: Candle[]; height?: number }) {
  const box = useRef<HTMLDivElement>(null)
  const chart = useRef<IChartApi | null>(null)
  const series = useRef<{ c: ReturnType<IChartApi['addSeries']>; v: ReturnType<IChartApi['addSeries']> } | null>(null)
  useEffect(() => {
    if (!box.current) return
    const ch = createChart(box.current, {
      height, autoSize: true,
      layout: { background: { color: '#ffffff' }, textColor: '#687089', fontFamily: 'Manrope, sans-serif', attributionLogo: true },
      grid: { vertLines: { color: '#f0f2f6' }, horzLines: { color: '#f0f2f6' } },
      rightPriceScale: { borderColor: '#e3e7ef' }, timeScale: { borderColor: '#e3e7ef', timeVisible: true },
      crosshair: { mode: 0 },
    })
    const c = ch.addSeries(CandlestickSeries, {
      upColor: '#0c8f61', downColor: '#d93d46', borderUpColor: '#0c8f61', borderDownColor: '#d93d46',
      wickUpColor: '#0c8f61', wickDownColor: '#d93d46',
    })
    const v = ch.addSeries(HistogramSeries, { priceFormat: { type: 'volume' }, priceScaleId: '' })
    v.priceScale().applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } })
    c.priceScale().applyOptions({ scaleMargins: { top: 0.08, bottom: 0.22 } })
    chart.current = ch
    series.current = { c, v }
    return () => { ch.remove(); chart.current = null; series.current = null }
  }, [height])
  useEffect(() => {
    if (!series.current || !candles.length) return
    series.current.c.setData(candles.map(k => ({ time: k.time as UTCTimestamp, open: k.open, high: k.high, low: k.low, close: k.close })))
    series.current.v.setData(candles.map(k => ({ time: k.time as UTCTimestamp, value: k.volume, color: k.close >= k.open ? 'rgba(12,143,97,.28)' : 'rgba(217,61,70,.28)' })))
  }, [candles])
  const first = useRef(true)
  useEffect(() => { if (candles.length && first.current && chart.current) { chart.current.timeScale().fitContent(); first.current = false } }, [candles])
  return <div ref={box} style={{ height }} className="w-full" role="img" aria-label="Candlestick price chart" />
}

export function Sheet({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: string; children: ReactNode }) {
  useEffect(() => {
    const k = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', k)
    return () => window.removeEventListener('keydown', k)
  }, [onClose])
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-navy/40 md:items-center" onClick={onClose}>
      <div role="dialog" aria-modal="true" aria-label={title} onClick={e => e.stopPropagation()}
        className="max-h-[92vh] w-full overflow-y-auto rounded-t-3xl bg-card p-5 shadow-2xl md:max-w-md md:rounded-3xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold" style={{ fontFamily: 'var(--font-display)' }}>{title}</h2>
          <button onClick={onClose} className="rounded-full px-3 py-1 text-sm text-muted hover:bg-canvas">Close</button>
        </div>
        {children}
      </div>
    </div>
  )
}

export function SignIn({ onDone }: { onDone?: () => void }) {
  const [f, setF] = useState({ email: '', password: '', otp: '' })
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const inp = 'w-full rounded-xl border border-line bg-canvas px-3 py-2.5 text-sm outline-none focus:border-violet'
  return (
    <form className="space-y-2" onSubmit={async e => {
      e.preventDefault(); setBusy(true); setErr(null)
      try { await login(f.email, f.password, f.otp || undefined); refreshAll(); onDone?.() } catch { setErr('Wrong email or password, or the 6-digit code is missing or expired.') } finally { setBusy(false) }
    }}>
      <input className={inp} type="email" autoComplete="username" placeholder="Email" value={f.email} onChange={e => setF({ ...f, email: e.target.value })} required />
      <input className={inp} type="password" autoComplete="current-password" placeholder="Password" value={f.password} onChange={e => setF({ ...f, password: e.target.value })} required />
      <input className={inp} inputMode="numeric" autoComplete="one-time-code" placeholder="6-digit code from your authenticator app (if 2FA is on)" value={f.otp} onChange={e => setF({ ...f, otp: e.target.value.replace(/\D/g, '').slice(0, 6) })} />
      {err && <p className="text-sm text-down">{err}</p>}
      <button disabled={busy} className="w-full rounded-xl bg-violet py-3 font-semibold text-white disabled:opacity-60">{busy ? 'Signing in…' : 'Sign in'}</button>
    </form>
  )
}

export { isSignedIn }
