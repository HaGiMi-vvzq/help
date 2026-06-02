<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { useAgentStore } from '@/stores/agent'
import { useAuthStore } from '@/stores/auth'
import { useNeedsStore } from '@/stores/needs'
import type { AgentMessage, AgentQuickOption, AgentSuggestion, NeedDraft, NeedRecommendation } from '@/types'

const route = useRoute()
const router = useRouter()
const store = useAgentStore()
const authStore = useAuthStore()
const needsStore = useNeedsStore()

const inputText = ref('')
const showSessions = ref(false)
const showTasks = ref(false)
const isMobile = ref(false)
const activeSessionId = ref<number | null>(null)
const fileInput = ref<HTMLInputElement>()
const uploading = ref(false)
const messagesEl = ref<HTMLElement>()
const knowledgeQuery = ref('')
const selectedDraftKeys = ref<string[]>([])
const initializedDraftPanels = ref<string[]>([])

const taskStats = computed(() => {
  const items = store.tasks
  return {
    total: items.length,
    running: items.filter((task) => task.status === 'running').length,
    waiting: items.filter((task) => task.status === 'waiting_user').length,
    done: items.filter((task) => task.status === 'done').length,
  }
})

const draftCount = computed(() =>
  store.messages.reduce((count, message) => count + getMessageDrafts(message).length, 0),
)

const latestFile = computed(() => store.workspace.files[0])

function checkMobile() {
  isMobile.value = window.innerWidth < 768
}

onMounted(async () => {
  checkMobile()
  window.addEventListener('resize', checkMobile)
  await initializeAgentRoute()
})

onUnmounted(() => {
  window.removeEventListener('resize', checkMobile)
})

watch(() => route.params.sessionId, () => initializeAgentRoute())

watch(() => authStore.user?.id, () => {
  store.clearActiveState()
  activeSessionId.value = null
  if (route.path.startsWith('/agent')) void initializeAgentRoute()
})

watch(
  () => store.messages.map((message) => `${message.id}:${JSON.stringify(message.extra_metadata?.drafts || [])}`).join('|'),
  () => initializeDraftSelections(),
  { immediate: true },
)

async function handleNewSession() {
  const id = await store.createSession()
  activeSessionId.value = id
  router.push(`/agent/${id}`)
  return id
}

function handleSelectSession(id: number) {
  activeSessionId.value = id
  showSessions.value = false
  router.push(`/agent/${id}`)
}

async function handleDeleteSession(id: number) {
  try {
    await ElMessageBox.confirm('确定删除这个会话吗？', '确认删除', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }

  try {
    await store.deleteSession(id)
    if (activeSessionId.value === id) {
      activeSessionId.value = null
      router.push('/agent')
    }
    ElMessage.success('已删除')
  } catch (error: any) {
    ElMessage.error('删除失败: ' + (error?.response?.data?.detail || error?.message || ''))
  }
}

async function openDefaultSession() {
  if (store.sessions.length > 0) {
    const fallbackId = store.sessions[0].id
    activeSessionId.value = fallbackId
    if (route.params.sessionId !== String(fallbackId)) {
      await router.replace(`/agent/${fallbackId}`)
      return
    }
    await store.loadSession(fallbackId)
    return
  }

  activeSessionId.value = null
  store.clearActiveState()
  if (route.path !== '/agent') await router.replace('/agent')
}

async function initializeAgentRoute() {
  await store.fetchSessions()
  const rawSessionId = Array.isArray(route.params.sessionId) ? route.params.sessionId[0] : route.params.sessionId
  const requestedSessionId = Number(rawSessionId)

  if (rawSessionId && Number.isFinite(requestedSessionId)) {
    const belongsToCurrentUser = store.sessions.some((session) => session.id === requestedSessionId)
    if (!belongsToCurrentUser) {
      await openDefaultSession()
      return
    }

    activeSessionId.value = requestedSessionId
    const loaded = await store.loadSession(requestedSessionId)
    if (!loaded) {
      await store.fetchSessions()
      await openDefaultSession()
    }
    return
  }

  await openDefaultSession()
}

async function ensureActiveSession() {
  if (activeSessionId.value) return activeSessionId.value
  if (store.sessions.length > 0) {
    const id = store.sessions[0].id
    activeSessionId.value = id
    await router.replace(`/agent/${id}`)
    return id
  }
  return await handleNewSession()
}

async function handleSend() {
  const text = inputText.value.trim()
  if (!text || store.isStreaming) return
  const sessionId = await ensureActiveSession()
  inputText.value = ''

  if (text.startsWith('/plan ')) {
    await store.triggerPlan(sessionId, text.slice(6))
  } else {
    await store.sendMessage(sessionId, text)
  }
  scrollToBottom()
}

async function handleFileUpload(file: File) {
  const sessionId = await ensureActiveSession()
  uploading.value = true
  try {
    const result = await store.uploadFile(sessionId, file)
    if (result) ElMessage.success(`${file.name} 分析完成`)
  } catch (error: any) {
    ElMessage.error('分析失败: ' + (error?.response?.data?.detail || error?.message || '未知错误'))
  } finally {
    uploading.value = false
    scrollToBottom()
  }
}

function handleFileChange(event: Event) {
  const element = event.target as HTMLInputElement
  const file = element.files?.[0]
  if (!file) return
  const allowedExtensions = ['txt', 'docx', 'pdf', 'doc', 'md']
  const allowedMimes = [
    'text/plain', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/pdf', 'application/msword', 'text/markdown',
  ]
  const ext = file.name.split('.').pop()?.toLowerCase() || ''
  const validExt = allowedExtensions.includes(ext)
  const validMime = file.type ? allowedMimes.includes(file.type) : validExt
  if (!validExt || !validMime) {
    ElMessage.error('仅支持 TXT、DOCX、PDF、DOC、MD 格式的文件')
    element.value = ''
    return
  }
  const maxSize = 10 * 1024 * 1024
  if (file.size > maxSize) {
    ElMessage.error('文件不能超过 10MB')
    element.value = ''
    return
  }
  handleFileUpload(file).finally(() => { element.value = '' })
}

async function handlePublishDrafts(drafts: NeedDraft[]) {
  if (!activeSessionId.value) return
  try {
    await store.confirmPublish(activeSessionId.value, drafts)
    ElMessage.success('需求已发布，正在匹配中')
  } catch (error: any) {
    const detail = error?.response?.data?.detail || error?.message || ''
    if (String(detail).includes('already published') || String(detail).includes('publish already in progress')) {
      ElMessage.info('这份草稿已经在发布中或已发布，已为你拦住重复提交')
      return
    }
    ElMessage.error('发布失败: ' + detail)
  }
}

async function handleKnowledgeSearch() {
  try {
    await store.searchKnowledge(knowledgeQuery.value)
  } catch (error: any) {
    ElMessage.error('知识搜索失败: ' + (error?.response?.data?.detail || error?.message || ''))
  }
}

async function handleResetMemory() {
  if (!activeSessionId.value) return
  try {
    await store.resetMemory(activeSessionId.value)
    ElMessage.success('记忆摘要已清空')
  } catch (error: any) {
    ElMessage.error('清空失败: ' + (error?.response?.data?.detail || error?.message || ''))
  }
}

async function handleSuggestionClick(suggestion: AgentSuggestion) {
  if (suggestion.action_type === 'prefill') {
    inputText.value = String(suggestion.payload?.text || suggestion.text)
    return
  }
  if (suggestion.action_type === 'navigate') {
    const path = String(suggestion.payload?.path || '')
    if (path) await router.push(path)
    return
  }
  if (suggestion.action_type === 'refresh_tasks' && activeSessionId.value) {
    await store.refreshTasks(activeSessionId.value)
    return
  }
  inputText.value = suggestion.text
}

function getMessageDrafts(message: AgentMessage): NeedDraft[] {
  const drafts = message.extra_metadata?.drafts
  return Array.isArray(drafts) ? (drafts as NeedDraft[]) : []
}

function getDraftPanelKey(message: AgentMessage) {
  return `${message.session_id}-${message.id}`
}

function getDraftKey(message: AgentMessage, draft: NeedDraft, index: number) {
  return `${getDraftPanelKey(message)}-${index}-${draft.type}-${draft.title}-${draft.selection_mode || 'single'}`
}

function initializeDraftSelections() {
  const availableKeys = new Set<string>()
  const nextSelected = new Set(selectedDraftKeys.value)
  const nextInitialized = new Set(initializedDraftPanels.value)

  for (const message of store.messages) {
    const drafts = getMessageDrafts(message)
    if (!drafts.length) continue

    const panelKey = getDraftPanelKey(message)
    const panelKeys = drafts.map((draft, index) => getDraftKey(message, draft, index))
    panelKeys.forEach((key) => availableKeys.add(key))

    if (!nextInitialized.has(panelKey)) {
      panelKeys.forEach((key) => nextSelected.add(key))
      nextInitialized.add(panelKey)
    }
  }

  selectedDraftKeys.value = Array.from(nextSelected).filter((key) => availableKeys.has(key))
  initializedDraftPanels.value = Array.from(nextInitialized)
}

function isDraftSelected(message: AgentMessage, draft: NeedDraft, index: number) {
  return selectedDraftKeys.value.includes(getDraftKey(message, draft, index))
}

function toggleDraftSelection(message: AgentMessage, draft: NeedDraft, index: number) {
  const key = getDraftKey(message, draft, index)
  if (selectedDraftKeys.value.includes(key)) {
    selectedDraftKeys.value = selectedDraftKeys.value.filter((item) => item !== key)
    return
  }
  selectedDraftKeys.value = [...selectedDraftKeys.value, key]
}

function getSelectedDrafts(message: AgentMessage) {
  return getMessageDrafts(message).filter((draft, index) => isDraftSelected(message, draft, index))
}

function getMessageFile(message: AgentMessage) {
  const extracted = message.extra_metadata?.extracted
  if (extracted && typeof extracted === 'object' && !Array.isArray(extracted)) {
    return extracted as Record<string, unknown>
  }
  return null
}

function isPlanMessage(message: AgentMessage) {
  return message.extra_metadata?.type === 'plan'
}

function isPublishMessage(message: AgentMessage) {
  return message.extra_metadata?.type === 'publish_done'
}

function getNeedRecommendations(message: AgentMessage): NeedRecommendation[] {
  const items = message.extra_metadata?.need_recommendations
  return Array.isArray(items) ? (items as NeedRecommendation[]) : []
}

function getFollowUpOptions(message: AgentMessage): AgentQuickOption[] {
  const items = message.extra_metadata?.options
  if (!Array.isArray(items)) return []
  return items.filter((item): item is AgentQuickOption => {
    return Boolean(
      item
      && typeof item === 'object'
      && 'label' in item
      && 'value' in item
      && typeof item.label === 'string'
      && typeof item.value === 'string',
    )
  })
}

async function handleFollowUpOptionClick(option: AgentQuickOption) {
  if (!activeSessionId.value || store.isStreaming) return
  inputText.value = option.value
  await handleSend()
}

async function handleOpenRecommendedNeed(needId: number) {
  await router.push(`/needs/${needId}`)
}

async function handleDraftApplication(recommendation: NeedRecommendation) {
  try {
    const text = await store.draftApplicationMessage({
      need_id: recommendation.need_id,
      need_title: recommendation.title,
      need_type: recommendation.type,
      owner_name: recommendation.owner_name,
      user_skills: authStore.user?.skill_tags || [],
      match_reason: recommendation.reason,
    })
    needsStore.setApplicationDraft(recommendation.need_id, text)
    await router.push(`/needs/${recommendation.need_id}`)
    ElMessage.success('已为你准备好申请消息，正在跳转到需求详情页')
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || error?.message || '起草申请失败')
  }
}

async function handleQuickApplyFromAgent(recommendation: NeedRecommendation) {
  try {
    const text = await store.draftApplicationMessage({
      need_id: recommendation.need_id,
      need_title: recommendation.title,
      need_type: recommendation.type,
      owner_name: recommendation.owner_name,
      user_skills: authStore.user?.skill_tags || [],
      match_reason: recommendation.reason,
    })

    try {
      await ElMessageBox.confirm(
        `将向 ${recommendation.owner_name || '发布者'} 发送以下申请：\n\n${text}`,
        '确认申请',
        {
          confirmButtonText: '发送申请并去沟通',
          cancelButtonText: '取消',
          type: 'info',
        },
      )
    } catch {
      needsStore.setApplicationDraft(recommendation.need_id, text)
      return
    }

    await needsStore.applyToNeed(recommendation.need_id, text)
    ElMessage.success('申请已发送，正在带你去消息页继续沟通')
    await router.push(`/messages/${recommendation.owner_id}?needId=${recommendation.need_id}`)
  } catch (error: any) {
    const detail = String(error?.response?.data?.detail || error?.message || '')
    if (detail.includes('application already exists')) {
      ElMessage.info('你已经申请过这个需求了，直接去消息页继续沟通')
      await router.push(`/messages/${recommendation.owner_id}?needId=${recommendation.need_id}`)
      return
    }
    ElMessage.error(detail || '一键申请失败')
  }
}

function triggerUpload() {
  fileInput.value?.click()
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesEl.value) messagesEl.value.scrollTop = messagesEl.value.scrollHeight
  })
}

function suggestionVariant(index: number) {
  return ['primary', 'success', 'warning'][index % 3]
}
</script>

<template>
  <div class="agent-workbench">
    <div v-if="isMobile && showSessions" class="mobile-overlay" @click="showSessions = false" />
    <aside class="agent-sessions" :class="{ 'is-open': showSessions }">
      <div class="surface-card-strong sessions-panel">
        <div class="sessions-header">
          <div>
            <span class="eyebrow">上下文</span>
            <h2>会话列表</h2>
          </div>
          <el-button type="primary" size="small" :icon="Plus" circle @click="handleNewSession" />
        </div>

        <div class="sessions-list">
          <button
            v-for="session in store.sessions"
            :key="session.id"
            type="button"
            class="session-item"
            :class="{ active: session.id === activeSessionId }"
            @click="handleSelectSession(session.id)"
          >
            <div class="session-item-main">
              <span class="session-item-title">{{ session.title }}</span>
              <span class="session-item-time">{{ session.updated_at?.slice(5, 16) }}</span>
            </div>
            <span class="session-item-summary">{{ session.summary || '等待新的任务与上下文' }}</span>
            <el-button
              size="small"
              text
              type="danger"
              class="session-item-delete"
              @click.stop="handleDeleteSession(session.id)"
            >
              <el-icon :size="14"><Delete /></el-icon>
            </el-button>
          </button>

          <div v-if="store.sessions.length === 0" class="empty-state">
            <el-icon :size="42" style="color: var(--text-muted)"><ChatLineSquare /></el-icon>
            <p>暂无会话。新建一个会话后，可以上传文件或直接让 Agent 帮你整理需求。</p>
            <el-button type="primary" @click="handleNewSession">新建会话</el-button>
          </div>
        </div>
      </div>
    </aside>

    <section class="agent-center">
      <div class="agent-hero surface-card-strong">
        <div class="hero-main">
          <span class="eyebrow">AI 主舞台</span>
          <h1>{{ store.currentSession?.title || '智能助手工作台' }}</h1>
          <p>
            让 Agent 帮你分析文件、整理需求草稿、确认发布，并在匹配完成后继续推进联系动作。
          </p>
          <div class="hero-actions">
            <el-button type="primary" @click="triggerUpload" :loading="uploading">上传文件</el-button>
            <el-button @click="inputText = '/plan 帮我规划从分析到发布的步骤'">制定计划</el-button>
            <el-button @click="inputText = '帮我发布一个需求'">开始追问</el-button>
          </div>
        </div>

        <div class="hero-metrics metric-grid">
          <div class="metric-card">
            <div class="metric-icon" style="background: var(--color-primary-bg); color: var(--color-primary)">
              <el-icon :size="18"><DataAnalysis /></el-icon>
            </div>
            <div>
              <span class="metric-value">{{ taskStats.total }}</span>
              <span class="metric-label">总任务数</span>
            </div>
          </div>
          <div class="metric-card">
            <div class="metric-icon" style="background: var(--color-warning-soft); color: var(--color-warning)">
              <el-icon :size="18"><Loading /></el-icon>
            </div>
            <div>
              <span class="metric-value">{{ taskStats.running + taskStats.waiting }}</span>
              <span class="metric-label">待推进任务</span>
            </div>
          </div>
          <div class="metric-card">
            <div class="metric-icon" style="background: var(--color-success-soft); color: var(--color-success)">
              <el-icon :size="18"><Document /></el-icon>
            </div>
            <div>
              <span class="metric-value">{{ draftCount }}</span>
              <span class="metric-label">已生成草稿</span>
            </div>
          </div>
          <div class="metric-card">
            <div class="metric-icon" style="background: var(--bg-panel-muted); color: var(--text-secondary)">
              <el-icon :size="18"><Files /></el-icon>
            </div>
            <div>
              <span class="metric-value">{{ store.workspace.files.length }}</span>
              <span class="metric-label">文件库</span>
            </div>
          </div>
        </div>
      </div>

      <div class="agent-chat-shell surface-card-strong">
        <div class="chat-topbar">
          <div class="chat-topbar-left">
            <el-button v-if="isMobile" text @click="showSessions = !showSessions">
              <el-icon :size="18"><Menu /></el-icon>
            </el-button>
            <div>
              <div class="chat-topbar-title">{{ store.currentSession?.title || '智能助手' }}</div>
              <div class="chat-topbar-subtitle">支持文件分析、需求追问、计划生成与发布确认</div>
            </div>
          </div>
          <el-button v-if="isMobile" text @click="showTasks = !showTasks">
            <el-icon :size="18"><List /></el-icon>
          </el-button>
        </div>

        <div ref="messagesEl" class="chat-stream">
          <div v-if="store.messages.length === 0 && !store.loading" class="welcome-panel">
            <div class="welcome-panel-icon">
              <el-icon :size="32"><MagicStick /></el-icon>
            </div>
            <div class="welcome-panel-copy">
              <h3>从一个目标开始</h3>
              <p>你可以上传赛事文档、直接描述需求，或让 Agent 先帮你制定一个执行计划。</p>
            </div>
            <div class="welcome-grid">
              <button type="button" class="welcome-action" @click="triggerUpload">
                <el-icon :size="20"><UploadFilled /></el-icon>
                <span>上传文件分析</span>
              </button>
              <button type="button" class="welcome-action" @click="inputText = '/plan 帮我规划需求发布流程'">
                <el-icon :size="20"><Guide /></el-icon>
                <span>生成任务计划</span>
              </button>
              <button type="button" class="welcome-action" @click="inputText = '帮我发布一个组队需求'">
                <el-icon :size="20"><EditPen /></el-icon>
                <span>直接开始追问</span>
              </button>
            </div>
          </div>

          <div v-if="store.loading" class="loading-state">
            <div class="skeleton" style="width: 62%; height: 16px; margin-bottom: 10px" />
            <div class="skeleton" style="width: 78%; height: 16px; margin-bottom: 10px" />
            <div class="skeleton" style="width: 45%; height: 16px" />
          </div>

          <template v-for="message in store.messages" :key="message.id">
            <div class="message-row" :class="message.role">
              <div class="message-avatar">
                {{ message.role === 'user' ? '我' : message.role === 'assistant' ? 'AI' : '!' }}
              </div>
              <div class="message-stack">
                <div class="message-bubble" :class="message.role">
                  <div class="message-content">{{ message.content }}</div>
                </div>

                <div v-if="getFollowUpOptions(message).length" class="follow-up-options">
                  <button
                    v-for="option in getFollowUpOptions(message)"
                    :key="`${message.id}-${option.value}`"
                    type="button"
                    class="follow-up-option-chip"
                    @click="handleFollowUpOptionClick(option)"
                  >
                    {{ option.label }}
                  </button>
                </div>

                <div v-if="getMessageFile(message)" class="message-result-card">
                  <div class="result-card-header">
                    <div>
                      <span class="result-card-kicker">文件分析</span>
                      <strong>{{ String(getMessageFile(message)?.title || latestFile?.filename || '已完成分析') }}</strong>
                    </div>
                    <span class="result-pill">可继续生成草稿</span>
                  </div>
                  <p class="result-card-summary">{{ String(getMessageFile(message)?.summary || '已提取关键信息') }}</p>
                  <div class="result-card-meta">
                    <span v-if="Array.isArray(getMessageFile(message)?.skills_needed)">
                      技能：{{ (getMessageFile(message)?.skills_needed as string[]).join('、') }}
                    </span>
                    <span v-if="getMessageFile(message)?.deadline">截止：{{ String(getMessageFile(message)?.deadline) }}</span>
                  </div>
                </div>

                <div v-if="getMessageDrafts(message).length" class="draft-panel">
                  <div class="draft-panel-header">
                    <div>
                      <span class="result-card-kicker">需求草稿</span>
                      <strong>Agent 已整理出可发布内容</strong>
                    </div>
                    <span class="result-pill">{{ getMessageDrafts(message).length }} 条</span>
                  </div>
                  <div class="draft-list">
                    <article
                      v-for="(draft, index) in getMessageDrafts(message)"
                      :key="getDraftKey(message, draft, index)"
                      class="draft-card"
                      :class="{ selected: isDraftSelected(message, draft, index) }"
                      role="checkbox"
                      tabindex="0"
                      :aria-checked="isDraftSelected(message, draft, index)"
                      @click="toggleDraftSelection(message, draft, index)"
                      @keydown.enter.prevent="toggleDraftSelection(message, draft, index)"
                      @keydown.space.prevent="toggleDraftSelection(message, draft, index)"
                    >
                      <div class="draft-card-top">
                        <div class="draft-card-tags">
                          <el-tag size="small" :type="draft.type === '求助' ? 'danger' : draft.type === '组队' ? 'primary' : 'success'">
                            {{ draft.type }}
                          </el-tag>
                          <span class="draft-selection">{{ draft.selection_mode === 'multi' ? '多人' : '单人' }}</span>
                        </div>
                        <span class="draft-check" :class="{ active: isDraftSelected(message, draft, index) }">
                          {{ isDraftSelected(message, draft, index) ? '已选' : '选择' }}
                        </span>
                      </div>
                      <strong>{{ draft.title }}</strong>
                      <p>{{ draft.description }}</p>
                    </article>
                  </div>
                  <el-button
                    type="primary"
                    size="small"
                    :loading="store.isPublishing"
                    :disabled="store.isPublishing || getSelectedDrafts(message).length === 0"
                    @click="handlePublishDrafts(getSelectedDrafts(message))"
                  >
                    确认发布选中的 {{ getSelectedDrafts(message).length }} 条需求
                  </el-button>
                </div>

                <div v-if="getNeedRecommendations(message).length" class="draft-panel recommendation-panel">
                  <div class="draft-panel-header">
                    <div>
                      <span class="result-card-kicker">需求推荐</span>
                      <strong>Agent 找到了适合你主动加入的需求</strong>
                    </div>
                    <span class="result-pill">{{ getNeedRecommendations(message).length }} 条</span>
                  </div>
                  <div class="recommendation-list">
                    <article
                      v-for="recommendation in getNeedRecommendations(message)"
                      :key="recommendation.need_id"
                      class="recommendation-card"
                    >
                      <div class="recommendation-top">
                        <el-tag size="small" type="success" effect="plain">{{ recommendation.type }}</el-tag>
                        <span class="recommendation-score">{{ recommendation.score }} 分匹配</span>
                      </div>
                      <strong>{{ recommendation.title }}</strong>
                      <p>{{ recommendation.reason }}</p>
                      <div v-if="recommendation.req_tags?.length" class="recommendation-tags">
                        <el-tag
                          v-for="tag in recommendation.req_tags.slice(0, 4)"
                          :key="`${recommendation.need_id}-${tag}`"
                          size="small"
                          effect="plain"
                        >
                          {{ tag }}
                        </el-tag>
                      </div>
                      <div class="recommendation-actions">
                        <el-button size="small" @click="handleOpenRecommendedNeed(recommendation.need_id)">
                          查看需求
                        </el-button>
                        <el-button type="primary" size="small" @click="handleDraftApplication(recommendation)">
                          起草申请
                        </el-button>
                        <el-button
                          class="quick-apply-button"
                          type="success"
                          size="small"
                          @click="handleQuickApplyFromAgent(recommendation)"
                        >
                          一键申请并去沟通
                        </el-button>
                      </div>
                    </article>
                  </div>
                </div>

                <div v-if="isPlanMessage(message)" class="plan-banner">
                  <el-icon :size="14"><Clock /></el-icon>
                  <span>计划已生成，右侧任务时间线已同步更新。</span>
                </div>

                <div v-if="isPublishMessage(message)" class="plan-banner success">
                  <el-icon :size="14"><CircleCheckFilled /></el-icon>
                  <span>需求已发布。现在可以转到匹配结果或等待 Agent 继续提醒。</span>
                </div>
              </div>
            </div>
          </template>
        </div>

        <div class="chat-input-bar">
          <input ref="fileInput" type="file" accept=".txt,.docx,.pdf,.doc,.md" style="display: none" @change="handleFileChange" />
          <el-tooltip content="上传文件" placement="top">
            <el-button text class="chat-tool-btn" :loading="uploading" @click="triggerUpload">
              <el-icon :size="18"><Link /></el-icon>
            </el-button>
          </el-tooltip>
          <el-input
            v-model="inputText"
            class="chat-input"
            :disabled="store.isStreaming"
            placeholder="输入消息，或使用 /plan 目标 来生成计划"
            @keyup.enter="handleSend"
          />
          <el-button type="primary" :disabled="!inputText.trim() || store.isStreaming" :loading="store.isStreaming" @click="handleSend">
            发送
          </el-button>
        </div>
      </div>
    </section>

    <div v-if="isMobile && showTasks" class="mobile-overlay" @click="showTasks = false" />
    <aside class="agent-sidepanels" :class="{ 'is-open': showTasks }">
      <div class="sidepanel-stack">
        <section class="surface-card-strong sidepanel-block">
          <div class="surface-section-title">
            <div>
              <span class="eyebrow">下一步</span>
              <h3>主动建议</h3>
            </div>
          </div>
          <div v-if="store.suggestions.length === 0" class="panel-empty">暂无建议</div>
          <button
            v-for="(suggestion, index) in store.suggestions"
            :key="suggestion.id"
            type="button"
            class="suggestion-card"
            :class="suggestionVariant(index)"
            @click="handleSuggestionClick(suggestion)"
          >
            <span class="suggestion-index">0{{ index + 1 }}</span>
            <span>{{ suggestion.text }}</span>
          </button>
        </section>

        <section class="surface-card-strong sidepanel-block">
          <div class="surface-section-title">
            <div>
              <span class="eyebrow">上下文检索</span>
              <h3>知识搜索</h3>
            </div>
          </div>
          <div class="knowledge-box">
            <el-input v-model="knowledgeQuery" size="small" placeholder="搜索历史文件和分析结果" @keyup.enter="handleKnowledgeSearch" />
            <el-button size="small" @click="handleKnowledgeSearch">搜索</el-button>
          </div>
          <div v-if="store.knowledgeResults.length === 0" class="panel-empty">暂无结果</div>
          <article v-for="(item, index) in store.knowledgeResults" :key="index" class="knowledge-item">
            <strong class="knowledge-title">{{ String(item.filename || `结果 ${index + 1}`) }}</strong>
            <span class="knowledge-meta">
              {{ item.similarity ? `相似度 ${(Number(item.similarity) * 100).toFixed(0)}%` : '历史内容' }}
            </span>
          </article>
        </section>

        <section class="surface-card-strong sidepanel-block">
          <div class="surface-section-title">
            <div>
              <span class="eyebrow">会话资产</span>
              <h3>文件库</h3>
            </div>
          </div>
          <div v-if="store.workspace.files.length === 0" class="panel-empty">暂无文件</div>
          <article v-for="file in store.workspace.files.slice(0, 4)" :key="file.id" class="workspace-file">
            <strong class="workspace-file-name">{{ file.filename }}</strong>
            <span class="workspace-file-meta">{{ file.file_type }} · {{ file.created_at.slice(5, 16) }}</span>
          </article>
        </section>

        <section class="surface-card-strong sidepanel-block">
          <div class="surface-section-title">
            <div>
              <span class="eyebrow">长期上下文</span>
              <h3>记忆摘要</h3>
            </div>
            <el-button v-if="activeSessionId" text size="small" @click="handleResetMemory">清空</el-button>
          </div>
          <div v-if="store.workspace.memory.summary" class="memory-summary">
            {{ store.workspace.memory.summary }}
          </div>
          <div v-else class="panel-empty">当前会话还没有长期摘要</div>
        </section>

        <section class="surface-card-strong sidepanel-block sidepanel-grow">
          <div class="surface-section-title">
            <div>
              <span class="eyebrow">执行状态</span>
              <h3>任务时间线</h3>
            </div>
            <el-button text size="small" @click="activeSessionId && store.refreshTasks(activeSessionId)">
              <el-icon :size="12"><Refresh /></el-icon>
            </el-button>
          </div>
          <div v-if="store.tasks.length === 0" class="panel-empty">暂无任务</div>
          <article v-for="task in store.tasks" :key="task.id" class="task-card">
            <div class="task-indicator" :class="task.status">
              <el-icon v-if="task.status === 'done'" :size="14"><CircleCheckFilled /></el-icon>
              <el-icon v-else-if="task.status === 'running'" :size="14"><Loading /></el-icon>
              <el-icon v-else-if="task.status === 'failed'" :size="14"><CircleCloseFilled /></el-icon>
              <el-icon v-else-if="task.status === 'waiting_user'" :size="14"><User /></el-icon>
              <div v-else class="task-dot" />
            </div>
            <div class="task-body">
              <div class="task-goal">
                <el-tag v-if="task.task_type" size="small" type="info" effect="plain" class="task-type-tag">
                  {{ task.task_type }}
                </el-tag>
                {{ task.goal }}
              </div>
              <div class="task-meta">
                <span v-if="task.assigned_agent" class="task-agent">{{ task.assigned_agent }}</span>
                <span v-if="task.retry_count > 0" class="task-retry">重试 {{ task.retry_count }} 次</span>
              </div>
              <div v-if="task.status === 'failed'" class="task-error-block">
                <span v-if="task.error_code" class="task-error-code">{{ task.error_code }}</span>
                <span v-if="task.error" class="task-error-message">{{ task.error }}</span>
                <el-button
                  v-if="activeSessionId"
                  size="small"
                  text
                  type="danger"
                  class="task-retry-btn"
                  @click="activeSessionId && store.retryTask(activeSessionId, task.id)"
                >
                  重试
                </el-button>
              </div>
              <div v-if="task.need_id || task.file_id" class="task-links">
                <el-button v-if="task.need_id" text size="small" type="primary" @click="router.push(`/needs/${task.need_id}/matches`)">
                  查看需求
                </el-button>
                <el-button v-if="task.file_id" text size="small" type="primary">
                  文件 {{ task.file_id }}
                </el-button>
              </div>
            </div>
          </article>
        </section>
      </div>
    </aside>
  </div>
</template>

<style scoped>
.agent-workbench {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr) 320px;
  gap: 18px;
  height: calc(100vh - var(--topbar-height) - 44px);
  min-height: calc(100vh - var(--topbar-height) - 44px);
  align-items: stretch;
}

.agent-sessions,
.agent-sidepanels {
  min-width: 0;
  min-height: 0;
}

.sessions-panel,
.sidepanel-stack,
.agent-chat-shell {
  min-height: 100%;
}

.sessions-panel {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.sessions-header,
.sidepanel-block {
  padding: 18px;
}

.sessions-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  border-bottom: 1px solid var(--border-subtle);
}

.sessions-header h2 {
  margin-top: 10px;
  font-size: 18px;
  font-weight: 700;
}

.sessions-list {
  flex: 1;
  overflow-y: auto;
  padding: 10px;
}

.session-item {
  width: 100%;
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 14px;
  margin-bottom: 8px;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  background: var(--bg-panel);
  text-align: left;
  cursor: pointer;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast), transform var(--transition-fast);
}

.session-item:hover {
  transform: translateY(-1px);
  border-color: var(--border-strong);
  box-shadow: var(--shadow-sm);
}

.session-item.active {
  background: linear-gradient(180deg, var(--bg-panel) 0%, var(--color-primary-bg) 100%);
  border-color: #b8cdf8;
}

.session-item-main {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.session-item-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-primary);
}

.session-item-time,
.session-item-summary {
  font-size: 12px;
  color: var(--text-tertiary);
}

.session-item-summary {
  line-height: 1.5;
}

.session-item-delete {
  position: absolute;
  top: 10px;
  right: 10px;
  opacity: 0;
  transition: opacity var(--transition-fast);
}

.session-item:hover .session-item-delete {
  opacity: 1;
}

.agent-center {
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.agent-hero {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(320px, 0.95fr);
  gap: 18px;
  padding: 22px;
}

.hero-main h1 {
  margin-top: 14px;
  font-size: 28px;
  line-height: 1.15;
  font-weight: 800;
  color: var(--text-primary);
}

.hero-main p {
  margin-top: 12px;
  font-size: 15px;
  line-height: 1.75;
  color: var(--text-secondary);
}

.hero-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 20px;
}

.hero-metrics {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.agent-chat-shell {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.chat-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 18px 20px 14px;
  border-bottom: 1px solid var(--border-subtle);
}

.chat-topbar-left {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.chat-topbar-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
}

.chat-topbar-subtitle {
  margin-top: 3px;
  font-size: 12px;
  color: var(--text-tertiary);
}

.chat-stream {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 20px;
  background: linear-gradient(180deg, #f8fafc 0%, #f3f6fb 100%);
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.welcome-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 22px;
  border: 1px dashed var(--border-strong);
  border-radius: var(--radius-xl);
  background: rgba(255, 255, 255, 0.88);
}

.welcome-panel-icon {
  width: 64px;
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 18px;
  background: linear-gradient(135deg, var(--color-primary-bg) 0%, #ede9fe 100%);
  color: var(--color-primary);
}

.welcome-panel-copy h3 {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
}

.welcome-panel-copy p {
  margin-top: 6px;
  color: var(--text-secondary);
  line-height: 1.7;
}

.welcome-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.welcome-action {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 10px;
  padding: 16px;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  background: var(--bg-panel);
  color: var(--text-primary);
  cursor: pointer;
  transition: transform var(--transition-fast), box-shadow var(--transition-fast), border-color var(--transition-fast);
}

.welcome-action:hover {
  transform: translateY(-2px);
  border-color: #bfd0e2;
  box-shadow: var(--shadow-sm);
}

.message-row {
  display: flex;
  gap: 12px;
  max-width: 92%;
}

.message-row.user {
  align-self: flex-end;
  flex-direction: row-reverse;
}

.message-avatar {
  width: 34px;
  height: 34px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  font-size: 12px;
  font-weight: 700;
}

.message-row.user .message-avatar {
  background: var(--color-primary);
  color: #fff;
}

.message-row.assistant .message-avatar {
  background: linear-gradient(135deg, var(--color-primary-bg) 0%, #ede9fe 100%);
  color: var(--color-primary);
}

.message-row.system .message-avatar {
  background: var(--color-warning-soft);
  color: var(--color-warning);
}

.message-stack {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.message-bubble {
  padding: 12px 15px;
  border-radius: 14px;
  line-height: 1.7;
  font-size: 14px;
}

.message-bubble.user {
  background: var(--color-primary);
  color: #fff;
  border-bottom-right-radius: 6px;
}

.message-bubble.assistant {
  background: var(--bg-panel);
  border: 1px solid var(--border-subtle);
  color: var(--text-primary);
  border-bottom-left-radius: 6px;
}

.message-bubble.system {
  background: #fff8e8;
  border: 1px solid #f6d78c;
  color: #7c4a03;
}

.message-content {
  white-space: pre-wrap;
  word-break: break-word;
}

.follow-up-options {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.follow-up-option-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 34px;
  padding: 0 14px;
  border: 1px solid #c8d7f7;
  border-radius: 999px;
  background: #eef4ff;
  color: var(--color-primary);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: transform var(--transition-fast), box-shadow var(--transition-fast), background var(--transition-fast);
}

.follow-up-option-chip:hover {
  transform: translateY(-1px);
  box-shadow: var(--shadow-sm);
  background: #e5efff;
}

.message-result-card,
.draft-panel {
  padding: 14px;
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-subtle);
  background: rgba(255, 255, 255, 0.96);
}

.result-card-header,
.draft-panel-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.result-card-kicker {
  display: block;
  margin-bottom: 4px;
  font-size: 11px;
  font-weight: 700;
  color: var(--text-tertiary);
  text-transform: uppercase;
}

.result-card-summary {
  margin-top: 10px;
  color: var(--text-secondary);
  line-height: 1.7;
}

.result-card-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 10px;
  font-size: 12px;
  color: var(--text-tertiary);
}

.result-pill {
  display: inline-flex;
  align-items: center;
  height: 24px;
  padding: 0 10px;
  border-radius: 999px;
  background: var(--bg-panel-muted);
  color: var(--text-secondary);
  font-size: 11px;
  font-weight: 700;
}

.draft-list {
  display: grid;
  gap: 10px;
  margin: 12px 0;
}

.draft-card {
  padding: 12px;
  border-radius: var(--radius-lg);
  background: var(--bg-panel-alt);
  border: 1px solid var(--border-subtle);
  cursor: pointer;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast), transform var(--transition-fast), background var(--transition-fast);
}

.draft-card:hover {
  transform: translateY(-1px);
  border-color: #bfd0e2;
  box-shadow: var(--shadow-sm);
}

.draft-card.selected {
  border-color: var(--color-primary);
  background: linear-gradient(180deg, #eef4ff 0%, #ffffff 100%);
}

.draft-card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}

.draft-card-tags {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.draft-selection {
  font-size: 11px;
  color: var(--text-tertiary);
}

.draft-check {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 42px;
  height: 24px;
  padding: 0 8px;
  border-radius: 999px;
  background: var(--bg-panel-muted);
  color: var(--text-tertiary);
  font-size: 11px;
  font-weight: 700;
}

.draft-check.active {
  background: var(--color-primary);
  color: #fff;
}

.draft-card strong {
  display: block;
  font-size: 14px;
  color: var(--text-primary);
}

.draft-card p {
  margin-top: 6px;
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
}

.recommendation-list {
  display: grid;
  gap: 10px;
  margin-top: 12px;
}

.recommendation-card {
  padding: 14px;
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-subtle);
  background: linear-gradient(180deg, rgba(247, 249, 255, 0.96), rgba(255, 255, 255, 0.98));
}

.recommendation-top,
.recommendation-actions,
.recommendation-tags {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.recommendation-top {
  justify-content: space-between;
}

.recommendation-card strong {
  display: block;
  margin-top: 10px;
  font-size: 14px;
}

.recommendation-card p {
  margin: 8px 0 10px;
  color: var(--text-secondary);
  line-height: 1.6;
}

.recommendation-score {
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 600;
}

.plan-banner {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-radius: var(--radius-lg);
  background: var(--color-primary-bg);
  color: var(--color-primary);
  font-size: 12px;
  font-weight: 600;
}

.plan-banner.success {
  background: var(--color-success-soft);
  color: var(--color-success);
}

.chat-input-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px 20px 18px;
  border-top: 1px solid var(--border-subtle);
  background: var(--bg-panel);
}

.chat-tool-btn {
  color: var(--text-secondary);
}

.chat-input {
  flex: 1;
}

.agent-sidepanels {
  min-width: 0;
  min-height: 0;
}

.sidepanel-stack {
  display: flex;
  flex-direction: column;
  gap: 18px;
  height: 100%;
  min-height: 0;
  overflow-y: auto;
  padding-right: 4px;
}

.sidepanel-block {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.sidepanel-grow {
  flex: 0 0 auto;
}

.panel-empty {
  font-size: 13px;
  color: var(--text-tertiary);
}

.suggestion-card {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  background: var(--bg-panel);
  color: var(--text-primary);
  cursor: pointer;
  text-align: left;
  transition: transform var(--transition-fast), border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.suggestion-card:hover {
  transform: translateY(-1px);
  box-shadow: var(--shadow-sm);
}

.suggestion-card.primary:hover {
  border-color: #bfd0e2;
}

.suggestion-card.success:hover {
  border-color: #b7e4c4;
}

.suggestion-card.warning:hover {
  border-color: #f2d191;
}

.suggestion-index {
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  background: var(--bg-panel-muted);
  color: var(--text-secondary);
  font-size: 11px;
  font-weight: 700;
  flex-shrink: 0;
}

.knowledge-box {
  display: flex;
  gap: 8px;
}

.knowledge-item,
.workspace-file,
.memory-summary,
.task-card {
  padding: 12px;
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-subtle);
  background: var(--bg-panel);
}

.knowledge-title,
.workspace-file-name {
  display: block;
  font-size: 13px;
  color: var(--text-primary);
}

.knowledge-meta,
.workspace-file-meta {
  display: block;
  margin-top: 4px;
  font-size: 11px;
  color: var(--text-tertiary);
}

.memory-summary {
  line-height: 1.7;
  color: var(--text-secondary);
  white-space: pre-wrap;
}

.task-card {
  display: flex;
  gap: 12px;
}

.task-indicator {
  width: 26px;
  height: 26px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: 2px;
}

.task-indicator.done {
  color: var(--color-success);
}

.task-indicator.running {
  color: var(--color-primary);
}

.task-indicator.failed {
  color: var(--color-danger);
}

.task-indicator.waiting_user {
  color: var(--color-warning);
}

.task-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--border-strong);
}

.task-body {
  min-width: 0;
}

.task-goal {
  font-size: 13px;
  color: var(--text-primary);
  line-height: 1.6;
}

.task-type-tag {
  margin-right: 4px;
  font-size: 10px !important;
  vertical-align: middle;
}

.task-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 4px;
}

.task-agent,
.task-retry {
  font-size: 11px;
  color: var(--text-tertiary);
}

.task-retry {
  color: var(--color-warning);
}

.task-error-block {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
}

.task-error-code {
  padding: 2px 7px;
  border-radius: 999px;
  background: var(--color-danger-soft);
  color: var(--color-danger);
  font-size: 10px;
  font-weight: 700;
}

.task-error-message {
  font-size: 11px;
  color: var(--color-danger);
}

.task-retry-btn {
  padding: 0 !important;
}

.task-links {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}

.mobile-overlay {
  display: none;
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.25);
  z-index: 40;
}

@media (max-width: 1280px) {
  .agent-workbench {
    grid-template-columns: 250px minmax(0, 1fr) 300px;
  }

  .agent-hero {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 1024px) {
  .agent-workbench {
    grid-template-columns: 1fr;
  }

  .agent-sessions,
  .agent-sidepanels {
    display: none;
  }
}

@media (max-width: 767px) {
  .mobile-overlay {
    display: block;
  }

  .agent-workbench {
    display: block;
    height: auto;
    min-height: 0;
  }

  .agent-sessions,
  .agent-sidepanels {
    display: block;
    position: fixed;
    top: 0;
    bottom: 0;
    width: min(84vw, 320px);
    z-index: 50;
    transform: translateX(-100%);
    transition: transform var(--transition-normal);
  }

  .agent-sessions {
    left: 0;
  }

  .agent-sidepanels {
    right: 0;
    transform: translateX(100%);
  }

  .agent-sessions.is-open {
    transform: translateX(0);
  }

  .agent-sidepanels.is-open {
    transform: translateX(0);
  }

  .sessions-panel,
  .sidepanel-stack {
    height: 100%;
    padding: 0;
    background: var(--bg-page);
  }

  .agent-chat-shell {
    min-height: calc(100vh - var(--topbar-height) - 44px);
  }

  .chat-stream {
    padding: 16px;
  }

  .welcome-grid {
    grid-template-columns: 1fr;
  }

  .message-row {
    max-width: 100%;
  }

  .chat-input-bar {
    padding: 12px 16px 16px;
  }
}
</style>
