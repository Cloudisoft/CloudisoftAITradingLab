import { useState } from 'react'
import { Button, Card, ErrorNote, usePoll } from '../ui'

export default function Reports() {
  const [period, setPeriod] = useState<'daily' | 'monthly'>('daily')
  const r = usePoll<{ markdown: string } & Record<string, unknown>>(`/api/reports/${period}`, 60000)
  const download = () => {
    if (!r.data) return
    const blob = new Blob([r.data.markdown], { type: 'text/markdown' })
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = `cloudisoft-${period}-report.md`; a.click()
  }
  return (
    <div className="space-y-4">
      <ErrorNote error={r.error} />
      <div className="flex gap-2"><Button tone={period === 'daily' ? 'primary' : 'ghost'} onClick={() => setPeriod('daily')}>Daily</Button><Button tone={period === 'monthly' ? 'primary' : 'ghost'} onClick={() => setPeriod('monthly')}>Monthly</Button><Button tone="ghost" onClick={download}>Download .md</Button></div>
      <Card title={`${period} report`}><pre className="whitespace-pre-wrap text-sm">{r.data?.markdown}</pre></Card>
      <Card title="Raw data"><pre className="max-h-96 overflow-auto text-xs">{JSON.stringify({ ...r.data, markdown: undefined }, null, 1)}</pre></Card>
    </div>
  )
}
