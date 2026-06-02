import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { User } from '@/types'
import * as authApi from '@/api/auth'
import * as profileApi from '@/api/profile'
import { useDebugStore } from '@/stores/debug'

const TOKEN_KEY = 'auth_token'

function loadToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY) || localStorage.getItem(TOKEN_KEY)
}

function saveToken(value: string) {
  sessionStorage.setItem(TOKEN_KEY, value)
}

function clearToken() {
  sessionStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(TOKEN_KEY)
}


export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(loadToken())
  const user = ref<User | null>(null)
  const debug = useDebugStore()

  const isLoggedIn = computed(() => !!token.value)
  const hasProfile = computed(() => !!user.value?.bio)

  async function login(username: string, password: string) {
    const { data } = await authApi.login(username, password)
    token.value = data.access_token
    user.value = data.user
    saveToken(data.access_token)
    debug.success(`登录: ${username}`)
  }

  async function register(payload: { username: string; password: string; bio?: string; school?: string }) {
    const { data } = await authApi.register(payload)
    token.value = data.access_token
    user.value = data.user
    saveToken(data.access_token)
    debug.success(`注册: ${payload.username}`)
  }

  async function fetchMe() {
    if (!token.value) return
    try {
      const { data } = await profileApi.getMe()
      user.value = data
      debug.info(`用户数据恢复: ${data.username}`)
    } catch {
      debug.error('用户数据恢复失败')
      logout()
    }
  }

  async function updateProfile(payload: { username?: string; bio?: string; skill_tags?: string[]; school?: string; extra?: string }) {
    const { data } = await profileApi.updateProfile(payload)
    user.value = data
    debug.success('资料已保存')
  }

  function logout() {
    debug.info('退出登录')
    token.value = null
    user.value = null
    clearToken()
  }

  return { token, user, isLoggedIn, hasProfile, login, register, fetchMe, updateProfile, logout }
})
