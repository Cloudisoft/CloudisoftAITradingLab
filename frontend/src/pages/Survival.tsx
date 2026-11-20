import { Fragment } from 'react'
import { Card, ErrorNote, Stat, money, usePoll } from '../ui'

type S = {
  state: string; survival_balance: string; daily_burn: string; monthly_burn_estimate: string; runway_days: string | null
  summary: Record<string, string>; policy: Record<string, string | number | boolean>; reasons: string[]
  profitability: { sustained: boolean; checks: Record<string, boolean>; days: number; trades: number }
  cost_by_agent: Record<string, string>; history: [string, string, string][]; note: string
}

const stateTone: Record<string, string> = {
  HIGH: 'text-gain', PROFITABLE: 'text-gain', NORMAL: 'text-accent', LOW_COMPUTE: 'text-warn', CRITICAL: 'text-loss', DEAD: 'text-loss',
}

export default function Survival() {
  const { data, error } = usePoll<S>('/api/survival')
  const s = data?.summary ?? {}
  return (
    <div className="space-y-4">
      <ErrorNote error={error} />
      <div className="rounded-xl border border-edge bg-panel p-5">
        <div className="text-xs uppercase tracking-wider text-slate-400">Current survival state</div>
        <div className={`text-4xl font-bold ${stateTone[data?.state ?? ''] ?? ''}`}>{data?.state ?? '—'}</div>
        <p className="mt-1 text-sm text-slate-400">{data?.reasons.join('; ') || 'Within thresholds.'} {data?.note}</p>
      </div>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Operational balance" value={money(data?.survival_balance)} origin="actual" />
        <Stat label="Daily costs (7d avg)" value={money(data?.daily_burn)} origin="actual" />
        <Stat label="Monthly costs" value={money(data?.monthly_burn_estimate)} origin="estimated" />
        <Stat label="Runway (days)" value={data?.runway_days ? money(data.runway_days, 1) : 'no burn yet'} origin="estimated" />
        <Stat label="Trading net profit" value={money(s.net_trading_profit)} origin="actual" />
        <Stat label="Verified external revenue" value={money(s.verified_external_revenue)} origin="actual" />
        <Stat label="Net operating profit" value={money(s.net_operating_profit)} origin="actual" />
        <Stat label="Expansion eligible" value={data?.profitability.sustained ? 'Yes — proposal only' : 'No'} />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Ledger breakdown" origin="actual">
          <dl className="grid grid-cols-2 gap-y-1 text-sm">
            {Object.entries(s).map(([k, v]) => (<Fragment key={k}><dt className="text-slate-400">{k.replaceAll('_', ' ')}</dt><dd className="text-right tabular-nums">{money(v)}</dd></Fragment>))}
          </dl>
        </Card>
        <Card title="Profitability verification">
          <ul className="space-y-1 text-sm">
            {Object.entries(data?.profitability.checks ?? {}).map(([k, ok]) => (
              <li key={k} className="flex justify-between"><span>{k.replaceAll('_', ' ')}</span><span className={ok ? 'text-gain' : 'text-slate-500'}>{ok ? 'pass' : 'not yet'}</span></li>
            ))}
          </ul>
          <h4 className="mt-4 text-xs uppercase text-slate-400">Cost per agent</h4>
          {Object.entries(data?.cost_by_agent ?? {}).map(([k, v]) => <div key={k} className="flex justify-between text-sm"><span>{k}</span><span>{money(v)}</span></div>)}
        </Card>
        <Card title="Active operating policy">
          <dl className="grid grid-cols-2 gap-y-1 text-sm">
            {Object.entries(data?.policy ?? {}).map(([k, v]) => (<Fragment key={k}><dt className="text-slate-400">{k.replaceAll('_', ' ')}</dt><dd className="text-right">{String(v)}</dd></Fragment>))}
          </dl>
        </Card>
        <Card title="State history">
          <ul className="space-y-1 text-sm">{(data?.history ?? []).slice(-10).reverse().map(([t, st, why]) => <li key={t + st}><b>{st}</b> <span className="text-slate-400">{t.slice(0, 19)} — {why}</span></li>)}</ul>
        </Card>
      </div>
    </div>
  )
}
