<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useNeedsStore } from '@/stores/needs'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus'
import { MagicStick, EditPen, Refresh } from '@element-plus/icons-vue'
import * as needsApi from '@/api/needs'
import { readDraft, removeDraft, writeDraft } from '@/utils/persistentDrafts'

const router = useRouter()
const store = useNeedsStore()
const authStore = useAuthStore()
const loading = ref(false)
const generating = ref(false)
const polishing = ref(false)
const showPreview = ref(false)
const previewText = ref('')
const previewMode = ref<'polish' | 'generate'>('polish')
const form = reactive({ type: '组队', title: '', description: '', selection_mode: 'single' as 'single' | 'multi' })
const draftKey = `need-create-draft:${authStore.user?.id || authStore.user?.username || 'anonymous'}`

const savedDraft = readDraft<{
  form?: Partial<typeof form>
  previewText?: string
  previewMode?: 'polish' | 'generate'
  showPreview?: boolean
}>(draftKey, {})
if (savedDraft.form) {
  form.type = savedDraft.form.type || form.type
  form.title = savedDraft.form.title || form.title
  form.description = savedDraft.form.description || form.description
  form.selection_mode = savedDraft.form.selection_mode || form.selection_mode
}
previewText.value = savedDraft.previewText || ''
previewMode.value = savedDraft.previewMode || previewMode.value
showPreview.value = Boolean(savedDraft.showPreview && previewText.value)

const hasTitle = computed(() => form.title.trim().length > 0)
const hasDescription = computed(() => form.description.trim().length > 0)

const typeOptions = [
  { value: '求助', label: '求助', icon: '🔍', desc: '寻求帮助' },
  { value: '组队', label: '组队', icon: '👥', desc: '组建团队' },
  { value: '技能交换', label: '技能交换', icon: '🤝', desc: '技能互换' },
]

const needTemplates = [
  {
    type: '组队',
    title: '寻找黑客松项目队友',
    description: '我正在准备一个校园创新项目，希望找到对前端、后端或产品设计感兴趣的同学一起组队。项目目标是做出可演示的 MVP，欢迎有 Vue、Python、UI 设计、路演表达经验的同学联系。',
    selection_mode: 'multi' as const,
  },
  {
    type: '求助',
    title: '课程作业/项目技术求助',
    description: '我在课程项目中遇到技术问题，希望找一位熟悉相关方向的同学一起梳理思路。希望对方能帮我定位问题、讲清楚关键知识点，并给出可执行的改进建议。',
    selection_mode: 'single' as const,
  },
  {
    type: '技能交换',
    title: '技能互助学习搭子',
    description: '我希望和同学进行技能交换：我可以分享自己擅长的内容，也想学习对方熟悉的方向。适合每周约定一次交流，互相给反馈、一起推进小作品。',
    selection_mode: 'multi' as const,
  },
]

const templateOptions = computed(() => needTemplates.filter(t => t.type === form.type))

function applyTemplate(template: typeof needTemplates[number]) {
  form.title = template.title
  form.description = template.description
  form.selection_mode = template.selection_mode
  ElMessage.success('已套用需求模板')
}

watch(
  () => ({
    form: { ...form },
    previewText: previewText.value,
    previewMode: previewMode.value,
    showPreview: showPreview.value,
  }),
  (draft) => {
    const hasContent = draft.form.title || draft.form.description || draft.previewText
    if (hasContent) {
      writeDraft(draftKey, draft)
    } else {
      removeDraft(draftKey)
    }
  },
  { deep: true },
)

async function handleGenerate() {
  if (!hasTitle.value) {
    ElMessage.warning('请先填写标题')
    return
  }
  generating.value = true
  try {
    const { data } = await needsApi.generateDescription({
      need_type: form.type,
      title: form.title,
      selection_mode: form.selection_mode,
    })
    previewText.value = data.result
    previewMode.value = 'generate'
    showPreview.value = true
  } catch (e: any) {
    ElMessage.error('生成失败: ' + (e?.response?.data?.detail || e?.message || '未知错误'))
  } finally {
    generating.value = false
  }
}

async function handlePolish() {
  if (!hasTitle.value || !hasDescription.value) {
    ElMessage.warning('请先填写标题和描述')
    return
  }
  polishing.value = true
  try {
    const { data } = await needsApi.polishDescription({
      need_type: form.type,
      title: form.title,
      description: form.description,
      selection_mode: form.selection_mode,
    })
    previewText.value = data.result
    previewMode.value = 'polish'
    showPreview.value = true
  } catch (e: any) {
    ElMessage.error('润色失败: ' + (e?.response?.data?.detail || e?.message || '未知错误'))
  } finally {
    polishing.value = false
  }
}

function acceptPreview() {
  form.description = previewText.value
  showPreview.value = false
  ElMessage.success('已填入描述')
}

function retryWithFeedback(direction: 'more' | 'rewrite') {
  // Modify description and re-polish/generate with user's adjustment intent
  if (direction === 'more') {
    if (previewMode.value === 'polish') {
      form.description = previewText.value  // Accept, then polish again
      showPreview.value = false
      setTimeout(() => handlePolish(), 100)
    } else {
      showPreview.value = false
      setTimeout(() => handleGenerate(), 100)
    }
  } else {
    showPreview.value = false
    // Let user modify description first, then they can polish again
  }
}

function rejectPreview() {
  showPreview.value = false
  ElMessage.info('已取消，可以修改后重新润色')
}

async function submit() {
  if (!form.title.trim() || !form.description.trim()) {
    ElMessage.warning('请填写标题和描述')
    return
  }
  loading.value = true
  try {
    const need = await store.createNeed({
      type: form.type,
      title: form.title.trim(),
      description: form.description.trim(),
      selection_mode: form.selection_mode,
    })
    removeDraft(draftKey)
    ElMessage.success('发布成功，正在跳转到匹配进度...')
    router.push(`/needs/${need.id}/matches`)
  } catch {
    ElMessage.error('发布失败')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="create-page">
    <h2 class="page-title">发布需求</h2>

    <el-card shadow="never" class="page-card">
      <el-form label-position="top" class="create-form">

        <!-- Type selector -->
        <el-form-item label="需求类型">
          <div class="type-selector">
            <div
              v-for="t in typeOptions"
              :key="t.value"
              class="type-card"
              :class="{ selected: form.type === t.value }"
              @click="form.type = t.value"
            >
              <span class="type-icon">{{ t.icon }}</span>
              <span class="type-label">{{ t.label }}</span>
              <span class="type-desc">{{ t.desc }}</span>
            </div>
          </div>
        </el-form-item>

        <!-- Selection mode -->
        <el-form-item label="匹配方式">
          <el-radio-group v-model="form.selection_mode">
            <el-radio value="single">单选（从匹配结果中选1人）</el-radio>
            <el-radio value="multi">多选（可选择多人合作）</el-radio>
          </el-radio-group>
        </el-form-item>

        <!-- Template library -->
        <el-form-item label="需求模板库">
          <div class="template-list">
            <button
              v-for="tpl in templateOptions"
              :key="tpl.title"
              type="button"
              class="template-item"
              @click="applyTemplate(tpl)"
            >
              <span class="template-title">{{ tpl.title }}</span>
              <span class="template-desc">{{ tpl.description.slice(0, 42) }}...</span>
            </button>
          </div>
        </el-form-item>

        <!-- Title with generate button -->
        <el-form-item label="标题">
          <div class="input-with-ai">
            <el-input
              v-model="form.title"
              placeholder="简短概括你的需求，例如：找一名前端队友参加黑客松"
              maxlength="60"
              show-word-limit
              class="flex-1"
            />
            <el-tooltip content="AI根据标题生成完整描述（参考你的历史风格）" placement="top">
              <el-button
                :disabled="!hasTitle"
                :loading="generating"
                @click="handleGenerate"
                class="ai-btn"
                type="warning"
                plain
              >
                <el-icon :size="15"><MagicStick /></el-icon>
                {{ generating ? '生成中...' : 'AI生成描述' }}
              </el-button>
            </el-tooltip>
          </div>
        </el-form-item>

        <!-- Description with polish button + preview area -->
        <el-form-item label="详细描述">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="6"
            placeholder="详细描述你的需求，AI 会自动分析关键词并匹配最合适的人选..."
            maxlength="500"
            show-word-limit
            class="desc-input"
          />
          <div class="desc-toolbar">
            <span class="desc-hint">写好后可以让AI帮你润色优化</span>
            <el-button
              :disabled="!hasTitle || !hasDescription"
              :loading="polishing"
              @click="handlePolish"
              size="small"
              type="primary"
              plain
            >
              <el-icon :size="14"><EditPen /></el-icon>
              AI润色
            </el-button>
          </div>

          <!-- Preview panel -->
          <div v-if="showPreview" class="preview-panel">
            <div class="preview-header">
              <span class="preview-label">
                {{ previewMode === 'generate' ? 'AI 生成' : 'AI 润色' }}结果
              </span>
            </div>
            <div class="preview-body">{{ previewText }}</div>
            <div class="preview-actions">
              <el-button size="small" @click="rejectPreview">取消</el-button>
              <el-button size="small" @click="retryWithFeedback('more')" :loading="polishing || generating">
                <el-icon :size="13"><Refresh /></el-icon> 再来一次
              </el-button>
              <el-button size="small" @click="retryWithFeedback('rewrite')">
                <el-icon :size="13"><EditPen /></el-icon> 修改后重试
              </el-button>
              <el-button size="small" type="primary" @click="acceptPreview">满意，填入</el-button>
            </div>
          </div>
        </el-form-item>

        <!-- Submit button -->
        <el-button
          type="primary"
          :loading="loading"
          @click="submit"
          size="large"
          class="submit-btn"
        >
          {{ loading ? 'AI 分析中...' : '发布需求 — AI 匹配' }}
        </el-button>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>
.create-page {
  max-width: 680px;
  margin: 0 auto;
  padding: 24px 16px;
}

.page-title {
  font-size: 20px;
  font-weight: 600;
  margin: 0 0 20px 0;
  color: #1a1a2e;
}

.page-card {
  border: 1px solid #e8e8e8 !important;
  border-radius: 8px !important;
}

.create-form :deep(.el-form-item__label) {
  font-size: 14px;
  font-weight: 500;
  color: #1a1a2e;
}

/* -- Type selector -- */
.type-selector {
  display: flex;
  gap: 12px;
  width: 100%;
}
.type-card {
  flex: 1;
  padding: 16px 10px;
  text-align: center;
  border: 2px solid #e8e8e8;
  border-radius: 8px;
  cursor: pointer;
  transition: border-color 0.2s, background 0.2s;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  background: #fff;
}
.type-card:hover { border-color: #0969da; }
.type-card.selected {
  border-color: #0969da;
  background: #eef5ff;
}
.type-icon { font-size: 26px; }
.type-label { font-size: 14px; font-weight: 600; color: #1a1a2e; }
.type-desc { font-size: 12px; color: #656d76; }

/* -- Templates -- */
.template-list {
  display: grid;
  grid-template-columns: 1fr;
  gap: 8px;
  width: 100%;
}
.template-item {
  border: 1px solid #d0d7de;
  border-radius: 8px;
  background: #fff;
  padding: 10px 12px;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}
.template-item:hover {
  border-color: #0969da;
  background: #f6f8fa;
}
.template-title {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: #1f2328;
}
.template-desc {
  display: block;
  margin-top: 3px;
  font-size: 12px;
  color: #656d76;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* -- Input with AI button -- */
.input-with-ai {
  display: flex;
  gap: 10px;
  width: 100%;
}
.flex-1 { flex: 1; }
.ai-btn { flex-shrink: 0; }

/* -- Description toolbar -- */
.desc-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 8px;
}
.desc-hint {
  font-size: 12px;
  color: #656d76;
}

/* -- Preview panel -- */
.preview-panel {
  margin-top: 12px;
  border: 1px solid #d0d7de;
  border-radius: 8px;
  overflow: hidden;
  background: #f6f8fa;
}
.preview-header {
  padding: 10px 14px;
  border-bottom: 1px solid #d0d7de;
  background: #fff;
}
.preview-label {
  font-size: 13px;
  font-weight: 600;
  color: #0969da;
}
.preview-body {
  padding: 14px;
  font-size: 14px;
  line-height: 1.7;
  color: #1f2328;
  white-space: pre-wrap;
  min-height: 80px;
}
.preview-actions {
  display: flex;
  gap: 8px;
  padding: 10px 14px;
  border-top: 1px solid #d0d7de;
  background: #fff;
  justify-content: flex-end;
}

/* -- Submit -- */
.submit-btn {
  width: 100%;
  margin-top: 8px;
  background-color: #0969da;
  border-color: #0969da;
  font-size: 15px;
  height: 44px;
}

/* -- Responsive -- */
@media (max-width: 768px) {
  .type-selector { flex-direction: column; gap: 8px; }
  .input-with-ai { flex-direction: column; gap: 8px; }
  .ai-btn { width: 100%; }
}
</style>
