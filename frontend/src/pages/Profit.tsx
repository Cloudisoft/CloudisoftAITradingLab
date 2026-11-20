import { useEffect, useState } from 'react'
import Revenue from './Revenue'
import { Button, Card, ErrorNote, KV, Stat, inputCls, money, post, useAction, usePoll } from '../ui'

type P = { paper: Record<string, string>; actual: Record<string, string>; recommendation: { amount: string; remaining_capital: string; reasons: string[]; label: string }; policy: Record<string, string | boolean>; overexposure: string[] }

export default function Profit() {
  const p = usePoll<P>('/api/profit', 10000)
  const [pol, setPol] = useState<Record<string, string | boolean> | null>(null)
  useEffect(() => { if (p.data && !pol) setPol(p.data.policy) }, [p.data, pol])
  const a = useAction()
  return (
    <div className="space-y-4">
      <ErrorNote error={p.error} />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Paper net realised" value={money(p.data?.paper.net_realised)} origin="simulated" />
        <Stat label="Actual net trading profit" value={money(p.data?.actual.net_trading_profit)} origin="actual" />
        <Stat label="Actual net operating profit" value={money(p.data?.actual.net_operating_profit)} origin="actual" />
        <Stat label="Recommended withdrawal" value={money(p.data?.recommendation.amount)} origin="estimated" />
      </div>
      <p className="text-xs text-warn">{p.data?.recommendation.label}. {p.data?.recommendation.reasons.join('; ')}</p>
      {!!p.data?.overexposure.length && <p className="text-sm text-loss">Overexposure: {p.data.overexposure.join('; ')}</p>}
      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Paper P&L" origin="simulated">{p.data && <KV data={p.data.paper} />}</Card>
        <Card title="Actual economics" origin="actual">{p.data && <KV data={p.data.actual} />}</Card>
        <Card title="Withdrawal policy">
          {pol && <div className="grid gap-1">{Object.entries(pol).map(([k, v]) => typeof v === 'boolean'
            ? <label key={k} className="flex items-center gap-1 text-xs"><input type="checkbox" checked={v} onChange={e => setPol({ ...pol, [k]: e.target.checked })} />{k.replaceAll('_', ' ')}</label>
            : <label key={k} className="grid text-xs text-slate-400">{k.replaceAll('_', ' ')}<input className={inputCls} value={v} onChange={e => setPol({ ...pol, [k]: e.target.value })} /></label>)}
            <Button onClick={() => a.run(() => post('/api/profit/policy', pol, 'PUT'), () => 'Policy saved')}>Save policy</Button></div>}
          {a.msg && <p className="text-xs text-slate-400">{a.msg}</p>}
        </Card>
      </div>
      <Revenue />
    </div>
  )
}
