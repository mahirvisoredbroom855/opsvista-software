/**
 * This is the sign-in / sign-up screen. It talks directly to Supabase
 * (the login provider) from the browser — the backend server never
 * sees anyone's password, only the access token Supabase hands back
 * afterward. New accounts get no special access by default; an Owner
 * has to manually promote someone before they can see the admin
 * dashboard.
 */
"use client";

import { CheckCircle2, Loader2, Lock, Mail, User } from "lucide-react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { supabase } from "../../lib/supabaseClient";

// [OPS:FE-LOGIN] LoginPage
//
// What it does: the sign-in/sign-up form. Calls Supabase Auth directly
// from the browser — the backend never sees a password, only the login
// token from a later request. It's one component with three modes
// (signin / signup / confirm-pending) rather than three separate pages,
// so switching modes doesn't lose whatever the user already typed.
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

  // [OPS:FE-LOGIN-a] submit()
  //
  // What it does: the only place this file actually talks to Supabase.
  // For sign-in, it logs in and redirects to the chat page. For
  // sign-up, it checks whether Supabase handed back an active session
  // right away — if email confirmation is turned off on this Supabase
  // project, it did, so the user goes straight into the app; if it's
  // required, session is null and the screen switches to
  // "confirm-pending" instead. Once the user clicks the emailed
  // confirmation link, the Supabase client picks up the session
  // automatically when they land back on the app.
  //
  // Called by: the "Sign in" / "Create account" button, and Enter in any
  // form field.
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
      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 -z-10 overflow-hidden"
      >
        <div className="animate-blob absolute top-1/4 -right-20 h-80 w-80 rounded-full bg-gradient-to-br from-brand/30 to-brand-deep/10 blur-3xl" />
        <div
          className="animate-blob absolute -bottom-20 -left-20 h-96 w-96 rounded-full bg-gradient-to-tr from-navy/20 to-navy-soft/5 blur-3xl"
          style={{ animationDelay: "-8s" }}
        />
      </div>
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
                <CheckCircle2
                  size={15}
                  style={{ verticalAlign: "-3px", marginRight: 5 }}
                />
                We sent a confirmation link to <strong>{email}</strong>. Click
                it, then come back here and sign in with the password you just
                set.
              </div>
              <button
                type="button"
                className="btn btn--gradient auth-submit"
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
                  <div className="input-icon-wrap">
                    <User size={15} className="input-icon" />
                    <input
                      id="name"
                      className="input input--with-icon"
                      type="text"
                      placeholder="Jane Doe"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      disabled={busy}
                      onKeyDown={(e) => e.key === "Enter" && submit()}
                    />
                  </div>
                </div>
              )}

              <div className="auth-field">
                <label htmlFor="email">Email</label>
                <div className="input-icon-wrap">
                  <Mail size={15} className="input-icon" />
                  <input
                    id="email"
                    className="input input--with-icon"
                    type="email"
                    placeholder="you@example.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    disabled={busy}
                    onKeyDown={(e) => e.key === "Enter" && submit()}
                  />
                </div>
              </div>
              <div className="auth-field">
                <label htmlFor="password">Password</label>
                <div className="input-icon-wrap">
                  <Lock size={15} className="input-icon" />
                  <input
                    id="password"
                    className="input input--with-icon"
                    type="password"
                    placeholder="••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    disabled={busy}
                    onKeyDown={(e) => e.key === "Enter" && submit()}
                  />
                </div>
              </div>

              <button
                type="button"
                className="btn btn--gradient auth-submit"
                onClick={submit}
                disabled={busy || !email || !password || (isSignup && !name)}
              >
                {busy ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : isSignup ? (
                  "Create account"
                ) : (
                  "Sign in"
                )}
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
