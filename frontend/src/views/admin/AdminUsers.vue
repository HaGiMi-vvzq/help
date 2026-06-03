<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as adminApi from '@/api/admin'
import type { AdminUser } from '@/api/admin'

const users = ref<AdminUser[]>([])
const total = ref(0)
const loading = ref(false)
const page = ref(1)
const pageSize = 20

onMounted(() => loadUsers())

async function loadUsers() {
  loading.value = true
  try {
    const { data } = await adminApi.listUsers({ page: page.value, page_size: pageSize })
    users.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

async function toggleRole(user: AdminUser) {
  const newRole = user.role === 'admin' ? 'user' : 'admin'
  const action = newRole === 'admin' ? '设为管理员' : '取消管理员'
  try {
    await ElMessageBox.confirm(`确定要${action}「${user.username}」吗？`, '提示', { type: 'warning' })
  } catch { return }
  await adminApi.updateUser(user.id, { role: newRole })
  user.role = newRole
  ElMessage.success(`${action}成功`)
}

async function toggleActive(user: AdminUser) {
  const action = user.is_active ? '禁用' : '启用'
  try {
    await ElMessageBox.confirm(`确定要${action}「${user.username}」吗？`, '提示', { type: 'warning' })
  } catch { return }
  await adminApi.updateUser(user.id, { is_active: !user.is_active })
  user.is_active = !user.is_active
  ElMessage.success(`${action}成功`)
}

async function handleDelete(user: AdminUser) {
  try {
    await ElMessageBox.confirm(
      `删除「${user.username}」将同时清除其所有需求、消息和申请记录，不可恢复。确定删除？`,
      '危险操作',
      { type: 'error', confirmButtonText: '确认删除' }
    )
  } catch { return }
  await adminApi.deleteUser(user.id)
  users.value = users.value.filter(u => u.id !== user.id)
  total.value--
  ElMessage.success('已删除')
}

function formatDate(iso: string) {
  return iso.slice(0, 10)
}
</script>

<template>
  <div class="page-shell" style="padding: 24px 16px">
    <div class="page-stack">
      <div class="surface-section-title">
        <h2>用户管理</h2>
        <span style="font-size:13px;color:var(--text-tertiary)">共 {{ total }} 人</span>
      </div>

      <el-table v-loading="loading" :data="users" class="surface-card" style="width:100%">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="username" label="用户名" width="140" />
        <el-table-column label="角色" width="100">
          <template #default="{ row }">
            <el-tag :type="row.role === 'admin' ? 'danger' : 'info'" size="small" effect="plain">
              {{ row.role === 'admin' ? '管理员' : '用户' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <span :style="{ color: row.is_active ? 'var(--color-success)' : 'var(--color-danger)', fontSize: '13px', fontWeight: 600 }">
              {{ row.is_active ? '正常' : '已禁用' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="school" label="学校" width="140" />
        <el-table-column prop="bio" label="简介" min-width="160" show-overflow-tooltip />
        <el-table-column label="注册时间" width="110">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="toggleRole(row)">
              {{ row.role === 'admin' ? '取消管理' : '设为管理' }}
            </el-button>
            <el-button size="small" :type="row.is_active ? 'warning' : 'success'" @click="toggleActive(row)">
              {{ row.is_active ? '禁用' : '启用' }}
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
        @current-change="loadUsers"
      />
    </div>
  </div>
</template>
