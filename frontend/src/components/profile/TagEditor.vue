<script setup lang="ts">
import { ref } from 'vue'

const props = defineProps<{ tags: string[] }>()
const emit = defineEmits<{ (e: 'update:tags', tags: string[]): void }>()

const newTag = ref('')
const inputVisible = ref(false)
const inputRef = ref<HTMLInputElement>()

function removeTag(index: number) {
  const updated = props.tags.filter((_, i) => i !== index)
  emit('update:tags', updated)
}

function showInput() {
  inputVisible.value = true
  requestAnimationFrame(() => {
    inputRef.value?.focus()
  })
}

function addTag() {
  const tag = newTag.value.trim()
  if (tag && !props.tags.includes(tag)) {
    emit('update:tags', [...props.tags, tag])
  }
  newTag.value = ''
  inputVisible.value = false
}

function handleInputBlur() {
  if (newTag.value.trim()) {
    addTag()
  } else {
    inputVisible.value = false
    newTag.value = ''
  }
}
</script>

<template>
  <div class="tag-editor">
    <div class="tag-list">
      <el-tag
        v-for="(tag, i) in tags"
        :key="i"
        closable
        size="default"
        class="tag-item"
        @close="removeTag(i)"
      >
        {{ tag }}
      </el-tag>

      <el-input
        v-if="inputVisible"
        ref="inputRef"
        v-model="newTag"
        size="small"
        class="tag-input"
        placeholder="新标签..."
        @keyup.enter="addTag"
        @blur="handleInputBlur"
      />

      <el-button
        v-else
        size="small"
        class="add-tag-btn"
        @click="showInput"
      >
        + 添加标签
      </el-button>
    </div>

    <el-empty
      v-if="tags.length === 0 && !inputVisible"
      description="暂无标签，点击上方按钮添加"
      :image-size="40"
    />
  </div>
</template>

<style scoped>
.tag-editor {
  padding: 4px 0;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  min-height: 36px;
}

.tag-item {
  font-size: 12px;
  height: 28px;
  line-height: 26px;
  border-radius: 4px;
  margin: 0;
}

.tag-item :deep(.el-tag__close) {
  color: #656d76;
}

.tag-item :deep(.el-tag__close:hover) {
  color: #1f2328;
  background: rgba(0, 0, 0, 0.06);
}

.tag-input {
  width: 120px;
}

.tag-input :deep(.el-input__inner) {
  height: 28px;
  font-size: 12px;
}

.add-tag-btn {
  font-size: 12px;
  height: 28px;
  padding: 0 12px;
  border: 1px dashed #c0c4cc;
  border-radius: 4px;
  color: #656d76;
}

.add-tag-btn:hover {
  color: #0969da;
  border-color: #0969da;
}
</style>
