export type TaskStatus = 'pending' | 'in_progress' | 'done' | 'overdue';
export type TaskPriority = 'low' | 'medium' | 'high' | 'urgent';

export interface TaskCreate {
  title: string;
  description?: string;
  assignee_id: string;
  due_date: string;
  priority?: TaskPriority;
}

export interface Task {
  task_id: string;
  title: string;
  description?: string;
  assigner_id: string;
  assignee_id: string;
  created_at: string;
  due_date: string;
  status: TaskStatus;
  priority: TaskPriority;
  updated_at: string;
  done_at?: string;
  assignee_name?: string; 
}

export interface Metrics {
  total: number;
  completed: number;
  overdue: number;
  completion_rate: number;
  avg_completion_hours: number;
}