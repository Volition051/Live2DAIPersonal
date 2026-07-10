<template>
  <div class="live2d-controller">
    <h2>Live2D 模型管理</h2>
    
    <!-- 上传区域 -->
    <el-card class="upload-section">
      <el-upload
        ref="uploadRef"
        :auto-upload="false"
        :on-change="handleFileChange"
        :limit="1"
        accept=".zip"
        drag
      >
        <el-icon class="el-icon--upload"><upload-filled /></el-icon>
        <div class="el-upload__text">
          拖拽文件到此处或 <em>点击上传</em>
        </div>
        <template #tip>
          <div class="el-upload__tip">
            仅支持 .zip 格式的 Live2D 模型压缩包
          </div>
        </template>
      </el-upload>
      
      <div class="upload-actions">
        <el-button 
          type="primary" 
          @click="uploadFile" 
          :disabled="!selectedFile"
          :loading="uploading"
        >
          上传模型
        </el-button>
        <el-button 
          type="info" 
          @click="loadModels"
          :loading="loadingModels"
        >
          刷新列表
        </el-button>
      </div>
    </el-card>
    
    <!-- 消息提示 -->
    <el-alert
      v-if="message"
      :title="message"
      :type="messageType"
      :closable="true"
      show-icon
      style="margin-top: 20px;"
    />
    
    <!-- 已有模型列表 -->
    <el-card class="existing-models-section" v-loading="loadingModels">
      <template #header>
        <div class="card-header">
          <span>已有模型列表 ({{ existingModels.length }})</span>
          <el-tag type="info" size="small">点击"设为当前"可切换模型</el-tag>
        </div>
      </template>
      
      <el-empty v-if="existingModels.length === 0" description="暂无模型，请上传模型压缩包" />
      
      <el-table v-else :data="existingModels" style="width: 100%">
        <el-table-column prop="name" label="模型名称" width="180">
          <template #default="scope">
            <el-text tag="b">{{ scope.row.name }}</el-text>
          </template>
        </el-table-column>
        <el-table-column prop="path" label="路径" min-width="250">
          <template #default="scope">
            <el-text type="info" size="small" class="model-path">{{ scope.row.path }}</el-text>
          </template>
        </el-table-column>
        <el-table-column label="文件大小" width="120" align="center">
          <template #default="scope">
            <el-text size="small">{{ formatFileSize(scope.row.size) }}</el-text>
          </template>
        </el-table-column>
        <el-table-column label="更新时间" width="180" align="center">
          <template #default="scope">
            <el-text size="small">{{ formatDate(scope.row.modified_time) }}</el-text>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="280" align="center" fixed="right">
          <template #default="scope">
            <el-button 
              size="small" 
              type="primary"
              @click="switchModel(scope.row.path)"
            >
              设为当前
            </el-button>
            <el-button 
              size="small" 
              type="success"
              @click="copyPath(scope.row.path)"
            >
              复制路径
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <!-- 使用说明 -->
      <el-divider />
      <div class="usage-tips">
        <h4>📝 使用说明</h4>
        <ol>
          <li><strong>快速切换</strong>：点击"设为当前"按钮，然后刷新游客端页面即可</li>
          <li><strong>手动配置</strong>：复制路径后，在 <code>Live2DViewers.vue</code> 中修改配置</li>
          <li><strong>批量管理</strong>：上传包含多个模型的压缩包可一次性添加</li>
        </ol>
        <el-alert
          title="💡 提示"
          type="info"
          :closable="false"
          show-icon
          style="margin-top: 12px;"
        >
          切换模型后，需要刷新游客端页面（frontend-tourist）才能看到效果
        </el-alert>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import request from '@/utils/request'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'

const selectedFile = ref(null)
const message = ref('')
const messageType = ref('') // 'success' | 'warning' | 'error' | 'info'
const uploading = ref(false)
const loadingModels = ref(false)
const existingModels = ref([])
const uploadRef = ref(null)

// 组件挂载时加载模型列表
onMounted(() => {
  loadModels()
})

/**
 * 加载已有模型列表
 */
const loadModels = async () => {
  loadingModels.value = true
  try {
    const response = await request.get('/admin/Live2D/models')
    existingModels.value = response.models || []
    
    if (existingModels.value.length > 0) {
      ElMessage.success(`已加载 ${existingModels.value.length} 个模型`)
    }
  } catch (error) {
    console.error('加载模型列表失败:', error)
    // 错误已由响应拦截器处理
  } finally {
    loadingModels.value = false
  }
}

const handleFileChange = (file) => {
  selectedFile.value = file.raw
  message.value = `已选择: ${file.name}`
  messageType.value = 'info'
}

const uploadFile = async () => {
  if (!selectedFile.value) {
    ElMessage.warning('请先选择文件')
    return
  }

  uploading.value = true
  message.value = '正在上传...'
  messageType.value = 'info'

  const formData = new FormData()
  formData.append('file', selectedFile.value)

  try {
    const response = await request.post('/admin/Live2D/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    
    // 上传成功
    message.value = response.message
    messageType.value = 'success'
    
    // 更新模型列表
    if (response.models && response.models.length > 0) {
      // 重新加载完整列表
      await loadModels()
      
      // 显示详细成功信息
      const modelNames = response.models.map(m => m.name).join(', ')
      ElMessage.success({
        message: `成功上传 ${response.models.length} 个模型: ${modelNames}`,
        duration: 3000
      })
    }
    
    // 清空选择
    selectedFile.value = null
    if (uploadRef.value) {
      uploadRef.value.clearFiles()
    }
    
  } catch (error) {
    // 上传失败
    const errorMsg = error.response?.data?.detail || error.response?.data?.message || '上传或处理失败'
    message.value = `❌ ${errorMsg}`
    messageType.value = 'error'
    
    ElMessage.error({
      message: errorMsg,
      duration: 3000
    })
    
    console.error('上传错误:', error)
  } finally {
    uploading.value = false
  }
}

/**
 * 切换模型
 */
const switchModel = async (modelPath) => {
  try {
    // 确认操作
    await ElMessageBox.confirm(
      `确定要切换到模型 "${modelPath}" 吗？\n\n切换后需要刷新游客端页面才能看到效果。`,
      '切换模型',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    //  使用封装好的 request 工具，自动携带认证 token
    const response = await request.post('/admin/Live2D/switch', null, {
      params: { model_path: modelPath }
    })
    
    ElMessage.success({
      message: response.message + '\n请刷新游客端页面以应用更改',
      duration: 3000
    })
    
    // 将当前模型信息存储到 localStorage，供前端读取
    localStorage.setItem('currentLive2DModel', modelPath)
    
  } catch (error) {
    if (error !== 'cancel') {
      const errorMsg = error.response?.data?.detail || '切换失败'
      ElMessage.error(errorMsg)
      console.error('切换模型失败:', error)
    }
  }
}

const copyPath = async (path) => {
  try {
    await navigator.clipboard.writeText(path)
    ElMessage.success({
      message: '路径已复制到剪贴板',
      duration: 2000
    })
  } catch (err) {
    // 降级方案
    const textArea = document.createElement('textarea')
    textArea.value = path
    document.body.appendChild(textArea)
    textArea.select()
    document.execCommand('copy')
    document.body.removeChild(textArea)
    
    ElMessage.success({
      message: '路径已复制',
      duration: 2000
    })
  }
}

/**
 * 格式化文件大小
 */
const formatFileSize = (bytes) => {
  if (!bytes || bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return (bytes / Math.pow(k, i)).toFixed(2) + ' ' + sizes[i]
}

/**
 * 格式化日期
 */
const formatDate = (dateString) => {
  if (!dateString) return '-'
  const date = new Date(dateString)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}
</script>

<style scoped>
.live2d-controller {
  padding: 20px;
  max-width: 1400px;
  margin: 0 auto;
}

h2 {
  color: #303133;
  margin-bottom: 20px;
  font-size: 24px;
}

.upload-section {
  margin-bottom: 20px;
}

.upload-actions {
  margin-top: 20px;
  display: flex;
  gap: 12px;
  justify-content: center;
}

.existing-models-section {
  margin-top: 30px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.model-path {
  font-family: 'Courier New', monospace;
  word-break: break-all;
}

.usage-tips {
  margin-top: 20px;
  padding: 20px;
  background: #f0f9ff;
  border-left: 4px solid #409eff;
  border-radius: 4px;
}

.usage-tips h4 {
  color: #303133;
  margin-bottom: 12px;
  font-size: 16px;
}

.usage-tips ol {
  margin: 12px 0;
  padding-left: 20px;
  color: #606266;
  line-height: 1.8;
}

.usage-tips li {
  margin-bottom: 8px;
}

code {
  background: #f4f4f5;
  padding: 2px 6px;
  border-radius: 3px;
  font-family: 'Courier New', monospace;
  font-size: 13px;
  color: #f56c6c;
}

/* 移动端适配 */
@media screen and (max-width: 768px) {
  .live2d-controller {
    padding: 16px;
  }
  
  .upload-actions {
    flex-direction: column;
  }
  
  .card-header {
    flex-direction: column;
    gap: 8px;
    align-items: flex-start;
  }
}
</style>