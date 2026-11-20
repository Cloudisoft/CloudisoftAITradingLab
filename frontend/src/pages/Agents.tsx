import { useState } from 'react'
import { Button, Card, ErrorNote, inputCls, post, useAction, usePoll } from '../ui'
import { Proposals } from './Command'

type A = { agent_id: string; name: string; scope: string; status: string; builtin: boolean; budget_usd: string; spent_usd: string; task_count: number; approved_by: string | null }

export default function Agents() {
  const ag = usePoll<{ agents: A[]; max_agents: number; replication: string }>('/api/agents', 10000)
  const [f, setF] = useState({ agent_id: 'research_assistant_2', name: 'Research Assistant 2', scope: 'additional market coverage', budget_usd: '0.50', justification: '' })
  const a = useAction()
  const exp = { title: 'Add data provider', description: '', initial_cost: '0', monthly_cost: '10', expected_monthly_benefit: '0', risk: '' }
  const [e, setE] = useState(exp)
  const [assess, setAssess] = useState<Record<string, unknown> | null>(null)
  return (
    <div className="space-y-4">
      <ErrorNote error={ag.error} />
      <p className="text-xs text-slate-400">{ag.data?.replication} · hard cap {ag.data?.max_agents} agents · every agent has its own budget, scope, task log and cost ledger.</p>
      <Card title="Agents">
        <table className="w-full text-sm"><thead className="text-left text-xs text-slate-400"><tr><th>Agent</th><th>Scope</th><th>Budget</th><th>Spent</th><th>Tasks</th><th>Status</th><th /></tr></thead>
          <tbody>{(ag.data?.agents ?? []).map(x => (
            <tr key={x.agent_id} className="border-t border-edge"><td className="py-1">{x.name}{!x.builtin && <span className="ml-1 text-xs text-accent">approved by {x.approved_by}</span>}</td><td className="text-xs text-slate-400">{x.scope}</td><td>${x.budget_usd}</td><td>${x.spent_usd}</td><td>{x.task_count}</td><td>{x.status}</td>
              <td className="text-right">{x.status === 'active' ? <Button tone="ghost" onClick={() => a.run(() => post(`/api/agents/${x.agent_id}/status`, { status: 'paused' }))}>Pause</Button> : <Button tone="ghost" onClick={() => a.run(() => post(`/api/agents/${x.agent_id}/status`, { status: 'active' }))}>Resume</Button>}</td></tr>))}</tbody></table>
        {a.msg && <p className="mt-2 text-xs text-slate-400">{a.msg}</p>}
      </Card>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Propose a new agent (owner approval required)">
          <div className="grid gap-1">{Object.entries(f).map(([k, v]) => <label key={k} className="grid text-xs text-slate-400">{k}<input className={inputCls} value={v} onChange={ev => setF({ ...f, [k]: ev.target.value })} /></label>)}</div>
          <Button onClick={() => a.run(() => post('/api/agents/proposals', f), () => 'Proposal submitted')}>Submit proposal</Button>
        </Card>
        <Card title="Expansion assessment">
          <div className="grid gap-1">{Object.entries(e).map(([k, v]) => <label key={k} className="grid text-xs text-slate-400">{k}<input className={inputCls} value={v} onChange={ev => setE({ ...e, [k]: ev.target.value })} /></label>)}</div>
          <div className="flex gap-2"><Button tone="ghost" onClick={() => a.run(() => post<Record<string, unknown>>('/api/expansion/assess', e), r => { setAssess(r); return 'Assessed' })}>Assess</Button>
            <Button onClick={() => a.run(() => post('/api/expansion/proposals', e), () => 'Proposal submitted')}>Propose</Button></div>
          {assess && <pre className="mt-2 overflow-auto text-xs">{JSON.stringify(assess, null, 1)}</pre>}
        </Card>
      </div>
      <Proposals />
    </div>
  )
}
