import { defineStore } from 'pinia'
import { ref } from 'vue'
import type {
  AgentMessage,
  AgentSession,
  AgentSuggestion,
  AgentTask,
  AgentWorkspace,
  NeedDraft,
  NeedRecommendation,
} from '@/types'
import * as agentApi from '@/api/agent'
import { useDebugStore } from '@/stores/debug'

export const useAgentStore = defineStore('agent', () => {
  const debug = useDebugStore()
  const sessions = ref<{ id: number; title: string; status: string; summary?: string; created_at: string; updated_at: string }[]>([])
  const currentSession = ref<AgentSession | null>(null)
  const messages = ref<AgentMessage[]>([])
  const tasks = ref<AgentTask[]>([])
  const suggestions = ref<AgentSuggestion[]>([])
  const workspace = ref<AgentWorkspace>({ memory: {}, files: [] })
  const knowledgeResults = ref<Record<string, unknown>[]>([])
  const isStreaming = ref(false)
  const isPublishing = ref(false)
  const loading = ref(false)

  function clearActiveState() {
    currentSession.value = null
    messages.value = []
    tasks.value = []
    suggestions.value = []
    workspace.value = { memory: {}, files: [] }
    knowledgeResults.value = []
  }

  function flattenTaskTree(tree: AgentTask[]) {
    const result: AgentTask[] = []
    function walk(nodes: AgentTask[]) {
      for (const node of nodes) {
        const { children, ...rest } = node
        result.push(rest as AgentTask)
        if (children?.length) walk(children)
      }
    }
    walk(tree)
    return result
  }

  async function fetchSessions() {
    try {
      const { data } = await agentApi.listSessions()
      sessions.value = data
    } catch {
      sessions.value = []
    }
  }

  async function createSession(title?: string) {
    const { data } = await agentApi.createSession(title)
    await fetchSessions()
    return data.id
  }

  async function loadSession(id: number) {
    loading.value = true
    try {
      const { data } = await agentApi.getSession(id)
      currentSession.value = data.session as AgentSession
      messages.value = data.messages as AgentMessage[]
      tasks.value = flattenTaskTree(data.tasks as AgentTask[])
      await fetchWorkspace(id)
      await fetchSuggestions(id)
      return true
    } catch {
      clearActiveState()
      return false
    } finally {
      loading.value = false
    }
  }

  async function refreshTasks(sessionId: number) {
    const { data } = await agentApi.getTasks(sessionId)
    tasks.value = flattenTaskTree(data as AgentTask[])
  }

  async function fetchWorkspace(sessionId: number) {
    const { data } = await agentApi.getWorkspace(sessionId)
    workspace.value = data
  }

  async function retryTask(sessionId: number, taskId: number) {
    try {
      await agentApi.retryTask(sessionId, taskId)
      await refreshTasks(sessionId)
      await fetchWorkspace(sessionId)
    } catch {
      // ignore
    }
  }

  async function deleteSession(id: number) {
    await agentApi.deleteSession(id)
    await fetchSessions()
  }

  function buildAssistantMetadata(data: { drafts?: NeedDraft[]; need_recommendations?: NeedRecommendation[] }) {
    const extra: Record<string, unknown> = {}
    const metadata = (data as { message_metadata?: Record<string, unknown> | null }).message_metadata
    if (metadata && typeof metadata === 'object') Object.assign(extra, metadata)
    if (data.drafts?.length) extra.drafts = data.drafts
    if (data.need_recommendations?.length) extra.need_recommendations = data.need_recommendations
    return Object.keys(extra).length ? extra : undefined
  }

  function draftSignature(draft: NeedDraft) {
    return JSON.stringify({
      description: draft.description,
      selection_mode: draft.selection_mode,
      title: draft.title,
      type: draft.type,
    })
  }

  function removePublishedDraftsFromMessages(publishedDrafts: NeedDraft[]) {
    const remainingBySignature = new Map<string, number>()
    for (const draft of publishedDrafts) {
      const signature = draftSignature(draft)
      remainingBySignature.set(signature, (remainingBySignature.get(signature) || 0) + 1)
    }

    messages.value = messages.value.map((message) => {
      const drafts = message.extra_metadata?.drafts
      if (!Array.isArray(drafts)) return message

      let changed = false
      const nextDrafts = (drafts as NeedDraft[]).filter((draft) => {
        const signature = draftSignature(draft)
        const remaining = remainingBySignature.get(signature) || 0
        if (remaining <= 0) return true
        remainingBySignature.set(signature, remaining - 1)
        changed = true
        return false
      })
      if (!changed) return message

      const extraMetadata = { ...(message.extra_metadata || {}) }
      if (nextDrafts.length) {
        extraMetadata.drafts = nextDrafts
      } else {
        delete extraMetadata.drafts
      }
      return { ...message, extra_metadata: extraMetadata }
    })
  }

  async function sendMessage(sessionId: number, content: string) {
    isStreaming.value = true
    debug.api(`Agent message -> session ${sessionId}`)
    messages.value.push({
      id: Date.now(),
      session_id: sessionId,
      role: 'user',
      content,
      created_at: new Date().toISOString(),
    })
    try {
      const { data } = await agentApi.sendMessage(sessionId, content)
      messages.value.push({
        id: Date.now() + 1,
        session_id: sessionId,
        role: data.message_role || 'assistant',
        content: data.reply,
        extra_metadata: buildAssistantMetadata(data),
        created_at: new Date().toISOString(),
      })
      if (data.drafts && currentSession.value) {
        currentSession.value = {
          ...currentSession.value,
          planning_state: { phase: 'drafts_ready', drafts: data.drafts },
        }
      }
      await refreshTasks(sessionId)
      await fetchWorkspace(sessionId)
      await fetchSuggestions(sessionId)
      await fetchSessions()
      return data
    } catch {
      messages.value.push({
        id: Date.now() + 1,
        session_id: sessionId,
        role: 'system',
        content: '抱歉，AI 回复出错了，请重试。',
        created_at: new Date().toISOString(),
      })
    } finally {
      isStreaming.value = false
    }
  }

  async function uploadFile(sessionId: number, file: File) {
    isStreaming.value = true
    try {
      const { data } = await agentApi.uploadFile(sessionId, file)
      messages.value.push({
        id: Date.now() + 1,
        session_id: sessionId,
        role: 'assistant',
        content: data.reply,
        extra_metadata: { file_id: data.file_id, extracted: data.extracted, drafts: data.drafts },
        created_at: new Date().toISOString(),
      })
      await refreshTasks(sessionId)
      await fetchWorkspace(sessionId)
      await fetchSuggestions(sessionId)
      await fetchSessions()
      return data
    } finally {
      isStreaming.value = false
    }
  }

  async function triggerPlan(sessionId: number, goal: string) {
    try {
      const { data } = await agentApi.triggerPlan(sessionId, goal)
      messages.value.push({
        id: Date.now() + 1,
        session_id: sessionId,
        role: 'system',
        content: data.reply,
        extra_metadata: { type: 'plan' },
        created_at: new Date().toISOString(),
      })
      if (data.tasks) tasks.value = flattenTaskTree(data.tasks as AgentTask[])
      await refreshTasks(sessionId)
      await fetchWorkspace(sessionId)
      await fetchSuggestions(sessionId)
      await fetchSessions()
      return data
    } catch {
      // ignore
    }
  }

  async function confirmPublish(sessionId: number, drafts: NeedDraft[]) {
    if (isPublishing.value) return
    isPublishing.value = true
    try {
      const { data } = await agentApi.confirmPublish(sessionId, drafts)
      removePublishedDraftsFromMessages(drafts)
      messages.value.push({
        id: Date.now() + 1,
        session_id: sessionId,
        role: 'system',
        content: data.reply,
        extra_metadata: { type: 'publish_done' },
        created_at: new Date().toISOString(),
      })
      await refreshTasks(sessionId)
      await fetchWorkspace(sessionId)
      await fetchSuggestions(sessionId)
      await fetchSessions()
      return data
    } finally {
      isPublishing.value = false
    }
  }

  async function fetchSuggestions(sessionId: number) {
    try {
      const { data } = await agentApi.getSuggestions(sessionId)
      suggestions.value = data.suggestions
    } catch {
      suggestions.value = []
    }
  }

  async function searchKnowledge(query: string) {
    const text = query.trim()
    if (!text) {
      knowledgeResults.value = []
      return []
    }
    const { data } = await agentApi.searchKnowledge(text)
    knowledgeResults.value = data.results
    return data.results
  }

  async function resetMemory(sessionId: number) {
    await agentApi.resetMemory(sessionId)
    await fetchWorkspace(sessionId)
  }

  async function draftApplicationMessage(data: {
    need_id: number
    need_title: string
    need_type: string
    owner_name: string
    user_skills: string[]
    match_reason: string
  }) {
    const response = await agentApi.draftApplicationMessage(data)
    return response.data.message
  }

  return {
    sessions,
    currentSession,
    messages,
    tasks,
    suggestions,
    workspace,
    knowledgeResults,
    isStreaming,
    isPublishing,
    loading,
    fetchSessions,
    createSession,
    loadSession,
    deleteSession,
    sendMessage,
    uploadFile,
    triggerPlan,
    confirmPublish,
    fetchSuggestions,
    refreshTasks,
    retryTask,
    fetchWorkspace,
    searchKnowledge,
    resetMemory,
    clearActiveState,
    draftApplicationMessage,
  }
})
