'use client';

import { useEffect, useState } from "react";
import { Auth } from "@supabase/auth-ui-react";
import { ThemeSupa } from "@supabase/auth-ui-shared";
import { createClient } from "@/lib/supabaseClient";

export default function AuthGate({ children }: { children: React.ReactNode }) {
  const supabase = createClient();
  const [loading, setLoading] = useState(true);
  const [session, setSession] = useState<any>(null);

  useEffect(() => {
    const init = async () => {
      const { data: { session } } = await supabase.auth.getSession();
      setSession(session ?? null);
      setLoading(false);
    };
    init();

    const { data: listener } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session ?? null);
    });
    return () => {
      listener.subscription.unsubscribe();
    };
  }, [supabase]);

  if (loading) {
    return <div className="p-6 text-neutral-500">Loading…</div>;
  }

  if (!session) {
    return (
      <div className="mx-auto max-w-md rounded-2xl border bg-white p-6 shadow-sm">
        <h2 className="mb-2 text-lg font-semibold">Sign in</h2>
        <p className="mb-4 text-sm text-neutral-600">
          Use email magic link or a provider configured in Supabase.
        </p>
        <Auth
          supabaseClient={supabase}
          appearance={{ theme: ThemeSupa }}
          providers={["google"]}
          view="magic_link"
        />
      </div>
    );
  }

  return <>{children}</>;
}
