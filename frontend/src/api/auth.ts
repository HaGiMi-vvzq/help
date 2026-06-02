import api from './client'
import type { TokenResponse } from '@/types'

export function login(username: string, password: string) {
  return api.post<TokenResponse>('/auth/login', { username, password })
}

export function register(data: {
  username: string
  password: string
  bio?: string
  school?: string
}) {
  return api.post<TokenResponse>('/auth/register', data)
}
