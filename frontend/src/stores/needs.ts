import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { MatchProgress, MatchResult, Need, NeedApplication } from '@/types'
import * as needsApi from '@/api/needs'
import { useAuthStore } from './auth'

export const useNeedsStore = defineStore('needs', () => {
  const needs = ref<Need[]>([])
  const total = ref(0)
  const currentNeed = ref<Need | null>(null)
  const currentApplications = ref<NeedApplication[]>([])
  const myApplications = ref<NeedApplication[]>([])
  const matches = ref<MatchResult[]>([])
  const matchProgress = ref<MatchProgress[]>([])
  const loading = ref(false)
  const applicationDrafts = ref<Record<number, string>>({})
  let activeEventSource: EventSource | null = null
  let sseErrorCount = 0

  async function fetchNeeds(params?: { page?: number; page_size?: number; status?: string; type?: string }) {
    loading.value = true
    try {
      const { data } = await needsApi.getNeeds(params)
      needs.value = data.items
      total.value = data.total
    } finally {
      loading.value = false
    }
  }

  async function createNeed(payload: { type: string; title: string; description: string; selection_mode?: string }) {
    const { data } = await needsApi.createNeed(payload)
    currentNeed.value = data
    return data
  }

  async function fetchNeedDetail(needId: number) {
    loading.value = true
    try {
      const { data } = await needsApi.getNeedDetail(needId)
      currentNeed.value = data
      return data
    } finally {
      loading.value = false
    }
  }

  async function fetchNeedApplications(needId: number) {
    const { data } = await needsApi.getNeedApplications(needId)
    currentApplications.value = data.items
    return data.items
  }

  async function fetchMyApplications() {
    const { data } = await needsApi.getMyApplications()
    myApplications.value = data.items
    return data.items
  }

  async function applyToNeed(needId: number, message: string) {
    const { data } = await needsApi.applyToNeed(needId, message)
    await Promise.all([fetchNeedDetail(needId), fetchMyApplications()])
    return data
  }

  async function reviewApplication(applicationId: number, accepted: boolean, ownerReply?: string) {
    const { data } = accepted
      ? await needsApi.acceptNeedApplication(applicationId, ownerReply)
      : await needsApi.rejectNeedApplication(applicationId, ownerReply)
    if (currentNeed.value) {
      await Promise.all([fetchNeedDetail(currentNeed.value.id), fetchNeedApplications(currentNeed.value.id)])
    }
    return data
  }

  function setApplicationDraft(needId: number, text: string) {
    applicationDrafts.value = { ...applicationDrafts.value, [needId]: text }
  }

  function consumeApplicationDraft(needId: number) {
    const text = applicationDrafts.value[needId] || ''
    const next = { ...applicationDrafts.value }
    delete next[needId]
    applicationDrafts.value = next
    return text
  }

  async function fetchMatches(needId: number) {
    loading.value = true
    try {
      const { data } = await needsApi.getMatches(needId)
      currentNeed.value = data.need
      matches.value = data.matches
      return data
    } finally {
      loading.value = false
    }
  }

  function streamMatches(needId: number) {
    if (activeEventSource) {
      activeEventSource.close()
    }
    sseErrorCount = 0
    matchProgress.value = []
    matches.value = []

    const authStore = useAuthStore()
    // Set auth_token cookie so the SSE EventSource sends it automatically
    if (authStore.token) {
      document.cookie = `auth_token=${encodeURIComponent(authStore.token)}; path=/; SameSite=Lax`
    }
    const url = needsApi.getMatchStreamUrl(needId)
    const eventSource = new EventSource(url)
    activeEventSource = eventSource

    const finish = () => {
      if (activeEventSource === eventSource) {
        activeEventSource = null
      }
      if (eventSource.readyState !== EventSource.CLOSED) {
        eventSource.close()
      }
    }

    const timeout = setTimeout(() => {
      finish()
      matchProgress.value.push({ stage: 'error', message: '匹配超时，请点击刷新重试' })
    }, 60000)

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as MatchProgress
        matchProgress.value.push(data)
        if (data.stage === 'done' && data.data?.results) {
          matches.value = data.data.results as MatchResult[]
          clearTimeout(timeout)
          finish()
        }
        if (data.stage === 'error') {
          clearTimeout(timeout)
          finish()
        }
      } catch {
        matchProgress.value.push({ stage: 'error', message: '数据解析失败' })
        clearTimeout(timeout)
        finish()
      }
    }

    eventSource.onerror = () => {
      sseErrorCount++
      if (sseErrorCount >= 3 || eventSource.readyState === EventSource.CLOSED) {
        clearTimeout(timeout)
        finish()
        matchProgress.value.push({ stage: 'error', message: '连接失败，请点击刷新重试' })
      }
    }

    return eventSource
  }

  async function refreshMatches(needId: number) {
    loading.value = true
    matchProgress.value = []
    try {
      const { data } = await needsApi.refreshMatches(needId)
      currentNeed.value = data.need
      matches.value = data.matches
      return data
    } finally {
      loading.value = false
    }
  }

  async function submitFeedback(matchId: number, feedback: number) {
    await needsApi.submitFeedback(matchId, feedback)
  }

  async function refineNeed(needId: number) {
    const { data } = await needsApi.refineNeed(needId)
    return data.question
  }

  async function logBehavior(event: string, extra?: { target_user_id?: number; need_id?: number }) {
    await needsApi.logBehavior({ event_type: event, ...extra })
  }

  return {
    needs,
    total,
    currentNeed,
    currentApplications,
    myApplications,
    matches,
    matchProgress,
    loading,
    applicationDrafts,
    fetchNeeds,
    createNeed,
    fetchNeedDetail,
    fetchNeedApplications,
    fetchMyApplications,
    applyToNeed,
    reviewApplication,
    setApplicationDraft,
    consumeApplicationDraft,
    fetchMatches,
    streamMatches,
    refreshMatches,
    submitFeedback,
    refineNeed,
    logBehavior,
  }
})
