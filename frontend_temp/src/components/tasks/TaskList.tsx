import { useQuery } from '@tanstack/react-query';
import { listTasks, listAllTasks } from '../../services/taskService';
import TaskCard from './TaskCard';

export default function TaskList({
  assigneeId,
  currentUserRole,
  isManager
}: {
  assigneeId: string;
  currentUserRole: string;
  isManager: boolean; // NEW PROP
}) {
  console.log('🔍 FRONTEND - TaskList rendered with:', { assigneeId, currentUserRole, isManager });
  
  const { data: tasks = [], refetch, isLoading, error, isError } = useQuery({
    queryKey: isManager ? ['allTasks'] : ['tasks', assigneeId],
    queryFn: () => {
      if (isManager) {
        console.log('🔍 FRONTEND - Manager requesting all tasks');
        return listAllTasks(); // Show all tasks for managers
      } else {
        console.log('🔍 FRONTEND - Worker requesting assigned tasks');
        return listTasks(assigneeId); // Show only assigned tasks for workers
      }
    },
    enabled: isManager || !!assigneeId, // Enable if manager OR if assigneeId exists
    refetchOnWindowFocus: false,
    staleTime: 30000
  });

  if (isLoading) return <div>Loading tasks...</div>;
  if (isError) return <div>Error: {error?.toString()}</div>;

  if (!tasks || tasks.length === 0) {
    return <div>{isManager ? 'No tasks in the system.' : 'No tasks assigned to you.'}</div>;
  }

  return (
    <div>
      <h2>{isManager ? 'All Tasks' : 'Your Tasks'}</h2>
      <p>Found {tasks.length} tasks:</p>
      {tasks.map(t => (
        <TaskCard
          key={t.task_id}
          task={t}
          onDone={refetch}
          currentUserRole={currentUserRole}
        />
      ))}
    </div>
  );
}