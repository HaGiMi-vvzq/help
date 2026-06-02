import api from './client'
import type { User } from '@/types'

export function getMe() {
  return api.get<User>('/profile/me')
}

export function updateProfile(data: { username?: string; bio?: string; skill_tags?: string[]; school?: string; extra?: string }) {
  return api.put<User>('/profile', data)
}
