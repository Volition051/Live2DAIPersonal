<template>
  <div class="audio-settings-container">
    <el-card>
      <template #header>
        <span class="card-title">🔊 语音合成配置</span>
      </template>

      <el-form label-width="120px" :model="form" v-loading="loading">
        <!-- 发音人选择 -->
        <el-form-item label="当前发音人">
          <el-select v-model="form.voice" placeholder="请选择发音人" style="width: 300px">
            <el-option
              v-for="v in voiceList"
              :key="v.id"
              :label="`${v.name} (${v.gender === 'male' ? '男' : '女'})`"
              :value="v.id"
            />
          </el-select>
          <el-button type="primary" style="margin-left: 20px" @click="previewVoice">
            试听
          </el-button>
        </el-form-item>

        <!-- 语速 -->
        <el-form-item label="语速">
          <el-slider
            v-model="form.ratePercent"
            :min="-50"
            :max="100"
            :step="5"
            show-input
            :format-tooltip="(val) => val + '%'"
          />
        </el-form-item>

        <!-- 音量 -->
        <el-form-item label="音量">
          <el-slider
            v-model="form.volumePercent"
            :min="-50"
            :max="50"
            :step="5"
            show-input
            :format-tooltip="(val) => val + '%'"
          />
        </el-form-item>

        <!-- 音调 -->
        <el-form-item label="音调">
          <el-slider
            v-model="form.pitchHz"
            :min="-12"
            :max="12"
            :step="1"
            show-input
            :format-tooltip="(val) => val + 'Hz'"
          />
        </el-form-item>

        <el-form-item>
          <el-button type="success" @click="saveSettings">保存配置</el-button>
          <el-button @click="resetForm">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 试听对话框 -->
    <el-dialog v-model="previewVisible" title="试听发音" width="400px">
      <div style="text-align: center;">
        <p>正在生成语音，请稍候...</p>
        <audio ref="previewAudio" controls autoplay style="width: 100%"></audio>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import request from '@/utils/request'

// 发音人列表
const voiceList = ref([])
// 表单数据
const form = reactive({
  voice: 'zh-CN-XiaoxiaoNeural',
  ratePercent: 2,    // 对应 "+2%"
  volumePercent: 0,  // 对应 "+0%"
  pitchHz: -2        // 对应 "-2Hz"
})
const loading = ref(false)

// 试听相关
const previewVisible = ref(false)
const previewAudio = ref(null)

// 获取发音人列表
async function fetchVoices() {
  try {
    const res = await request.get('/admin/tts/voices')
    if (res.success) {
      voiceList.value = res.voices
    }
  } catch (e) {
    ElMessage.error('获取发音人列表失败')
  }
}

// 获取当前配置
async function fetchCurrentConfig() {
  loading.value = true
  try {
    // 假设后端提供了获取配置的接口 /tts/config
    const res = await request.get('/admin/tts/config')
    if (res.success && res.config) {
      form.voice = res.config.voice || 'zh-CN-XiaoxiaoNeural'
      // 后端可能返回字符串如 "+2%" ，需转换为数值
      form.ratePercent = parseFloat(res.config.rate) || 2
      form.volumePercent = parseFloat(res.config.volume) || 0
      form.pitchHz = parseFloat(res.config.pitch) || -2
    }
  } catch (e) {
    ElMessage.warning('无法获取当前配置，使用默认值')
  } finally {
    loading.value = false
  }
}

// 保存配置
async function saveSettings() {
  loading.value = true
  try {
    const payload = {
      voice: form.voice,
      rate: `${form.ratePercent >= 0 ? '+' : ''}${form.ratePercent}%`,
      volume: `${form.volumePercent >= 0 ? '+' : ''}${form.volumePercent}%`,
      pitch: `${form.pitchHz >= 0 ? '+' : ''}${form.pitchHz}Hz`
    }
    await request.post('/admin/tts/config', payload)
    ElMessage.success('语音配置已保存')
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    loading.value = false
  }
}

// 重置为默认
function resetForm() {
  form.voice = 'zh-CN-XiaoxiaoNeural'
  form.ratePercent = 2
  form.volumePercent = 0
  form.pitchHz = -2
}

// 试听当前发音人
async function previewVoice() {
  previewVisible.value = true
  try {
    const payload = {
      text: '你好，这是发音试听语音。',
      voice: form.voice,
      rate: `${form.ratePercent >= 0 ? '+' : ''}${form.ratePercent}%`,
      volume: `${form.volumePercent >= 0 ? '+' : ''}${form.volumePercent}%`,
      pitch: `${form.pitchHz >= 0 ? '+' : ''}${form.pitchHz}Hz`
    }
    const res = await request.post('/admin/tts/text-to-speech', payload, { responseType: 'blob' })
    // 创建 blob URL 给 audio 播放
    const url = URL.createObjectURL(res)
    if (previewAudio.value) {
      previewAudio.value.src = url
      previewAudio.value.load()
    }
  } catch (e) {
    ElMessage.error('试听失败')
  }
}

onMounted(() => {
  fetchVoices()
  fetchCurrentConfig()
})
</script>

<style scoped>
.audio-settings-container {
  padding: 20px;
}
.card-title {
  font-size: 18px;
  font-weight: bold;
}
</style>