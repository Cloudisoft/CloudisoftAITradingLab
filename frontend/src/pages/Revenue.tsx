import { useState } from 'react'
import { Button, Card, inputCls, money, post, useAction, usePoll } from '../ui'

type O = { id: string; name: string; description: string; target_customers: string; status: string; delivery_cost_monthly: string; expected_revenue_monthly: string; score: { estimated_monthly_margin: string; label: string }; receipts: { amount: string; reference: string }[] }

export default function Revenue() {
  const r = usePoll<{ opportunities: O[]; compliance_checklist: string[]; verified_external_revenue: string }>('/api/revenue', 20000)
  const a = useAction()
  const [n, setN] = useState({ name: '', description: '', target_customers: '', delivery_cost_monthly: '0', expected_revenue_monthly: '0' })
  const [rc, setRc] = useState<Record<string, { amount: string; reference: string }>>({})
  return (
    <Card title={`Revenue opportunities (non-trading) · verified received: ${money(r.data?.verified_external_revenue)}`}>
      <ul className="mb-3 list-disc pl-5 text-xs text-slate-400">{r.data?.compliance_checklist.map(c => <li key={c}>{c}</li>)}</ul>
      <div className="space-y-2">{(r.data?.opportunities ?? []).map(o => (
        <div key={o.id} className="rounded-lg border border-edge p-2 text-sm">
          <div className="flex flex-wrap justify-between gap-2"><span><b>{o.name}</b> <span className="text-xs text-slate-400">{o.status} · est. margin {money(o.score.estimated_monthly_margin)}/mo (estimated)</span></span>
            {['idea', 'researching'].includes(o.status) && <Button tone="ghost" onClick={() => a.run(() => post(`/api/revenue/${o.id}/propose`, {}), () => 'Proposed to owner')}>Propose</Button>}</div>
          <p className="text-xs text-slate-400">{o.description} — for {o.target_customers}</p>
          {['approved', 'active'].includes(o.status) && <div className="mt-1 flex flex-wrap gap-1">
            <input className={inputCls + ' w-24'} placeholder="amount" onChange={e => setRc({ ...rc, [o.id]: { ...rc[o.id], amount: e.target.value } })} />
            <input className={inputCls} placeholder="payment reference" onChange={e => setRc({ ...rc, [o.id]: { ...rc[o.id], reference: e.target.value } })} />
            <Button onClick={() => a.run(() => post(`/api/revenue/${o.id}/receipts`, { ...rc[o.id], payer: 'customer' }), () => 'Receipt recorded as verified revenue')}>Record received payment</Button></div>}
        </div>))}</div>
      <div className="mt-3 grid gap-1 md:grid-cols-5">{Object.entries(n).map(([k, v]) => <input key={k} className={inputCls} placeholder={k.replaceAll('_', ' ')} value={v} onChange={e => setN({ ...n, [k]: e.target.value })} />)}</div>
      <Button onClick={() => a.run(() => post('/api/revenue', n), () => 'Added')}>Add opportunity</Button>
      {a.msg && <p className="mt-1 text-xs text-slate-400">{a.msg}</p>}
    </Card>
  )
}
