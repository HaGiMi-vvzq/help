<script setup lang="ts">
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import { useAuthStore } from '@/stores/auth'
import TagEditor from '@/components/profile/TagEditor.vue'
import { ElMessage } from 'element-plus'
import api from '@/api/client'

const auth = useAuthStore()

const editing = ref(false)
const loading = ref(false)
const username = ref('')
const bio = ref('')
const tags = ref<string[]>([])

function loadFromUser() {
  const u = auth.user

  if (!u) {
    username.value = ''
    bio.value = ''
    tags.value = []
    isStudent.value = true
    campus.value = '安州校区'
    college.value = ''
    major.value = ''
    grade.value = ''
    gender.value = ''
    town.value = ''
    return
  }

  username.value = u.username || ''
  bio.value = u.bio || ''
  tags.value = u.skill_tags || []

  let extra: Record<string, any> = {}
  if (u.extra) {
    extra = typeof u.extra === 'string' ? JSON.parse(u.extra) : u.extra
  }

  restoring = true
  isStudent.value = extra.is_student !== false
  campus.value = extra.campus || '安州校区'
  college.value = extra.college || ''
  major.value = extra.major || ''
  grade.value = extra.grade || ''
  gender.value = extra.gender || ''
  town.value = extra.town || ''
  nextTick(() => { restoring = false })
}

watch(() => auth.user, () => {
  loadFromUser()
})
onMounted(() => {
  loadFromUser()
})

const CAMPUS_MAJORS: Record<string, Record<string, string[]>> = {
  '安州校区': {
    '人工智能学院': ['计算机科学与技术','软件工程','电子信息工程','物联网工程','通信工程','人工智能'],
    '智能制造与工程学院': ['机械设计制造及其自动化','智能制造工程','自动化','电气工程及其自动化','能源与环境系统工程','测绘工程','地理信息科学','工程管理','工程造价','土木工程','交通工程'],
    '创意设计学院': ['产品设计','艺术设计学','新媒体艺术','数字媒体技术','智能工程与创意设计','城乡规划','风景园林'],
    '马克思主义学院': [],
    '通识与职素教育中心': [],
    '终身教育学院': [],
  },
  '游仙校区': {
    '健康与教育学院': ['健康服务与管理','学前教育','体育教育','休闲体育','数学与应用数学','英语'],
    '商学院': ['财务管理','金融工程','金融科技','物流工程','电子商务','工商管理'],
    '马克思主义学院': [],
    '通识与职素教育中心': [],
    '终身教育学院': [],
  },
}

let restoring = false
const ANZHOU_TOWNS = ['花荄镇','桑枣镇','黄土镇','塔水镇','秀水镇','河清镇','界牌镇','雎水镇','千佛镇','高川乡']

const isStudent = ref(true)
const campus = ref('安州校区')
const college = ref('')
const major = ref('')
const grade = ref('')
const gender = ref('')
const town = ref('')

const colleges = computed(() => Object.keys(CAMPUS_MAJORS[campus.value] || {}))
const majors = computed(() => CAMPUS_MAJORS[campus.value]?.[college.value] || [])

// Only reset on manual user changes, not during programmatic restore
watch(campus, () => { if (!restoring) { college.value = ''; major.value = '' } })
watch(college, () => { if (!restoring) major.value = '' })

async function analyze() {
  if (!bio.value.trim()) { ElMessage.warning('请先填写个人介绍'); return }
  loading.value = true
  try {
    const { data } = await api.post('/profile/extract-tags', { bio: bio.value })
    if (data.tags && data.tags.length) {
      tags.value = data.tags
      ElMessage.success(`AI 提取了 ${data.tags.length} 个标签`)
    } else {
      ElMessage.info('AI 未提取到标签，请丰富个人介绍内容')
    }
  } catch (e: any) {
    ElMessage.error('AI 分析失败: ' + (e?.response?.data?.detail || e?.message || ''))
  } finally { loading.value = false }
}

async function save() {
  if (!username.value.trim()) { ElMessage.warning('请输入用户名'); return }
  loading.value = true
  try {
    await auth.updateProfile({
      username: username.value.trim(),
      bio: bio.value,
      skill_tags: tags.value,
      school: isStudent.value ? '绵阳城市学院' : '',
      extra: JSON.stringify({
        is_student: isStudent.value,
        campus: isStudent.value ? campus.value : '',
        college: isStudent.value ? college.value : '',
        major: isStudent.value ? major.value : '',
        grade: grade.value,
        gender: gender.value,
        town: town.value,
      }),
    })
    editing.value = false
    loadFromUser()
    ElMessage.success('资料已保存')
  } catch (e: any) {
    ElMessage.error('保存失败: ' + (e?.response?.data?.detail || e?.message || '未知错误'))
  } finally { loading.value = false }
}

function cancel() {
  loadFromUser()
  editing.value = false
}
</script>

<template>
  <div class="profile-page">
    <div class="page-header">
      <h2>我的画像</h2>
      <p>完善你的个人资料，AI 会据此为你精准匹配队友</p>
    </div>

    <div class="profile-content">
      <!-- Username -->
      <el-card shadow="never" class="section-card">
        <template #header><span class="card-title">用户名</span></template>
        <div class="form-item full-width">
          <el-input v-if="editing" v-model="username" placeholder="输入你的用户名" maxlength="30" />
          <span v-else class="form-value">{{ username }}</span>
        </div>
      </el-card>

      <!-- School Info (only for students) -->
      <el-card shadow="never" class="section-card">
        <template #header>
          <div class="card-header-row">
            <span class="card-title">学校信息</span>
            <el-switch v-if="editing" v-model="isStudent" active-text="在校生" inactive-text="校外人士" />
            <el-tag v-else :type="isStudent ? 'success' : 'info'" size="small">{{ isStudent ? '绵阳城市学院' : '校外人士' }}</el-tag>
          </div>
        </template>
        <div v-if="isStudent" class="form-grid">
          <div class="form-item">
            <span class="form-label">学校</span>
            <span class="form-value fixed">绵阳城市学院</span>
          </div>
          <div class="form-item">
            <span class="form-label">校区</span>
            <el-select v-if="editing" v-model="campus" size="small" style="width:100%">
              <el-option v-for="c in Object.keys(CAMPUS_MAJORS)" :key="c" :label="c" :value="c" />
            </el-select>
            <span v-else class="form-value">{{ campus || '未选择' }}</span>
          </div>
          <div class="form-item">
            <span class="form-label">学院</span>
            <el-select v-if="editing" v-model="college" size="small" style="width:100%">
              <el-option v-for="c in colleges" :key="c" :label="c" :value="c" />
            </el-select>
            <span v-else class="form-value">{{ college || '未选择' }}</span>
          </div>
          <div class="form-item">
            <span class="form-label">专业</span>
            <el-select v-if="editing" v-model="major" size="small" style="width:100%" filterable>
              <el-option v-for="m in majors" :key="m" :label="m" :value="m" />
            </el-select>
            <span v-else class="form-value">{{ major || '未选择' }}</span>
          </div>
          <div class="form-item">
            <span class="form-label">年级</span>
            <el-select v-if="editing" v-model="grade" size="small" style="width:100%">
              <el-option v-for="g in ['大一','大二','大三','大四']" :key="g" :label="g" :value="g" />
            </el-select>
            <span v-else class="form-value">{{ grade || '未选择' }}</span>
          </div>
        </div>
        <div v-else class="non-student-hint">校外用户无需填写学校信息，系统将基于你的技能标签和所在区域进行匹配。</div>
      </el-card>

      <!-- Gender (all users) -->
      <el-card shadow="never" class="section-card">
        <template #header><span class="card-title">性别</span></template>
        <div class="form-item">
          <el-radio-group v-if="editing" v-model="gender">
            <el-radio value="男">男</el-radio>
            <el-radio value="女">女</el-radio>
          </el-radio-group>
          <span v-else class="form-value">{{ gender || '未选择' }}</span>
        </div>
      </el-card>

      <!-- Local Area -->
      <el-card shadow="never" class="section-card">
        <template #header><span class="card-title">所在区域</span></template>
        <div class="form-grid">
          <div class="form-item">
            <span class="form-label">区县</span>
            <span class="form-value fixed">安州区</span>
          </div>
          <div class="form-item">
            <span class="form-label">乡镇/街道</span>
            <el-select v-if="editing" v-model="town" size="small" style="width:100%">
              <el-option v-for="t in ANZHOU_TOWNS" :key="t" :label="t" :value="t" />
            </el-select>
            <span v-else class="form-value">{{ town || '未选择' }}</span>
          </div>
        </div>
      </el-card>

      <!-- Skills -->
      <el-card shadow="never" class="section-card">
        <template #header>
          <div class="card-header-row">
            <span class="card-title">技能标签</span>
            <el-button v-if="editing" type="primary" size="small" :loading="loading" @click="analyze">AI 提取标签</el-button>
          </div>
        </template>
        <div class="form-item full-width">
          <span class="form-label">个人介绍</span>
          <el-input v-if="editing" v-model="bio" type="textarea" :rows="4"
            placeholder="用自然语言描述你的技能和兴趣，AI 会自动提取标签" />
          <p v-else class="bio-text">{{ bio || '未填写' }}</p>
        </div>
        <div class="form-item full-width" style="margin-top:12px">
          <span class="form-label">技能标签</span>
          <TagEditor v-if="editing" :tags="tags" @update:tags="tags = $event" />
          <div v-else-if="tags.length" class="tags-display">
            <el-tag v-for="(t, i) in tags" :key="i" size="large" effect="plain" style="margin:4px">{{ t }}</el-tag>
          </div>
          <span v-else class="empty-hint">还没有技能标签</span>
        </div>
      </el-card>

      <div v-if="editing" class="action-bar">
        <el-button @click="cancel">取消</el-button>
        <el-button type="primary" :loading="loading" @click="save">保存资料</el-button>
      </div>
      <div v-else class="action-bar">
        <el-button type="primary" @click="editing = true">编辑资料</el-button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.profile-page { padding: 0; }
.page-header {
  width: 100%;
  max-width: 720px;
  margin: 0 auto 24px;
}
.page-header h2 { font-size: 20px; font-weight: 600; margin-bottom: 4px; }
.page-header p { font-size: 14px; color: rgba(0,0,0,0.45); }

.profile-content {
  width: 100%;
  max-width: 720px;
  margin: 0 auto;
}
.section-card {
  border: 1px solid #e8e8e8; border-radius: 8px; margin-bottom: 16px;
}
.card-title { font-size: 15px; font-weight: 600; }
.card-header-row { display: flex; align-items: center; justify-content: space-between; }

.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px 24px; }
.form-item.full-width { grid-column: 1 / -1; }
.form-label { display: block; font-size: 13px; color: rgba(0,0,0,0.45); margin-bottom: 4px; }
.form-value { font-size: 14px; color: rgba(0,0,0,0.85); }
.form-value.fixed { color: rgba(0,0,0,0.65); }
.bio-text { white-space: pre-wrap; line-height: 1.6; font-size: 14px; margin: 0; }
.tags-display { padding: 4px 0; }
.empty-hint { color: rgba(0,0,0,0.25); font-size: 14px; }
.non-student-hint { color: rgba(0,0,0,0.45); font-size: 14px; padding: 8px 0; }
.action-bar { display: flex; gap: 12px; justify-content: flex-end; margin-top: 8px; }
</style>
