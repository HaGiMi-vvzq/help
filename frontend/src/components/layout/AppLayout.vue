<script setup lang="ts">
import { computed, onMounted, provide, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '@/api/client'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const collapsed = ref(false)
const avatarUploading = ref(false)
const avatarInput = ref<HTMLInputElement>()
const notifyCount = ref(0)
const notifyItems = ref<{ id: number; sender_name: string; content: string; time: string; need_id: number }[]>([])

const menuItems = [
  { path: '/', icon: 'House', label: '需求广场', hint: 'Browse open collaboration needs' },
  { path: '/needs/new', icon: 'CirclePlus', label: '发布需求', hint: 'Create a new collaboration brief' },
  { path: '/needs/manage', icon: 'List', label: '我的需求', hint: 'Track published needs and selections' },
  { path: '/needs/applications', icon: 'Tickets', label: 'My Applications', hint: 'Track applications as a participant' },
  { path: '/agent', icon: 'MagicStick', label: '智能助手', hint: 'AI workspace for planning and outreach' },
  { path: '/messages', icon: 'ChatDotRound', label: '站内消息', hint: 'Continue follow-up conversations' },
  { path: '/profile/setup', icon: 'User', label: '个人中心', hint: 'Profile, skills, and identity' },
  { path: '/settings', icon: 'Setting', label: '系统设置', hint: 'Model and environment settings' },
]

const activeMenu = computed(() => {
  if (route.path.startsWith('/messages')) return '/messages'
  if (route.path.startsWith('/agent')) return '/agent'
  if (route.path.startsWith('/needs/applications')) return '/needs/applications'
  if (route.path.startsWith('/needs/manage')) return '/needs/manage'
  if (route.path.startsWith('/needs/new')) return '/needs/new'
  if (route.path.startsWith('/needs/')) return '/'
  if (route.path.startsWith('/settings')) return '/settings'
  if (route.path.startsWith('/profile')) return '/profile/setup'
  return '/'
})

const pageTitle = computed(() => {
  if (route.path.startsWith('/needs/applications')) return 'My Applications'
  if (route.path.startsWith('/agent')) return 'Agent Workspace'
  if (route.path.startsWith('/needs/new')) return '发布需求'
  if (route.path.startsWith('/needs/manage')) return '我的需求'
  if (route.path.includes('/matches')) return '匹配结果'
  if (route.path.startsWith('/messages')) return '站内消息'
  if (route.path.startsWith('/profile')) return '个人中心'
  if (route.path.startsWith('/settings')) return '系统设置'
  return '需求广场'
})

const pageSummary = computed(() => {
  if (route.path.startsWith('/needs/applications')) {
    return 'Review what you have applied to, where each application stands, and where to continue the conversation.'
  }
  if (route.path.startsWith('/agent')) {
    return 'Upload files, refine needs, review drafts, and move from planning into collaboration.'
  }
  if (route.path.startsWith('/needs/new')) return 'Turn an idea into a publishable need.'
  if (route.path.startsWith('/needs/manage')) return 'Track your own needs, candidate status, and final selections.'
  if (route.path.includes('/matches')) return 'Compare system matches and incoming applicants in one decision surface.'
  if (route.path.startsWith('/messages')) return 'Keep the collaboration moving after the match or application.'
  if (route.path.startsWith('/profile')) return 'Maintain your skills and profile so matching stays accurate.'
  if (route.path.startsWith('/settings')) return 'Inspect the current environment and configuration.'
  return 'Browse open collaboration opportunities across projects, help requests, and skill exchange.'
})

const pagePill = computed(() => {
  if (route.path.startsWith('/agent')) return 'AI Workspace'
  if (route.path.includes('/matches')) return 'Decision Surface'
  if (route.path.startsWith('/needs/applications')) return 'Participant View'
  if (route.path.startsWith('/messages')) return 'Follow-up'
  return 'Product Demo'
})

const userCampus = computed(() => {
  const extra = auth.user?.extra
  if (extra && typeof extra === 'object' && !Array.isArray(extra)) {
    const campus = extra.campus
    if (typeof campus === 'string' && campus.trim()) return campus
  }
  return auth.user?.school || 'Demo Account'
})

function go(path: string) {
  router.push(path)
}

function triggerAvatarInput() {
  avatarInput.value?.click()
}

async function handleAvatarUpload(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  if (file.size > 2 * 1024 * 1024) {
    ElMessage.warning('Image must be smaller than 2MB')
    return
  }
  avatarUploading.value = true
  try {
    const form = new FormData()
    form.append('file', file)
    const { data } = await api.post('/profile/avatar', form)
    if (auth.user) auth.user = { ...auth.user, avatar: data.avatar }
    ElMessage.success('Avatar updated')
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || error?.message || 'Upload failed')
  } finally {
    avatarUploading.value = false
  }
}

async function fetchNotifications() {
  if (!auth.token) {
    notifyCount.value = 0
    notifyItems.value = []
    return
  }
  try {
    const { data } = await api.get('/messages/notifications')
    notifyCount.value = data.count
    notifyItems.value = data.items
  } catch {
    notifyCount.value = 0
    notifyItems.value = []
  }
}

provide('refreshNotifications', fetchNotifications)

onMounted(() => {
  if (auth.token && !auth.user) void auth.fetchMe()
  void fetchNotifications()
})

watch(() => route.fullPath, () => {
  void fetchNotifications()
})

function handleLogout() {
  auth.logout()
  router.push('/login')
  ElMessage.success('Logged out')
}
</script>

<template>
  <div class="app-shell">
    <aside class="shell-sidebar" :class="{ collapsed }">
      <div class="sidebar-brand" @click="go('/')">
        <div class="brand-mark">
          <el-icon :size="20"><MagicStick /></el-icon>
        </div>
        <div v-show="!collapsed" class="brand-copy">
          <span class="brand-title">Campus AI Match</span>
          <span class="brand-subtitle">Hackathon Demo</span>
        </div>
      </div>

      <div v-show="!collapsed" class="sidebar-context">
        <span class="sidebar-context-pill">{{ pagePill }}</span>
        <p>{{ pageSummary }}</p>
      </div>

      <nav class="sidebar-nav">
        <button
          v-for="item in menuItems"
          :key="item.path"
          type="button"
          class="nav-item"
          :class="{ active: activeMenu === item.path }"
          @click="go(item.path)"
        >
          <span class="nav-icon">
            <el-icon :size="18"><component :is="item.icon" /></el-icon>
          </span>
          <span v-show="!collapsed" class="nav-copy">
            <span class="nav-label">{{ item.label }}</span>
            <span class="nav-hint">{{ item.hint }}</span>
          </span>
        </button>
      </nav>

      <div class="sidebar-footer">
        <input ref="avatarInput" type="file" accept="image/*" style="display: none" @change="handleAvatarUpload" />
        <el-dropdown trigger="click" placement="right-end">
          <div class="user-card">
            <el-avatar :size="38" :src="auth.user?.avatar" icon="UserFilled" />
            <div v-show="!collapsed" class="user-copy">
              <span class="user-name">{{ auth.user?.username || 'Guest' }}</span>
              <span class="user-campus">{{ userCampus }}</span>
            </div>
            <el-icon v-show="!collapsed" class="user-chevron"><ArrowUp /></el-icon>
          </div>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="go('/profile/setup')">
                <el-icon><User /></el-icon>
                个人中心
              </el-dropdown-item>
              <el-dropdown-item @click="triggerAvatarInput">
                <el-icon><Camera /></el-icon>
                {{ avatarUploading ? 'Uploading...' : 'Change Avatar' }}
              </el-dropdown-item>
              <el-dropdown-item divided @click="handleLogout">
                <el-icon><SwitchButton /></el-icon>
                退出登录
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </aside>

    <main class="shell-main">
      <header class="shell-topbar">
        <div class="topbar-left">
          <el-button text class="topbar-icon-btn" @click="collapsed = !collapsed">
            <el-icon :size="18"><Fold v-if="!collapsed" /><Expand v-else /></el-icon>
          </el-button>
          <div class="page-copy">
            <div class="page-copy-top">
              <span class="page-pill">{{ pagePill }}</span>
              <el-breadcrumb separator="/">
                <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
                <el-breadcrumb-item>{{ pageTitle }}</el-breadcrumb-item>
              </el-breadcrumb>
            </div>
            <div class="page-heading">{{ pageTitle }}</div>
          </div>
        </div>

        <div class="topbar-right">
          <div class="status-chip">
            <span class="status-dot" />
            <span>Demo Ready</span>
          </div>
          <el-dropdown trigger="click" placement="bottom-end">
            <el-badge :value="notifyCount" :hidden="notifyCount === 0" :max="99">
              <el-button text class="topbar-icon-btn">
                <el-icon :size="18"><Bell /></el-icon>
              </el-button>
            </el-badge>
            <template #dropdown>
              <el-dropdown-menu>
                <div class="notify-panel">
                  <div class="notify-header">
                    <span>消息通知</span>
                    <span class="notify-count">{{ notifyCount }}</span>
                  </div>
                  <div v-if="notifyItems.length === 0" class="notify-empty">暂无通知</div>
                  <button
                    v-for="item in notifyItems"
                    :key="item.id"
                    type="button"
                    class="notify-item"
                    @click="go(item.need_id ? `/needs/${item.need_id}` : '/messages')"
                  >
                    <strong>{{ item.sender_name }}</strong>
                    <span>{{ item.content }}</span>
                    <small>{{ item.time.slice(5, 16) }}</small>
                  </button>
                  <button v-if="notifyItems.length" type="button" class="notify-link" @click="go('/messages')">
                    查看全部消息
                  </button>
                </div>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>

      <section class="shell-content">
        <slot />
      </section>
    </main>

  </div>
</template>

<style scoped>
.app-shell {
  display: flex;
  min-height: 100vh;
  background: var(--bg-app);
}

.shell-sidebar {
  width: var(--sidebar-width);
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: linear-gradient(180deg, var(--bg-accent-strong) 0%, #111b2f 100%);
  color: var(--text-inverse);
  transition: width var(--transition-normal);
  border-right: 1px solid rgba(148, 163, 184, 0.12);
  overflow: hidden;
}

.shell-sidebar.collapsed {
  width: var(--sidebar-collapsed);
}

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 76px;
  padding: 18px 18px 14px;
  cursor: pointer;
}

.brand-mark {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-accent) 100%);
  color: #fff;
  box-shadow: 0 10px 22px rgba(37, 99, 235, 0.28);
  flex-shrink: 0;
}

.brand-copy,
.nav-copy,
.user-copy {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.brand-title,
.nav-label,
.user-name {
  font-weight: 700;
}

.brand-subtitle,
.nav-hint,
.user-campus {
  font-size: 12px;
  color: #94a3b8;
}

.sidebar-context {
  margin: 0 14px 10px;
  padding: 14px;
  border-radius: var(--radius-lg);
  background: rgba(148, 163, 184, 0.08);
  border: 1px solid rgba(148, 163, 184, 0.1);
}

.sidebar-context-pill,
.page-pill {
  display: inline-flex;
  align-items: center;
  padding: 0 10px;
  height: 26px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.12);
  font-size: 12px;
  font-weight: 700;
}

.sidebar-context p {
  margin: 12px 0 0;
  line-height: 1.7;
  color: #cbd5e1;
  font-size: 13px;
}

.sidebar-nav {
  display: grid;
  gap: 6px;
  padding: 8px 12px 12px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border: 0;
  border-radius: 12px;
  color: inherit;
  background: transparent;
  cursor: pointer;
  text-align: left;
}

.nav-item.active {
  background: rgba(59, 130, 246, 0.16);
}

.nav-icon {
  width: 18px;
  display: inline-flex;
  justify-content: center;
}

.sidebar-footer {
  margin-top: auto;
  padding: 14px 12px 16px;
}

.user-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.08);
  cursor: pointer;
}

.user-chevron {
  margin-left: auto;
}

.shell-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.shell-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  min-height: var(--topbar-height);
  padding: 0 24px;
  border-bottom: 1px solid var(--border-subtle);
  background: rgba(255, 255, 255, 0.82);
  backdrop-filter: blur(16px);
}

.topbar-left,
.topbar-right,
.page-copy-top {
  display: flex;
  align-items: center;
  gap: 12px;
}

.page-copy {
  display: grid;
  gap: 6px;
}

.page-heading {
  font-size: 22px;
  font-weight: 800;
  color: var(--text-primary);
}

.status-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  height: 34px;
  padding: 0 12px;
  border-radius: 999px;
  background: var(--bg-panel-muted);
  color: var(--text-secondary);
  font-size: 13px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #22c55e;
}

.topbar-icon-btn {
  width: 38px;
  height: 38px;
}

.shell-content {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.notify-panel {
  width: 320px;
  padding: 8px;
}

.notify-header,
.notify-item {
  display: grid;
  gap: 4px;
}

.notify-header {
  grid-template-columns: 1fr auto;
  padding: 8px 10px 10px;
}

.notify-count {
  color: var(--text-secondary);
}

.notify-empty {
  padding: 16px 10px;
  color: var(--text-secondary);
}

.notify-item {
  width: 100%;
  border: 0;
  text-align: left;
  background: transparent;
  padding: 10px;
  border-radius: 10px;
  cursor: pointer;
}

.notify-link {
  width: 100%;
  border: 0;
  background: transparent;
  color: var(--color-primary);
  padding: 10px;
  cursor: pointer;
  text-align: left;
}

@media (max-width: 1024px) {
  .shell-sidebar {
    position: sticky;
    top: 0;
    height: 100vh;
  }

  .shell-topbar {
    padding: 0 16px;
  }
}
</style>
