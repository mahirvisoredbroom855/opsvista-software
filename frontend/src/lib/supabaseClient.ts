// [OPS:FE-LIB-001] supabase — the browser-side Supabase client, ANON key
// only (never service-role — that stays backend-only, see [OPS:PVEC-001]).
// persistSession + autoRefreshToken + detectSessionInUrl together are what
// let a session survive a page reload and complete an OAuth-style redirect
// callback. Imported by login/page.tsx [OPS:FE-LOGIN] for sign-in/sign-up
// and by page.tsx [OPS:FE-CHAT] to read the current access token for the
// Authorization header sent to the backend's [OPS:AUTH-001] dependency.
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
