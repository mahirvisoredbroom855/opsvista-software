'use client';

import { createClient as _createClient } from '@supabase/supabase-js';

let _client: ReturnType<typeof _createClient> | null = null;

export function createClient() {
  if (_client) return _client;
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL!;
  const anon = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;
  _client = _createClient(url, anon, {
    auth: {
      persistSession: true,
      autoRefreshToken: true,
    },
  });
  return _client;
}
