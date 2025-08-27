
import { useEffect, useState } from 'react'
import { fetchHealth, fetchMetrics } from '../api/finance'

export default function DashboardPage() {
  const [health, setHealth] = useState<any>(null)
  const [metrics, setMetrics] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    (async () => {
      try {
        const [h, m] = await Promise.all([fetchHealth(), fetchMetrics()])
        setHealth(h); setMetrics(m)
      } catch (e: any) {
        setError(e?.message || 'Failed to load')
      } finally { setLoading(false) }
    })()
  }, [])

  if (loading) return <div className="card">Loading…</div>
  if (error) return <div className="card">Error: {error}</div>

  return (
    <div className="grid">
      <div className="card">
        <h3>System Health</h3>
        <pre className="muted" style={{whiteSpace:'pre-wrap'}}>{JSON.stringify(health, null, 2)}</pre>
      </div>
      <div className="card">
        <h3>Finance Metrics</h3>
        <div className="grid">
          <Metric label="Today Cash" value={metrics.today_cash_received} />
          <Metric label="Today Expenses" value={metrics.today_expenses} />
          <Metric label="Month Net Flow" value={metrics.month_net_flow} />
          <Metric label="Year Profit/Loss" value={metrics.year_profit_loss} />
        </div>
        <details style={{marginTop:10}}>
          <summary>All metrics</summary>
          <pre className="muted" style={{whiteSpace:'pre-wrap'}}>{JSON.stringify(metrics, null, 2)}</pre>
        </details>
      </div>
    </div>
  )
}

function Metric({ label, value }: {label:string, value:number}) {
  return (
    <div className="card">
      <div className="muted">{label}</div>
      <div style={{fontSize:24, fontWeight:700}}>{Number(value).toLocaleString()}</div>
    </div>
  )
}
