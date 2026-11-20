import { useState } from 'react'
import { Button, Card, ErrorNote, inputCls, post, useAction, usePoll } from '../ui'

type D = { symbol: string; rows: number; start: string; end: string; origin: string; source: string }

export default function MarketData() {
  const [t, setT] = useState(0)
  const ds = usePoll<{ datasets: D[] }>('/api/research/datasets?t=' + t, 30000)
  const [symbol, setSymbol] = useState('BTCUSDT'); const [source, setSource] = useState(''); const [real, setReal] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const a = useAction()
  const upload = async () => {
    if (!file) return
    const csv = await file.text()
    await a.run(() => post('/api/research/datasets', { symbol, csv, source, owner_asserts_real: real }), () => { setT(x => x + 1); return 'Uploaded and validated' })
  }
  return (
    <div className="space-y-4">
      <ErrorNote error={ds.error} />
      <p className="rounded-lg border border-warn/40 bg-warn/10 p-3 text-sm text-warn">Live provider feeds are deferred (broker/exchange connections postponed). Until then the paper loop uses synthetic data; you can upload real historical candles for backtesting or replay (CLAB_MARKET_DATA_SOURCE=csv_replay).</p>
      <Card title="Upload historical candles (CSV: timestamp,open,high,low,close,volume)">
        <div className="flex flex-wrap items-end gap-2 text-sm">
          <label className="grid">Symbol<input className={inputCls} value={symbol} onChange={e => setSymbol(e.target.value.toUpperCase())} /></label>
          <label className="grid">Source<input className={inputCls} placeholder="e.g. Binance data export" value={source} onChange={e => setSource(e.target.value)} /></label>
          <label className="flex items-center gap-1"><input type="checkbox" checked={real} onChange={e => setReal(e.target.checked)} />This is a genuine provider export</label>
          <input type="file" accept=".csv" onChange={e => setFile(e.target.files?.[0] ?? null)} />
          <Button onClick={upload} disabled={!file || !source || a.busy}>Upload</Button>
        </div>
        {a.msg && <p className="mt-2 text-xs text-slate-400">{a.msg}</p>}
      </Card>
      <Card title="Datasets">
        <table className="w-full text-sm"><thead className="text-left text-xs text-slate-400"><tr><th>Symbol</th><th>Rows</th><th>From</th><th>To</th><th>Label</th><th>Source</th></tr></thead>
          <tbody>{(ds.data?.datasets ?? []).map(d => <tr key={d.symbol} className="border-t border-edge"><td className="py-1">{d.symbol}</td><td>{d.rows}</td><td>{d.start.slice(0, 16)}</td><td>{d.end.slice(0, 16)}</td><td>{d.origin}</td><td>{d.source}</td></tr>)}</tbody></table>
      </Card>
    </div>
  )
}
