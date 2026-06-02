<script setup lang="ts">
import { computed, defineAsyncComponent, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useNeedsStore } from '@/stores/needs'
import * as agentApi from '@/api/agent'
import * as needsApi from '@/api/needs'
import * as messagesApi from '@/api/messages'
import { readDraft, writeDraft } from '@/utils/persistentDrafts'
import { useAuthStore } from '@/stores/auth'

const ConciergeChat = defineAsyncComponent(() => import('@/components/chat/ConciergeChat.vue'))

const route = useRoute()
const router = useRouter()
const store = useNeedsStore()
const authStore = useAuthStore()
const needId = Number(route.params.id)
const matchDraftKey = `match-message-drafts:${authStore.user?.id || authStore.user?.username || 'anonymous'}:${needId}`

const streaming = ref(false)
const chatVisible = ref(false)
const selectedUserIds = ref<number[]>([])
const selecting = ref(false)
const draftingMsg = ref<number | null>(null)
const sendingDraftMsg = ref<number | null>(null)
const draftMessages = ref<Record<number, string>>(readDraft<Record<number, string>>(matchDraftKey, {}))

let eventSource: EventSource | null = null

const isSingleMode = computed(() => store.currentNeed?.selection_mode === 'single')
const avgScore = computed(() => {
  if (!store.matches.length) return 0
  const total = store.matches.reduce((sum, match) => sum + match.score, 0)
  return Math.round(total / store.matches.length)
})
const topCandidate = computed(() => store.matches[0])
const applicationRows = computed(() =>
  store.currentApplications.map((application) => ({
    application,
    relatedMatch: store.matches.find((match) => match.user_id === application.applicant_user_id) || null,
    isSelected: selectedUserIds.value.includes(application.applicant_user_id),
  })),
)

const stageDefs = [
  { key: 'tag_extraction', label: '标签提取', icon: 'Collection' },
  { key: 'semantic_search', label: '语义搜索', icon: 'Search' },
  { key: 'rerank', label: 'AI 精排', icon: 'TrendCharts' },
  { key: 'done', label: '匹配完成', icon: 'CircleCheck' },
] as const

const currentStage = computed(() => {
  const last = store.matchProgress[store.matchProgress.length - 1]
  return last?.stage || 'tag_extraction'
})

const currentStageIdx = computed(() => stageDefs.findIndex((stage) => stage.key === currentStage.value))

const stageMessages = computed(() => {
  const map: Record<string, string> = {}
  for (const progress of store.matchProgress) map[progress.stage] = progress.message
  return map
})

onMounted(async () => {
  try {
    await store.fetchNeedApplications(needId)
  } catch {
    // ignore
  }
  try {
    const result = await store.fetchMatches(needId)
    if ((!result?.matches?.length) && result?.matching_active) {
      startStream()
    }
  } catch {
    startStream()
  }
})

onUnmounted(() => {
  if (eventSource) eventSource.close()
})

watch(
  () => store.currentNeed?.selected_user_ids,
  (ids) => {
    selectedUserIds.value = ids || []
  },
  { immediate: true },
)

watch(
  () => store.matches.length,
  (count) => {
    if (count > 0) {
      streaming.value = false
      if (eventSource) {
        eventSource.close()
        eventSource = null
      }
    }
  },
)

watch(
  () => store.matchProgress[store.matchProgress.length - 1]?.stage,
  (stage) => {
    if (stage === 'done' || stage === 'error') {
      streaming.value = false
      if (eventSource) {
        eventSource.close()
        eventSource = null
      }
    }
  },
)

watch(draftMessages, (drafts) => {
  writeDraft(matchDraftKey, drafts)
}, { deep: true })

function startStream() {
  streaming.value = true
  store.matchProgress = []
  store.matches = []
  eventSource = store.streamMatches(needId)
}

async function handleRefresh() {
  streaming.value = false
  if (eventSource) eventSource.close()
  await store.refreshMatches(needId)
}

function handleContact(userId: number) {
  store.logBehavior('contact_click', { target_user_id: userId, need_id: needId })
  router.push(`/messages/${userId}?needId=${needId}`)
}

async function handleSelect(userId: number) {
  selecting.value = true
  try {
    const { data } = await needsApi.selectUsers(needId, [userId])
    selectedUserIds.value = data.selected_user_ids || []
    store.currentNeed = data
    ElMessage.success(data.status === '已匹配' ? '已选定，需求自动关闭' : '已选择')
  } catch (error: any) {
    ElMessage.error('操作失败: ' + (error?.response?.data?.detail || error?.message || ''))
  } finally {
    selecting.value = false
  }
}

async function handleDeselect(userId: number) {
  selecting.value = true
  try {
    const { data } = await needsApi.deselectUser(needId, userId)
    selectedUserIds.value = data.selected_user_ids || []
    store.currentNeed = data
    ElMessage.success('已取消选择')
  } catch (error: any) {
    ElMessage.error('操作失败: ' + (error?.response?.data?.detail || error?.message || ''))
  } finally {
    selecting.value = false
  }
}

async function handleDraftMessage(match: { user_id: number; username: string; skill_tags: string[]; reason: string }) {
  if (!store.currentNeed) return
  draftingMsg.value = match.user_id
  try {
    const { data } = await agentApi.draftMessage({
      need_title: store.currentNeed.title,
      match_name: match.username,
      match_skills: match.skill_tags,
      match_reason: match.reason,
    })
    draftMessages.value[match.user_id] = data.message
    ElMessage.success('私信草稿已生成')
  } catch {
    ElMessage.error('生成失败，请重试')
  } finally {
    draftingMsg.value = null
  }
}

async function handleSendDraft(match: { user_id: number; username: string }) {
  const draft = (draftMessages.value[match.user_id] || '').trim()
  if (!draft) {
    ElMessage.warning('请先生成私信草稿')
    return
  }
  sendingDraftMsg.value = match.user_id
  try {
    await messagesApi.sendMessage({
      need_id: needId,
      receiver_id: match.user_id,
      content: draft,
    })
    const nextDrafts = { ...draftMessages.value }
    delete nextDrafts[match.user_id]
    draftMessages.value = nextDrafts
    ElMessage.success(`已发送给 ${match.username}`)
    router.push(`/messages/${match.user_id}?needId=${needId}`)
  } catch (error: any) {
    ElMessage.error('发送失败: ' + (error?.response?.data?.detail || error?.message || '未知错误'))
  } finally {
    sendingDraftMsg.value = null
  }
}

function scoreHex(score: number) {
  if (score >= 85) return '#16a34a'
  if (score >= 70) return '#d97706'
  return '#64748b'
}

function matchRowClassName({ rowIndex }: { rowIndex: number }) {
  return rowIndex === 0 ? 'top-row' : ''
}
</script>

<template>
  <div class="page-shell-narrow match-page" v-loading="store.loading && !streaming">
    <div class="page-stack">
      <button type="button" class="back-link" @click="router.push('/')">
        <el-icon :size="14"><ArrowLeft /></el-icon>
        返回需求广场
      </button>

      <section v-if="store.currentNeed" class="surface-card-strong result-hero">
        <div class="result-hero-main">
          <span class="eyebrow">结果决策台</span>
          <h1>{{ store.currentNeed.title }}</h1>
          <p>{{ store.currentNeed.description }}</p>
          <div v-if="store.currentNeed.req_tags?.length" class="result-tags">
            <el-tag v-for="tag in store.currentNeed.req_tags" :key="tag" size="small" effect="plain">{{ tag }}</el-tag>
          </div>
        </div>
        <div class="result-hero-side">
          <el-tag
            :type="store.currentNeed.type === '求助' ? 'danger' : store.currentNeed.type === '组队' ? 'primary' : 'success'"
            size="large"
          >
            {{ store.currentNeed.type }}
          </el-tag>
          <div class="hero-side-note">
            当前模式：{{ store.currentNeed.selection_mode === 'single' ? '单人选择' : '多人参与' }}
          </div>
        </div>
      </section>

      <section v-if="streaming && store.matchProgress.length > 0" class="surface-card progress-panel">
        <div class="progress-steps">
          <div
            v-for="(stage, index) in stageDefs"
            :key="stage.key"
            class="progress-step"
            :class="{ 'is-done': currentStageIdx > index, 'is-active': currentStageIdx === index }"
          >
            <div class="step-indicator">
              <el-icon v-if="currentStageIdx > index" :size="15"><CircleCheck /></el-icon>
              <el-icon v-else-if="currentStageIdx === index" :size="15"><Loading /></el-icon>
              <span v-else>{{ index + 1 }}</span>
            </div>
            <div class="step-copy">
              <strong>{{ stage.label }}</strong>
              <span v-if="stageMessages[stage.key]">{{ stageMessages[stage.key] }}</span>
            </div>
          </div>
        </div>
      </section>

      <section v-if="store.matches.length > 0" class="result-overview">
        <div class="metric-card">
          <div class="metric-icon" style="background: var(--color-primary-bg); color: var(--color-primary)">
            <el-icon :size="20"><UserFilled /></el-icon>
          </div>
          <div>
            <span class="metric-value">{{ store.matches.length }}</span>
            <span class="metric-label">候选人数</span>
          </div>
        </div>
        <div class="metric-card">
          <div class="metric-icon" style="background: var(--color-success-soft); color: var(--color-success)">
            <el-icon :size="20"><TrendCharts /></el-icon>
          </div>
          <div>
            <span class="metric-value">{{ avgScore }}%</span>
            <span class="metric-label">平均匹配度</span>
          </div>
        </div>
        <div class="metric-card">
          <div class="metric-icon" style="background: var(--color-warning-soft); color: var(--color-warning)">
            <el-icon :size="20"><Medal /></el-icon>
          </div>
          <div>
            <span class="metric-value">{{ topCandidate?.username || '-' }}</span>
            <span class="metric-label">推荐首选</span>
          </div>
        </div>
      </section>

      <section
        v-if="applicationRows.length > 0"
        class="surface-card application-comparison-board"
      >
        <div class="surface-section-title comparison-header">
          <div>
            <span class="eyebrow">Dual Funnel</span>
            <h2>收到的主动申请</h2>
          </div>
          <span class="comparison-hint">把主动报名者和系统推荐候选人放在同一视图里看，更容易做最终决策。</span>
        </div>

        <div class="application-comparison-grid">
          <div class="applicant-column">
            <strong class="column-title">主动申请者</strong>
            <article
              v-for="row in applicationRows"
              :key="row.application.id"
              class="application-compare-card"
              :class="{ selected: row.isSelected }"
            >
              <div class="compare-card-top">
                <div>
                  <strong>{{ row.application.applicant_username }}</strong>
                  <div class="compare-subtitle">{{ row.application.status }} · {{ row.application.updated_at.slice(5, 16) }}</div>
                </div>
                <el-tag size="small" :type="row.relatedMatch ? 'success' : 'warning'" effect="plain">
                  {{ row.relatedMatch ? '系统也推荐了 TA' : '仅主动申请' }}
                </el-tag>
              </div>

              <div v-if="row.application.applicant_skill_tags?.length" class="cell-tags">
                <el-tag
                  v-for="tag in row.application.applicant_skill_tags.slice(0, 5)"
                  :key="`${row.application.id}-${tag}`"
                  size="small"
                  effect="plain"
                >
                  {{ tag }}
                </el-tag>
              </div>

              <p class="compare-copy">{{ row.application.message }}</p>

              <div v-if="row.relatedMatch" class="compare-match-meta">
                <span>系统匹配分：{{ row.relatedMatch.score }}%</span>
                <span class="cell-reason">{{ row.relatedMatch.reason }}</span>
              </div>

              <div class="candidate-actions">
                <el-button
                  v-if="!row.isSelected"
                  :disabled="selecting || (isSingleMode && selectedUserIds.length >= 1)"
                  type="primary"
                  size="small"
                  @click="handleSelect(row.application.applicant_user_id)"
                >
                  选定 TA
                </el-button>
                <el-button v-else type="success" size="small" :disabled="selecting" @click="handleDeselect(row.application.applicant_user_id)">
                  已选择
                </el-button>
                <el-button size="small" @click="handleContact(row.application.applicant_user_id)">去沟通</el-button>
              </div>
            </article>
          </div>

          <div class="applicant-column">
            <strong class="column-title">系统推荐但尚未申请</strong>
            <article
              v-for="match in store.matches.filter((item) => !store.currentApplications.some((app) => app.applicant_user_id === item.user_id)).slice(0, 4)"
              :key="match.user_id"
              class="application-compare-card"
            >
              <div class="compare-card-top">
                <div>
                  <strong>{{ match.username }}</strong>
                  <div class="compare-subtitle">{{ match.school || '未填写学校' }}</div>
                </div>
                <el-tag size="small" type="info" effect="plain">{{ match.score }}%</el-tag>
              </div>
              <div class="cell-tags">
                <el-tag v-for="tag in match.skill_tags.slice(0, 5)" :key="`${match.user_id}-${tag}`" size="small" effect="plain">
                  {{ tag }}
                </el-tag>
              </div>
              <p class="compare-copy">{{ match.reason }}</p>
              <div class="candidate-actions">
                <el-button size="small" type="primary" @click="handleSelect(match.user_id)">选定 TA</el-button>
                <el-button size="small" @click="handleDraftMessage(match)">起草私信</el-button>
              </div>
            </article>
          </div>
        </div>
      </section>

      <section v-if="store.matches.length > 0" class="surface-card comparison-section comparison-table">
        <div class="surface-section-title comparison-header">
          <div>
            <span class="eyebrow">快速对比</span>
            <h2>候选人对比表</h2>
          </div>
          <span class="comparison-hint">优先扫读分数、技能和推荐理由</span>
        </div>

        <el-table :data="store.matches" size="small" class="match-table" :row-class-name="matchRowClassName">
          <el-table-column label="候选人" min-width="120">
            <template #default="{ row, $index }">
              <div class="cell-user">
                <span class="cell-rank">{{ $index === 0 ? 'TOP' : `#${$index + 1}` }}</span>
                <div>
                  <strong>{{ row.username }}</strong>
                  <div class="cell-sub">{{ row.school || '未填写学校' }}</div>
                </div>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="匹配度" width="90" sortable :sort-method="(a: any, b: any) => a.score - b.score">
            <template #default="{ row }">
              <span class="cell-score" :style="{ color: scoreHex(row.score) }">{{ row.score }}%</span>
            </template>
          </el-table-column>
          <el-table-column label="技能" min-width="160">
            <template #default="{ row }">
              <div class="cell-tags">
                <el-tag v-for="tag in row.skill_tags?.slice(0, 4)" :key="tag" size="small" effect="plain">{{ tag }}</el-tag>
                <el-tag v-if="row.skill_tags?.length > 4" size="small" effect="plain">+{{ row.skill_tags.length - 4 }}</el-tag>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="推荐理由" min-width="220">
            <template #default="{ row }">
              <span class="cell-reason">{{ row.reason }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="170" fixed="right">
            <template #default="{ row }">
              <div class="cell-actions">
                <el-button
                  v-if="!selectedUserIds.includes(row.user_id)"
                  :disabled="selecting || (isSingleMode && selectedUserIds.length >= 1)"
                  type="primary"
                  size="small"
                  @click="handleSelect(row.user_id)"
                >
                  {{ isSingleMode ? '选定 TA' : '加入选择' }}
                </el-button>
                <el-button v-else type="success" size="small" :disabled="selecting" @click="handleDeselect(row.user_id)">
                  已选择
                </el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </section>

      <section v-if="store.matches.length > 0" class="candidate-section">
        <div class="surface-section-title">
          <div>
            <span class="eyebrow">详细判断</span>
            <h2>候选人卡片</h2>
          </div>
        </div>
        <div class="candidate-list">
          <article v-for="(match, index) in store.matches" :key="match.user_id" class="surface-card-strong candidate-card">
            <div class="candidate-header">
              <div class="candidate-identity">
                <span class="candidate-rank">{{ index === 0 ? 'TOP 1' : `#${index + 1}` }}</span>
                <div>
                  <div class="candidate-name">{{ match.username }}</div>
                  <div class="candidate-school">{{ match.school || '未填写学校' }}</div>
                </div>
              </div>
              <div class="candidate-score" :style="{ background: scoreHex(match.score) }">{{ match.score }}%</div>
            </div>

            <div class="candidate-progress">
              <div class="candidate-progress-fill" :style="{ width: `${match.score}%`, background: scoreHex(match.score) }" />
            </div>

            <blockquote class="candidate-reason">
              <el-icon :size="14"><ChatDotSquare /></el-icon>
              <span>{{ match.reason }}</span>
            </blockquote>

            <div v-if="match.skill_tags?.length" class="candidate-tags">
              <el-tag v-for="tag in match.skill_tags.slice(0, 8)" :key="tag" size="small" effect="plain">{{ tag }}</el-tag>
            </div>

            <div v-if="draftMessages[match.user_id]" class="candidate-draft">
              <div class="draft-head">
                <el-icon :size="14"><EditPen /></el-icon>
                <strong>AI 起草私信</strong>
              </div>
              <p>{{ draftMessages[match.user_id] }}</p>
              <div class="draft-actions">
                <el-button
                  type="primary"
                  size="small"
                  :loading="sendingDraftMsg === match.user_id"
                  @click="handleSendDraft(match)"
                >
                  发送草稿
                </el-button>
              </div>
            </div>

            <div class="candidate-actions">
              <el-button
                v-if="!selectedUserIds.includes(match.user_id)"
                :disabled="selecting || (isSingleMode && selectedUserIds.length >= 1)"
                type="primary"
                @click="handleSelect(match.user_id)"
              >
                {{ isSingleMode ? '选定此人' : '加入选择' }}
              </el-button>
              <el-button v-else type="success" :disabled="selecting" @click="handleDeselect(match.user_id)">
                <el-icon :size="14"><Check /></el-icon>
                已选择
              </el-button>
              <el-button @click="handleContact(match.user_id)">联系 TA</el-button>
              <el-button text type="primary" :loading="draftingMsg === match.user_id" @click="handleDraftMessage(match)">
                <el-icon :size="14"><EditPen /></el-icon>
                {{ draftMessages[match.user_id] ? '重新起草' : '起草私信' }}
              </el-button>
              <el-button
                v-if="draftMessages[match.user_id]"
                text
                type="success"
                :loading="sendingDraftMsg === match.user_id"
                @click="handleSendDraft(match)"
              >
                发送草稿
              </el-button>
            </div>
          </article>
        </div>
      </section>

      <section v-if="!store.loading && !streaming && store.matches.length === 0" class="empty-state surface-card-strong">
        <el-icon :size="48" style="color: var(--text-muted)"><Search /></el-icon>
        <p>暂无匹配结果。可以重新匹配，或进入 AI 追问进一步细化需求。</p>
        <div style="display: flex; gap: 10px; flex-wrap: wrap; justify-content: center">
          <el-button type="primary" @click="handleRefresh">重新匹配</el-button>
          <el-button @click="chatVisible = true">AI 继续追问</el-button>
        </div>
      </section>

      <div v-if="store.matches.length > 0" class="bottom-bar">
        <el-button :loading="store.loading" @click="handleRefresh">刷新匹配</el-button>
        <el-button type="primary" @click="chatVisible = true">AI 追问细化</el-button>
      </div>
    </div>

    <ConciergeChat
      v-if="store.currentNeed"
      :visible="chatVisible"
      :need-id="needId"
      :need-title="store.currentNeed.title"
      :need-description="store.currentNeed.description"
      :need-tags="store.currentNeed.req_tags || []"
      @update:visible="chatVisible = $event"
    />
  </div>
</template>

<style scoped>
.match-page {
  padding-bottom: 12px;
}

.back-link {
  width: fit-content;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 0;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 14px;
}

.back-link:hover {
  color: var(--color-primary);
}

.result-hero {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  padding: 24px;
}

.result-hero-main h1 {
  margin-top: 14px;
  font-size: 28px;
  line-height: 1.15;
  font-weight: 800;
  color: var(--text-primary);
}

.result-hero-main p {
  margin-top: 10px;
  font-size: 15px;
  line-height: 1.75;
  color: var(--text-secondary);
}

.result-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 14px;
}

.result-hero-side {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 12px;
  flex-shrink: 0;
}

.hero-side-note {
  padding: 10px 12px;
  border-radius: var(--radius-lg);
  background: var(--bg-panel-alt);
  color: var(--text-secondary);
  font-size: 12px;
  border: 1px solid var(--border-subtle);
}

.progress-panel {
  padding: 18px 20px;
}

.progress-steps {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.progress-step {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px;
  border-radius: var(--radius-lg);
  background: var(--bg-panel-alt);
  border: 1px solid var(--border-subtle);
}

.progress-step.is-active {
  border-color: #bfd0e2;
  background: var(--color-primary-bg);
}

.progress-step.is-done {
  border-color: #b7e4c4;
  background: #f2fbf4;
}

.step-indicator {
  width: 28px;
  height: 28px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: var(--bg-panel);
  border: 1px solid var(--border-soft);
  font-size: 12px;
  font-weight: 700;
}

.step-copy {
  min-width: 0;
}

.step-copy strong {
  display: block;
  font-size: 13px;
  color: var(--text-primary);
}

.step-copy span {
  display: block;
  margin-top: 3px;
  font-size: 11px;
  color: var(--text-tertiary);
  line-height: 1.5;
}

.result-overview {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.application-comparison-board {
  padding: 18px 20px;
}

.application-comparison-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.applicant-column {
  display: grid;
  gap: 12px;
}

.column-title {
  font-size: 15px;
  color: var(--text-primary);
}

.application-compare-card {
  display: grid;
  gap: 12px;
  padding: 14px;
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-subtle);
  background: rgba(255, 255, 255, 0.92);
}

.application-compare-card.selected {
  border-color: rgba(34, 197, 94, 0.28);
  box-shadow: 0 14px 28px rgba(34, 197, 94, 0.12);
}

.compare-card-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.compare-subtitle,
.compare-copy,
.compare-match-meta {
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.6;
}

.compare-match-meta {
  display: grid;
  gap: 6px;
}

.comparison-section {
  padding: 18px 20px;
}

.comparison-header {
  margin-bottom: 12px;
}

.comparison-hint {
  font-size: 12px;
  color: var(--text-tertiary);
}

.match-table :deep(.top-row) {
  background: var(--color-primary-bg);
}

.cell-user {
  display: flex;
  align-items: center;
  gap: 10px;
}

.cell-rank {
  min-width: 36px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 24px;
  border-radius: 999px;
  background: var(--bg-panel-muted);
  color: var(--text-secondary);
  font-size: 10px;
  font-weight: 800;
}

.cell-sub {
  margin-top: 2px;
  font-size: 11px;
  color: var(--text-tertiary);
}

.cell-score {
  font-size: 15px;
  font-weight: 800;
}

.cell-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.cell-reason {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
  font-size: 12px;
  line-height: 1.55;
  color: var(--text-secondary);
}

.candidate-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.candidate-card {
  padding: 20px 22px;
}

.candidate-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.candidate-identity {
  display: flex;
  align-items: center;
  gap: 12px;
}

.candidate-rank {
  min-width: 58px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 28px;
  border-radius: 999px;
  background: var(--bg-panel-muted);
  color: var(--text-secondary);
  font-size: 11px;
  font-weight: 800;
}

.candidate-name {
  font-size: 17px;
  font-weight: 700;
  color: var(--text-primary);
}

.candidate-school {
  margin-top: 2px;
  font-size: 12px;
  color: var(--text-secondary);
}

.candidate-score {
  min-width: 86px;
  height: 40px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  color: #fff;
  font-size: 18px;
  font-weight: 800;
}

.candidate-progress {
  margin: 14px 0;
  height: 8px;
  border-radius: 999px;
  background: var(--bg-panel-muted);
  overflow: hidden;
}

.candidate-progress-fill {
  height: 100%;
  border-radius: 999px;
}

.candidate-reason {
  display: flex;
  gap: 8px;
  margin: 0;
  padding: 12px 14px;
  border-radius: var(--radius-lg);
  background: var(--bg-panel-alt);
  color: var(--text-secondary);
  line-height: 1.7;
  border-left: 3px solid var(--color-primary);
}

.candidate-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 14px;
}

.candidate-draft {
  margin-top: 14px;
  padding: 14px;
  border-radius: var(--radius-lg);
  background: var(--color-primary-bg);
  border: 1px solid #bfd0e2;
}

.draft-head {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--color-primary);
  font-size: 12px;
  font-weight: 700;
}

.candidate-draft p {
  margin-top: 8px;
  color: var(--text-primary);
  line-height: 1.6;
}

.draft-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 10px;
}

.candidate-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 16px;
}

.bottom-bar {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

@media (max-width: 1024px) {
  .progress-steps,
  .result-overview,
  .application-comparison-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 767px) {
  .result-hero {
    flex-direction: column;
  }

  .result-hero-side {
    align-items: flex-start;
  }

  .candidate-header,
  .candidate-actions {
    align-items: stretch;
    flex-direction: column;
  }

  .candidate-score {
    width: fit-content;
  }
}
</style>
