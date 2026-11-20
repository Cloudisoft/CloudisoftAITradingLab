import { Card, usePoll } from '../ui'

type S = { live_trading_gates: Record<string, boolean | string[]> }

export default function Live() {
  const s = usePoll<S>('/api/settings', 30000)
  const gates = s.data?.live_trading_gates ?? {}
  return (
    <div className="space-y-4">
      <p className="rounded-lg border border-loss/40 bg-loss/10 p-3 text-sm text-loss">Live trading is DISABLED. Broker/exchange connections are deferred by the owner. Every gate below must pass, and each real order still goes through the independent risk engine and the configured confirmation policy.</p>
      <Card title="Live-trading gates">
        {s.error ? <p className="text-sm text-slate-400">Sign in as owner to view gate status.</p> :
          <ul className="space-y-1 text-sm">{Object.entries(gates).map(([k, v]) => <li key={k} className="flex justify-between"><span>{k.replaceAll('_', ' ')}</span><span className={v === true || (Array.isArray(v) && v.length) ? 'text-gain' : 'text-loss'}>{Array.isArray(v) ? (v.join(', ') || 'none') : v ? 'pass' : 'not satisfied'}</span></li>)}</ul>}
      </Card>
      <Card title="Path to live (owner decisions)"><ol className="list-decimal space-y-1 pl-5 text-sm text-slate-300">
        <li>Connect a broker/exchange with trade-only, IP-restricted keys (withdrawals disabled).</li>
        <li>Paper trade on real market data for at least 30 days and 50 trades.</li>
        <li>Pass out-of-sample, walk-forward and Monte Carlo checks with costs.</li>
        <li>Verify SEBI / exchange / RBI-FEMA / tax requirements for the chosen market.</li>
        <li>Drill the kill switch, then set CLAB_LIVE_TRADING_ENABLED and CLAB_OWNER_LIVE_TRADING_APPROVED.</li>
      </ol></Card>
    </div>
  )
}
