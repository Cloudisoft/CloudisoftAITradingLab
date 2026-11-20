import { useState } from 'react'
import { Button, Card, ErrorNote, KV, inputCls, money, post, useAction, usePoll } from '../ui'

type Ver = { version: number; author: string; note: string; created_at: string; backtests: { out_of_sample?: Record<string, number | null>; dataset?: string }[] }
type S = { id: string; name: string; status: string; version: number; versions: Ver[]; definition: Record<string, unknown> }
const INDS = ['close', 'open', 'high', 'low', 'volume', 'sma', 'ema', 'rsi', 'macd', 'macd_signal', 'macd_hist', 'bb_upper', 'bb_lower', 'bb_mid', 'atr', 'adx', 'vwap', 'support', 'resistance', 'volume_z']
const OPS = ['>', '<', '>=', '<=', 'crosses_above', 'crosses_below']
type Row = { li: string; lp: string; op: string; ri: string; rp: string; rv: string }
const blank: Row = { li: 'rsi', lp: '14', op: '<', ri: '', rp: '', rv: '30' }

function operand(i: string, p: string, v?: string) {
  return i ? { indicator: i, params: p ? { period: Number(p) } : {} } : { value: Number(v) }
}

function Builder({ onCreated }: { onCreated: () => void }) {
  const [name, setName] = useState('My strategy')
  const [logic, setLogic] = useState('AND')
  const [rows, setRows] = useState<Row[]>([blank])
  const [exitRows, setExitRows] = useState<Row[]>([{ ...blank, op: '>', rv: '65' }])
  const [risk, setRisk] = useState({ stop_loss_pct: '0.03', take_profit_pct: '0.06', trailing_stop_pct: '', position_fraction: '0.5' })
  const a = useAction()
  const editor = (rs: Row[], set: (r: Row[]) => void) => rs.map((r, i) => {
    const upd = (k: keyof Row, v: string) => set(rs.map((x, j) => (j === i ? { ...x, [k]: v } : x)))
    return (
      <div key={i} className="flex flex-wrap items-center gap-1">
        <select className={inputCls} value={r.li} onChange={e => upd('li', e.target.value)}>{INDS.map(x => <option key={x}>{x}</option>)}</select>
        <input className={inputCls + ' w-16'} placeholder="period" value={r.lp} onChange={e => upd('lp', e.target.value)} />
        <select className={inputCls} value={r.op} onChange={e => upd('op', e.target.value)}>{OPS.map(x => <option key={x}>{x}</option>)}</select>
        <select className={inputCls} value={r.ri} onChange={e => upd('ri', e.target.value)}><option value="">value</option>{INDS.map(x => <option key={x}>{x}</option>)}</select>
        {r.ri ? <input className={inputCls + ' w-16'} placeholder="period" value={r.rp} onChange={e => upd('rp', e.target.value)} /> : <input className={inputCls + ' w-20'} value={r.rv} onChange={e => upd('rv', e.target.value)} />}
        <button className="text-slate-500" onClick={() => set(rs.filter((_, j) => j !== i))}>✕</button>
      </div>)
  })
  const conds = (rs: Row[]) => rs.map(r => ({ left: operand(r.li, r.lp), op: r.op, right: operand(r.ri, r.rp, r.rv) }))
  const create = () => a.run(() => post('/api/strategies', {
    note: 'visual builder', definition: {
      name, entry: { logic, conditions: conds(rows) }, exit: exitRows.length ? { logic: 'OR', conditions: conds(exitRows) } : null,
      risk: Object.fromEntries(Object.entries(risk).map(([k, v]) => [k, v === '' ? null : Number(v)])),
    },
  }), () => { onCreated(); return 'Strategy created (status: research)' })
  return (
    <Card title="Visual strategy builder">
      <div className="space-y-2 text-sm">
        <input className={inputCls + ' w-full'} value={name} onChange={e => setName(e.target.value)} />
        <div className="flex items-center gap-2">Entry when <select className={inputCls} value={logic} onChange={e => setLogic(e.target.value)}><option>AND</option><option>OR</option></select> of:</div>
        {editor(rows, setRows)}<Button tone="ghost" onClick={() => setRows([...rows, blank])}>+ entry condition</Button>
        <div>Exit when ANY of:</div>
        {editor(exitRows, setExitRows)}<Button tone="ghost" onClick={() => setExitRows([...exitRows, blank])}>+ exit condition</Button>
        <div className="flex flex-wrap gap-2">{Object.entries(risk).map(([k, v]) => <label key={k} className="grid text-xs text-slate-400">{k}<input className={inputCls + ' w-28'} value={v} onChange={e => setRisk({ ...risk, [k]: e.target.value })} /></label>)}</div>
        <Button onClick={create} disabled={a.busy}>Create strategy</Button>
        {a.msg && <p className="text-xs text-slate-400">{a.msg}</p>}
      </div>
    </Card>
  )
}

export default function StrategyLab() {
  const [tick, setTick] = useState(0)
  const list = usePoll<{ strategies: S[] }>('/api/strategies?t=' + tick, 15000)
  const [text, setText] = useState('Buy when RSI 14 below 30 and close above SMA 200, sell when RSI above 60. Stop loss 3%, take profit 6%, position size 50%')
  const [gen, setGen] = useState<Record<string, unknown> | null>(null)
  const a = useAction()
  const refresh = () => setTick(t => t + 1)
  const act = (path: string, body: unknown = {}) => a.run(() => post<Record<string, unknown>>(path, body), r => { refresh(); return JSON.stringify(r).slice(0, 300) })
  return (
    <div className="space-y-4">
      <ErrorNote error={list.error} />
      <Card title="Natural-language strategy generation">
        <textarea className={inputCls + ' h-20 w-full'} value={text} onChange={e => setText(e.target.value)} />
        <div className="mt-2 flex gap-2"><Button disabled={a.busy} onClick={() => a.run(() => post<Record<string, unknown>>('/api/strategies/generate', { text }), r => { setGen(r); refresh(); return 'Generated and backtested (SIMULATED)' })}>Generate + backtest</Button></div>
        {gen && <div className="mt-3 grid gap-3 lg:grid-cols-2"><KV data={(gen.meta ?? {}) as Record<string, unknown>} /><KV data={((gen.backtest as Record<string, unknown>)?.out_of_sample ?? {}) as Record<string, unknown>} /></div>}
      </Card>
      <Builder onCreated={refresh} />
      {a.msg && <p className="rounded-lg border border-edge p-2 text-xs text-slate-400">{a.msg}</p>}
      <Card title="Strategies (versioned)">
        <div className="space-y-3">{(list.data?.strategies ?? []).map(s => {
          const last = s.versions.at(-1)?.backtests.at(-1)
          return (
            <div key={s.id} className="rounded-lg border border-edge p-3">
              <div className="flex flex-wrap items-center justify-between gap-2"><div><b>{s.name}</b> <span className="text-xs text-slate-400">v{s.version} · {s.status}</span></div>
                <div className="flex flex-wrap gap-1">
                  <Button tone="ghost" onClick={() => act(`/api/strategies/${s.id}/backtest`, {})}>Backtest</Button>
                  <Button tone="ghost" onClick={() => act(`/api/strategies/${s.id}/improve`, {})}>Research improvement</Button>
                  <Button tone="ghost" onClick={() => act(`/api/strategies/${s.id}/promote`)}>Request paper trading</Button>
                  <Button tone="ghost" onClick={() => act(`/api/strategies/${s.id}/pause`)}>Pause</Button>
                </div></div>
              {last?.out_of_sample && <p className="mt-1 text-xs text-slate-400">Latest out-of-sample (simulated): Sharpe {money(last.out_of_sample.sharpe, 2)} · return {money(last.out_of_sample.net_return, 4)} · trades {last.out_of_sample.num_trades} · max DD {money(last.out_of_sample.max_drawdown, 3)}</p>}
              <details className="mt-1 text-xs"><summary className="cursor-pointer text-slate-400">Versions</summary>{s.versions.map(v => <div key={v.version}>v{v.version} · {v.author} · {v.note} · {v.created_at.slice(0, 16)}</div>)}</details>
            </div>)
        })}</div>
      </Card>
    </div>
  )
}
