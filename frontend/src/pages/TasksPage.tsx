
import { FormEvent, useEffect, useState } from 'react'
import { listAllTasks, createTask } from '../api/tasks'

export default function TasksPage() {
  const [tasks, setTasks] = useState<any[]>([])
  const [title, setTitle] = useState('')
  const [desc, setDesc] = useState('')

  async function load() {
    try {
      const data = await listAllTasks()
      setTasks(Array.isArray(data) ? data : (data?.data ?? []))
    } catch (e) {
      console.error(e)
    }
  }

  useEffect(() => { load() }, [])

  async function onCreate(e: FormEvent) {
    e.preventDefault()
    try {
      await createTask({ title, description: desc, priority: 'medium', status: 'pending', due_date: new Date().toISOString().slice(0,10) })
      setTitle(''); setDesc(''); await load()
    } catch (e) { console.error(e) }
  }

  return (
    <div className="grid">
      <div className="card">
        <h3>Create Task</h3>
        <form onSubmit={onCreate}>
          <div className="field">
            <label>Title</label>
            <input value={title} onChange={e=>setTitle(e.target.value)} required />
          </div>
          <div className="field">
            <label>Description</label>
            <textarea value={desc} onChange={e=>setDesc(e.target.value)} />
          </div>
          <button type="submit">Create</button>
        </form>
      </div>
      <div className="card">
        <h3>All Tasks</h3>
        <table>
          <thead><tr><th>Title</th><th>Status</th><th>Priority</th></tr></thead>
          <tbody>
            {tasks.map((t:any) => (
              <tr key={t.task_id || t.id}>
                <td>{t.title}</td>
                <td>{t.status}</td>
                <td>{t.priority}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
