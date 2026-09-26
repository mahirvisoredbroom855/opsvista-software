"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { supabase } from "../../lib/supabaseClient";

type Mode = "signin" | "signup" | "confirm-pending";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("signin");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  function resetMessages() {
    setErr(null);
  }

  async function submit() {
    setBusy(true);
    setErr(null);
    try {
      if (mode === "signin") {
        const { error } = await supabase.auth.signInWithPassword({
          email,
          password,
        });
        if (error) throw error;
        router.replace("/"); // go to chat
      } else if (mode === "signup") {
        if (!name.trim()) {
          setErr("Please enter your name.");
          setBusy(false);
          return;
        }
        const { data, error } = await supabase.auth.signUp({
          email,
          password,
          options: { data: { full_name: name.trim() } },
        });
        if (error) throw error;

        if (data.session) {
          // Email confirmation is disabled on this project — already signed in.
          router.replace("/");
        } else {
          // Confirmation required: Supabase sent a link to this email. Once
          // clicked, supabaseClient's detectSessionInUrl picks up the
          // session automatically and lands them back in the app signed in.
          setMode("confirm-pending");
        }
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  function switchTo(next: Mode) {
    resetMessages();
    setMode(next);
  }

  const isSignup = mode === "signup";

  return (
    <div className="auth-shell">
      <div className="auth-card">
        <div className="auth-card__banner">
          <div className="auth-card__logo">
            <Image
              src="/opsvista-logo.png"
              alt="OpsVista"
              width={28}
              height={28}
              style={{ borderRadius: 8 }}
            />
            <span className="auth-card__brand">opsvista.</span>
          </div>
          <h1 className="auth-card__title">
            {mode === "signin" && "Welcome back"}
            {mode === "signup" && "Create your account"}
            {mode === "confirm-pending" && "Check your email"}
          </h1>
          <p className="auth-card__subtitle">
            {mode === "signin" && "Sign in to the Knowledge Assistant"}
            {mode === "signup" && "Set up access to the Knowledge Assistant"}
            {mode === "confirm-pending" &&
              "One more step before you can sign in"}
          </p>
        </div>

        <div className="auth-card__body">
          {mode === "confirm-pending" ? (
            <>
              <div className="auth-alert auth-alert--success">
                We sent a confirmation link to <strong>{email}</strong>. Click
                it, then come back here and sign in with the password you just
                set.
              </div>
              <button
                type="button"
                className="btn auth-submit"
                onClick={() => switchTo("signin")}
              >
                Back to sign in
              </button>
            </>
          ) : (
            <>
              {err && <div className="auth-alert auth-alert--error">{err}</div>}

              {isSignup && (
                <div className="auth-field">
                  <label htmlFor="name">Full name</label>
                  <input
                    id="name"
                    className="input"
                    type="text"
                    placeholder="Jane Doe"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    disabled={busy}
                    onKeyDown={(e) => e.key === "Enter" && submit()}
                  />
                </div>
              )}

              <div className="auth-field">
                <label htmlFor="email">Email</label>
                <input
                  id="email"
                  className="input"
                  type="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  disabled={busy}
                  onKeyDown={(e) => e.key === "Enter" && submit()}
                />
              </div>
              <div className="auth-field">
                <label htmlFor="password">Password</label>
                <input
                  id="password"
                  className="input"
                  type="password"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  disabled={busy}
                  onKeyDown={(e) => e.key === "Enter" && submit()}
                />
              </div>

              <button
                type="button"
                className="btn auth-submit"
                onClick={submit}
                disabled={busy || !email || !password || (isSignup && !name)}
              >
                {busy ? "…" : isSignup ? "Create account" : "Sign in"}
              </button>

              <div className="auth-switch">
                {mode === "signin" ? (
                  <>
                    No account?{" "}
                    <button
                      type="button"
                      className="link-inline"
                      onClick={() => switchTo("signup")}
                    >
                      Create one
                    </button>
                  </>
                ) : (
                  <>
                    Already have an account?{" "}
                    <button
                      type="button"
                      className="link-inline"
                      onClick={() => switchTo("signin")}
                    >
                      Sign in
                    </button>
                  </>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
