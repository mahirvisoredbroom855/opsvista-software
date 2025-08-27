
import { api } from '../modules/http/api'

const TASKS_BASE = '/api/v1/tasks'

export async function listAllTasks() {
  const { data } = await api.get(`${TASKS_BASE}/tasks/all`)
  return data
}

export async function createTask(payload: any) {
  const { data } = await api.post(`${TASKS_BASE}/tasks/`, payload)
  return data
}
