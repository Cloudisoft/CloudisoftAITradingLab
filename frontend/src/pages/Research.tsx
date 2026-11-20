import { useState } from 'react'
import { Button, Card, KV, inputCls, post, useAction, usePoll } from '../ui'

export default function Research() {
  const llm = usePoll<{ available: boolean; note: string | null; calls: Record<string, unknown>[] }>('/api/research/llm', 20000)
  const pf = usePoll<Record<string, unknown>>('/api/research/portfolio', 20000)
  const [text, setText] = useState('Bitcoin surges after ETF approval')
  const [heads, setHeads] = useState('Bitcoin rallies to record high\nEthereum exploit drains bridge funds')
  const [fund, setFund] = useState({ symbol: 'INFY', pe: '24', pb: '7', roe: '0.31', debt_to_equity: '0.1', revenue_growth: '0.06', eps_growth: '0.09' })
  const [out, setOut] = useState<Record<string, unknown> | null>(null)
  const a = useAction()
  const go = (p: string, b: unknown) => a.run(() => post<Record<string, unknown>>(p, b), r => { setOut(r); return 'OK' })
  return (
    <div className="space-y-4">
      <p className={`rounded-lg border p-3 text-sm ${llm.data?.available ? 'border-gain/40 text-gain' : 'border-warn/40 text-warn'}`}>
        {llm.data?.available ? 'Claude models available. Model tier follows the survival state; every call is costed in the survival ledger.' : (llm.data?.note ?? 'Checking LLM availability…')}
      </p>
      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Sentiment analyst">
          <textarea className={inputCls + ' h-20 w-full'} value={text} onChange={e => setText(e.target.value)} />
          <Button onClick={() => go('/api/research/sentiment', { text })}>Score</Button>
        </Card>
        <Card title="News analyst (one headline per line)">
          <textarea className={inputCls + ' h-20 w-full'} value={heads} onChange={e => setHeads(e.target.value)} />
          <div className="flex gap-2"><Button onClick={() => go('/api/research/news', { headlines: heads.split('\n').filter(Boolean) })}>Analyse</Button>
            <Button tone="ghost" onClick={() => go('/api/research/news', {})}>Fetch configured feeds</Button></div>
        </Card>
        <Card title="Fundamental analyst">
          <div className="grid grid-cols-2 gap-1">{Object.entries(fund).map(([k, v]) => <label key={k} className="grid text-xs text-slate-400">{k}<input className={inputCls} value={v} onChange={e => setFund({ ...fund, [k]: e.target.value })} /></label>)}</div>
          <Button onClick={() => go('/api/research/fundamentals', Object.fromEntries(Object.entries(fund).map(([k, v]) => [k, k === 'symbol' ? v : v === '' ? null : Number(v)])))}>Score</Button>
        </Card>
      </div>
      {a.msg && a.msg !== 'OK' && <p className="text-sm text-loss">{a.msg}</p>}
      {out && <Card title="Result (research only — not investment advice)"><pre className="max-h-96 overflow-auto text-xs">{JSON.stringify(out, null, 2)}</pre></Card>}
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Portfolio analyst" origin="simulated">{pf.data && <KV data={pf.data} />}</Card>
        <Card title="Recent LLM calls">{(llm.data?.calls ?? []).length ? <pre className="max-h-64 overflow-auto text-xs">{JSON.stringify(llm.data?.calls, null, 1)}</pre> : <p className="text-sm text-slate-500">None yet</p>}</Card>
      </div>
    </div>
  )
}
