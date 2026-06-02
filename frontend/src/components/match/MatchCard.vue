<script setup lang="ts">
import type { MatchResult } from '@/types'
import { computed } from 'vue'

const props = defineProps<{ match: MatchResult; rank: number }>()
const emit = defineEmits<{ (e: 'contact', userId: number): void }>()

const medal = computed(() => ['🥇', '🥈', '🥉'][props.rank - 1] || `#${props.rank}`)
const scoreColor = computed(() => {
  if (props.match.score >= 85) return '#52c41a'
  if (props.match.score >= 70) return '#faad14'
  return 'rgba(0,0,0,0.65)'
})
</script>

<template>
  <el-card shadow="never" class="match-card">
    <div class="match-top">
      <span class="rank">{{ medal }}</span>
      <div class="user-info">
        <span class="user-name">{{ match.username }}</span>
        <span class="user-school">{{ match.school }}</span>
      </div>
      <div class="score-col">
        <span class="score-num" :style="{ color: scoreColor }">{{ match.score }}</span>
        <span class="score-pct">%</span>
      </div>
    </div>
    <el-progress :percentage="match.score" :color="scoreColor" :stroke-width="6" style="margin-bottom:12px" />
    <div class="skill-tags">
      <el-tag v-for="(t, i) in match.skill_tags?.slice(0, 5)" :key="i" size="small" effect="plain" style="margin: 2px">{{ t }}</el-tag>
    </div>
    <blockquote class="ai-reason">"{{ match.reason }}"</blockquote>
    <el-button type="primary" size="small" @click="emit('contact', match.user_id)">联系 TA</el-button>
  </el-card>
</template>

<style scoped>
.match-card { margin-bottom: 16px; transition: transform 0.15s; }
.match-card:hover { transform: translateY(-2px); }
.match-top { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
.rank { font-size: 22px; width: 36px; text-align: center; flex-shrink: 0; }
.user-info { flex: 1; display: flex; flex-direction: column; }
.user-name { font-size: 16px; font-weight: 600; }
.user-school { font-size: 12px; color: rgba(0,0,0,0.45); }
.score-col { text-align: right; }
.score-num { font-size: 30px; font-weight: 700; }
.score-pct { font-size: 14px; color: rgba(0,0,0,0.45); }
.skill-tags { margin-bottom: 10px; }
.ai-reason { border-left: 3px solid #e8e8e8; padding: 8px 16px; margin: 0 0 14px 0; font-size: 13px; color: rgba(0,0,0,0.65); font-style: italic; line-height: 1.6; }
</style>
