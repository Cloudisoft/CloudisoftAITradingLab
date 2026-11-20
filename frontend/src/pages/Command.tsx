import { Button, Card, ErrorNote, Stat, post, useAction, usePoll } from '../ui'

type P = { id: string; kind: string; title: string; status: string; created_by: string; created_at: string; evidence: Record<string, unknown>; payload: Record<string, unknown> }
type A = { agent_id: string; name: string; status: string; task_count: number; spent_usd: string; tasks: { at: string; kind: string; status: string }[] }

export function Proposals() {
  const props = usePoll<{ proposals: P[] }>('/api/proposals', 8000)
  const a = useAction()
  const decide = (id: string, approve: boolean) => a.run(() => post(`/api/proposals/${id}/decision`, { approve }), () => (approve ? 'Approved and applied' : 'Rejected'))
  return (
    <Card title="Owner decisions (proposals)">
      {a.msg && <p className="mb-2 text-xs text-slate-400">{a.msg}</p>}
      <ul className="space-y-2 text-sm">{(props.data?.proposals ?? []).map(p => (
        <li key={p.id} className="rounded-lg border border-edge p-2">
          <div className="flex flex-wrap items-center justify-between gap-2"><span><b>{p.title}</b> <span className="text-xs text-slate-400">{p.kind} · by {p.created_by} · {p.status}</span></span>
            {p.status === 'pending' && <span className="flex gap-1"><Button onClick={() => decide(p.id, true)}>Approve</Button><Button tone="ghost" onClick={() => decide(p.id, false)}>Reject</Button></span>}</div>
          <details className="text-xs"><summary className="cursor-pointer text-slate-500">Evidence</summary><pre className="overflow-auto">{JSON.stringify(p.evidence, null, 1)}</pre></details>
        </li>))}{!props.data?.proposals.length && <li className="text-slate-500">No proposals</li>}</ul>
    </Card>
  )
}

export default function Command() {
  const ag = usePoll<{ agents: A[] }>('/api/agents', 10000)
  const notes = usePoll<{ notifications: { at: string; kind: string; severity: string; message: string }[] }>('/api/notifications', 10000)
  const st = usePoll<{ ticks: number; strategy: string; llm_available: boolean; last_error: string | null; kill_switch: boolean }>('/api/system/status', 5000)
  const sv = usePoll<{ state: string; runway_days: string | null }>('/api/survival', 10000)
  const active = (ag.data?.agents ?? []).filter(a => a.status === 'active').length
  return (
    <div className="space-y-4">
      <ErrorNote error={ag.error} />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <Stat label="Survival state" value={sv.data?.state ?? '—'} />
        <Stat label="Active agents" value={`${active}/${ag.data?.agents.length ?? 0}`} />
        <Stat label="Paper loop ticks" value={st.data?.ticks ?? '—'} />
        <Stat label="Active strategy" value={<span className="text-base">{st.data?.strategy ?? '—'}</span>} />
        <Stat label="LLM" value={st.data?.llm_available ? 'available' : 'rule-based'} />
      </div>
      {st.data?.last_error && <p className="text-xs text-warn">Last error: {st.data.last_error}</p>}
      <div className="grid gap-4 lg:grid-cols-2">
        <Proposals />
        <Card title="Owner notifications">
          <ul className="max-h-80 space-y-1 overflow-auto text-xs">{(notes.data?.notifications ?? []).map((n, i) => <li key={i}><span className={n.severity === 'critical' ? 'text-loss' : n.severity === 'warning' ? 'text-warn' : 'text-slate-400'}>{n.at.slice(0, 19)} [{n.kind}]</span> {n.message}</li>)}</ul>
        </Card>
      </div>
      <Card title="Agent activity">
        <div className="grid gap-2 md:grid-cols-2 lg:grid-cols-3">{(ag.data?.agents ?? []).map(a => (
          <div key={a.agent_id} className="rounded-lg border border-edge p-2 text-xs"><b className="text-sm">{a.name}</b> <span className={a.status === 'active' ? 'text-gain' : 'text-warn'}>{a.status}</span>
            <div className="text-slate-400">{a.task_count} tasks · spent ${a.spent_usd}</div>
            <div className="text-slate-500">{a.tasks.at(-1) ? `${a.tasks.at(-1)!.at.slice(11, 19)} ${a.tasks.at(-1)!.kind} ${a.tasks.at(-1)!.status}` : 'idle'}</div></div>))}</div>
      </Card>
    </div>
  )
}
