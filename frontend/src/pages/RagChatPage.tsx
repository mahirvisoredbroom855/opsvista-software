
import { FormEvent, useState } from 'react'
import { retrieve } from '../api/chat'

export default function RagChatPage() {
  const [q, setQ] = useState('')
  const [results, setResults] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function onSearch(e: FormEvent) {
    e.preventDefault()
    setError(null); setLoading(true); setResults(null)
    try {
      const data = await retrieve(q)
      setResults(data)
    } catch (e:any) {
      setError(e?.message || 'Failed')
    } finally { setLoading(false) }
  }

  return (
    <div className="card">
      <h3>RAG Search</h3>
      <form onSubmit={onSearch} className="row">
        <input value={q} onChange={e=>setQ(e.target.value)} placeholder="Ask about finance docs, customers, etc." />
        <button type="submit" disabled={loading}>{loading ? 'Searching…' : 'Search'}</button>
      </form>
      {error && <div style={{color:'#ff8080',marginTop:10}}>{error}</div>}
      {results && (
        <div style={{marginTop:14}}>
          <pre className="muted" style={{whiteSpace:'pre-wrap'}}>{JSON.stringify(results, null, 2)}</pre>
        </div>
      )}
    </div>
  )
}
