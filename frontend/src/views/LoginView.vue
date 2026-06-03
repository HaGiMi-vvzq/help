<script setup lang="ts">
import { ref, reactive, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'

const router = useRouter()
const auth = useAuthStore()

const activeTab = ref('login')
const loading = ref(false)
const loginFormRef = ref<FormInstance>()
const registerFormRef = ref<FormInstance>()

const loginForm = reactive({ username: '', password: '' })
const registerForm = reactive({
  username: '',
  password: '',
  confirmPassword: '',
})

const loginRules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码长度不能少于 6 位', trigger: 'blur' },
  ],
}

const validateConfirmPassword = (_rule: unknown, value: string, callback: (error?: Error) => void) => {
  if (value !== registerForm.password) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const registerRules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 20, message: '用户名长度为 2-20 个字符', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码长度不能少于 6 位', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' },
  ],
}

// Re-validate confirmPassword when password changes
watch(() => registerForm.password, () => {
  registerFormRef.value?.validateField('confirmPassword').catch(() => {})
})

function resetRegisterForm() {
  registerForm.username = ''
  registerForm.password = ''
  registerForm.confirmPassword = ''
  registerFormRef.value?.resetFields()
}

async function handleLogin() {
  const valid = await loginFormRef.value?.validate().catch(() => false)
  if (!valid) return
  loading.value = true
  try {
    await auth.login(loginForm.username, loginForm.password)
    router.push(auth.hasProfile ? '/' : '/profile/setup')
  } catch {
    ElMessage.error('用户名或密码错误')
  } finally {
    loading.value = false
  }
}

async function handleRegister() {
  const valid = await registerFormRef.value?.validate().catch(() => false)
  if (!valid) return
  loading.value = true
  try {
    await auth.register({
      username: registerForm.username,
      password: registerForm.password,
    })
    router.push('/')
  } catch {
    ElMessage.error('注册失败，用户名可能已存在')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <!-- Decorative top bar -->
    <div class="login-topbar">
      <span class="topbar-brand">AI Campus</span>
    </div>

    <div class="login-wrapper">
      <!-- Left branding panel -->
      <div class="login-branding">
        <span class="branding-kicker">校园AI互助匹配</span>
        <h2 class="branding-title">校园AI互助匹配</h2>
        <p class="branding-desc">通过 AI 语义理解与智能匹配，帮你找到最合适的队友。<br />无论是课程求助、项目组队还是技能交换，这里都能精准连接。</p>
        <div class="branding-features">
          <div class="feature-item">
            <span class="feature-dot" />
            <span>智能语义匹配</span>
          </div>
          <div class="feature-item">
            <span class="feature-dot" />
            <span>实时进度反馈</span>
          </div>
          <div class="feature-item">
            <span class="feature-dot" />
            <span>校园专属网络</span>
          </div>
        </div>
      </div>

      <!-- Right login card -->
      <el-card shadow="never" class="login-card">
        <div class="card-header-text">
          <h3 class="card-title">{{ activeTab === 'login' ? '欢迎回来' : '创建账号' }}</h3>
          <p class="card-subtitle">{{ activeTab === 'login' ? '登录你的账号继续使用' : '注册一个新账号开始使用' }}</p>
        </div>

        <el-tabs v-model="activeTab" class="login-tabs" @tab-change="activeTab === 'register' && resetRegisterForm()">
          <el-tab-pane label="登录" name="login">
            <el-form
              ref="loginFormRef"
              :model="loginForm"
              :rules="loginRules"
              label-position="top"
              @submit.prevent="handleLogin"
            >
              <el-form-item label="用户名" prop="username">
                <el-input v-model="loginForm.username" placeholder="请输入用户名" />
              </el-form-item>
              <el-form-item label="密码" prop="password">
                <el-input
                  v-model="loginForm.password"
                  type="password"
                  show-password
                  placeholder="请输入密码"
                  @keyup.enter="handleLogin"
                />
              </el-form-item>
              <el-form-item>
                <el-button
                  type="primary"
                  :loading="loading"
                  class="submit-btn"
                  @click="handleLogin"
                >
                  登 录
                </el-button>
              </el-form-item>
            </el-form>
          </el-tab-pane>

          <el-tab-pane label="注册" name="register">
            <el-form
              ref="registerFormRef"
              :model="registerForm"
              :rules="registerRules"
              label-position="top"
              @submit.prevent="handleRegister"
            >
              <el-form-item label="用户名" prop="username">
                <el-input v-model="registerForm.username" placeholder="2-20 个字符" />
              </el-form-item>
              <el-form-item label="密码" prop="password">
                <el-input
                  v-model="registerForm.password"
                  type="password"
                  show-password
                  placeholder="至少 6 位"
                />
              </el-form-item>
              <el-form-item label="确认密码" prop="confirmPassword">
                <el-input
                  v-model="registerForm.confirmPassword"
                  type="password"
                  show-password
                  placeholder="请再次输入密码"
                />
              </el-form-item>
              <el-form-item>
                <el-button
                  type="primary"
                  :loading="loading"
                  class="submit-btn"
                  @click="handleRegister"
                >
                  注 册
                </el-button>
              </el-form-item>
            </el-form>
          </el-tab-pane>
        </el-tabs>
      </el-card>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  background: #f0f2f5;
  display: flex;
  flex-direction: column;
}

.login-topbar {
  height: 56px;
  display: flex;
  align-items: center;
  padding: 0 32px;
  background: #fff;
  border-bottom: 1px solid #e8e8e8;
  flex-shrink: 0;
}

.topbar-brand {
  font-size: 16px;
  font-weight: 700;
  color: #0969da;
}

.login-wrapper {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 24px;
  gap: 80px;
}

/* ---- Left branding panel ---- */
.login-branding {
  max-width: 360px;
  display: none;
}

.branding-kicker {
  display: inline-flex;
  align-items: center;
  height: 24px;
  padding: 0 10px;
  margin-bottom: 14px;
  border-radius: 999px;
  background: rgba(9, 105, 218, 0.1);
  color: #0969da;
  font-size: 12px;
  font-weight: 700;
}

.branding-title {
  font-size: 28px;
  font-weight: 700;
  color: rgba(0, 0, 0, 0.85);
  margin: 0 0 16px;
  line-height: 1.3;
}

.branding-desc {
  font-size: 14px;
  color: rgba(0, 0, 0, 0.45);
  line-height: 1.8;
  margin: 0 0 32px;
}

.branding-features {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.feature-item {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  color: rgba(0, 0, 0, 0.65);
}

.feature-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #0969da;
  flex-shrink: 0;
}

/* ---- Right card ---- */
.login-card {
  width: 420px;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  padding: 8px;
}

.login-card :deep(.el-card__body) {
  padding: 32px;
}

.card-header-text {
  margin-bottom: 8px;
}

.card-title {
  font-size: 20px;
  font-weight: 600;
  color: rgba(0, 0, 0, 0.85);
  margin: 0 0 4px;
}

.card-subtitle {
  font-size: 14px;
  color: rgba(0, 0, 0, 0.45);
  margin: 0;
}

/* ---- Tabs ---- */
.login-tabs :deep(.el-tabs__header) {
  margin-bottom: 24px;
}

.login-tabs :deep(.el-tabs__nav-wrap::after) {
  height: 1px;
  background-color: #e8e8e8;
}

.login-tabs :deep(.el-tabs__item) {
  font-size: 15px;
  padding: 0 20px;
  height: 40px;
  line-height: 40px;
}

.login-tabs :deep(.el-tabs__item.is-active) {
  font-weight: 600;
}

.login-tabs :deep(.el-tabs__active-bar) {
  background-color: #0969da;
}

/* ---- Form ---- */
:deep(.el-form-item__label) {
  font-size: 13px;
  color: rgba(0, 0, 0, 0.85);
  padding-bottom: 4px;
}

.submit-btn {
  width: 100%;
  height: 40px;
  font-size: 15px;
  font-weight: 500;
  border-radius: 6px;
  background: #0969da;
  border-color: #0969da;
}

.submit-btn:hover {
  background: #0858b5;
  border-color: #0858b5;
}

/* ---- Responsive ---- */
@media (min-width: 900px) {
  .login-branding {
    display: block;
  }
}
</style>
