import { useQuery } from '@tanstack/react-query';
import { getMetrics } from '../../services/taskService';

export default function TaskMetrics() {
  const { data } = useQuery({ queryKey: ['metrics'], queryFn: getMetrics });
  
  if (!data) return null;
  
  return (
    <div style={{ margin: '12px 0' }}>
      <p>Total: {data.total}</p>
      <p>Completed: {data.completed}</p>
      <p>Overdue: {data.overdue}</p>
      <p>Rate: {data.completion_rate}%</p>
    </div>
  );
}