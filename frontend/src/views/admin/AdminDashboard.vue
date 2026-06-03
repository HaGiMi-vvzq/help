<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { User, DataAnalysis, Connection, ChatDotRound } from '@element-plus/icons-vue'
import * as adminApi from '@/api/admin'
import type { AdminStats } from '@/api/admin'

const stats = ref<AdminStats>({
  total_users: 0, active_users: 0, total_needs: 0,
  open_needs: 0, matched_needs: 0, total_messages: 0,
  today_users: 0, today_needs: 0,
})
const loading = ref(false)

onMounted(() => loadStats())

async function loadStats() {
  loading.value = true
  try {
    const { data } = await adminApi.getStats()
    stats.value = data
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="page-shell" style="padding: 24px 16px">
    <div class="page-stack">
      <h2 style="font-size:20px;font-weight:700;color:var(--text-primary);margin:0">管理后台</h2>

      <div v-loading="loading" class="metric-grid" style="grid-template-columns: repeat(4, minmax(0, 1fr))">
        <div class="metric-card">
          <div class="metric-icon" style="background:var(--color-primary-bg);color:var(--color-primary)">
            <el-icon :size="20"><User /></el-icon>
          </div>
          <div>
            <span class="metric-value">{{ stats.total_users }}</span>
            <span class="metric-label">总用户（今日 +{{ stats.today_users }}）</span>
          </div>
        </div>
        <div class="metric-card">
          <div class="metric-icon" style="background:var(--color-success-soft);color:var(--color-success)">
            <el-icon :size="20"><DataAnalysis /></el-icon>
          </div>
          <div>
            <span class="metric-value">{{ stats.total_needs }}</span>
            <span class="metric-label">总需求（今日 +{{ stats.today_needs }}）</span>
          </div>
        </div>
        <div class="metric-card">
          <div class="metric-icon" style="background:var(--color-warning-soft);color:var(--color-warning)">
            <el-icon :size="20"><Connection /></el-icon>
          </div>
          <div>
            <span class="metric-value">{{ stats.open_needs }}</span>
            <span class="metric-label">开放中 / {{ stats.matched_needs }} 已匹配</span>
          </div>
        </div>
        <div class="metric-card">
          <div class="metric-icon" style="background:#ede9fe;color:var(--color-accent)">
            <el-icon :size="20"><ChatDotRound /></el-icon>
          </div>
          <div>
            <span class="metric-value">{{ stats.total_messages }}</span>
            <span class="metric-label">总消息数</span>
          </div>
        </div>
      </div>

      <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
        <div class="surface-card" style="padding:20px;text-align:center">
          <div style="font-size:14px;color:var(--text-tertiary);margin-bottom:8px">活跃率</div>
          <div style="font-size:36px;font-weight:800;color:var(--color-primary)">
            {{ stats.total_users ? Math.round(stats.active_users / stats.total_users * 100) : 0 }}%
          </div>
          <div style="font-size:12px;color:var(--text-tertiary);margin-top:4px">{{ stats.active_users }} / {{ stats.total_users }} 用户</div>
        </div>
        <div class="surface-card" style="padding:20px;text-align:center">
          <div style="font-size:14px;color:var(--text-tertiary);margin-bottom:8px">匹配率</div>
          <div style="font-size:36px;font-weight:800;color:var(--color-success)">
            {{ stats.total_needs ? Math.round(stats.matched_needs / stats.total_needs * 100) : 0 }}%
          </div>
          <div style="font-size:12px;color:var(--text-tertiary);margin-top:4px">{{ stats.matched_needs }} / {{ stats.total_needs }} 需求</div>
        </div>
      </div>
    </div>
  </div>
</template>
