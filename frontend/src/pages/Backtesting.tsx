import { Fragment } from 'react'
import { useEffect, useState } from 'react'
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../api'
import { Card, ErrorNote, money } from '../ui'

type R = { label: string; metrics: Record<string, number | null>; monte_carlo: Record<string, number>; equity: [string, number][]; skipped_uneconomical: number; dataset: string }

export default function Backtesting() {
  const [templates, setTemplates] = useState<Record<string, unknown>>({})
  const [tpl, setTpl] = useState('ema_crossover')
  const [regime, setRegime] = useState('volatile')
  const [capital, setCapital] = useState(5)
  const [res, setRes] = useState<R | null>(null)
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => { api<Record<string, unknown>>('/api/strategies/templates').then(setTemplates).catch(e => setErr(String(e))) }, [])
  const run = () => api<R>('/api/backtest', { method: 'POST', body: JSON.stringify({ strategy: templates[tpl], regime, capital }) }).then(setRes).catch(e => setErr(String(e)))
  const sel = 'rounded-lg border border-edge bg-ink px-2 py-1.5 text-sm'
  return (
    <div className="space-y-4">
      <ErrorNote error={err} />
      <Card title="Run backtest (synthetic data until a verified market-data provider is connected)" origin="simulated">
        <div className="flex flex-wrap items-end gap-3 text-sm">
          <label className="grid gap-1">Strategy<select className={sel} value={tpl} onChange={e => setTpl(e.target.value)}>{Object.keys(templates).map(k => <option key={k}>{k}</option>)}</select></label>
          <label className="grid gap-1">Market regime<select className={sel} value={regime} onChange={e => setRegime(e.target.value)}>{['trend_up', 'trend_down', 'sideways', 'volatile'].map(k => <option key={k}>{k}</option>)}</select></label>
          <label className="grid gap-1">Capital<input type="number" min={1} className={sel + ' w-28'} value={capital} onChange={e => setCapital(Number(e.target.value))} /></label>
          <button onClick={run} className="rounded-lg bg-accent px-4 py-2 font-semibold text-white">Run</button>
        </div>
      </Card>
      {res && (
        <>
          <p className="text-xs text-warn">{res.label}. Dataset: {res.dataset}. Uneconomical orders skipped: {res.skipped_uneconomical}.</p>
          <div className="grid gap-4 lg:grid-cols-3">
            <Card title="Equity" origin="simulated" className="lg:col-span-2">
              <div className="h-64"><ResponsiveContainer><LineChart data={res.equity.map(([t, v]) => ({ t, v }))}><XAxis dataKey="t" hide /><YAxis domain={['auto', 'auto']} width={60} stroke="#64748b" /><Tooltip contentStyle={{ background: '#121a2e' }} /><Line dataKey="v" dot={false} stroke="#4f8cff" /></LineChart></ResponsiveContainer></div>
            </Card>
            <Card title="Metrics" origin="simulated">
              <dl className="grid grid-cols-2 gap-y-1 text-sm">{Object.entries(res.metrics).map(([k, v]) => (<Fragment key={k}><dt className="text-slate-400">{k.replaceAll('_', ' ')}</dt><dd className="text-right tabular-nums">{money(v, 4)}</dd></Fragment>))}</dl>
              <h4 className="mt-3 text-xs uppercase text-slate-400">Monte Carlo</h4>
              <dl className="grid grid-cols-2 gap-y-1 text-sm">{Object.entries(res.monte_carlo).map(([k, v]) => (<Fragment key={k}><dt className="text-slate-400">{k.replaceAll('_', ' ')}</dt><dd className="text-right">{money(v, 4)}</dd></Fragment>))}</dl>
            </Card>
          </div>
        </>
      )}
    </div>
  )
}
