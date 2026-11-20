import { useEffect, useState } from 'react'
import { Button, Card, ErrorNote, KV, inputCls, post, useAction, usePoll } from '../ui'

type S = { risk_config: Record<string, string | number | boolean>; survival_config: Record<string, unknown>; paper: Record<string, unknown>; holidays: Record<string, string[]>; llm_available: boolean }

export default function Settings() {
  const s = usePoll<S>('/api/settings', 30000)
  const users = usePoll<{ users: { email: string; role: string; totp: boolean }[] }>('/api/users', 30000)
  const [risk, setRisk] = useState<Record<string, string | number | boolean> | null>(null)
  useEffect(() => { if (s.data && !risk) setRisk(s.data.risk_config) }, [s.data, risk])
  const [nu, setNu] = useState({ email: '', password: '', role: 'viewer' })
  const [totp, setTotp] = useState<{ secret: string; otpauth_uri: string } | null>(null)
  const [code, setCode] = useState('')
  const a = useAction()
  return (
    <div className="space-y-4">
      <ErrorNote error={s.error} />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Risk limits (owner; bounded by immutable ceilings; audited)">
          {risk && <div className="grid gap-1">{Object.entries(risk).map(([k, v]) => typeof v === 'boolean'
            ? <label key={k} className="flex items-center gap-1 text-xs"><input type="checkbox" checked={v} onChange={e => setRisk({ ...risk, [k]: e.target.checked })} />{k.replaceAll('_', ' ')}</label>
            : <label key={k} className="grid text-xs text-slate-400">{k.replaceAll('_', ' ')}<input className={inputCls} value={String(v)} onChange={e => setRisk({ ...risk, [k]: e.target.value })} /></label>)}
            <Button onClick={() => a.run(() => post('/api/settings/risk', { config: risk, justification: 'owner edit via dashboard' }, 'PUT'), () => 'Saved')}>Save risk limits</Button></div>}
        </Card>
        <Card title="Paper trading & survival configuration">{s.data && <><KV data={s.data.paper} /><div className="my-2 border-t border-edge" /><KV data={s.data.survival_config as Record<string, unknown>} /></>}</Card>
        <Card title="Users & roles">
          <ul className="mb-2 text-sm">{(users.data?.users ?? []).map(u => <li key={u.email}>{u.email} · {u.role} · 2FA {u.totp ? 'on' : 'off'}</li>)}</ul>
          <div className="flex flex-wrap gap-1"><input className={inputCls} placeholder="email" value={nu.email} onChange={e => setNu({ ...nu, email: e.target.value })} />
            <input className={inputCls} type="password" placeholder="password (12+)" value={nu.password} onChange={e => setNu({ ...nu, password: e.target.value })} />
            <select className={inputCls} value={nu.role} onChange={e => setNu({ ...nu, role: e.target.value })}><option>viewer</option><option>operator</option></select>
            <Button onClick={() => a.run(() => post('/api/users', nu), () => 'User created')}>Add</Button></div>
        </Card>
        <Card title="Two-factor authentication (TOTP)">
          {!totp ? <Button onClick={() => a.run(() => post<{ secret: string; otpauth_uri: string }>('/api/users/me/totp', {}), r => { setTotp(r); return 'Add this secret to your authenticator app, then confirm' })}>Enable 2FA</Button>
            : <div className="space-y-1 text-xs"><p>Secret: <code>{totp.secret}</code></p><p className="break-all text-slate-500">{totp.otpauth_uri}</p>
              <input className={inputCls} placeholder="6-digit code" value={code} onChange={e => setCode(e.target.value)} />
              <Button onClick={() => a.run(() => post('/api/users/me/totp/confirm', { secret: totp.secret, code }), () => '2FA enabled')}>Confirm</Button></div>}
        </Card>
      </div>
      {a.msg && <p className="text-xs text-slate-400">{a.msg}</p>}
    </div>
  )
}
