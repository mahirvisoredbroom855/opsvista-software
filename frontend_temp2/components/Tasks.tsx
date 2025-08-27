'use client';

import { useEffect, useState } from 'react';
import { createClient } from '@/lib/supabaseClient';

type Task = {
  task_id: string;
  title: string;
  description: string | null;
  assigner_id: string;
  assignee_id: string;
  created_at: string;
  due_date: string;
  status: 'pending'|'in_progress'|'done'|'overdue';
  priority: 'low'|'medium'|'high'|'urgent';
};

export default function Tasks() {
  const supabase = createClient();
  const [tasks, setTasks] = useState<Task[]>([]);
  const [title, setTitle] = useState('');
  const [due, setDue] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reload = async () => {
    setError(null);
    const { data: userRes } = await supabase.auth.getUser();
    const uid = userRes.user?.id;
    if (!uid) return;
    const { data, error } = await supabase
      .from('tasks')
      .select('*')
      .eq('assignee_id', uid)
      .order('due_date', { ascending: true });
    if (error) setError(error.message);
    else setTasks(data || []);
  };

  useEffect(() => {
    reload();
  }, []);

  const createTask = async () => {
    setLoading(true);
    setError(null);
    try {
      const { data: auth } = await supabase.auth.getUser();
      const uid = auth.user?.id;
      if (!uid) throw new Error('No user');
      if (!title || !due) throw new Error('Title and due date are required');

      const { error } = await supabase.from('tasks').insert({
        title,
        description: null,
        assigner_id: uid,
        assignee_id: uid,
        due_date: due,
        status: 'pending',
        priority: 'medium',
      });
      if (error) throw error;
      setTitle('');
      setDue('');
      await reload();
    } catch (e: any) {
      setError(e?.message || 'Failed to create task');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      {error && <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</div>}

      <div className="flex flex-col gap-2 md:flex-row">
        <input
          className="flex-1 rounded-xl border bg-white px-3 py-2 outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="Task title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />
        <input
          type="date"
          className="rounded-xl border bg-white px-3 py-2 outline-none focus:ring-2 focus:ring-blue-500"
          value={due}
          onChange={(e) => setDue(e.target.value)}
        />
        <button
          onClick={createTask}
          disabled={loading}
          className="rounded-xl bg-emerald-600 px-4 py-2 text-white disabled:opacity-50"
        >
          {loading ? 'Saving…' : 'Add Task'}
        </button>
      </div>

      <ul className="divide-y rounded-xl border bg-white">
        {tasks.map((t) => (
          <li key={t.task_id} className="flex items-center justify-between gap-2 p-3">
            <div>
              <div className="font-medium">{t.title}</div>
              <div className="text-xs text-neutral-500">Due: {t.due_date} • Status: {t.status}</div>
            </div>
            <div className="text-xs rounded-full bg-neutral-100 px-2 py-1">{t.priority}</div>
          </li>
        ))}
        {tasks.length === 0 && <li className="p-3 text-sm text-neutral-500">No tasks yet.</li>}
      </ul>
    </div>
  );
}
