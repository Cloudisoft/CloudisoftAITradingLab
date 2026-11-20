import { Fragment } from 'react'
import { useState } from 'react'
import { api, login } from '../api'
import { Card, ErrorNote, usePoll } from '../ui'

type A = { verified: boolean; events: { seq: number; at: string; event: string; actor: string; hash: string }[] }
type St = { kill_switch: boolean; live_trading_allowed: boolean; immutable_policy: Record<string, string> }

export default function Security() {
  const audit = usePoll<A>('/api/audit', 15000)
  const status = usePoll<St>('/api/system/status', 5000)
  const [email, setEmail] = useState(''); const [pw, setPw] = useState(''); const [msg, setMsg] = useState<string | null>(null)
  const toggle = (engaged: boolean) => api('/api/system/kill-switch', { method: 'POST', body: JSON.stringify({ engaged }) }).then(() => setMsg(engaged ? 'Kill switch ENGAGED' : 'Kill switch released')).catch(e => setMsg(String(e)))
  const inp = 'rounded-lg border border-edge bg-ink px-2 py-1.5 text-sm'
  return (
    <div className="space-y-4">
      <ErrorNote error={audit.error} />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Emergency kill switch">
          <p className="mb-3 text-sm">Status: <b className={status.data?.kill_switch ? 'text-loss' : 'text-gain'}>{status.data?.kill_switch ? 'ENGAGED — no new orders' : 'off'}</b> · Live trading: <b>{status.data?.live_trading_allowed ? 'allowed' : 'disabled'}</b></p>
          <div className="flex gap-2"><button onClick={() => toggle(true)} className="rounded-lg bg-loss px-4 py-2 font-semibold text-white">ENGAGE</button><button onClick={() => toggle(false)} className="rounded-lg border border-edge px-4 py-2">Release (owner)</button></div>
          {msg && <p className="mt-2 text-sm text-slate-400">{msg}</p>}
          <form className="mt-4 flex flex-wrap gap-2" onSubmit={e => { e.preventDefault(); login(email, pw).then(() => setMsg('Signed in for this browser session')).catch(er => setMsg(String(er))) }}>
            <input className={inp} placeholder="owner email" value={email} onChange={e => setEmail(e.target.value)} />
            <input className={inp} type="password" placeholder="password" value={pw} onChange={e => setPw(e.target.value)} />
            <button className="rounded-lg border border-edge px-3">Sign in</button>
          </form>
        </Card>
        <Card title="Immutable safety policy (cannot be changed by any agent)">
          <dl className="grid grid-cols-2 gap-y-1 text-sm">{Object.entries(status.data?.immutable_policy ?? {}).map(([k, v]) => (<Fragment key={k}><dt className="text-slate-400">{k.replaceAll('_', ' ')}</dt><dd className="text-right font-mono">{v}</dd></Fragment>))}</dl>
        </Card>
      </div>
      <Card title={`Audit trail — hash chain ${audit.data?.verified ? 'VERIFIED' : 'not verified'}`}>
        <ul className="max-h-96 space-y-0.5 overflow-auto font-mono text-xs">{(audit.data?.events ?? []).slice().reverse().map(e => <li key={e.seq}>#{e.seq} {e.at.slice(0, 19)} <b>{e.event}</b> by {e.actor} <span className="text-slate-500">{e.hash.slice(0, 12)}</span></li>)}</ul>
      </Card>
    </div>
  )
}
