
import { api } from '../modules/http/api'

// Using the retrieve endpoint (simple)
const CHAT_BASE = '/api/chat/api/rag/chat'

export async function retrieve(query: string) {
  const { data } = await api.get(`${CHAT_BASE}/_retrieve`, { params: { q: query }})
  return data
}

// If you decide to use the "complete" endpoint later, wire it like this:
export async function complete(messages: {role:'user'|'system'|'assistant', content:string}[]) {
  const { data } = await api.post(`${CHAT_BASE}/complete`, { messages })
  return data
}
