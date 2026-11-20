import { useState } from 'react'
import { Button, Card, ErrorNote, Label, inputCls, money, post, useAction, usePoll } from '../ui'

type Acc = Record<string, string | number>
type W = { accounts: Acc[]; transactions: { kind: string; amount: string; status: string; provider_reference: string | null; at: string; origin: string }[]; withdrawal_requests: { request_id: string; amount: string; destination: string; status: string; history: string[] }[]; providers: { provider: string; status: string; funding: string }[]; custody_notice: string }
const CONF = ['provider', 'asset', 'amount', 'destination', 'network', 'fees', 'final_details']

export default function Wallet() {
  const w = usePoll<W>('/api/wallet', 8000)
  const a = useAction()
  const [dep, setDep] = useState('10')
  const [wd, setWd] = useState({ amount: '1', destination: 'owner bank (simulated)', estimated_fee: '0' })
  const [checks, setChecks] = useState<Record<string, boolean>>({})
  return (
    <div className="space-y-4">
      <ErrorNote error={w.error} />
      <p className="rounded-lg border border-accent/40 bg-accent/10 p-3 text-sm text-accent">{w.data?.custody_notice} Never enter broker passwords, bank passwords or OTPs here.</p>
      <Card title="Accounts">
        <div className="overflow-x-auto"><table className="w-full text-sm"><thead className="text-left text-xs text-slate-400"><tr>{['provider', 'currency', 'available_balance', 'total_balance', 'invested_capital', 'withdrawable_balance', 'open_positions', 'realised_pnl', 'unrealised_pnl', 'deposits', 'withdrawals'].map(h => <th key={h} className="pr-2">{h.replaceAll('_', ' ')}</th>)}<th /></tr></thead>
          <tbody>{(w.data?.accounts ?? []).map(x => <tr key={String(x.account_id)} className="border-t border-edge">{['provider', 'currency', 'available_balance', 'total_balance', 'invested_capital', 'withdrawable_balance', 'open_positions', 'realised_pnl', 'unrealised_pnl', 'deposits', 'withdrawals'].map(h => <td key={h} className="py-1 pr-2 tabular-nums">{typeof x[h] === 'string' && !isNaN(Number(x[h])) ? money(x[h]) : x[h]}</td>)}<td><Label origin="simulated" /></td></tr>)}
            {(w.data?.providers ?? []).map(p => <tr key={p.provider} className="border-t border-edge text-slate-500"><td className="py-1">{p.provider}</td><td colSpan={10}>{p.status} — funding: {p.funding}</td><td /></tr>)}</tbody></table></div>
      </Card>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Simulated deposit (owner)" origin="simulated">
          <div className="flex gap-2"><input className={inputCls} value={dep} onChange={e => setDep(e.target.value)} /><Button onClick={() => a.run(() => post('/api/paper/deposit', { amount: dep }), () => 'Deposited (simulated)')}>Deposit</Button></div>
        </Card>
        <Card title="Request withdrawal" origin="simulated">
          <div className="grid gap-1">{Object.entries(wd).map(([k, v]) => <label key={k} className="grid text-xs text-slate-400">{k}<input className={inputCls} value={v} onChange={e => setWd({ ...wd, [k]: e.target.value })} /></label>)}</div>
          <Button onClick={() => a.run(() => post('/api/wallet/withdrawals', { provider: 'paper', ...wd }), () => 'Requested — owner must confirm every detail below')}>Request</Button>
        </Card>
      </div>
      {a.msg && <p className="text-xs text-slate-400">{a.msg}</p>}
      <Card title="Withdrawal approvals (owner confirms every field)">
        <div className="mb-2 flex flex-wrap gap-3 text-xs">{CONF.map(c => <label key={c} className="flex items-center gap-1"><input type="checkbox" checked={!!checks[c]} onChange={e => setChecks({ ...checks, [c]: e.target.checked })} />{c.replace('_', ' ')} confirmed</label>)}</div>
        <ul className="space-y-1 text-sm">{(w.data?.withdrawal_requests ?? []).slice().reverse().map(r => (
          <li key={r.request_id} className="flex flex-wrap items-center justify-between gap-2 border-t border-edge py-1"><span>{money(r.amount)} → {r.destination} · <b>{r.status}</b></span>
            {r.status === 'pending_owner_approval' && <span className="flex gap-1"><Button onClick={() => a.run(() => post(`/api/wallet/withdrawals/${r.request_id}/decision`, { approve: true, confirmations: checks }))}>Approve</Button><Button tone="ghost" onClick={() => a.run(() => post(`/api/wallet/withdrawals/${r.request_id}/decision`, { approve: false }))}>Reject</Button></span>}</li>))}</ul>
      </Card>
      <Card title="Transaction history" origin="simulated">
        <ul className="text-xs">{(w.data?.transactions ?? []).slice().reverse().map((t, i) => <li key={i}>{t.at.slice(0, 19)} {t.kind} {money(t.amount)} · {t.status} · ref {t.provider_reference ?? '—'}</li>)}</ul>
      </Card>
    </div>
  )
}
