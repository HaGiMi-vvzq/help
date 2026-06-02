<script setup lang="ts">
defineProps<{ modelValue: string }>()
const emit = defineEmits<{ (e: 'update:modelValue', v: string): void }>()

const types = [
  { value: '求助', icon: 'Search', label: '求助', desc: '寻求帮助解决问题' },
  { value: '组队', icon: 'UserFilled', label: '组队', desc: '组建项目团队' },
  { value: '技能交换', icon: 'Connection', label: '技能交换', desc: '互相学习技能' },
]
</script>

<template>
  <div class="type-selector">
    <div v-for="t in types" :key="t.value" class="type-option" :class="{ selected: modelValue === t.value }" @click="emit('update:modelValue', t.value)">
      <el-icon :size="24"><component :is="t.icon" /></el-icon>
      <span class="type-label">{{ t.label }}</span>
      <span class="type-desc">{{ t.desc }}</span>
    </div>
  </div>
</template>

<style scoped>
.type-selector { display: flex; gap: 12px; }
.type-option {
  flex: 1; padding: 16px 12px; text-align: center; border: 2px solid #e8e8e8; border-radius: 8px;
  cursor: pointer; transition: all 0.2s; display: flex; flex-direction: column; align-items: center; gap: 6px;
}
.type-option:hover { border-color: #91caff; }
.type-option.selected { border-color: #0969da; background: #e6f4ff; }
.type-label { font-size: 14px; font-weight: 600; }
.type-desc { font-size: 12px; color: rgba(0,0,0,0.45); }
</style>
