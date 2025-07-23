import { useQuery } from '@tanstack/react-query';
import { listTasks } from '../../services/taskService';
import TaskCard from './TaskCard';

export default function TaskList({ assigneeId }: { assigneeId: string }) {
  console.log('🔍 FRONTEND - TaskList rendered with assigneeId:', assigneeId);
  
  const { data: tasks = [], refetch, isLoading, error, isError } = useQuery({
    queryKey: ['tasks', assigneeId],
    queryFn: () => listTasks(assigneeId),
    enabled: !!assigneeId, // Only run if assigneeId exists
    refetchOnWindowFocus: false, // Stop excessive refetching
    staleTime: 30000 // Cache for 30 seconds
  });

  console.log('🔍 FRONTEND - Full query result:', {
  isLoading,
  isError,
  error: error?.toString(),
  tasksCount: tasks?.length,
  tasks: tasks,
  assigneeId: assigneeId
  });

  // Add this after the console.log
  if (tasks && tasks.length > 0) {
    console.log('🔍 FRONTEND - First task details:', tasks[0]);
  }
  
  if (isLoading) return <div>Loading tasks...</div>;
  if (isError) return <div>Error: {error?.toString()}</div>;
  if (!tasks || tasks.length === 0) return <div>No tasks assigned to you.</div>;

  return (
    <div>
      <p>Found {tasks.length} tasks:</p>
      {tasks.map(t => (
        <TaskCard key={t.task_id} task={t} onDone={refetch} />
      ))}
    </div>
  );
}



