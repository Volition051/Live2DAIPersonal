<template>
  <div class="background-settings">
    <h2>🖼️ 背景图片管理</h2>
    <p class="desc">设置游客端 Live2D 数字人右侧面板的背景图片</p>

    <!-- 当前背景预览 -->
    <el-card class="preview-card">
      <template #header>
        <div class="card-header">
          <span>当前背景</span>
          <div class="header-actions">
            <el-button-group size="small" style="margin-right: 8px;">
              <el-button :type="previewMode === 'mobile' ? 'primary' : ''" @click="previewMode = 'mobile'">📱 移动端</el-button>
              <el-button :type="previewMode === 'desktop' ? 'primary' : ''" @click="previewMode = 'desktop'">🖥️ 桌面端</el-button>
            </el-button-group>
            <el-button size="small" @click="openFrontend">
              <el-icon><FullScreen /></el-icon> 打开游客端
            </el-button>
          </div>
        </div>
      </template>
      <div class="preview-row">
        <div class="current-preview">
          <img :src="currentBg || '/static/background.jpg'" alt="当前背景" />
        </div>
        <div class="live-preview" :class="previewMode">
          <div class="live-label">实况效果 · {{ previewMode === 'mobile' ? '移动端' : '桌面端' }}</div>
          <div class="iframe-wrapper">
            <iframe
              :src="touristUrl + '?_t=' + previewKey"
              class="live-iframe"
              frameborder="0"
              scrolling="no"
            />
          </div>
        </div>
      </div>
    </el-card>

    <!-- 上传新背景 -->
    <el-card class="upload-card">
      <template #header>上传新背景</template>
      <el-upload
        ref="uploadRef"
        drag
        action=""
        :auto-upload="false"
        :on-change="handleFileChange"
        :limit="1"
        accept="image/*"
      >
        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
        <div class="el-upload__text">拖拽图片到此处 或 <em>点击选择</em></div>
        <template #tip>
          <div class="el-upload__tip">支持 JPG / PNG / WebP，建议尺寸 800×1200</div>
        </template>
      </el-upload>
      <div style="margin-top: 16px; display: flex; gap: 12px;">
        <el-button
          type="primary"
          :disabled="!selectedFile"
          :loading="uploading"
          @click="handleUpload"
        >
          {{ uploading ? '上传中...' : '上传背景' }}
        </el-button>
        <el-button
          type="warning"
          :loading="resetting"
          @click="handleReset"
        >
          {{ resetting ? '重置中...' : '重置为默认' }}
        </el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled, FullScreen } from '@element-plus/icons-vue'
import request from '@/utils/request'

const uploadRef = ref(null)
const selectedFile = ref(null)
const uploading = ref(false)
const resetting = ref(false)
const currentBg = ref('')
const previewMode = ref('mobile')
const previewKey = ref(0)

const loadCurrentBg = async () => {
  try {
    const res = await request.get('/admin/background')
    if (res.url) {
      currentBg.value = res.url + '?t=' + Date.now()
    }
  } catch {
    // 暂无背景
  }
}

const handleFileChange = (file) => {
  selectedFile.value = file.raw
}

const handleUpload = async () => {
  if (!selectedFile.value) return
  uploading.value = true
  try {
    const formData = new FormData()
    formData.append('file', selectedFile.value)
    await request.post('/admin/background/upload', formData)
    ElMessage.success('背景上传成功')
    uploadRef.value?.clearFiles()
    selectedFile.value = null
    await loadCurrentBg()
    previewKey.value++
  } catch {
    // 错误由 request.js 拦截器处理
  } finally {
    uploading.value = false
  }
}

const handleReset = async () => {
  resetting.value = true
  try {
    await request.post('/admin/background/reset')
    ElMessage.success('已重置为默认背景')
    currentBg.value = ''
    previewKey.value++
  } catch {
    // 错误由拦截器处理
  } finally {
    resetting.value = false
  }
}

// 在新标签页打开游客端
const touristUrl = import.meta.env.VITE_TOURIST_URL || 'http://localhost:8000'
const openFrontend = () => {
  window.open(touristUrl, '_blank')
}

onMounted(() => {
  loadCurrentBg()
})
</script>

<style scoped>
.background-settings {
  max-width: 900px;
  margin: 0 auto;
}

.desc {
  color: #909399;
  margin-bottom: 24px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-actions {
  display: flex;
  align-items: center;
}

.preview-card,
.upload-card {
  margin-bottom: 20px;
}

.preview-row {
  display: flex;
  gap: 20px;
}

.current-preview {
  flex: 1;
  text-align: center;
  min-height: 400px;
  background: #f5f7fa;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.current-preview img {
  max-width: 100%;
  max-height: 500px;
  object-fit: contain;
}

.no-bg {
  color: #c0c4cc;
  font-size: 16px;
}

.live-preview {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
}

.live-preview.mobile {
  width: 375px;
}

.live-preview.desktop {
  width: 480px;
}

.live-label {
  font-size: 12px;
  color: #909399;
  margin-bottom: 8px;
  text-align: center;
}

.iframe-wrapper {
  overflow: hidden;
  border: 1px solid #ebeef5;
  border-radius: 8px;
}

.live-preview.mobile .iframe-wrapper {
  width: 375px;
  height: 600px;
}

.live-preview.mobile .live-iframe {
  width: 375px;
  height: 600px;
}

.live-preview.desktop .iframe-wrapper {
  width: 480px;
  height: 420px;
}

.live-preview.desktop .live-iframe {
  width: 1000px;
  height: 700px;
  transform: scale(0.48);
  transform-origin: top left;
}
</style>
