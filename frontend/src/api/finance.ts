
import { api } from '../modules/http/api'

const FINANCE_BASE = '/api/finance/api/v1/finance'

export async function fetchHealth() {
  const { data } = await api.get(`${FINANCE_BASE}/health`)
  return data
}

export async function fetchMetrics() {
  const { data } = await api.get(`${FINANCE_BASE}/dashboard/metrics`)
  return data
}

export async function listTransactions(params: Record<string, any> = {}) {
  const { data } = await api.get(`${FINANCE_BASE}/transactions`, { params })
  return data
}
