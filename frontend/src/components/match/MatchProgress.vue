<script setup lang="ts">
import { computed } from 'vue'
import type { MatchProgress as MP } from '@/types'

const props = defineProps<{ progress: MP[] }>()

const stages = [
  { key: 'tag_extraction', icon: 'Search', label: 'AI 分析需求标签' },
  { key: 'semantic_search', icon: 'Connection', label: '语义向量检索候选人' },
  { key: 'rerank', icon: 'DataAnalysis', label: 'AI 精排打分' },
  { key: 'done',           icon: 'CircleCheck', label: '匹配完成' },
]

const currentStage = computed(() => {
  const last = props.progress[props.progress.length - 1]
  return last?.stage || 'tag_extraction'
})

const msgs = computed(() => {
  const m: Record<string, string> = {}
  for (const p of props.progress) m[p.stage] = p.message
  return m
})
</script>

<template>
  <el-card shadow="never" class="progress-card">
    <div v-for="(s, i) in stages" :key="s.key" class="step-row">
      <div class="step-dot" :class="{
        done: stages.findIndex(x => x.key === currentStage) > i,
        active: currentStage === s.key && currentStage !== 'done',
        finished: currentStage === 'done' && currentStage === s.key,
      }">
        <el-icon v-if="stages.findIndex(x => x.key === currentStage) > i || currentStage === 'done'"><Check /></el-icon>
        <span v-else-if="currentStage === s.key" class="dot-pulse" />
        <span v-else class="dot-idle">{{ i + 1 }}</span>
      </div>
      <div class="step-info">
        <span class="step-label" :class="{ active: currentStage === s.key }">{{ s.label }}</span>
        <span v-if="msgs[s.key]" class="step-msg">{{ msgs[s.key] }}</span>
      </div>
    </div>
  </el-card>
</template>

<style scoped>
.progress-card { margin-bottom: 20px; }
.step-row { display: flex; align-items: flex-start; gap: 14px; padding: 8px 0; }
.step-dot {
  width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center;
  font-size: 14px; font-weight: 600; border: 2px solid #d9d9d9; color: #bfbfbf; flex-shrink: 0;
  transition: all 0.3s;
}
.step-dot.done { background: #52c41a; border-color: #52c41a; color: #fff; }
.step-dot.active { border-color: #0969da; color: #0969da; box-shadow: 0 0 0 3px rgba(9,105,218,0.12); }
.step-dot.finished { background: #52c41a; border-color: #52c41a; color: #fff; }
.dot-pulse { width: 8px; height: 8px; background: #0969da; border-radius: 50%; animation: pulse 1s infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.3} }
.step-info { display: flex; flex-direction: column; padding-top: 4px; }
.step-label { font-size: 14px; font-weight: 500; color: rgba(0,0,0,0.45); }
.step-label.active { color: rgba(0,0,0,0.85); font-weight: 600; }
.step-msg { font-size: 12px; color: rgba(0,0,0,0.45); margin-top: 2px; }
</style>
