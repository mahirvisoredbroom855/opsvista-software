/**
 * This creates the one Supabase connection the browser uses to sign
 * people in and keep them signed in across page reloads. It only ever
 * uses the public "anon" key — never a secret key — since this code
 * runs in the user's own browser, where nothing can truly stay secret.
 */
// [OPS:FE-LIB-001] supabase
//
// What it does: the one Supabase client used in the browser, built with
// only the public "anon" key — never the secret service-role key, which
// stays backend-only. The three auth options together mean a login
// survives a page reload and any OAuth-style redirect completes
// correctly.
//
// Called by: login/page.tsx (sign-in/sign-up) and page.tsx (reading the
// current login token to send with requests).
import { createClient } from "@supabase/supabase-js";

const url = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";

export const supabase = createClient(url, key, {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
    detectSessionInUrl: true,
  },
});
