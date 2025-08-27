// src/components/AuthForm.tsx
import { useState } from 'react';
import { login } from '../services/auth';

const AuthForm = () => {
  const [email, setEmail]       = useState('');
  const [password, setPassword] = useState('');
  const [error, setError]       = useState<string | null>(null);
  const [loading, setLoading]   = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      await login(email, password);     // ← uses auth.ts helper
      // ➜ TODO: navigate to dashboard, e.g. with React‑Router:
      // navigate('/tasks');
    } catch (err: any) {
      setError(err.message ?? 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <form
      onSubmit={handleLogin}
      style={{ border: '1px solid #ccc', padding: 24, maxWidth: 320 }}
    >
      <h2 style={{ marginTop: 0 }}>Sign In</h2>

      <input
        type="email"
        placeholder="Email"
        value={email}
        onChange={e => setEmail(e.target.value)}
        style={{ width: '100%', marginBottom: 8 }}
        required
      />

      <input
        type="password"
        placeholder="Password"
        value={password}
        onChange={e => setPassword(e.target.value)}
        style={{ width: '100%', marginBottom: 12 }}
        required
      />

      <button
        type="submit"
        disabled={loading}
        style={{ width: '100%', padding: 8 }}
      >
        {loading ? 'Signing in…' : 'Login'}
      </button>

      {error && (
        <p style={{ color: 'crimson', marginTop: 12 }}>
          {error}
        </p>
      )}
    </form>
  );
};

export default AuthForm;
