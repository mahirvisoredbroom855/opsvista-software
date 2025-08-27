
import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { createClient, type Session, type User } from '@supabase/supabase-js'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL as string
const supabaseAnon = import.meta.env.VITE_SUPABASE_ANON_KEY as string

export const supabase = createClient(supabaseUrl, supabaseAnon, {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
    detectSessionInUrl: true,
  },
})

type Ctx = {
  session: Session | null
  user: User | null
  ready: boolean
  signIn: (email: string, password: string) => Promise<{ error?: string }>
  signUp: (email: string, password: string) => Promise<{ error?: string }>
  signOut: () => Promise<void>
  getAccessToken: () => Promise<string | null>
}

const AuthCtx = createContext<Ctx | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session | null>(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session ?? null)
      setReady(true)
    })
    const { data: sub } = supabase.auth.onAuthStateChange((_e, s) => setSession(s))
    return () => { sub.subscription.unsubscribe() }
  }, [])

  const value = useMemo<Ctx>(() => ({
    session,
    user: session?.user ?? null,
    ready,
    async signIn(email, password) {
      const { error } = await supabase.auth.signInWithPassword({ email, password })
      return { error: error ? error.message : undefined }
    },
    async signUp(email, password) {
      const { error } = await supabase.auth.signUp({ email, password })
      return { error: error ? error.message : undefined }
    },
    async signOut() {
      await supabase.auth.signOut()
    },
    async getAccessToken() {
      const { data } = await supabase.auth.getSession()
      return data.session?.access_token ?? null
    }
  }), [session, ready])

  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthCtx)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
