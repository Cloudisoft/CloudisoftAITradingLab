import { Card } from '../ui'

export default function Brokers() {
  const rows = [
    ['Binance', 'via CCXT (MIT)', 'Deferred by owner; official docs to be verified first'],
    ['Zerodha', 'official kiteconnect SDK', 'Deferred by owner; Kite Connect subscription decision pending'],
    ['Groww', '—', 'Optional future integration'],
  ]
  return (
    <div className="space-y-4">
      <p className="rounded-lg border border-warn/40 bg-warn/10 p-3 text-sm text-warn">Connecting brokers and exchanges is postponed. The interfaces are in place (MarketDataProvider, BrokerConnector, FundingInterface, WithdrawalInterface), so adapters can be added without rebuilding the platform.</p>
      <Card title="Planned connections">
        <table className="w-full text-sm"><thead className="text-left text-xs text-slate-400"><tr><th>Provider</th><th>Integration</th><th>Status</th></tr></thead>
          <tbody>{rows.map(r => <tr key={r[0]} className="border-t border-edge"><td className="py-1">{r[0]}</td><td>{r[1]}</td><td className="text-slate-400">{r[2]}</td></tr>)}</tbody></table>
      </Card>
      <Card title="When you connect"><ul className="list-disc space-y-1 pl-5 text-sm text-slate-300">
        <li>Create trade-only API keys. Never enable withdrawal permission.</li>
        <li>Restrict keys to the server's static IP where supported.</li>
        <li>Enter keys only in this platform's encrypted credential form or Railway variables — never in chat or git.</li>
        <li>Never share broker passwords, PINs, bank passwords or OTPs.</li>
      </ul></Card>
    </div>
  )
}
