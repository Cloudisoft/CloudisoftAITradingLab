import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Card, ErrorNote, Stat, money, usePoll } from '../ui'

type O = {
  account_value: string; available_capital: string; realised_pnl: string; unrealised_pnl: string; fees_paid: string
  open_positions: number; survival_state: string; survival_runway_days: string | null; net_operating_profit: string
  equity_curve: [string, number][]; opportunities: { symbol: string; flags: string[]; snapshot: Record<string, number | null> }[]
}

export default function Overview() {
  const { data, error } = usePoll<O>('/api/overview')
  const tone = (v?: string) => (Number(v) > 0 ? 'gain' : Number(v) < 0 ? 'loss' : undefined)
  return (
    <div className="space-y-4">
      <ErrorNote error={error} />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Account value" value={money(data?.account_value)} origin="simulated" />
        <Stat label="Available capital" value={money(data?.available_capital)} origin="simulated" />
        <Stat label="Realised P&L" value={money(data?.realised_pnl)} tone={tone(data?.realised_pnl)} origin="simulated" />
        <Stat label="Unrealised P&L" value={money(data?.unrealised_pnl)} tone={tone(data?.unrealised_pnl)} origin="simulated" />
        <Stat label="Net operating profit" value={money(data?.net_operating_profit)} tone={tone(data?.net_operating_profit)} origin="actual" />
        <Stat label="Survival state" value={data?.survival_state ?? '—'} />
        <Stat label="Runway (days)" value={data?.survival_runway_days ? money(data.survival_runway_days, 1) : '∞ / no burn'} origin="estimated" />
        <Stat label="Open positions" value={data?.open_positions ?? '—'} origin="simulated" />
      </div>
      <Card title="Paper equity curve" origin="simulated">
        <div className="h-64">
          <ResponsiveContainer>
            <AreaChart data={(data?.equity_curve ?? []).map(([t, v]) => ({ t: t.slice(5, 16), v }))}>
              <XAxis dataKey="t" hide /><YAxis domain={['auto', 'auto']} width={60} stroke="#64748b" />
              <Tooltip contentStyle={{ background: '#121a2e', border: '1px solid #1f2a44' }} />
              <Area dataKey="v" stroke="#4f8cff" fill="#4f8cff22" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </Card>
      <Card title="Market scanner — opportunities (analysis only)" origin="simulated">
        <table className="w-full text-sm">
          <thead className="text-left text-xs text-slate-400"><tr><th>Symbol</th><th>Close</th><th>RSI</th><th>ADX</th><th>Flags</th></tr></thead>
          <tbody>
            {(data?.opportunities ?? []).map(o => (
              <tr key={o.symbol} className="border-t border-edge">
                <td className="py-1.5 font-medium">{o.symbol}</td><td>{money(o.snapshot.close, 2)}</td>
                <td>{money(o.snapshot.rsi14, 1)}</td><td>{money(o.snapshot.adx14, 1)}</td>
                <td className="text-xs text-slate-400">{o.flags.join(', ') || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  )
}
