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
    return () => { live = false; clearInterval(id) }
  }, [path, ms])
  return { data, error }
}

export const money = (v: string | number | null | undefined, d = 4) =>
  v === null || v === undefined ? '—' : Number(v).toLocaleString(undefined, { maximumFractionDigits: d })

export function ErrorNote({ error }: { error: string | null }) {
  return error ? <p className="rounded-lg border border-loss/40 bg-loss/10 p-3 text-sm text-loss">Backend unavailable: {error}</p> : null
}
