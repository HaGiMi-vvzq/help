<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, inject } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { ConversationPreview, MessageItem } from '@/types'
import * as messagesApi from '@/api/messages'
import ConversationList from '@/components/message/ConversationList.vue'
import ChatWindow from '@/components/message/ChatWindow.vue'

const route = useRoute()
const refreshNotifications = inject<() => void>('refreshNotifications', () => {})

const conversations = ref<ConversationPreview[]>([])
const messages = ref<MessageItem[]>([])
const activeUserId = ref<number | null>(null)
const activeNeedId = ref<number>(0)
const loading = ref(false)

const isMobile = ref(window.innerWidth < 768)
const showList = ref(true)

const activeUserName = computed(() =>
  conversations.value.find(
    (c) => c.other_user_id === activeUserId.value && c.need_id === activeNeedId.value,
  )?.other_username ||
  conversations.value.find((c) => c.other_user_id === activeUserId.value)?.other_username ||
  ''
)

const hasActiveConversation = computed(() => activeUserId.value !== null)

function onResize() {
  isMobile.value = window.innerWidth < 768
}

onMounted(() => {
  loadConversations()
  window.addEventListener('resize', onResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', onResize)
})

watch(
  () => [route.params.userId, route.query.needId],
  ([id, needId]) => {
    if (id) {
      const needIdFromQuery = Number(needId) || 0
      selectConversation(Number(id), needIdFromQuery)
    }
  },
  { immediate: true }
)

async function loadConversations() {
  try {
    const { data } = await messagesApi.getConversations()
    conversations.value = data
  } catch {
    /* ignore */
  }
}

async function selectConversation(userId: number, initialNeedId: number = 0) {
  activeUserId.value = userId
  loading.value = true

  const listedNeedId = conversations.value.find((c) => c.other_user_id === userId)?.need_id || 0
  activeNeedId.value = initialNeedId || listedNeedId || 0

  try {
    const { data } = await messagesApi.getMessages(userId, activeNeedId.value || undefined)
    messages.value = data
    if (!activeNeedId.value && data.length > 0 && data[0].need_id) {
      activeNeedId.value = data[0].need_id
    }
  } catch {
    messages.value = []
  } finally {
    loading.value = false
  }

  // Mark messages as read
  try { await messagesApi.markRead(userId, activeNeedId.value || undefined) } catch (e: any) { console.error('markRead failed:', e?.response?.status, e?.response?.data || e?.message || e) }
  refreshNotifications()
  if (isMobile.value) {
    showList.value = false
  }
}

function handleBackToList() {
  showList.value = true
}

async function handleSend(content: string) {
  if (!activeUserId.value) return
  try {
    const { data } = await messagesApi.sendMessage({
      need_id: activeNeedId.value,
      receiver_id: activeUserId.value,
      content,
    })
    messages.value.push(data)
    loadConversations()
  } catch (e: any) {
    ElMessage.error('发送失败: ' + (e?.response?.data?.detail || e?.message || '未知错误'))
  }
}
</script>

<template>
  <div class="messages-page">
    <div class="page-header">
      <h1 class="page-title">站内消息</h1>
    </div>

    <el-card shadow="never" class="messages-card" :body-style="{ padding: '0' }">
      <div class="msg-layout">
        <!-- Left: Conversation List -->
        <div
          class="msg-sidebar"
          :class="{ 'is-active': showList }"
        >
          <ConversationList
            :conversations="conversations"
            :active-id="activeUserId"
            :active-need-id="activeNeedId"
            @select="selectConversation"
          />
        </div>

        <!-- Right: Chat Window -->
        <div
          class="msg-main"
          :class="{ 'is-active': !showList || !isMobile }"
        >
          <!-- Mobile back button -->
          <div v-if="isMobile && hasActiveConversation && !showList" class="mobile-back-row">
            <el-button type="primary" link @click="handleBackToList">
              <el-icon><ArrowLeft /></el-icon>
              返回对话列表
            </el-button>
          </div>

          <div v-if="hasActiveConversation" v-loading="loading" class="chat-container">
            <ChatWindow
              :messages="messages"
              :other-name="activeUserName"
              @send="handleSend"
            />
          </div>

          <div v-else class="empty-placeholder">
            <el-empty description="选择一个对话开始聊天" :image-size="80" />
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.messages-page {
  padding: var(--space-lg);
  height: calc(100vh - var(--topbar-height) - 2 * var(--space-lg));
  display: flex;
  flex-direction: column;
}

.page-header {
  margin-bottom: var(--space-md);
  flex-shrink: 0;
}

.page-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.messages-card {
  flex: 1;
  min-height: 0;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.messages-card :deep(.el-card__body) { height: 100%; }

.msg-layout { display: flex; height: 100%; }

.msg-sidebar { width: 280px; flex-shrink: 0; }

.msg-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
}

.mobile-back-row {
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-color-light);
  flex-shrink: 0;
  background: var(--bg-surface-hover);
}

.chat-container { flex: 1; min-height: 0; }

.empty-placeholder {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

@media (max-width: 767px) {
  .messages-page {
    padding: var(--space-md);
    height: calc(100vh - var(--topbar-height));
  }

  .msg-layout { position: relative; }

  .msg-sidebar { width: 100%; display: none; }
  .msg-sidebar.is-active { display: block; }

  .msg-main { display: none; }
  .msg-main.is-active { display: flex; }
}
</style>
