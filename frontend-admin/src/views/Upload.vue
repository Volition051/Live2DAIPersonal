<template>
  <div class="page-container">
    <el-card>
      <template #header>
        <span>上传景区资料</span>
      </template>

      <div class="upload-area">
        <el-upload
          drag
          action=""
          :auto-upload="false"
          :on-change="handleFileChange"
          :file-list="fileList"
          accept=".pdf,.docx,.xlsx,.txt"
          :limit="1"
        >
          <el-icon class="el-icon--upload"><upload-filled /></el-icon>
          <div class="el-upload__text">
            将PDF文件拖到此处，或<em>点击上传</em>
          </div>
          <template #tip>
            <div class="el-upload__tip">支持 PDF、Word(.docx)、Excel(.xlsx)、TXT 格式</div>
          </template>
        </el-upload>

        <el-button 
          type="primary" 
          style="margin-top: 20px;" 
          :disabled="!selectedFile" 
          :loading="uploading"
          @click="handleUpload"
        >
          确认上传并构建索引
        </el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import request from '@/utils/request'

const router = useRouter()
const uploading = ref(false)
const fileList = ref([])
const selectedFile = ref(null)

// 选择文件
const handleFileChange = (file) => {
  selectedFile.value = file.raw
}

// 上传文件
const handleUpload = async () => {
  if (!selectedFile.value) {
    ElMessage.warning('请先选择文件')
    return
  }

  uploading.value = true
  const formData = new FormData()
  formData.append('file', selectedFile.value)

  try {
    await request.post('/admin/knowledge/upload', formData)
    ElMessage.success('上传成功，索引已构建')
    router.push('/knowledge')
  } finally {
    uploading.value = false
  }
}
</script>

<style scoped>
.page-container {
  padding: 0;
}
.upload-area {
  max-width: 600px;
  margin: 0 auto;
}
</style>