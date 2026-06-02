<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()
</script>

<template>
  <div class="not-found-page">
    <div class="not-found-card">
      <h1>404</h1>
      <p>页面不存在</p>
      <el-button type="primary" @click="router.push('/')">返回首页</el-button>
    </div>
  </div>
</template>

<style scoped>
.not-found-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 60vh;
}
.not-found-card {
  text-align: center;
}
.not-found-card h1 {
  font-size: 64px;
  margin: 0 0 12px;
  color: var(--text-secondary);
}
.not-found-card p {
  margin-bottom: 24px;
  color: var(--text-secondary);
}
</style>
