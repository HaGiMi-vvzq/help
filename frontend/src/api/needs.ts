import api from './client'
import type { MatchResult, Need, NeedApplication } from '@/types'

export function createNeed(data: { type: string; title: string; description: string; selection_mode?: string }) {
  return api.post<Need>('/needs', data)
}

export function getNeeds(params?: { page?: number; page_size?: number; status?: string; type?: string }) {
  return api.get<{ items: Need[]; total: number; page: number; page_size: number }>('/needs', { params })
}

export function getNeedDetail(id: number) {
  return api.get<Need>(`/needs/${id}`)
}

export function applyToNeed(needId: number, message: string) {
  return api.post<NeedApplication>(`/needs/${needId}/apply`, { message })
}

export function getNeedApplications(needId: number) {
  return api.get<{ items: NeedApplication[] }>(`/needs/${needId}/applications`)
}

export function acceptNeedApplication(applicationId: number, ownerReply?: string) {
  return api.post<NeedApplication>(`/needs/applications/${applicationId}/accept`, { owner_reply: ownerReply })
}

export function rejectNeedApplication(applicationId: number, ownerReply?: string) {
  return api.post<NeedApplication>(`/needs/applications/${applicationId}/reject`, { owner_reply: ownerReply })
}

export function getMyApplications() {
  return api.get<{ items: NeedApplication[] }>('/needs/applications/mine')
}

export function getMatches(needId: number) {
  return api.get<{ need: Need; matches: MatchResult[]; matching_active?: boolean }>(`/needs/${needId}/matches`)
}

export function refreshMatches(needId: number) {
  return api.post<{ need: Need; matches: MatchResult[]; matching_active?: boolean }>(`/needs/${needId}/matches/refresh`)
}

export function getMatchStreamUrl(needId: number) {
  return `/api/needs/${needId}/matches/stream`
}

export function submitFeedback(matchId: number, feedback: number) {
  return api.post(`/needs/matches/${matchId}/feedback`, { feedback })
}

export function refineNeed(needId: number) {
  return api.post<{ question: string }>(`/needs/${needId}/refine`)
}

export function polishDescription(data: { need_type: string; title: string; description: string; selection_mode?: string }) {
  return api.post<{ result: string }>('/needs/polish', data)
}

export function generateDescription(data: { need_type: string; title: string; selection_mode?: string }) {
  return api.post<{ result: string }>('/needs/generate', data)
}

export function getMyNeeds() {
  return api.get<Need[]>('/needs/mine')
}

export function getMySelectedNeeds() {
  return api.get<Need[]>('/needs/selected/mine')
}

export function updateNeed(id: number, data: { title?: string; description?: string; status?: string }) {
  return api.put<Need>(`/needs/${id}`, data)
}

export function deleteNeed(id: number) {
  return api.delete(`/needs/${id}`)
}

export function closeNeed(id: number) {
  return api.post<Need>(`/needs/${id}/close`)
}

export function selectUsers(needId: number, userIds: number[]) {
  return api.post<Need>(`/needs/${needId}/select`, { user_ids: userIds })
}

export function deselectUser(needId: number, userId: number) {
  return api.post<Need>(`/needs/${needId}/deselect/${userId}`)
}

export function logBehavior(data: { event_type: string; target_user_id?: number; need_id?: number }) {
  return api.post('/needs/behavior/log', data)
}
