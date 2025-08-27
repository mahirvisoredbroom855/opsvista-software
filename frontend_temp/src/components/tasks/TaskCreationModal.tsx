import { useEffect, useState } from 'react';
import { createTask } from '../../services/taskService';
import { supabase } from '../../services/supabaseClient'; // adjust path if needed

interface UserOption {
  id: string;
  full_name: string;
  email: string;
}

export default function TaskCreationModal({ 
  assigneeId, 
  onClose, 
  onCreated 
}: {
  assigneeId: string;
  onClose: () => void;
  onCreated: () => void;
}) {
  const [users, setUsers] = useState<UserOption[]>([]);
  const [selectedAssignee, setSelectedAssignee] = useState(assigneeId);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [dueDate, setDueDate] = useState(new Date().toISOString().slice(0, 10));
  const [priority, setPriority] = useState<'low' | 'medium' | 'high' | 'urgent'>('medium');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    async function fetchUsers() {
      const { data, error } = await supabase.from('users').select('id, full_name, email');
      if (error) console.error('Error fetching users', error);
      else setUsers(data);
    }
    fetchUsers();
  }, []);

  async function save() {
    if (!title.trim()) {
      setError('Title is required');
      return;
    }

    setLoading(true);
    setError('');
    
    try {
      await createTask({
        title: title.trim(),
        description: description.trim() || undefined,
        assignee_id: selectedAssignee,
        due_date: dueDate,
        priority
      });
      
      console.log('✅ Task created successfully');
      onCreated();
      onClose();
    } catch (err) {
      console.error('❌ Error creating task:', err);
      setError(err instanceof Error ? err.message : 'Failed to create task');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ 
      position: 'fixed', 
      top: '50%', 
      left: '50%', 
      transform: 'translate(-50%, -50%)',
      border: '1px solid black', 
      padding: 20,
      backgroundColor: 'white',
      boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)',
      zIndex: 1000,
      minWidth: 300
    }}>
      <h3>Create New Task</h3>
      
      {error && <p style={{ color: 'red', fontSize: '14px' }}>{error}</p>}
      
      <div style={{ marginBottom: 10 }}>
        <label>Title *</label>
        <input 
          type="text"
          value={title} 
          onChange={e => setTitle(e.target.value)}
          placeholder="Enter task title"
          style={{ width: '100%', padding: 5, marginTop: 5 }}
        />
      </div>

      <div style={{ marginBottom: 10 }}>
        <label>Description</label>
        <textarea 
          value={description} 
          onChange={e => setDescription(e.target.value)}
          placeholder="Enter task description (optional)"
          style={{ width: '100%', padding: 5, marginTop: 5, height: 60 }}
        />
      </div>

      <div style={{ marginBottom: 10 }}>
        <label>Assign to</label>
        <select
          value={selectedAssignee}
          onChange={e => setSelectedAssignee(e.target.value)}
          style={{ width: '100%', padding: 5, marginTop: 5 }}
        >
          <option value="">-- Select User --</option>
          {users.map(user => (
            <option key={user.id} value={user.id}>
              {user.full_name || user.email}
            </option>
          ))}
        </select>
      </div>

      <div style={{ marginBottom: 10 }}>
        <label>Due Date</label>
        <input 
          type="date"
          value={dueDate} 
          onChange={e => setDueDate(e.target.value)}
          style={{ width: '100%', padding: 5, marginTop: 5 }}
        />
      </div>

      <div style={{ marginBottom: 15 }}>
        <label>Priority</label>
        <select 
          value={priority} 
          onChange={e => setPriority(e.target.value as any)}
          style={{ width: '100%', padding: 5, marginTop: 5 }}
        >
          <option value="low">Low</option>
          <option value="medium">Medium</option>
          <option value="high">High</option>
          <option value="urgent">Urgent</option>
        </select>
      </div>

      <div style={{ display: 'flex', gap: 10 }}>
        <button 
          onClick={save} 
          disabled={loading}
          style={{ 
            padding: '8px 16px', 
            backgroundColor: loading ? '#ccc' : '#007bff',
            color: 'white',
            border: 'none',
            cursor: loading ? 'not-allowed' : 'pointer'
          }}
        >
          {loading ? 'Creating...' : 'Create Task'}
        </button>
        <button 
          onClick={onClose}
          style={{ padding: '8px 16px', backgroundColor: '#6c757d', color: 'white', border: 'none' }}
        >
          Cancel
        </button>
      </div>
    </div>
  );
}