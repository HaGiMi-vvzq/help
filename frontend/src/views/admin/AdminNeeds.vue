<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as adminApi from '@/api/admin'
import type { AdminNeed } from '@/api/admin'

const needs = ref<AdminNeed[]>([])
const total = ref(0)
const loading = ref(false)
const page = ref(1)
const pageSize = 20

onMounted(() => loadNeeds())

async function loadNeeds() {
  loading.value = true
  try {
    const { data } = await adminApi.listNeeds({ page: page.value, page_size: pageSize })
    needs.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

function statusTagType(status: string) {
  return status === '开放' ? 'success' : status === '已匹配' ? 'primary' : 'info'
}

async function changeStatus(need: AdminNeed) {
  const nextStatus = need.status === '开放' ? '已关闭' : '开放'
  try {
    await ElMessageBox.confirm(`将「${need.title}」状态从「${need.status}」改为「${nextStatus}」？`, '提示', { type: 'warning' })
  } catch { return }
  const { data } = await adminApi.updateNeedStatus(need.id, nextStatus)
  need.status = data.status
  ElMessage.success('已更新')
}

async function handleDelete(need: AdminNeed) {
  try {
    await ElMessageBox.confirm(
      `删除「${need.title}」将同时清除其匹配、申请和消息记录。确定？`,
      '危险操作',
      { type: 'error', confirmButtonText: '确认删除' }
    )
  } catch { return }
  await adminApi.deleteNeed(need.id)
  needs.value = needs.value.filter(n => n.id !== need.id)
  total.value--
  ElMessage.success('已删除')
}

function formatDate(iso: string) {
  return iso.slice(0, 10)
}

function typeTagType(type: string) {
  return type === '组队' ? 'success' : type === '求助' ? 'danger' : 'warning'
}
</script>

<template>
  <div class="page-shell" style="padding: 24px 16px">
    <div class="page-stack">
      <div class="surface-section-title">
        <h2>需求管理</h2>
        <span style="font-size:13px;color:var(--text-tertiary)">共 {{ total }} 条</span>
      </div>

      <el-table v-loading="loading" :data="needs" class="surface-card" style="width:100%">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column label="类型" width="90">
          <template #default="{ row }">
            <el-tag :type="typeTagType(row.type)" size="small" effect="plain">{{ row.type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="标题" min-width="160" show-overflow-tooltip />
        <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
        <el-table-column prop="username" label="发布者" width="100" />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small" effect="plain">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="时间" width="110">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="changeStatus(row)">
              {{ row.status === '开放' ? '关闭' : '开放' }}
            </el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-if="total > pageSize"
        v-model:current-page="page"
        :total="total"
        :page-size="pageSize"
        background
        layout="prev, pager, next"
        @current-change="loadNeeds"
      />
    </div>
  </div>
</template>
