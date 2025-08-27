
import axios from 'axios'
import { supabase } from '../auth/AuthContext'

const baseURL = import.meta.env.VITE_BACKEND_URL as string

export const api = axios.create({
  baseURL,
  withCredentials: false,
  timeout: 25000
})

api.interceptors.request.use(async (config) => {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  if (token) {
    config.headers = config.headers || {}
    config.headers['Authorization'] = `Bearer ${token}`
  }
  return config
})
