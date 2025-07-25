import { useEffect, useState } from 'react';
import { createClient } from '@supabase/supabase-js';
import type { Session } from '@supabase/supabase-js';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import TaskList from './components/tasks/TaskList';
import TaskCreationModal from './components/tasks/TaskCreationModal';
import TaskMetrics from './components/tasks/TaskMetrics';
import AuthForm from './components/AuthForm';
import LogoutButton from './components/LogoutButton';

const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL!,
  import.meta.env.VITE_SUPABASE_ANON_KEY!
);

const qc = new QueryClient();

export default function App() {
  const [session, setSession] = useState<Session | null>(null);
  const [showModal, setShowModal] = useState(false);

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
    });

    const {
      data: { subscription }
    } = supabase.auth.onAuthStateChange((_event, sess) => {
      setSession(sess);
    });

    return () => subscription.unsubscribe();
  }, []);

  if (!session) return <AuthForm />;

  const userId = session.user.id;
  const currentUserRole = session.user.app_metadata?.role || 'user';

  // NEW: Determine what to show based on role
  const isManager = ['owner', 'admin', 'manager'].includes(currentUserRole);

  return (
    <QueryClientProvider client={qc}>
      <h1>Mini Task Board</h1>
      <LogoutButton />
      
      {/* Only show metrics for managers */}
      {isManager && <TaskMetrics />}
      
      {/* Only show create button for managers */}
      {isManager && (
        <button onClick={() => setShowModal(true)}>+ Create Task</button>
      )}
      
      {showModal && (
        <TaskCreationModal
          assigneeId={userId}
          onClose={() => setShowModal(false)}
          onCreated={() => {
            // Invalidate both queries to refresh the list
            qc.invalidateQueries({ queryKey: ['tasks', userId] });
            qc.invalidateQueries({ queryKey: ['allTasks'] });
          }}
        />
      )}

      {/* UPDATED: Pass role info to TaskList */}
      <TaskList 
        assigneeId={userId} 
        currentUserRole={currentUserRole}
        isManager={isManager}
      />
    </QueryClientProvider>
  );
}