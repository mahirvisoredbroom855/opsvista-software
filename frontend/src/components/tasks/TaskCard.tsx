import type { Task } from '../../types/task.types';
import { patchTaskStatus, deleteTask } from '../../services/taskService';

// Assume you pass currentUserRole as a prop
export default function TaskCard({
  task,
  onDone,
  currentUserRole,
}: {
  task: Task;
  onDone: () => void;
  currentUserRole: string;
}) {
  async function markDone() {
    console.log('🔍 FRONTEND - Marking task as done:', task.task_id);
    try {
      const result = await patchTaskStatus(task.task_id, 'done');
      console.log('✅ FRONTEND - Done updated:', result);
      onDone();
    } catch (error) {
      console.error('❌ FRONTEND - Error marking as done:', error);
    }
  }

  async function handleDelete() {
    const confirmed = confirm('Are you sure you want to delete this task?');
    if (!confirmed) return;
    console.log('🗑️ FRONTEND - Deleting task:', task.task_id);
    try {
      await deleteTask(task.task_id);
      console.log('✅ FRONTEND - Task deleted!');
      onDone(); // refresh task list
    } catch (error) {
      console.error('❌ FRONTEND - Error deleting task:', error);
    }
  }

  const canDelete = ['owner', 'admin', 'manager'].includes(currentUserRole);

  return (
    <div style={{ border: '1px solid #ccc', padding: 8, marginBottom: 4 }}>
      <strong>{task.title}</strong> — {task.status}
      <br />
      <small>Assigned to: {task.assignee_name || 'Unknown'}</small>
      {task.status !== 'done' && (
        <button onClick={markDone} style={{ marginLeft: 8 }}>
          ✅ Done
        </button>
      )}
      {canDelete && (
        <button onClick={handleDelete} style={{ color: 'red', marginLeft: 8 }}>
          🗑️ Delete
        </button>
      )}
    </div>
  );
}