import api from './client'
import type {
  AgentChatResponse,
  AgentMessage,
  AgentSession,
  AgentSuggestion,
  AgentTask,
  AgentWorkspace,
  NeedDraft,
} from '@/types'

export function createSession(title?: string) {
  return api.post<{ id: number; title: string; status: string; created_at: string }>('/agent/sessions', {
    title: title || '新对话',
  })
}

export function listSessions() {
  return api.get<{ id: number; title: string; status: string; summary?: string; created_at: string; updated_at: string }[]>(
    '/agent/sessions',
  )
}

export function getSession(id: number) {
  return api.get<{ session: AgentSession; messages: AgentMessage[]; tasks: AgentTask[] }>(`/agent/sessions/${id}`)
}

export function deleteSession(id: number) {
  return api.delete(`/agent/sessions/${id}`)
}

export function sendMessage(sessionId: number, message: string) {
  // AgentChatResponse includes message_metadata for follow-up options and publish confirmations.
  return api.post<AgentChatResponse>(`/agent/sessions/${sessionId}/chat`, { message })
}

export function uploadFile(sessionId: number, file: File) {
  const form = new FormData()
  form.append('file', file)
  return api.post<{ reply: string; file_id: number; extracted: Record<string, unknown>; drafts?: NeedDraft[] }>(
    `/agent/sessions/${sessionId}/upload`,
    form,
  )
}

export function triggerPlan(sessionId: number, goal: string) {
  return api.post<{ reply: string; tasks: AgentTask[] }>(`/agent/sessions/${sessionId}/plan`, { goal })
}

export function confirmPublish(sessionId: number, drafts: NeedDraft[]) {
  return api.post<{ reply: string; needs: { id: number; title: string; type: string }[] }>(
    `/agent/sessions/${sessionId}/confirm-publish`,
    { draft: drafts },
  )
}

export function getTasks(sessionId: number) {
  return api.get<AgentTask[]>(`/agent/sessions/${sessionId}/tasks`)
}

export function getWorkspace(sessionId: number) {
  return api.get<AgentWorkspace>(`/agent/sessions/${sessionId}/workspace`)
}

export function resetMemory(sessionId: number) {
  return api.post<{ ok: boolean }>(`/agent/sessions/${sessionId}/memory/reset`)
}

export function searchKnowledge(query: string) {
  return api.post<{ results: Record<string, unknown>[] }>('/agent/search-knowledge', { query })
}

export function retryTask(sessionId: number, taskId: number) {
  return api.post<{ ok: boolean; status: string; retry_count: number }>(`/agent/sessions/${sessionId}/tasks/${taskId}/retry`)
}

export function getSuggestions(sessionId: number) {
  return api.get<{ suggestions: AgentSuggestion[] }>(`/agent/suggestions/${sessionId}`)
}

export function draftMessage(data: { need_title: string; match_name: string; match_skills: string[]; match_reason: string }) {
  return api.post<{ message: string }>('/agent/draft-message', data)
}

export function draftApplicationMessage(data: {
  need_id: number
  need_title: string
  need_type: string
  owner_name: string
  user_skills: string[]
  match_reason: string
}) {
  return api.post<{ message: string }>('/agent/draft-application-message', data)
}
