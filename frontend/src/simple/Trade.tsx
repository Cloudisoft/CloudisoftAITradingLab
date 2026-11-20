import { useEffect, useState } from 'react'
import { api } from '../api'
import { Sheet, SignIn, isSignedIn, refreshAll, usd } from './kit'

type Preview = { approved: boolean; qty: string; price: string; notional: string; fees: string; friendly_reasons: string[]; name: string }
type Result = { status: string; qty: string; price: string | null; fees: string; friendly_reasons: string[]; name: string }

export default function TradeSheet({ symbol, name, side, open, onClose, cash, holdingQty, price }: {
  symbol: string; name: string; side: 'buy' | 'sell'; open: boolean; onClose: () => void; cash: number; holdingQty: number; price: number
}) {
  const [amount, setAmount] = useState('')
  const [sellAll, setSellAll] = useState(false)
  const [pv, setPv] = useState<Preview | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [res, setRes] = useState<Result | null>(null)
  const [busy, setBusy] = useState(false)
  const [, force] = useState(0)
  const holdingValue = holdingQty * price
  const max = side === 'buy' ? cash : holdingValue

  useEffect(() => { if (open) { setAmount(''); setSellAll(false); setPv(null); setErr(null); setRes(null) } }, [open, side])
  const body = () => ({ symbol, side, amount_usd: sellAll ? null : amount || null, sell_all: sellAll })
  useEffect(() => {
    if (!open || !isSignedIn() || (!sellAll && !(Number(amount) > 0))) { setPv(null); return }
    const t = setTimeout(() => api<Preview>('/api/trade/preview', { method: 'POST', body: JSON.stringify(body()) })
      .then(p => { setPv(p); setErr(null) }).catch(e => { setPv(null); setErr(String(e).replace(/^Error: \d+ /, '')) }), 350)
    return () => clearTimeout(t)
  }, [amount, sellAll, open]) // eslint-disable-line react-hooks/exhaustive-deps

  const verb = side === 'buy' ? 'Buy' : 'Sell'
  const confirm = async () => {
    setBusy(true)
    try { const r = await api<Result>('/api/trade', { method: 'POST', body: JSON.stringify(body()) }); setRes(r); refreshAll() }
    catch (e) { setErr(String(e).replace(/^Error: \d+ /, '')) } finally { setBusy(false) }
  }
  const chip = (label: string, v: number | 'all') => (
    <button type="button" onClick={() => { if (v === 'all') { setSellAll(true); setAmount(holdingValue.toFixed(2)) } else { setSellAll(false); setAmount(v.toFixed(2)) } }}
      className="rounded-full border border-line px-3 py-1.5 text-sm font-medium hover:border-violet">{label}</button>)

  return (
    <Sheet open={open} onClose={onClose} title={`${verb} ${name}`}>
      {!isSignedIn() ? (<><p className="mb-3 text-sm text-muted">Sign in to place practice trades.</p><SignIn onDone={() => force(x => x + 1)} /></>) : res ? (
        <div className="space-y-3 text-center">
          {res.status === 'filled' ? (<>
            <p className="num text-2xl font-semibold text-up">{side === 'buy' ? 'Bought' : 'Sold'}</p>
            <p className="text-sm text-muted">{res.qty} {name} at {usd(res.price)} · fee {usd(res.fees)}</p>
          </>) : (<>
            <p className="num text-2xl font-semibold text-down">Not placed</p>
            {res.friendly_reasons.map(r => <p key={r} className="text-sm">{r}</p>)}
          </>)}
          <p className="text-xs text-muted">Practice trade with simulated money.</p>
          <button onClick={onClose} className="w-full rounded-xl bg-navy py-3 font-semibold text-white">Done</button>
        </div>
      ) : (
        <div className="space-y-4">
          <label className="block">
            <span className="text-sm text-muted">Amount in dollars</span>
            <div className="mt-1 flex items-center rounded-2xl border border-line bg-canvas px-4 focus-within:border-violet">
              <span className="num text-2xl text-muted">$</span>
              <input autoFocus inputMode="decimal" value={amount} placeholder="0.00"
                onChange={e => { setSellAll(false); setAmount(e.target.value.replace(/[^\d.]/g, '')) }}
                className="no-ring num w-full bg-transparent px-2 py-3 text-3xl font-semibold outline-none" />
            </div>
            <span className="mt-1 block text-xs text-muted">{side === 'buy' ? `Available: ${usd(cash)}` : `You own ${usd(holdingValue)} of ${name}`}</span>
          </label>
          <div className="flex flex-wrap gap-2">
            {side === 'buy' ? <>{chip('$5', 5)}{chip('$10', 10)}{chip('25%', max * 0.25)}{chip('50%', max * 0.5)}</> : <>{chip('25%', max * 0.25)}{chip('50%', max * 0.5)}{chip('Sell all', 'all')}</>}
          </div>
          {pv && (
            <div className="space-y-1.5 rounded-2xl bg-canvas p-4 text-sm">
              <div className="flex justify-between"><span className="text-muted">You {side === 'buy' ? 'get' : 'sell'}</span><span className="num">{pv.qty} {name}</span></div>
              <div className="flex justify-between"><span className="text-muted">Price</span><span className="num">{usd(pv.price)}</span></div>
              <div className="flex justify-between"><span className="text-muted">Estimated fee</span><span className="num">{usd(pv.fees, 4)}</span></div>
              <div className={`mt-2 rounded-xl px-3 py-2 ${pv.approved ? 'bg-up/10 text-up' : 'bg-down/10 text-down'}`}>
                {pv.approved ? 'Safety check passed.' : pv.friendly_reasons.map(r => <p key={r}>{r}</p>)}
              </div>
            </div>)}
          {err && <p className="text-sm text-down">{err}</p>}
          <button disabled={!pv?.approved || busy} onClick={confirm}
            className={`w-full rounded-xl py-3.5 text-base font-semibold text-white disabled:opacity-40 ${side === 'buy' ? 'bg-up' : 'bg-down'}`}>
            {busy ? 'Placing…' : `${verb} ${name}`}
          </button>
          <p className="text-center text-xs text-muted">Practice money only. No real funds are used.</p>
        </div>
      )}
    </Sheet>
  )
}
