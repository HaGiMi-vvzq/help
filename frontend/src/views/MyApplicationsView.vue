<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useNeedsStore } from '@/stores/needs'

const router = useRouter()
const needsStore = useNeedsStore()
const filter = ref<'all' | 'pending' | 'accepted' | 'rejected'>('all')

onMounted(() => {
  void needsStore.fetchMyApplications()
})

const filteredApplications = computed(() => {
  if (filter.value === 'all') return needsStore.myApplications
  return needsStore.myApplications.filter((item) => item.status === filter.value)
})

function statusTone(status: string) {
  if (status === 'accepted') return 'success'
  if (status === 'rejected') return 'danger'
  return 'warning'
}

function statusText(status: string) {
  if (status === 'accepted') return '已接受'
  if (status === 'rejected') return '未通过'
  return '待处理'
}

function goToNeed(needId: number) {
  router.push(`/needs/${needId}`)
}
</script>

<template>
  <div class="page-shell my-applications-page" v-loading="needsStore.loading">
    <div class="page-stack">
      <section class="surface-card-strong applications-hero">
        <div>
          <span class="eyebrow">Participant Flow</span>
          <h1>我的申请</h1>
          <p>从参与者视角跟进你已经投出的申请，快速判断下一步是补充说明、继续沟通，还是回到详情页重新申请。</p>
        </div>
        <div class="hero-metrics">
          <div class="metric-card">
            <span class="metric-value">{{ needsStore.myApplications.length }}</span>
            <span class="metric-label">总申请数</span>
          </div>
          <div class="metric-card">
            <span class="metric-value">{{ needsStore.myApplications.filter((item) => item.status === 'accepted').length }}</span>
            <span class="metric-label">已接受</span>
          </div>
          <div class="metric-card">
            <span class="metric-value">{{ needsStore.myApplications.filter((item) => item.status === 'pending').length }}</span>
            <span class="metric-label">待处理</span>
          </div>
        </div>
      </section>

      <section class="surface-card applications-toolbar">
        <div>
          <div class="toolbar-title">申请状态</div>
          <div class="toolbar-subtitle">切换查看待处理、已接受和未通过的需求申请。</div>
        </div>
        <el-radio-group v-model="filter" class="application-status-filter" size="small">
          <el-radio-button value="all">全部</el-radio-button>
          <el-radio-button value="pending">待处理</el-radio-button>
          <el-radio-button value="accepted">已接受</el-radio-button>
          <el-radio-button value="rejected">未通过</el-radio-button>
        </el-radio-group>
      </section>

      <section class="applications-list">
        <div v-if="filteredApplications.length === 0" class="surface-card empty-state">
          <p>当前筛选下还没有申请记录。可以去需求广场继续浏览开放需求，或者让 Agent 反向帮你找项目。</p>
          <div class="empty-actions">
            <el-button type="primary" @click="router.push('/')">去需求广场</el-button>
            <el-button @click="router.push('/agent')">打开 Agent</el-button>
          </div>
        </div>

        <article
          v-for="application in filteredApplications"
          :key="application.id"
          class="surface-card application-record"
        >
          <div class="record-top">
            <div>
              <strong class="record-title">{{ application.need_title || `需求 #${application.need_id}` }}</strong>
              <div class="record-meta">发布者：{{ application.owner_username || '未知' }}</div>
            </div>
            <el-tag :type="statusTone(application.status)" effect="plain">{{ statusText(application.status) }}</el-tag>
          </div>

          <p class="record-copy">{{ application.message }}</p>
          <p v-if="application.owner_reply" class="record-reply">最新回复：{{ application.owner_reply }}</p>

          <div class="record-footer">
            <span class="record-time">最近更新 {{ application.updated_at.slice(5, 16) }}</span>
            <div class="record-actions">
              <el-button size="small" @click="goToNeed(application.need_id)">查看需求详情</el-button>
              <el-button
                v-if="application.owner_user_id"
                size="small"
                type="primary"
                @click="router.push(`/messages/${application.owner_user_id}?needId=${application.need_id}`)"
              >
                去沟通
              </el-button>
            </div>
          </div>
        </article>
      </section>
    </div>
  </div>
</template>

<style scoped>
.my-applications-page {
  padding-bottom: 40px;
}

.applications-hero {
  display: grid;
  grid-template-columns: minmax(0, 1.3fr) minmax(280px, 0.9fr);
  gap: 20px;
  padding: 26px;
}

.applications-hero h1 {
  margin: 14px 0 10px;
  font-size: 32px;
}

.applications-hero p,
.toolbar-subtitle,
.record-copy,
.record-reply,
.record-time,
.record-meta {
  color: var(--text-secondary);
  line-height: 1.7;
}

.hero-metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.metric-card {
  display: flex;
  flex-direction: column;
  justify-content: center;
  min-height: 110px;
  padding: 16px;
  border-radius: 12px;
  border: 1px solid var(--border-subtle);
  background: rgba(255, 255, 255, 0.82);
}

.metric-value {
  font-size: 26px;
  font-weight: 800;
  color: var(--text-primary);
}

.metric-label {
  margin-top: 8px;
  font-size: 13px;
  color: var(--text-secondary);
}

.applications-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.toolbar-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
}

.applications-list {
  display: grid;
  gap: 14px;
}

.application-record {
  display: grid;
  gap: 14px;
}

.record-top,
.record-footer {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.record-title {
  font-size: 18px;
  color: var(--text-primary);
}

.record-actions,
.empty-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

@media (max-width: 960px) {
  .applications-hero,
  .applications-toolbar,
  .record-top,
  .record-footer {
    grid-template-columns: 1fr;
    flex-direction: column;
  }

  .hero-metrics {
    grid-template-columns: 1fr;
  }
}
</style>
