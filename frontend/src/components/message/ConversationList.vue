<script setup lang="ts">
import type { ConversationPreview } from '@/types'

defineProps<{
  conversations: ConversationPreview[]
  activeId: number | null
  activeNeedId: number
}>()

const emit = defineEmits<{
  (e: 'select', id: number, needId: number): void
}>()

function formatPreviewTime(ts: string): string {
  if (!ts) return ''
  const d = new Date(ts)
  if (isNaN(d.getTime())) return ''

  const now = new Date()
  const diff = now.getTime() - d.getTime()
  const oneDay = 24 * 60 * 60 * 1000

  if (diff < oneDay) {
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }
  if (diff < 7 * oneDay) {
    const weekdays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
    return weekdays[d.getDay()]
  }
  return `${d.getMonth() + 1}/${d.getDate()}`
}
</script>

<template>
  <div class="conv-list">
    <div v-if="conversations.length > 0" class="conv-scroll">
      <div
        v-for="c in conversations"
        :key="`${c.other_user_id}-${c.need_id}`"
        class="conv-item"
        :class="{ active: c.other_user_id === activeId && c.need_id === activeNeedId }"
        @click="emit('select', c.other_user_id, c.need_id)"
      >
        <div class="conv-row">
          <span class="conv-name">{{ c.other_username }}</span>
          <span v-if="c.last_time" class="conv-time">{{ formatPreviewTime(c.last_time) }}</span>
        </div>
        <div class="conv-preview">{{ c.last_message }}</div>
      </div>
    </div>

    <div v-else class="conv-empty-wrapper">
      <el-empty description="暂无对话" :image-size="60" />
    </div>
  </div>
</template>

<style scoped>
.conv-list {
  height: 100%;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--border-color-light);
  background: var(--bg-surface);
}

.conv-scroll { flex: 1; overflow-y: auto; }

.conv-item {
  padding: 14px 16px;
  cursor: pointer;
  border-bottom: 1px solid var(--border-color-light);
  transition: background var(--transition-fast);
}

.conv-item:hover { background: var(--bg-surface-hover); }

.conv-item.active {
  background: var(--color-primary-bg);
  border-left: 3px solid var(--color-primary);
  padding-left: 13px;
}

.conv-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 4px;
}

.conv-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.conv-time {
  font-size: 12px;
  color: var(--text-tertiary);
  flex-shrink: 0;
  margin-left: 8px;
}

.conv-preview {
  font-size: 13px;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  line-height: 1.4;
}

.conv-empty-wrapper {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-lg);
}
</style>
