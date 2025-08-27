import { createClient } from '@supabase/supabase-js';
import type { Task, TaskCreate, Metrics, TaskStatus } from '../types/task.types';

const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL!,
  import.meta.env.VITE_SUPABASE_ANON_KEY!
);

// ✅ Enhanced apiFetch with logging
async function apiFetch<T = any>(path: string, init: RequestInit = {}) {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;

  const fullUrl = `${import.meta.env.VITE_API_URL}${path}`;
  console.log("📡 Fetching:", fullUrl);
  console.log("📦 Request Init:", init);

  const res = await fetch(fullUrl, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      Authorization: token ? `Bearer ${token}` : '',
      ...init.headers
    }
  });

  if (!res.ok) {
    const error = await res.json();
    console.error("❌ API Error:", error);
    throw error;
  }

  const json = await res.json();
  console.log("✅ API Success Response:", json);
  return json as T;
}

// ✅ Logs when PATCH is called
export const patchTaskStatus = (id: string, status: TaskStatus) => {
  console.log("🛠️ patchTaskStatus called with:", { id, status });
  return apiFetch<Task>(`/api/v1/tasks/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ status })
  });
};

export const listAllTasks = () =>
  apiFetch<Task[]>('/api/v1/tasks/all');

export const createTask = (body: TaskCreate) =>
  apiFetch<Task>('/api/v1/tasks', {
    method: 'POST',
    body: JSON.stringify(body)
  });

export const listTasks = (assigneeId: string) =>
  apiFetch<Task[]>(`/api/v1/tasks/assigned/${assigneeId}`);

export const getMetrics = () => apiFetch<Metrics>('/api/v1/tasks/metrics');


export const deleteTask = (id: string) =>
  apiFetch<{ deleted: boolean }>(`/api/v1/tasks/${id}`, {
    method: 'DELETE'
  });
