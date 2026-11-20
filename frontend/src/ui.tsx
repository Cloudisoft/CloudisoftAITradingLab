import { useEffect, useState, type ReactNode } from 'react'
import { api } from './api'

export type Origin = 'actual' | 'simulated' | 'estimated'

export function Label({ origin }: { origin: Origin }) {
  const cls = { actual: 'bg-gain/15 text-gain', simulated: 'bg-accent/15 text-accent', estimated: 'bg-warn/15 text-warn' }[origin]
  return <span className={`rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${cls}`}>{origin}</span>
}

export function Card({ title, children, origin, className = '' }: { title: string; children: ReactNode; origin?: Origin; className?: string }) {
  return (
    <section className={`rounded-xl border border-edge bg-panel p-4 ${className}`}>
      <header className="mb-3 flex items-center justify-between gap-2">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">{title}</h3>
        {origin && <Label origin={origin} />}
      </header>
      {children}
    </section>
  )
}

export function Stat({ label, value, tone, origin }: { label: string; value: ReactNode; tone?: 'gain' | 'loss' | 'warn'; origin?: Origin }) {
  const color = tone ? { gain: 'text-gain', loss: 'text-loss', warn: 'text-warn' }[tone] : 'text-white'
  return (
    <div className="rounded-xl border border-edge bg-panel p-4">
      <div className="flex items-center justify-between text-xs text-slate-400">{label}{origin && <Label origin={origin} />}</div>
      <div className={`mt-1 text-2xl font-semibold tabular-nums ${color}`}>{value}</div>
    </div>
  )
}

export function usePoll<T>(path: string, ms = 10000) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    let live = true
    const load = () => api<T>(path).then(d => live && (setData(d), setError(null))).catch(e => live && setError(String(e)))
    load()
    const id = setInterval(load, ms)
    window.addEventListener('clab:refresh', load)
    return () => { live = false; clearInterval(id); window.removeEventListener('clab:refresh', load) }
  }, [path, ms])
  return { data, error }
}

export const money = (v: string | number | null | undefined, d = 4) =>
  v === null || v === undefined ? '—' : Number(v).toLocaleString(undefined, { maximumFractionDigits: d })

export function ErrorNote({ error }: { error: string | null }) {
  return error ? <p className="rounded-lg border border-loss/40 bg-loss/10 p-3 text-sm text-loss">Backend unavailable: {error}</p> : null
}

export function Button({ children, onClick, tone = 'primary', disabled }: { children: ReactNode; onClick?: () => void; tone?: 'primary' | 'ghost' | 'danger'; disabled?: boolean }) {
  const cls = { primary: 'bg-accent text-white', ghost: 'border border-edge text-slate-200', danger: 'bg-loss text-white' }[tone]
  return <button disabled={disabled} onClick={onClick} className={`rounded-lg px-3 py-1.5 text-sm font-semibold disabled:opacity-50 ${cls}`}>{children}</button>
}

export const inputCls = 'rounded-lg border border-edge bg-ink px-2 py-1.5 text-sm'

function fmt(v: unknown): string {
  if (typeof v === 'object' && v !== null) return JSON.stringify(v)
  if (typeof v === 'string' && v.trim() !== '' && !isNaN(Number(v))) return money(v, 6)
  if (typeof v === 'number') return money(v, 6)
  return String(v ?? '—')
}

export function KV({ data }: { data: Record<string, unknown> }) {
  return (
    <dl className="grid grid-cols-2 gap-y-1 text-sm">
      {Object.entries(data).map(([k, v]) => (
        <div key={k} className="contents"><dt className="text-slate-400">{k.replaceAll('_', ' ')}</dt><dd className="break-all text-right tabular-nums">{fmt(v)}</dd></div>
      ))}
    </dl>
  )
}

export function useAction() {
  const [msg, setMsg] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const run = async <T,>(fn: () => Promise<T>, ok?: (r: T) => string) => {
    setBusy(true); setMsg(null)
    try { const r = await fn(); setMsg(ok ? ok(r) : 'Done'); window.dispatchEvent(new Event('clab:refresh')); return r } catch (e) { setMsg(String(e)); return null } finally { setBusy(false) }
  }
  return { msg, busy, run }
}

export const post = <T,>(path: string, body: unknown, method = 'POST') => api<T>(path, { method, body: JSON.stringify(body) })
