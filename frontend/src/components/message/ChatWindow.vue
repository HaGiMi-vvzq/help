<script setup lang="ts">
import { ref, watch, nextTick, onMounted } from 'vue'
import type { MessageItem } from '@/types'
import { useAuthStore } from '@/stores/auth'

const props = defineProps<{
  messages: MessageItem[]
  otherName: string
}>()

const emit = defineEmits<{
  (e: 'send', content: string): void
}>()

const auth = useAuthStore()
const input = ref('')
const container = ref<HTMLElement>()
const inputRef = ref<HTMLInputElement>()

function formatTime(ts: string): string {
  const d = new Date(ts)
  if (isNaN(d.getTime())) return ''

  const now = new Date()
  const diff = now.getTime() - d.getTime()
  const oneDay = 24 * 60 * 60 * 1000

  if (diff < oneDay) {
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }
  return `${d.getMonth() + 1}/${d.getDate()} ${d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`
}

function scrollToBottom() {
  nextTick(() => {
    if (container.value) {
      container.value.scrollTop = container.value.scrollHeight
    }
  })
}

function handleSend() {
  const text = input.value.trim()
  if (!text) return
  emit('send', text)
  input.value = ''
  scrollToBottom()
}

watch(
  () => props.messages.length,
  () => {
    scrollToBottom()
  }
)

onMounted(() => {
  scrollToBottom()
  inputRef.value?.focus()
})
</script>

<template>
  <div class="chat-window">
    <!-- Header -->
    <div class="chat-header">
      <span class="chat-header-name">{{ otherName }}</span>
    </div>

    <!-- Messages -->
    <div ref="container" class="chat-body">
      <div v-if="messages.length === 0" class="chat-empty">
        <el-empty description="暂无消息，发送第一条消息吧" :image-size="48" />
      </div>

      <div
        v-for="m in messages"
        :key="m.id"
        class="msg-row"
        :class="{ mine: m.sender_id === auth.user?.id }"
      >
        <div class="msg-bubble" :class="{ mine: m.sender_id === auth.user?.id }">
          {{ m.content }}
        </div>
        <div class="msg-time">{{ formatTime(m.created_at) }}</div>
      </div>
    </div>

    <!-- Input -->
    <div class="chat-input-bar">
      <div class="chat-input-row">
        <el-input
          ref="inputRef"
          v-model="input"
          placeholder="输入消息..."
          class="chat-input"
          @keyup.enter="handleSend"
        >
          <template #append>
            <el-button
              type="primary"
              :disabled="!input.trim()"
              @click="handleSend"
            >
              发送
            </el-button>
          </template>
        </el-input>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat-window {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-surface);
}

.chat-header {
  padding: 14px 20px;
  border-bottom: 1px solid var(--border-color-light);
  background: var(--bg-surface-hover);
  flex-shrink: 0;
}

.chat-header-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.chat-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  background: var(--bg-page);
}

.chat-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
}

.msg-row { margin-bottom: 16px; display: flex; flex-direction: column; }
.msg-row.mine { align-items: flex-end; }

.msg-bubble {
  max-width: 70%;
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
  background: var(--border-color-light);
  color: var(--text-primary);
}

.msg-bubble.mine {
  background: var(--color-primary);
  color: #fff;
  border-bottom-right-radius: 4px;
}

.msg-bubble:not(.mine) {
  border-bottom-left-radius: 4px;
}

.msg-time {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-top: 4px;
  padding: 0 4px;
}

.chat-input-bar {
  padding: 12px 16px;
  border-top: 1px solid var(--border-color-light);
  background: var(--bg-surface);
  flex-shrink: 0;
}

.chat-input-row { display: flex; align-items: center; }
.chat-input { flex: 1; }

.chat-input :deep(.el-input-group__append) {
  background: var(--color-primary);
  border-color: var(--color-primary);
  padding: 0;
}

.chat-input :deep(.el-input-group__append .el-button) {
  background: transparent;
  border: none;
  color: #fff;
  font-size: 14px;
  padding: 0 16px;
  height: 32px;
}

.chat-input :deep(.el-input-group__append .el-button.is-disabled) {
  background: transparent;
  color: rgba(255,255,255,0.6);
}

.chat-input :deep(.el-input__inner) { border-radius: var(--radius-sm) 0 0 var(--radius-sm); }
.chat-input :deep(.el-input-group__append) { border-radius: 0 var(--radius-sm) var(--radius-sm) 0; }
</style>
