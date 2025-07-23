// frontend/src/components/LogoutButton.tsx
import { useNavigate } from 'react-router-dom';
import { supabase } from '../services/supabaseClient';  // ✅ adjust if needed

export default function LogoutButton() {
  const navigate = useNavigate();

  const handleLogout = async () => {
    try {
      // Step 1: Sign out from Supabase
      const { error } = await supabase.auth.signOut();
      if (error) throw error;

      // Step 2: Clear token (if you're storing manually)
      localStorage.removeItem('access_token');

      // Step 3: Optional - Notify backend to invalidate token (if implemented)
      await fetch('/api/auth/logout', {
        method: 'POST',
        credentials: 'include',
      });

      // Step 4: Redirect to login page
      navigate('/login');
    } catch (err) {
      console.error('Logout failed:', err);
    }
  };

  return (
    <button onClick={handleLogout} className="px-4 py-2 rounded bg-red-600 text-white">
      Logout
    </button>
  );
}
