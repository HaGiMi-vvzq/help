<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api/client'

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

const props = defineProps<{
  visible: boolean
  needId: number
  needTitle: string
  needDescription: string
  needTags: string[]
}>()

const emit = defineEmits<{
  (e: 'update:visible', v: boolean): void
}>()

const messages = ref<ChatMessage[]>([])
const inputText = ref('')
const sending = ref(false)
const msgList = ref<HTMLElement>()

watch(() => props.visible, async (v) => {
  if (v && messages.value.length === 0) {
    // Fetch match-aware greeting from AI
    sending.value = true
    try {
      const { data } = await api.post(`/needs/${props.needId}/chat`, { messages: [] })
      messages.value.push({ role: 'assistant', content: data.reply })
      scrollToBottom()
    } catch (e: any) {
      messages.value.push({
        role: 'assistant',
        content: '你好！我是AI匹配顾问，让我们来细化你的需求"' + props.needTitle + '"，让匹配更精准。你希望从哪些方面改进匹配结果？'
      })
    } finally {
      sending.value = false
    }
  }
})

function scrollToBottom() {
  nextTick(() => {
    const el = msgList.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

async function send() {
  const text = inputText.value.trim()
  if (!text || sending.value) return

  messages.value.push({ role: 'user', content: text })
  inputText.value = ''
  scrollToBottom()

  sending.value = true
  try {
    const history = messages.value.map(m => ({ role: m.role, content: m.content }))
    const { data } = await api.post(`/needs/${props.needId}/chat`, { messages: history })
    messages.value.push({ role: 'assistant', content: data.reply })
    scrollToBottom()
  } catch (e: any) {
    ElMessage.error('AI回复失败: ' + (e?.response?.data?.detail || e?.message || '未知错误'))
  } finally {
    sending.value = false
  }
}

</script>

<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="emit('update:visible', $event)"
    title="AI 匹配顾问"
    width="520px"
    :close-on-click-modal="false"
    destroy-on-close
    class="concierge-dialog"
  >
    <div class="chat-container">
      <!-- Messages -->
      <div ref="msgList" class="chat-messages">
        <div
          v-for="(m, i) in messages"
          :key="i"
          class="chat-bubble"
          :class="m.role"
        >
          <div class="bubble-avatar">
            <span v-if="m.role === 'assistant'">AI</span>
            <span v-else>我</span>
          </div>
          <div class="bubble-content">{{ m.content }}</div>
        </div>

        <!-- Typing indicator -->
        <div v-if="sending" class="chat-bubble assistant">
          <div class="bubble-avatar"><span>AI</span></div>
          <div class="bubble-content typing">
            <span class="dot" />
            <span class="dot" />
            <span class="dot" />
          </div>
        </div>
      </div>

      <!-- Input area -->
      <div class="chat-input-area">
        <el-input
          v-model="inputText"
          placeholder="输入你的回答..."
          :disabled="sending"
          @keyup.enter="send"
          class="chat-input"
        >
          <template #append>
            <el-button
              :disabled="!inputText.trim() || sending"
              @click="send"
              type="primary"
            >
              发送
            </el-button>
          </template>
        </el-input>
      </div>
    </div>
  </el-dialog>
</template>

<style scoped>
.chat-container {
  display: flex;
  flex-direction: column;
  height: 420px;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 0 4px 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.chat-bubble {
  display: flex;
  gap: 10px;
  max-width: 90%;
}

.chat-bubble.user {
  align-self: flex-end;
  flex-direction: row-reverse;
}

.chat-bubble.assistant {
  align-self: flex-start;
}

.bubble-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
}

.chat-bubble.assistant .bubble-avatar {
  background: #e8f4fd;
  color: #0969da;
}

.chat-bubble.user .bubble-avatar {
  background: #0969da;
  color: #fff;
}

.bubble-content {
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
}

.chat-bubble.assistant .bubble-content {
  background: #f6f8fa;
  border: 1px solid #e8e8e8;
  color: #1f2328;
}

.chat-bubble.user .bubble-content {
  background: #0969da;
  color: #fff;
}

/* Typing dots */
.typing {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 14px 18px;
}
.typing .dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #8b949e;
  animation: type-dot 1.4s infinite ease-in-out both;
}
.typing .dot:nth-child(1) { animation-delay: 0s; }
.typing .dot:nth-child(2) { animation-delay: 0.2s; }
.typing .dot:nth-child(3) { animation-delay: 0.4s; }

@keyframes type-dot {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}

/* Input area */
.chat-input-area {
  border-top: 1px solid #f0f0f0;
  padding-top: 12px;
  flex-shrink: 0;
}

.chat-input :deep(.el-input-group__append) {
  padding: 0;
}
.chat-input :deep(.el-input-group__append .el-button) {
  border-radius: 0 6px 6px 0;
  height: 100%;
}
</style>
