<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { Need } from '@/types'
import * as needsApi from '@/api/needs'

const router = useRouter()
const needs = ref<Need[]>([])
const selectedNeeds = ref<Need[]>([])
const loading = ref(false)

onMounted(load)

async function load() {
  loading.value = true
  try {
    const [publishedResponse, selectedResponse] = await Promise.all([
      needsApi.getMyNeeds(),
      needsApi.getMySelectedNeeds(),
    ])
    needs.value = publishedResponse.data
    selectedNeeds.value = selectedResponse.data
  } catch (error: any) { ElMessage.error(error?.response?.data?.detail || error?.message || '加载失败') }
  finally { loading.value = false }
}

async function handleClose(need: Need) {
  try {
    await ElMessageBox.confirm('确定关闭这个需求吗？', '确认', { type: 'warning' })
  } catch { return }
  try {
    await needsApi.closeNeed(need.id)
    ElMessage.success('已关闭')
    load()
  } catch (error: any) { ElMessage.error(error?.response?.data?.detail || error?.message || '操作失败') }
}

async function handleDelete(need: Need) {
  try {
    await ElMessageBox.confirm('确定删除这个需求吗？此操作不可恢复', '确认删除', { type: 'error' })
  } catch { return }
  try {
    await needsApi.deleteNeed(need.id)
    ElMessage.success('已删除')
    load()
  } catch (error: any) { ElMessage.error(error?.response?.data?.detail || error?.message || '删除失败') }
}

async function handleReopen(need: Need) {
  try {
    await needsApi.updateNeed(need.id, { status: '开放' })
    ElMessage.success('已重新开放')
    load()
  } catch (error: any) { ElMessage.error(error?.response?.data?.detail || error?.message || '操作失败') }
}

function statusTag(status: string) {
  switch (status) {
    case '开放': return 'success'
    case '已匹配': return 'warning'
    case '关闭': return 'info'
    default: return ''
  }
}

function goMatch(needId: number) { router.push(`/needs/${needId}/matches`) }
function goNeed(needId: number) { router.push(`/needs/${needId}`) }
function goSelectedConversation(need: Need) { router.push(`/messages/${need.user_id}?needId=${need.id}`) }
</script>

<template>
  <div class="manage-page">
    <section class="manage-hero">
      <div>
        <span class="eyebrow">Need Dashboard</span>
        <h1>我的需求</h1>
        <p>集中查看自己发布的需求，以及别人已经选中你参与的需求，下一步可以直接去匹配结果或站内沟通。</p>
      </div>
      <div class="hero-stats">
        <div class="stat-card">
          <strong>{{ needs.length }}</strong>
          <span>我发布的需求</span>
        </div>
        <div class="stat-card">
          <strong>{{ selectedNeeds.length }}</strong>
          <span>我被选中的需求</span>
        </div>
      </div>
    </section>

    <div v-loading="loading" class="manage-sections">
      <section class="need-section published-needs-section">
        <div class="section-title">
          <div>
            <span class="eyebrow">Published</span>
            <h2>我发布的需求</h2>
          </div>
          <span class="page-count">共 {{ needs.length }} 个</span>
        </div>

        <el-empty v-if="!loading && needs.length === 0" description="还没有发布过需求" />

        <div v-else class="need-card-grid">
          <article v-for="n in needs" :key="n.id" class="need-card">
            <div class="need-top">
              <el-tag :type="n.type === '求助' ? 'danger' : n.type === '组队' ? 'success' : 'warning'" size="small">
                {{ n.type }}
              </el-tag>
              <el-tag :type="statusTag(n.status)" size="small" effect="plain">{{ n.status }}</el-tag>
              <el-tag v-if="n.selection_mode === 'multi'" size="small" effect="plain" type="info">多选</el-tag>
            </div>
            <h3 class="need-title">{{ n.title }}</h3>
            <p class="need-desc">{{ n.description.slice(0, 92) }}{{ n.description.length > 92 ? '...' : '' }}</p>
            <div class="need-meta">
              <span>{{ n.created_at.slice(0, 10) }}</span>
              <span v-if="n.selected_user_ids?.length" class="selected-badge">已选 {{ n.selected_user_ids.length }} 人</span>
            </div>
            <div class="need-actions">
              <el-button v-if="n.status === '开放'" size="small" type="primary" @click.stop="goMatch(n.id)">查看匹配</el-button>
              <el-button v-if="n.status === '开放'" size="small" @click.stop="handleClose(n)">关闭</el-button>
              <el-button v-if="n.status === '已匹配'" size="small" type="primary" @click.stop="goMatch(n.id)">查看结果</el-button>
              <el-button v-if="n.status === '关闭'" size="small" type="warning" @click.stop="handleReopen(n)">重新开放</el-button>
              <el-button size="small" type="danger" plain @click.stop="handleDelete(n)">删除</el-button>
            </div>
          </article>
        </div>
      </section>

      <section class="need-section selected-needs-section">
        <div class="section-title">
          <div>
            <span class="eyebrow">Selected</span>
            <h2>我被选中的需求</h2>
          </div>
          <span class="page-count">共 {{ selectedNeeds.length }} 个</span>
        </div>

        <el-empty v-if="!loading && selectedNeeds.length === 0" description="还没有被选中的需求" />

        <div v-else class="need-card-grid selected-grid">
          <article v-for="n in selectedNeeds" :key="n.id" class="need-card selected-need-card">
            <div class="need-top">
              <el-tag :type="n.type === '求助' ? 'danger' : n.type === '组队' ? 'success' : 'warning'" size="small">
                {{ n.type }}
              </el-tag>
              <el-tag type="success" size="small" effect="plain">已选中我</el-tag>
              <el-tag :type="statusTag(n.status)" size="small" effect="plain">{{ n.status }}</el-tag>
            </div>
            <h3 class="need-title">{{ n.title }}</h3>
            <p class="need-desc">{{ n.description.slice(0, 92) }}{{ n.description.length > 92 ? '...' : '' }}</p>
            <div class="need-meta">
              <span>发布者：{{ n.username || `用户 #${n.user_id}` }}</span>
              <span>{{ n.created_at.slice(0, 10) }}</span>
            </div>
            <div class="need-actions">
              <el-button size="small" @click.stop="goNeed(n.id)">查看需求</el-button>
              <el-button size="small" type="primary" @click.stop="goSelectedConversation(n)">去沟通</el-button>
            </div>
          </article>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.manage-page { max-width: 1040px; margin: 0 auto; padding: 24px 16px 40px; }
.manage-hero {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  padding: 22px;
  margin-bottom: 18px;
  border: 1px solid #d8e2ef;
  border-radius: 18px;
  background: linear-gradient(135deg, #f8fbff 0%, #eef6ff 52%, #fffaf0 100%);
}
.eyebrow { display: block; margin-bottom: 8px; font-size: 12px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.08em; }
.manage-hero h1 { margin: 0; font-size: 26px; font-weight: 800; color: #102033; }
.manage-hero p { max-width: 620px; margin: 10px 0 0; line-height: 1.7; color: #526172; }
.hero-stats { display: grid; grid-template-columns: repeat(2, minmax(110px, 1fr)); gap: 10px; min-width: 250px; }
.stat-card { padding: 16px; border: 1px solid rgba(148, 163, 184, 0.3); border-radius: 14px; background: rgba(255, 255, 255, 0.75); }
.stat-card strong { display: block; font-size: 28px; color: #0f4c81; }
.stat-card span { font-size: 12px; color: #64748b; }
.manage-sections { display: grid; gap: 18px; }
.need-section { padding: 18px; border: 1px solid #e2e8f0; border-radius: 16px; background: #fff; }
.section-title { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin-bottom: 14px; }
.section-title h2 { margin: 0; font-size: 18px; font-weight: 700; color: #102033; }
.page-count { font-size: 14px; color: #656d76; }
.need-card-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 12px; }
.need-card {
  display: flex;
  min-height: 190px;
  flex-direction: column;
  gap: 10px;
  padding: 16px;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  background: #fbfdff;
}
.selected-need-card { background: linear-gradient(180deg, #f0fdf4 0%, #ffffff 100%); border-color: #bbf7d0; }
.need-top { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }
.need-title { font-size: 16px; font-weight: 700; margin: 0; color: #1a1a2e; }
.need-desc { flex: 1; font-size: 13px; color: #656d76; margin: 0; line-height: 1.65; }
.need-meta { display: flex; flex-wrap: wrap; gap: 10px; font-size: 12px; color: #8492a6; }
.need-actions { display: flex; flex-wrap: wrap; gap: 8px; flex-shrink: 0; }
.selected-badge { color: #0969da; font-weight: 600; }

@media (max-width: 720px) {
  .manage-hero { flex-direction: column; }
  .hero-stats { min-width: 0; }
}
</style>
