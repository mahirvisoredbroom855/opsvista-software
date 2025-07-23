import type { Task } from '../../types/task.types';
import { patchTaskStatus } from '../../services/taskService';

export default function TaskCard({ task, onDone }: { task: Task; onDone: () => void }) {
  async function markDone() {
  console.log('🔍 FRONTEND - Marking task as done:', task.task_id);
  try {
    const result = await patchTaskStatus(task.task_id, 'done');
    console.log('🔍 FRONTEND - Success:', result);
    onDone();
  } catch (error) {
    console.error('🔍 FRONTEND - Error:', error);
  }
}
    
  return (
    <div style={{ border: '1px solid #ccc', padding: 8, marginBottom: 4 }}>
      <strong>{task.title}</strong> — {task.status}
      {task.status !== 'done' && <button onClick={markDone}>Done</button>}
    </div>
  );
}