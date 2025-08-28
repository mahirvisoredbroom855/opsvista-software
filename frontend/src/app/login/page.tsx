"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "../../lib/supabaseClient";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);

  async function submit() {
    setBusy(true);
    setErr(null);
    setOk(null);
    try {
      if (mode === "signin") {
        const { error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) throw error;
        router.replace("/"); // go to chat
      } else {
        const { error } = await supabase.auth.signUp({ email, password });
        if (error) throw error;
        setOk("Account created. You can sign in now.");
        setMode("signin");
      }
    } catch (e: any) {
      setErr(e?.message || "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="site-main" style={{ maxWidth: 520 }}>
      <div className="card">
        <div className="card__section">
          <h1 style={{ margin: 0, fontSize: 22, fontWeight: 700 }}>opsvista.</h1>
          <div className="note" style={{ marginTop: 4 }}>Sign {mode === "signin" ? "in" : "up"} to continue</div>
        </div>

        <div className="card__section">
          <div className="row" style={{ flexDirection: "column", gap: 10 }}>
            <input
              className="input"
              type="email"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={busy}
            />
            <input
              className="input"
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={busy}
            />
            <button className="btn" onClick={submit} disabled={busy || !email || !password}>
              {busy ? "…" : mode === "signin" ? "Sign in" : "Create account"}
            </button>
            <div className="note">
              {mode === "signin" ? (
                <>No account?{" "}
                  <a href="#" onClick={(e)=>{e.preventDefault(); setMode("signup");}} style={{ color: "var(--brand)" }}>
                    Create one
                  </a></>
              ) : (
                <>Already have an account?{" "}
                  <a href="#" onClick={(e)=>{e.preventDefault(); setMode("signin");}} style={{ color: "var(--brand)" }}>
                    Sign in
                  </a></>
              )}
            </div>
            {err && <div className="note" style={{ color: "#b91c1c" }}>Error: {err}</div>}
            {ok && <div className="note" style={{ color: "#065f46" }}>{ok}</div>}
          </div>
        </div>
      </div>
    </div>
  );
}
