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
    // 1-shot fetch
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
    });

    // live listener
    const {
      data: { subscription }
    } = supabase.auth.onAuthStateChange((_event, sess) => {
      setSession(sess);
    });

    return () => subscription.unsubscribe();
  }, []);

  if (!session) return <AuthForm />;

  const userId = session.user.id;

  return (
    <QueryClientProvider client={qc}>
      <h1>Mini Task Board</h1>
      <LogoutButton/>

      <TaskMetrics />
      <button onClick={() => setShowModal(true)}>+ Create Task</button>
      {showModal && (
        <TaskCreationModal
          assigneeId={userId}
          onClose={() => setShowModal(false)}
          onCreated={() => qc.invalidateQueries({ queryKey: ['tasks', userId] })}
        />
      )}
      <TaskList assigneeId={userId} />
    </QueryClientProvider>
  );
}