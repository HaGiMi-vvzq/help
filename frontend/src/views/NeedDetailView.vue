<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { useNeedsStore } from '@/stores/needs'
import { useAgentStore } from '@/stores/agent'
import type { NeedApplication } from '@/types'
import { readDraft, removeDraft, writeDraft } from '@/utils/persistentDrafts'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const needsStore = useNeedsStore()
const agentStore = useAgentStore()

const applying = ref(false)
const drafting = ref(false)
const reviewLoading = ref<Record<number, 'accept' | 'reject' | ''>>({})
const applicationMessage = ref('')
const reviewReplies = ref<Record<number, string>>({})

const needId = computed(() => Number(route.params.id))
const need = computed(() => needsStore.currentNeed)
const isOwner = computed(() => need.value?.user_id === authStore.user?.id)
const myApplication = computed(() =>
  needsStore.myApplications.find((item) => item.need_id === needId.value) || null,
)
const selectedUsers = computed(() => new Set(need.value?.selected_user_ids || []))
const applicationDraftKey = computed(
  () => `need-application-draft:${authStore.user?.id || authStore.user?.username || 'anonymous'}:${needId.value}`,
)

onMounted(() => {
  void load()
})

watch(() => route.params.id, () => {
  void load()
})

async function load() {
  if (!needId.value) return
  await needsStore.fetchNeedDetail(needId.value)
  const cachedDraft = needsStore.consumeApplicationDraft(needId.value)
  if (cachedDraft) {
    applicationMessage.value = cachedDraft
    writeDraft(applicationDraftKey.value, cachedDraft)
  } else {
    applicationMessage.value = readDraft<string>(applicationDraftKey.value, applicationMessage.value)
  }
  if (isOwner.value) {
    await needsStore.fetchNeedApplications(needId.value)
  } else {
    await needsStore.fetchMyApplications()
    if (!applicationMessage.value && myApplication.value?.status === 'rejected') {
      applicationMessage.value = myApplication.value.message
    }
  }
}

async function handleApply() {
  if (!need.value) return
  applying.value = true
  try {
    await needsStore.applyToNeed(need.value.id, applicationMessage.value)
    removeDraft(applicationDraftKey.value)
    applicationMessage.value = ''
    ElMessage.success('申请已发送，发布者会在消息页继续沟通。')
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || error?.message || '申请失败')
  } finally {
    applying.value = false
  }
}

watch(applicationMessage, (value) => {
  if (!needId.value || isOwner.value) return
  if (value.trim()) {
    writeDraft(applicationDraftKey.value, value)
  } else {
    removeDraft(applicationDraftKey.value)
  }
})

async function handleDraftWithAgent() {
  if (!need.value || !authStore.user) return
  drafting.value = true
  try {
    const text = await agentStore.draftApplicationMessage({
      need_id: need.value.id,
      need_title: need.value.title,
      need_type: need.value.type,
      owner_name: need.value.username,
      user_skills: authStore.user.skill_tags || [],
      match_reason: `我的技能和该需求的方向比较贴合，尤其是 ${(need.value.req_tags || []).slice(0, 3).join('、') || '核心交付'}`,
    })
    applicationMessage.value = text
    ElMessage.success('Agent 已帮你起草申请消息')
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || error?.message || '起草失败')
  } finally {
    drafting.value = false
  }
}

async function handleReview(application: NeedApplication, accepted: boolean) {
  reviewLoading.value = { ...reviewLoading.value, [application.id]: accepted ? 'accept' : 'reject' }
  try {
    await needsStore.reviewApplication(application.id, accepted, reviewReplies.value[application.id])
    ElMessage.success(accepted ? '已接受申请' : '已拒绝申请')
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || error?.message || '处理失败')
  } finally {
    reviewLoading.value = { ...reviewLoading.value, [application.id]: '' }
  }
}

function goToConversation(application: NeedApplication) {
  router.push(`/messages/${application.applicant_user_id}?needId=${application.need_id}`)
}

function statusText(status?: string | null) {
  if (status === 'accepted') return '已接受'
  if (status === 'rejected') return '未通过'
  if (status === 'withdrawn') return '已撤回'
  return '待处理'
}

function canSubmitApplication() {
  return Boolean(need.value?.can_apply) || myApplication.value?.status === 'rejected'
}
</script>

<template>
  <div class="page-shell need-detail-page" v-loading="needsStore.loading">
    <div v-if="needsStore.loading" class="page-stack" style="min-height: 40vh" />
    <div v-else-if="!need" class="page-stack">
      <section class="surface-card empty-state" style="text-align: center; padding: 48px">
        <h2>需求不存在</h2>
        <p>该需求可能已被删除或链接无效。</p>
        <el-button type="primary" @click="router.push('/')">返回需求广场</el-button>
      </section>
    </div>
    <div v-else class="page-stack">
      <section class="detail-hero surface-card-strong">
        <div class="detail-hero-main">
          <div class="detail-badges">
            <el-tag size="small" type="primary" effect="plain">{{ need.type }}</el-tag>
            <span class="detail-status">{{ need.status }}</span>
            <span class="detail-meta">发布者 {{ need.username }}</span>
          </div>
          <h1>{{ need.title }}</h1>
          <p>{{ need.description }}</p>
          <div v-if="need.req_tags?.length" class="detail-tags">
            <el-tag v-for="tag in need.req_tags" :key="tag" size="small" effect="plain">{{ tag }}</el-tag>
          </div>
          <div class="detail-actions">
            <el-button v-if="isOwner" type="primary" @click="router.push(`/needs/${need.id}/matches`)">查看匹配结果</el-button>
            <el-button v-else type="primary" @click="router.push('/agent')">去 Agent 反向搜索更多需求</el-button>
            <el-button @click="router.push('/messages')">打开消息页</el-button>
          </div>
        </div>

        <div class="detail-summary">
          <div class="summary-item">
            <span class="summary-label">协作方式</span>
            <strong>{{ need.selection_mode === 'multi' ? '多人协作' : '单人补位' }}</strong>
          </div>
          <div class="summary-item">
            <span class="summary-label">申请人数</span>
            <strong>{{ need.application_count || 0 }}</strong>
          </div>
          <div class="summary-item">
            <span class="summary-label">当前状态</span>
            <strong>{{ need.status }}</strong>
          </div>
          <div class="summary-item">
            <span class="summary-label">已选候选人</span>
            <strong>{{ need.selected_user_ids?.length || 0 }}</strong>
          </div>
        </div>
      </section>

      <div class="detail-grid">
        <section v-if="!isOwner" class="surface-card detail-panel">
          <div class="panel-header">
            <div>
              <span class="eyebrow">Join Flow</span>
              <h2>申请加入</h2>
            </div>
            <el-tag v-if="myApplication" size="small" type="info" effect="plain">
              {{ statusText(myApplication.status) }}
            </el-tag>
          </div>

          <div v-if="myApplication" class="application-state">
            <strong>我的当前申请状态</strong>
            <p>{{ statusText(myApplication.status) }}</p>
            <p class="application-copy">{{ myApplication.message }}</p>
            <p v-if="myApplication.owner_reply" class="owner-reply">发布者回复：{{ myApplication.owner_reply }}</p>
          </div>

          <div class="application-form">
            <el-input
              v-model="applicationMessage"
              type="textarea"
              :rows="6"
              placeholder="介绍你能做什么、为什么适合这个需求，以及希望如何配合。"
            />
            <div class="application-actions">
              <el-button :loading="drafting" @click="handleDraftWithAgent">Agent 帮我起草</el-button>
              <el-button
                type="primary"
                :loading="applying"
                :disabled="!canSubmitApplication()"
                @click="handleApply"
              >
                申请加入
              </el-button>
            </div>
            <p class="application-hint">
              发送申请后，会自动建立与发布者的消息上下文，后续沟通可以直接在消息页继续。
            </p>
          </div>
        </section>

        <section v-else class="surface-card detail-panel">
          <div class="panel-header">
            <div>
              <span class="eyebrow">Owner Queue</span>
              <h2>收到的申请</h2>
            </div>
            <span class="panel-count">{{ needsStore.currentApplications.length }} 条</span>
          </div>

          <div v-if="needsStore.currentApplications.length === 0" class="panel-empty">
            还没有人申请。可以先去匹配结果页挑候选人，也可以把需求再优化得更具体一些。
          </div>

          <div v-else class="application-list">
            <article
              v-for="application in needsStore.currentApplications"
              :key="application.id"
              class="application-card"
              :class="{ selected: selectedUsers.has(application.applicant_user_id) }"
            >
              <div class="application-top">
                <div>
                  <strong>{{ application.applicant_username }}</strong>
                  <span class="application-status">{{ statusText(application.status) }}</span>
                </div>
                <el-button text size="small" @click="goToConversation(application)">打开消息</el-button>
              </div>

              <div v-if="application.applicant_skill_tags?.length" class="detail-tags compact">
                <el-tag
                  v-for="tag in application.applicant_skill_tags"
                  :key="`${application.id}-${tag}`"
                  size="small"
                  effect="plain"
                >
                  {{ tag }}
                </el-tag>
              </div>

              <p class="application-copy">{{ application.message }}</p>
              <p v-if="application.owner_reply" class="owner-reply">回复记录：{{ application.owner_reply }}</p>

              <div v-if="application.status === 'pending'" class="review-box">
                <el-input
                  v-model="reviewReplies[application.id]"
                  type="textarea"
                  :rows="3"
                  placeholder="给申请者留一句确认或反馈。"
                />
                <div class="review-actions">
                  <el-button
                    type="primary"
                    :loading="reviewLoading[application.id] === 'accept'"
                    @click="handleReview(application, true)"
                  >
                    接受
                  </el-button>
                  <el-button
                    :loading="reviewLoading[application.id] === 'reject'"
                    @click="handleReview(application, false)"
                  >
                    暂不合适
                  </el-button>
                </div>
              </div>
            </article>
          </div>
        </section>

        <section class="surface-card detail-panel secondary">
          <div class="panel-header">
            <div>
              <span class="eyebrow">Collaboration Notes</span>
              <h2>这条需求现在适合怎么推进</h2>
            </div>
          </div>
          <ul class="detail-notes">
            <li>如果你是参与者，先用 Agent 起草一句自荐，再发出申请会更稳。</li>
            <li>如果你是发布者，先看申请质量，再去匹配结果页比较系统推荐的人选。</li>
            <li>一旦接受申请，消息页会自动接住后续分工和时间沟通。</li>
          </ul>
        </section>
      </div>
    </div>
  </div>
</template>

<style scoped>
.need-detail-page {
  padding-bottom: 40px;
}

.detail-hero {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) 320px;
  gap: 20px;
  padding: 28px;
}

.detail-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.detail-status,
.detail-meta,
.panel-count {
  color: var(--text-secondary);
  font-size: 13px;
}

.detail-hero-main h1 {
  margin: 14px 0 12px;
  font-size: 34px;
  line-height: 1.1;
}

.detail-hero-main p {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.7;
}

.detail-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 16px;
}

.detail-tags.compact {
  margin-top: 10px;
}

.detail-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 20px;
}

.detail-summary {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.summary-item {
  border: 1px solid var(--border-subtle);
  border-radius: 12px;
  padding: 16px;
  background: var(--bg-panel-muted);
}

.summary-label {
  display: block;
  margin-bottom: 10px;
  color: var(--text-secondary);
  font-size: 13px;
}

.summary-item strong {
  font-size: 18px;
  color: var(--text-primary);
}

.detail-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(300px, 0.9fr);
  gap: 20px;
}

.detail-panel {
  padding: 22px;
}

.detail-panel.secondary {
  align-self: start;
}

.panel-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 18px;
}

.panel-header h2 {
  margin: 6px 0 0;
  font-size: 22px;
}

.application-form,
.application-state,
.review-box {
  display: grid;
  gap: 14px;
}

.application-actions,
.review-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.application-hint,
.panel-empty,
.owner-reply,
.application-copy,
.detail-notes {
  color: var(--text-secondary);
  line-height: 1.7;
}

.application-list {
  display: grid;
  gap: 14px;
}

.application-card {
  border: 1px solid var(--border-subtle);
  border-radius: 12px;
  padding: 16px;
  background: rgba(255, 255, 255, 0.82);
}

.application-card.selected {
  border-color: rgba(41, 98, 255, 0.22);
  box-shadow: 0 14px 36px rgba(41, 98, 255, 0.12);
}

.application-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.application-top strong {
  margin-right: 10px;
}

.application-status {
  color: var(--text-secondary);
  font-size: 13px;
}

.detail-notes {
  margin: 0;
  padding-left: 18px;
}

@media (max-width: 1100px) {
  .detail-hero,
  .detail-grid {
    grid-template-columns: 1fr;
  }
}
</style>
