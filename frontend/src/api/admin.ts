import api from './client'

export interface AdminStats {
  total_users: number
  active_users: number
  total_needs: number
  open_needs: number
  matched_needs: number
  total_messages: number
  today_users: number
  today_needs: number
}

export interface AdminUser {
  id: number
  username: string
  role: string
  is_active: boolean
  school: string | null
  bio: string | null
  skill_tags: string[] | null
  created_at: string
}

export interface AdminNeed {
  id: number
  user_id: number
  username: string
  type: string
  title: string
  description: string
  status: string
  selection_mode: string
  created_at: string
}

export function getStats() {
  return api.get<AdminStats>('/admin/stats')
}

export function listUsers(params: { page?: number; page_size?: number }) {
  return api.get<{ items: AdminUser[]; total: number }>('/admin/users', { params })
}

export function updateUser(userId: number, data: { role?: string; is_active?: boolean }) {
  return api.put(`/admin/users/${userId}`, data)
}

export function deleteUser(userId: number) {
  return api.delete(`/admin/users/${userId}`)
}

export function listNeeds(params: { page?: number; page_size?: number }) {
  return api.get<{ items: AdminNeed[]; total: number }>('/admin/needs', { params })
}

export function updateNeedStatus(needId: number, status: string) {
  return api.put(`/admin/needs/${needId}`, { status })
}

export function deleteNeed(needId: number) {
  return api.delete(`/admin/needs/${needId}`)
}
