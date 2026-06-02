import api from './client'
import type { MessageItem, ConversationPreview } from '@/types'

export function sendMessage(data: { need_id: number; receiver_id: number; content: string }) {
  return api.post<MessageItem>('/messages', data)
}

export function getConversations() {
  return api.get<ConversationPreview[]>('/messages/conversations')
}

export function getMessages(otherUserId: number, needId?: number) {
  return api.get<MessageItem[]>(`/messages/${otherUserId}`, {
    params: needId ? { need_id: needId } : undefined,
  })
}

export function markRead(otherUserId: number, needId?: number) {
  return api.post(`/messages/read/${otherUserId}`, null, {
    params: needId ? { need_id: needId } : undefined,
  })
}
