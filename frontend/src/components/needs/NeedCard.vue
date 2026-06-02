<script setup lang="ts">
import type { Need } from '@/types'

defineProps<{ need: Need }>()
const emit = defineEmits<{ (e: 'click'): void }>()

function typeTag(type: string) {
  return type === '求助' ? 'warning' : type === '组队' ? 'success' : 'info'
}
</script>

<template>
  <el-card shadow="never" class="need-card" @click="emit('click')">
    <div class="card-head">
      <el-tag :type="typeTag(need.type)" size="small">{{ need.type }}</el-tag>
      <span class="card-time">{{ need.created_at.slice(0, 10) }}</span>
    </div>
    <h3 class="card-title">{{ need.title }}</h3>
    <p class="card-desc">{{ need.description.slice(0, 80) }}{{ need.description.length > 80 ? '...' : '' }}</p>
  </el-card>
</template>

<style scoped>
.need-card { cursor: pointer; transition: transform 0.15s; }
.need-card:hover { transform: translateY(-2px); }
.card-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
.card-time { font-size: 12px; color: rgba(0,0,0,0.45); }
.card-title { font-size: 16px; font-weight: 600; margin-bottom: 6px; }
.card-desc { font-size: 13px; color: rgba(0,0,0,0.45); line-height: 1.5; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
</style>
