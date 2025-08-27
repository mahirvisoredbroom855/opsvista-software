import { supabase } from './supabaseClient';

export async function login(email: string, password: string) {
  const { data, error } = await supabase.auth.signInWithPassword({
    email,
    password,
  });

  if (error) throw error;

  const token = data.session?.access_token;
  if (token) localStorage.setItem("access_token", token);

  return data.user;
}

export function logout() {
  localStorage.removeItem("access_token");
  return supabase.auth.signOut();
}

export function getToken(): string | null {
  return localStorage.getItem("access_token");
}
