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
    type: '组队',
    title: '蓝桥杯/ACM算法竞赛组队',
    description: '寻找算法竞赛队友一起刷题训练。我目前掌握 C++ 和基础数据结构，希望找到能一起参加蓝桥杯或 ACM 区域赛的同学，每周固定时间训练和复盘。',
    selection_mode: 'multi' as const,
  },
  {
    type: '组队',
    title: '大创/互联网+项目招募',
    description: '正在筹备大学生创新创业项目，需要不同方向的同学加入。项目方向偏技术应用，欢迎对产品设计、商业计划书或技术开发感兴趣的同学联系。',
    selection_mode: 'multi' as const,
  },
  {
    type: '求助',
    title: '课程作业/项目技术求助',
    description: '我在课程项目中遇到技术问题，希望找一位熟悉相关方向的同学一起梳理思路。希望对方能帮我定位问题、讲清楚关键知识点，并给出可执行的改进建议。',
    selection_mode: 'single' as const,
  },
  {
    type: '求助',
    title: '考试/面试经验指导',
    description: '正在准备即将到来的考试或面试，希望能请教有经验的同学。主要想了解复习重点、常见题型和面试流程，希望能约一次线上交流。',
    selection_mode: 'single' as const,
  },
  {
    type: '技能交换',
    title: '技能互助学习搭子',
    description: '我希望和同学进行技能交换：我可以分享自己擅长的内容，也想学习对方熟悉的方向。适合每周约定一次交流，互相给反馈、一起推进小作品。',
    selection_mode: 'multi' as const,
  },
  {
    type: '技能交换',
    title: '语言/口语练习交换',
    description: '我想练习英语口语或某个方向的专业表达，同时可以帮助对方学习我擅长的技术或课程内容。希望找到能定期练习、互相纠正的学习伙伴。',
    selection_mode: 'single' as const,
  },
]

const templateOptions = computed(() => needTemplates.filter(t => t.type === form.type))

// Template edit dialog
const showTemplateDialog = ref(false)
const editingTemplate = reactive({ title: '', description: '', selection_mode: 'single' as 'single' | 'multi' })

function openTemplateEditor(template: typeof needTemplates[number]) {
  editingTemplate.title = template.title
  editingTemplate.description = template.description
  editingTemplate.selection_mode = template.selection_mode
  showTemplateDialog.value = true
}

function confirmTemplateApply() {
  form.title = editingTemplate.title
  form.description = editingTemplate.description
  form.selection_mode = editingTemplate.selection_mode
  showTemplateDialog.value = false
  ElMessage.success('已套用并自定义需求模板')
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

function retryAi() {
  if (previewMode.value === 'polish') {
    form.description = previewText.value
    showPreview.value = false
    setTimeout(() => handlePolish(), 100)
  } else {
    showPreview.value = false
    setTimeout(() => handleGenerate(), 100)
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

        <!-- Type selector + selection mode -->
        <el-form-item label="需求类型">
          <div class="type-area">
            <div class="type-pills">
              <button
                v-for="t in typeOptions"
                :key="t.value"
                type="button"
                class="type-pill"
                :class="{ selected: form.type === t.value }"
                @click="form.type = t.value"
              >
                <span class="pill-icon">{{ t.icon }}</span>
                <span class="pill-label">{{ t.label }}</span>
              </button>
            </div>
            <div class="selection-toggle">
              <button
                type="button"
                class="toggle-btn"
                :class="{ active: form.selection_mode === 'single' }"
                @click="form.selection_mode = 'single'"
              >
                单人匹配
              </button>
              <button
                type="button"
                class="toggle-btn"
                :class="{ active: form.selection_mode === 'multi' }"
                @click="form.selection_mode = 'multi'"
              >
                多人组队
              </button>
            </div>
          </div>
        </el-form-item>

        <!-- Quick templates -->
        <el-form-item label="快速模板">
          <div class="template-chips">
            <button
              v-for="tpl in templateOptions"
              :key="tpl.title"
              type="button"
              class="template-chip"
              @click="openTemplateEditor(tpl)"
            >
              {{ tpl.title }}
            </button>
          </div>
        </el-form-item>

        <!-- Template edit dialog -->
        <el-dialog v-model="showTemplateDialog" title="自定义模板内容" width="560px" :close-on-click-modal="false">
          <el-form label-position="top">
            <el-form-item label="标题">
              <el-input v-model="editingTemplate.title" maxlength="60" show-word-limit />
            </el-form-item>
            <el-form-item label="详细描述">
              <el-input
                v-model="editingTemplate.description"
                type="textarea"
                :rows="6"
                maxlength="500"
                show-word-limit
              />
            </el-form-item>
            <el-form-item label="匹配方式">
              <el-radio-group v-model="editingTemplate.selection_mode">
                <el-radio value="single">单选（选1人）</el-radio>
                <el-radio value="multi">多选（可选多人）</el-radio>
              </el-radio-group>
            </el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="showTemplateDialog = false">取消</el-button>
            <el-button type="primary" @click="confirmTemplateApply">确认套用</el-button>
          </template>
        </el-dialog>

        <!-- Title with AI generate -->
        <el-form-item label="标题">
          <div class="input-with-ai">
            <el-input
              v-model="form.title"
              placeholder="简短概括你的需求，例如：找一名前端队友参加黑客松"
              maxlength="60"
              show-word-limit
              class="flex-1"
            />
            <el-tooltip content="AI根据标题生成完整描述" placement="top">
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

        <!-- Description with AI polish + preview -->
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
              <el-button size="small" @click="retryAi" :loading="polishing || generating">
                <el-icon :size="13"><Refresh /></el-icon> 再来一次
              </el-button>
              <el-button size="small" type="primary" @click="acceptPreview">满意，填入</el-button>
            </div>
          </div>
        </el-form-item>

        <!-- Submit -->
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
  color: var(--text-primary);
}

.page-card {
  border: 1px solid var(--border-subtle) !important;
  border-radius: var(--radius-lg) !important;
}

.create-form :deep(.el-form-item__label) {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
}

/* -- Type area: pills + selection toggle -- */
.type-area {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  width: 100%;
}

.type-pills {
  display: flex;
  gap: 8px;
}

.type-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 18px;
  border: 1.5px solid var(--border-soft);
  border-radius: var(--radius-xl);
  background: var(--bg-panel);
  cursor: pointer;
  transition: border-color var(--transition-fast), background var(--transition-fast);
  font-size: 14px;
  color: var(--text-primary);
}

.type-pill:hover {
  border-color: var(--color-primary-hover);
}

.type-pill.selected {
  border-color: var(--color-primary);
  background: var(--color-primary-bg);
  color: var(--color-primary);
  font-weight: 600;
}

.pill-icon { font-size: 18px; }
.pill-label { white-space: nowrap; }

.selection-toggle {
  display: flex;
  gap: 2px;
  padding: 3px;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  background: var(--bg-panel-muted);
}

.toggle-btn {
  padding: 5px 14px;
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  cursor: pointer;
  font-size: 13px;
  color: var(--text-secondary);
  transition: background var(--transition-fast), color var(--transition-fast);
}

.toggle-btn.active {
  background: var(--bg-panel);
  color: var(--text-primary);
  font-weight: 600;
  box-shadow: var(--shadow-xs);
}

.toggle-btn:hover:not(.active) {
  color: var(--text-primary);
}

/* -- Templates: horizontal chip row -- */
.template-chips {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding-bottom: 4px;
  scrollbar-width: thin;
  -webkit-overflow-scrolling: touch;
}

.template-chip {
  flex-shrink: 0;
  padding: 6px 16px;
  border: 1px solid var(--border-soft);
  border-radius: 999px;
  background: var(--bg-panel);
  cursor: pointer;
  font-size: 13px;
  color: var(--text-primary);
  white-space: nowrap;
  transition: border-color var(--transition-fast), background var(--transition-fast), color var(--transition-fast);
}

.template-chip:hover {
  border-color: var(--color-primary);
  background: var(--color-primary-bg);
  color: var(--color-primary);
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
  color: var(--text-tertiary);
}

/* -- Preview panel -- */
.preview-panel {
  margin-top: 12px;
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-md);
  overflow: hidden;
  background: var(--bg-panel-muted);
}
.preview-header {
  padding: 10px 14px;
  border-bottom: 1px solid var(--border-soft);
  background: var(--bg-panel);
}
.preview-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-primary);
}
.preview-body {
  padding: 14px;
  font-size: 14px;
  line-height: 1.7;
  color: var(--text-primary);
  white-space: pre-wrap;
  min-height: 80px;
}
.preview-actions {
  display: flex;
  gap: 8px;
  padding: 10px 14px;
  border-top: 1px solid var(--border-soft);
  background: var(--bg-panel);
  justify-content: flex-end;
}

/* -- Submit -- */
.submit-btn {
  width: 100%;
  margin-top: 8px;
  background-color: var(--color-primary);
  border-color: var(--color-primary);
  font-size: 15px;
  height: 44px;
}

/* -- Responsive -- */
@media (max-width: 768px) {
  .type-area {
    flex-direction: column;
    align-items: flex-start;
  }

  .type-pills {
    width: 100%;
  }

  .type-pill {
    flex: 1;
    justify-content: center;
  }

  .input-with-ai {
    flex-direction: column;
    gap: 8px;
  }

  .ai-btn {
    width: 100%;
  }
}
</style>
