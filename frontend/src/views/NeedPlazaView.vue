<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Plus } from '@element-plus/icons-vue'
import { useNeedsStore } from '@/stores/needs'
import type { Need } from '@/types'

const router = useRouter()
const store = useNeedsStore()

const filterType = ref('')
const page = ref(1)
const pageSize = 20

const totalPages = computed(() => Math.ceil(store.total / pageSize))
const openCount = computed(() => store.needs.filter((item) => item.status === '开放').length)
const teamCount = computed(() => store.needs.filter((item) => item.type === '组队').length)
const featuredNeed = computed(() =>
  store.needs.find((item) => item.username === 'alice' || item.title.includes('数据可视化')) || store.needs[0] || null,
)
const latestDate = computed(() => {
  const latest = store.needs[0]?.created_at
  return latest ? latest.slice(0, 10) : '--'
})

onMounted(() => load())

async function load() {
  const params: { page?: number; page_size?: number; type?: string } = {
    page: page.value,
    page_size: pageSize,
  }
  if (filterType.value) params.type = filterType.value
  await store.fetchNeeds(params)
}

function onFilterChange(value: string) {
  filterType.value = value
  page.value = 1
  load()
}

function onPageChange(nextPage: number) {
  page.value = nextPage
  load()
}

function goToNeedDetail(needId: number) {
  router.push(`/needs/${needId}`)
}

function goToMatch(needId: number) {
  router.push(`/needs/${needId}/matches`)
}

function typeTagType(type: Need['type']) {
  switch (type) {
    case '求助':
      return 'danger'
    case '组队':
      return 'success'
    case '技能交换':
      return 'warning'
    default:
      return 'info'
  }
}

function statusLabel(status: Need['status']) {
  if (status === '开放') return '开放中'
  if (status === '已匹配') return '已匹配'
  return '已关闭'
}

function statusTone(status: Need['status']) {
  if (status === '开放') return 'is-open'
  if (status === '已匹配') return 'is-done'
  return 'is-closed'
}

function formatDate(iso: string) {
  return iso.slice(0, 10)
}
</script>

<template>
  <div class="page-shell plaza-page">
    <div class="page-stack">
      <section class="plaza-hero surface-card-strong">
        <div class="hero-copy">
          <span class="eyebrow">产品主入口</span>
          <h1>需求广场</h1>
          <p>
            浏览校园内的组队、求助和技能交换需求。这里既是平台首页，也是你向评委说明“内容已经在流动”的最快一屏。
          </p>
          <div class="hero-actions">
            <el-button type="primary" size="large" @click="router.push('/needs/new')">发布需求</el-button>
            <el-button size="large" @click="router.push('/agent')">打开智能助手</el-button>
          </div>
        </div>

        <div class="hero-metrics">
          <div class="metric-card">
            <div class="metric-icon" style="background: var(--color-primary-bg); color: var(--color-primary)">
              <el-icon :size="20"><DataAnalysis /></el-icon>
            </div>
            <div>
              <span class="metric-value">{{ store.total }}</span>
              <span class="metric-label">当前列表需求</span>
            </div>
          </div>
          <div class="metric-card">
            <div class="metric-icon" style="background: var(--color-success-soft); color: var(--color-success)">
              <el-icon :size="20"><Connection /></el-icon>
            </div>
            <div>
              <span class="metric-value">{{ teamCount }}</span>
              <span class="metric-label">组队需求</span>
            </div>
          </div>
          <div class="metric-card">
            <div class="metric-icon" style="background: var(--color-warning-soft); color: var(--color-warning)">
              <el-icon :size="20"><Calendar /></el-icon>
            </div>
            <div>
              <span class="metric-value">{{ latestDate }}</span>
              <span class="metric-label">最近发布时间</span>
            </div>
          </div>
          <div class="hero-note">
            <strong>{{ openCount }}</strong>
            <span>条开放中的需求，适合直接进入匹配和联系流程。</span>
          </div>
        </div>
      </section>

      <section class="plaza-toolbar surface-card">
        <div class="toolbar-left">
          <div>
            <div class="toolbar-title">筛选需求</div>
            <div class="toolbar-subtitle">按类型缩小范围，快速进入目标链路。</div>
          </div>
          <el-radio-group v-model="filterType" class="toolbar-filters" @change="onFilterChange">
            <el-radio-button value="">全部</el-radio-button>
            <el-radio-button value="求助">求助</el-radio-button>
            <el-radio-button value="组队">组队</el-radio-button>
            <el-radio-button value="技能交换">技能交换</el-radio-button>
          </el-radio-group>
        </div>
        <el-button type="primary" @click="router.push('/needs/new')">
          <el-icon :size="16"><Plus /></el-icon>
          发布需求
        </el-button>
      </section>

      <section class="surface-card demo-flow">
        <div class="surface-section-title">
          <div>
            <span class="eyebrow">Demo Flow</span>
            <h2>推荐演示路径</h2>
          </div>
          <span class="demo-flow-hint">从 AI 到匹配，再到联系，三屏就能讲清楚。</span>
        </div>
        <div class="demo-flow-grid">
          <button type="button" class="demo-flow-card" @click="router.push('/agent')">
            <span class="demo-flow-step">01</span>
            <strong>打开 Agent 工作台</strong>
            <p>上传材料、生成计划、整理草稿，展示 AI 是如何参与决策的。</p>
          </button>
          <button
            type="button"
            class="demo-flow-card"
            :disabled="!featuredNeed"
            @click="featuredNeed && goToMatch(featuredNeed.id)"
          >
            <span class="demo-flow-step">02</span>
            <strong>进入匹配结果页</strong>
            <p>
              直接看候选人对比、AI 推荐理由和起草私信。
              <span v-if="featuredNeed" class="demo-flow-inline">当前推荐：{{ featuredNeed.title }}</span>
            </p>
          </button>
          <button type="button" class="demo-flow-card" @click="router.push('/messages')">
            <span class="demo-flow-step">03</span>
            <strong>查看消息推进</strong>
            <p>从匹配转到沟通，把“找到人”继续推进到“开始合作”。</p>
          </button>
        </div>
      </section>

      <section v-loading="store.loading" class="plaza-results">
        <div v-if="!store.loading && store.needs.length === 0" class="empty-state surface-card">
          <el-icon :size="48" style="color: var(--text-muted)"><Files /></el-icon>
          <p>还没有符合筛选条件的需求，可以切换筛选或直接发布第一条需求。</p>
          <el-button type="primary" @click="router.push('/needs/new')">发布需求</el-button>
        </div>

        <div v-else class="need-grid">
          <article v-for="need in store.needs" :key="need.id" class="need-card surface-card" @click="goToNeedDetail(need.id)">
            <div class="need-card-top">
              <div class="need-card-badges">
                <el-tag :type="typeTagType(need.type)" effect="plain" size="small">{{ need.type }}</el-tag>
                <span class="need-status" :class="statusTone(need.status)">{{ statusLabel(need.status) }}</span>
              </div>
              <span class="need-date">{{ formatDate(need.created_at) }}</span>
            </div>

            <div class="need-card-main">
              <h3>{{ need.title }}</h3>
              <p>{{ need.description }}</p>
            </div>

            <div v-if="need.req_tags?.length" class="need-card-tags">
              <el-tag v-for="tag in need.req_tags.slice(0, 4)" :key="tag" size="small" effect="plain">{{ tag }}</el-tag>
              <el-tag v-if="need.req_tags.length > 4" size="small" effect="plain">+{{ need.req_tags.length - 4 }}</el-tag>
            </div>

            <div class="need-card-footer">
              <div class="need-author">
                <span class="need-author-label">发布者</span>
                <strong>{{ need.username }}</strong>
              </div>
              <span class="need-cta">查看需求详情</span>
            </div>
          </article>
        </div>

        <div v-if="totalPages > 1" class="plaza-pagination">
          <el-pagination
            v-model:current-page="page"
            :total="store.total"
            :page-size="pageSize"
            background
            layout="prev, pager, next"
            @current-change="onPageChange"
          />
        </div>
      </section>
    </div>

    <el-tooltip content="发布需求" placement="left">
      <el-button type="primary" circle size="large" class="fab-btn" @click="router.push('/needs/new')">
        <el-icon :size="22"><Plus /></el-icon>
      </el-button>
    </el-tooltip>
  </div>
</template>

<style scoped>
.plaza-page {
  position: relative;
}

.plaza-hero {
  display: grid;
  grid-template-columns: minmax(0, 1.3fr) minmax(320px, 0.9fr);
  gap: 20px;
  padding: 26px;
}

.hero-copy h1 {
  margin-top: 14px;
  font-size: 32px;
  line-height: 1.1;
  font-weight: 800;
  color: var(--text-primary);
}

.hero-copy p {
  margin-top: 14px;
  max-width: 680px;
  font-size: 15px;
  line-height: 1.8;
  color: var(--text-secondary);
}

.hero-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 20px;
}

.hero-metrics {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  align-content: start;
}

.hero-note {
  grid-column: 1 / -1;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px 18px;
  border-radius: var(--radius-lg);
  background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
  color: #e2e8f0;
}

.hero-note strong {
  font-size: 24px;
  line-height: 1;
}

.plaza-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 20px;
}

.toolbar-left {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 18px;
}

.toolbar-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
}

.toolbar-subtitle {
  margin-top: 2px;
  font-size: 12px;
  color: var(--text-tertiary);
}

.toolbar-filters :deep(.el-radio-button__inner) {
  min-width: 78px;
  padding: 8px 14px;
  font-size: 13px;
}

.plaza-results {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.demo-flow {
  padding: 18px 20px;
}

.demo-flow-hint {
  font-size: 12px;
  color: var(--text-tertiary);
}

.demo-flow-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-top: 12px;
}

.demo-flow-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 170px;
  padding: 18px;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  background: var(--bg-panel);
  text-align: left;
  cursor: pointer;
  transition: transform var(--transition-fast), box-shadow var(--transition-fast), border-color var(--transition-fast);
}

.demo-flow-card:hover:not(:disabled) {
  transform: translateY(-2px);
  border-color: var(--border-strong);
  box-shadow: var(--shadow-sm);
}

.demo-flow-card:disabled {
  cursor: default;
  opacity: 0.72;
}

.demo-flow-step {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 10px;
  background: var(--bg-panel-muted);
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 800;
}

.demo-flow-card strong {
  font-size: 16px;
  color: var(--text-primary);
}

.demo-flow-card p {
  font-size: 13px;
  line-height: 1.7;
  color: var(--text-secondary);
}

.demo-flow-inline {
  display: block;
  margin-top: 6px;
  color: var(--color-primary);
  font-weight: 600;
}

.need-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.need-card {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 20px;
  cursor: pointer;
  transition: transform var(--transition-fast), box-shadow var(--transition-fast), border-color var(--transition-fast);
}

.need-card:hover {
  transform: translateY(-2px);
  border-color: var(--border-strong);
  box-shadow: var(--shadow-md);
}

.need-card-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.need-card-badges {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.need-status {
  display: inline-flex;
  align-items: center;
  height: 24px;
  padding: 0 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
}

.need-status.is-open {
  background: var(--color-success-soft);
  color: var(--color-success);
}

.need-status.is-done {
  background: var(--color-primary-bg);
  color: var(--color-primary);
}

.need-status.is-closed {
  background: var(--bg-panel-muted);
  color: var(--text-tertiary);
}

.need-date {
  font-size: 12px;
  color: var(--text-tertiary);
  flex-shrink: 0;
}

.need-card-main h3 {
  font-size: 18px;
  line-height: 1.35;
  font-weight: 700;
  color: var(--text-primary);
}

.need-card-main p {
  margin-top: 8px;
  color: var(--text-secondary);
  font-size: 14px;
  line-height: 1.7;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
  overflow: hidden;
}

.need-card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.need-card-footer {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 12px;
  margin-top: auto;
}

.need-author {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.need-author-label {
  font-size: 11px;
  color: var(--text-tertiary);
}

.need-author strong {
  font-size: 13px;
  color: var(--text-primary);
}

.need-cta {
  font-size: 12px;
  font-weight: 700;
  color: var(--color-primary);
}

.plaza-pagination {
  display: flex;
  justify-content: center;
  padding-bottom: 8px;
}

.fab-btn {
  position: fixed;
  right: 40px;
  bottom: 36px;
  width: 54px;
  height: 54px;
  box-shadow: 0 18px 34px rgba(37, 99, 235, 0.28);
}

@media (max-width: 1024px) {
  .plaza-hero {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 767px) {
  .need-grid {
    grid-template-columns: 1fr;
  }

  .plaza-hero,
  .plaza-toolbar {
    padding: 18px;
  }

  .hero-copy h1 {
    font-size: 28px;
  }

  .hero-metrics {
    grid-template-columns: 1fr;
  }

  .plaza-toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .demo-flow-grid {
    grid-template-columns: 1fr;
  }

  .toolbar-left {
    flex-direction: column;
    align-items: stretch;
  }

  .fab-btn {
    right: 20px;
    bottom: 20px;
  }
}
</style>
