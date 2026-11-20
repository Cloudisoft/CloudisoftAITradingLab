import { Card, ErrorNote, money, usePoll } from '../ui'

type P = { balances: { currency: string; available: string; total: string }[]; positions: { symbol: string; quantity: string; average_price: string; market_price: string }[]; orders: { client_order_id: string; symbol: string; side: string; status: string; filled_quantity: string; average_price: string | null; fees: string; reason: string | null }[] }

export default function Paper() {
  const { data, error } = usePoll<P>('/api/paper/portfolio')
  return (
    <div className="space-y-4">
      <ErrorNote error={error} />
      <p className="rounded-lg border border-accent/40 bg-accent/10 p-3 text-sm text-accent">PAPER TRADING — simulated balances and fills. No order here can reach a live account.</p>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Balances" origin="simulated">{data?.balances.map(b => <div key={b.currency} className="flex justify-between text-sm"><span>{b.currency}</span><span>avail {money(b.available)} / total {money(b.total)}</span></div>)}</Card>
        <Card title="Positions" origin="simulated">{data?.positions.length ? data.positions.map(p => <div key={p.symbol} className="flex justify-between text-sm"><span>{p.symbol}</span><span>{money(p.quantity, 6)} @ {money(p.average_price, 2)} (mkt {money(p.market_price, 2)})</span></div>) : <p className="text-sm text-slate-500">No open positions</p>}</Card>
      </div>
      <Card title="Order blotter (latest 100)" origin="simulated">
        <div className="overflow-x-auto"><table className="w-full text-sm">
          <thead className="text-left text-xs text-slate-400"><tr><th>ID</th><th>Symbol</th><th>Side</th><th>Status</th><th>Qty</th><th>Price</th><th>Fee</th><th>Reason</th></tr></thead>
          <tbody>{(data?.orders ?? []).slice().reverse().map(o => (
            <tr key={o.client_order_id} className="border-t border-edge"><td className="py-1 font-mono text-xs">{o.client_order_id.slice(0, 8)}</td><td>{o.symbol}</td><td className={o.side === 'buy' ? 'text-gain' : 'text-loss'}>{o.side}</td><td>{o.status}</td><td>{money(o.filled_quantity, 6)}</td><td>{money(o.average_price, 2)}</td><td>{money(o.fees, 6)}</td><td className="text-xs text-slate-400">{o.reason}</td></tr>
          ))}</tbody>
        </table></div>
      </Card>
    </div>
  )
}
