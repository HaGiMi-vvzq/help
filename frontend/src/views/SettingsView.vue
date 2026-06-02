<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Connection } from '@element-plus/icons-vue'
import * as settingsApi from '@/api/settings'

const apiKey = ref('')
const loading = ref(false)
const saving = ref(false)
const checking = ref(false)
const hasKey = ref(false)
const maskedKey = ref('')

onMounted(load)

async function load() {
  loading.value = true
  try {
    const { data } = await settingsApi.getSettings()
    hasKey.value = data.has_api_key
    maskedKey.value = data.api_key_masked
  } catch {
    // Settings are non-critical for entering the app; keep the page usable.
  } finally {
    loading.value = false
  }
}

function getValidatedKey() {
  const key = apiKey.value.trim()
  if (!key) {
    ElMessage.warning('请输入 API Key')
    return ''
  }
  if (!key.startsWith('sk-')) {
    ElMessage.warning('API Key 应以 sk- 开头')
    return ''
  }
  return key
}

function formatConnectionPath(path?: 'default' | 'local_proxy') {
  if (path === 'local_proxy') return '连接路径：本地代理 127.0.0.1:7897'
  if (path === 'default') return '连接路径：默认网络'
  return ''
}

async function testApiKeyBeforeSave(showSuccess = true) {
  const key = getValidatedKey()
  if (!key) return false

  checking.value = true
  try {
    const { data } = await settingsApi.testApiKey({ deepseek_api_key: key })
    const detail = [data.message, formatConnectionPath(data.connection_path)].filter(Boolean).join('\n')
    if (data.ok) {
      if (showSuccess) {
        await ElMessageBox.alert(detail, '检测通过', {
          type: 'success',
          confirmButtonText: '知道了',
        })
      }
      return true
    }

    await ElMessageBox.alert(detail, '检测未通过', {
      type: 'error',
      confirmButtonText: '知道了',
    })
    return false
  } catch (e: any) {
    await ElMessageBox.alert(e?.response?.data?.detail || e?.message || '检测失败', '检测未通过', {
      type: 'error',
      confirmButtonText: '知道了',
    })
    return false
  } finally {
    checking.value = false
  }
}

async function save() {
  const usable = await testApiKeyBeforeSave(false)
  if (!usable) return

  saving.value = true
  try {
    await settingsApi.updateSettings({ deepseek_api_key: apiKey.value.trim() })
    ElMessage.success('API Key 已保存并立即生效')
    apiKey.value = ''
    load()
  } catch (e: any) {
    ElMessage.error('保存失败: ' + (e?.response?.data?.detail || e?.message || ''))
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="settings-page">
    <h2>系统设置</h2>

    <el-card v-loading="loading" shadow="never" class="section-card">
      <template #header><span class="card-title">DeepSeek API 配置</span></template>

      <div class="setting-row">
        <span class="setting-label">API Key 状态</span>
        <el-tag :type="hasKey ? 'success' : 'danger'">
          {{ hasKey ? '已配置 ' + maskedKey : '未配置' }}
        </el-tag>
      </div>

      <div class="setting-row hint">
        获取 API Key: 前往 <a href="https://platform.deepseek.com/api_keys" target="_blank">DeepSeek 开放平台</a> 创建
      </div>

      <div class="setting-row key-row">
        <el-input
          v-model="apiKey"
          placeholder="sk-..."
          type="password"
          show-password
          class="key-input"
        />
        <el-button :icon="Connection" :loading="checking" :disabled="saving" @click="testApiKeyBeforeSave()">
          检测
        </el-button>
        <el-button type="primary" :loading="saving" :disabled="checking" @click="save">保存</el-button>
      </div>

      <el-alert type="success" :closable="false" show-icon style="margin-top:12px">
        修改 API Key 前会先检测可用性；系统会自动尝试默认网络和本地代理，无需重启后端服务。
      </el-alert>
    </el-card>

    <el-card shadow="never" class="section-card" style="margin-top:16px">
      <template #header><span class="card-title">本地模型</span></template>
      <p class="hint">
        Qwen3-Embedding-0.6B 和 Qwen3-Reranker-0.6B 需要放在 <code>backend/model_cache/</code> 目录，演示包已包含本地模型时无需重新下载。
      </p>
    </el-card>
  </div>
</template>

<style scoped>
.settings-page { max-width: 680px; margin: 0 auto; padding: 24px 16px; }
.settings-page h2 { font-size: 20px; font-weight: 600; margin-bottom: 20px; }
.section-card { border: 1px solid #e8e8e8; border-radius: 8px; }
.card-title { font-size: 15px; font-weight: 600; }
.setting-row { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
.setting-label { font-size: 14px; color: #1f2328; min-width: 100px; }
.key-row { align-items: stretch; }
.key-input { flex: 1; min-width: 0; }
.hint { font-size: 13px; color: #656d76; }
.hint a { color: #0969da; }

@media (max-width: 640px) {
  .setting-row { align-items: flex-start; flex-direction: column; }
  .setting-label { min-width: 0; }
  .key-row { align-items: stretch; }
  .key-row .el-button { width: 100%; }
}
</style>
