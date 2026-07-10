<template>
  <div class="appearance-page">
    <!-- 左侧设置区 -->
    <div class="settings-area">
      <h2> 前端外观设置</h2>
      <p class="desc">自定义游客端 Chat 页面的外观样式</p>

      <el-tabs v-model="activeTab">
        <el-tab-pane label="导航栏" name="header">
          <el-card><template #header>顶部导航栏</template>
            <el-form label-width="100px">
              <el-form-item label="品牌标题">
                <el-input v-model="form.brand_title" placeholder="灵山胜境 · 智能导游" />
              </el-form-item>
              <el-form-item label="文字颜色">
                <el-color-picker v-model="form.header_text_color" />
                <span class="color-value">{{ form.header_text_color || '#2c3e50' }}</span>
              </el-form-item>
              <el-form-item label="背景颜色">
                <el-color-picker v-model="form.header_bg" show-alpha />
                <span class="color-value">{{ form.header_bg }}</span>
              </el-form-item>
              <el-form-item label="背景图片">
                <div style="display:flex;gap:8px;width:100%">
                  <el-input v-model="form.header_bg_image" placeholder="留空使用纯色，或上传图片" style="flex:1" />
                  <el-button @click="triggerUpload('header_bg_image')">📎 上传</el-button>
                </div>
              </el-form-item>
            </el-form>
          </el-card>
          <el-card style="margin-top:16px"><template #header>功能按钮显隐</template>
            <el-form label-width="80px">
              <el-form-item label="🗺️ 地图"><el-switch v-model="form.btn_map" active-value="true" inactive-value="false" /></el-form-item>
              <el-form-item label="🎯 推荐"><el-switch v-model="form.btn_recommend" active-value="true" inactive-value="false" /></el-form-item>
              <el-form-item label="🎬 视频"><el-switch v-model="form.btn_video" active-value="true" inactive-value="false" /></el-form-item>
              <el-form-item label="🙋 动作"><el-switch v-model="form.btn_action" active-value="true" inactive-value="false" /></el-form-item>
            </el-form>
          </el-card>
          <el-card style="margin-top:16px"><template #header>欢迎卡片</template>
            <el-form label-width="80px">
              <el-form-item label="欢迎标题"><el-input v-model="form.welcome_title" placeholder="您好，我是您的智能导游" /></el-form-item>
              <el-form-item label="欢迎文字"><el-input v-model="form.welcome_text" type="textarea" :rows="2" /></el-form-item>
              <el-form-item label="提示词（逗号分隔）"><el-input v-model="form.welcome_tips" placeholder="🕐 表演时间,📏 景点参数,🗺️ 游览路线,⭐ 猜你喜欢" /></el-form-item>
            </el-form>
          </el-card>
        </el-tab-pane>

        <el-tab-pane label="对话框" name="chat">
          <el-card><template #header>聊天区域</template>
            <el-form label-width="100px">
              <el-form-item label="背景颜色">
                <el-color-picker v-model="form.chat_bg" show-alpha />
                <span class="color-value">{{ form.chat_bg || 'transparent' }}</span>
              </el-form-item>
              <el-form-item label="背景图片">
                <div style="display:flex;gap:8px;width:100%">
                  <el-input v-model="form.chat_bg_image" placeholder="留空使用纯色，或上传图片" style="flex:1" />
                  <el-button @click="triggerUpload('chat_bg_image')">📎 上传</el-button>
                </div>
              </el-form-item>
              <el-form-item label="字体颜色">
                <el-color-picker v-model="form.chat_text_color" />
                <span class="color-value">{{ form.chat_text_color || '#2c3e50' }}</span>
              </el-form-item>
              <el-form-item label="字体大小">
                <el-input-number v-model="form.chat_font_size" :min="12" :max="20" /> px
              </el-form-item>
            </el-form>
          </el-card>
          <el-card style="margin-top:16px"><template #header>消息气泡</template>
            <el-form label-width="100px">
              <el-form-item label="AI 气泡背景">
                <el-color-picker v-model="form.bubble_ai_bg" show-alpha />
                <span class="color-value">{{ form.bubble_ai_bg || '#ffffff' }}</span>
              </el-form-item>
              <el-form-item label="用户气泡背景">
                <el-color-picker v-model="form.bubble_user_bg" />
                <span class="color-value">{{ form.bubble_user_bg || '#4a7c59' }}</span>
              </el-form-item>
              <el-form-item label="用户气泡文字">
                <el-color-picker v-model="form.bubble_user_text" />
                <span class="color-value">{{ form.bubble_user_text || '#ffffff' }}</span>
              </el-form-item>
            </el-form>
          </el-card>
          <el-card style="margin-top:16px"><template #header>输入框</template>
            <el-form label-width="100px">
              <el-form-item label="背景颜色">
                <el-color-picker v-model="form.input_bg" show-alpha />
                <span class="color-value">{{ form.input_bg || '#ffffff' }}</span>
              </el-form-item>
              <el-form-item label="背景图片">
                <div style="display:flex;gap:8px;width:100%">
                  <el-input v-model="form.input_bg_image" placeholder="留空使用纯色，或上传图片" style="flex:1" />
                  <el-button @click="triggerUpload('input_bg_image')">📎 上传</el-button>
                </div>
              </el-form-item>
              <el-form-item label="边框颜色">
                <el-color-picker v-model="form.input_border" show-alpha />
                <span class="color-value">{{ form.input_border || '#e5e0d8' }}</span>
              </el-form-item>
              <el-form-item label="发送按钮色">
                <el-color-picker v-model="form.input_send_btn" />
                <span class="color-value">{{ form.input_send_btn || '#4a7c59' }}</span>
              </el-form-item>
              <el-form-item label="占位文字">
                <el-input v-model="form.input_placeholder" placeholder="输入您的问题，按 Enter 发送..." />
              </el-form-item>
            </el-form>
          </el-card>
          <el-card style="margin-top:16px"><template #header>其他</template>
            <el-form label-width="100px">
              <el-form-item label="Live2D面板">
                <el-switch v-model="form.show_live2d" active-value="true" inactive-value="false" />
              </el-form-item>
              <el-form-item label="地图默认展开">
                <el-switch v-model="form.map_default_open" active-value="true" inactive-value="false" />
              </el-form-item>
            </el-form>
          </el-card>
        </el-tab-pane>

        <el-tab-pane label="右侧背景" name="background">
          <el-card><template #header>Live2D 右侧面板背景</template>
            <div class="bg-preview-img">
              <img :src="currentBg || '/static/background.jpg'" alt="当前背景" />
            </div>
          </el-card>
          <el-card style="margin-top:16px"><template #header>上传新背景</template>
            <el-upload ref="uploadRef" drag action="" :auto-upload="false" :on-change="handleFileChange" :limit="1" accept="image/*">
              <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
              <div class="el-upload__text">拖拽图片 或 <em>点击选择</em></div>
              <template #tip><div class="el-upload__tip">JPG / PNG / WebP，建议 800×1200</div></template>
            </el-upload>
            <div style="margin-top:16px;display:flex;gap:12px">
              <el-button type="primary" :disabled="!selectedFile" :loading="uploading" @click="handleUpload">{{ uploading?'上传中...':'上传背景' }}</el-button>
              <el-button type="warning" :loading="resettingBg" @click="handleResetBg">{{ resettingBg?'重置中...':'重置为默认' }}</el-button>
            </div>
          </el-card>
        </el-tab-pane>
      </el-tabs>

      <div style="margin-top:24px;display:flex;gap:12px">
        <el-button type="success" size="large" :loading="saving" @click="handleSave"> 保存外观设置</el-button>
        <el-button size="large" :loading="resetting" @click="handleResetAll">↺ 恢复全部默认</el-button>
      </div>
    </div>

    <!-- 右侧固定预览 -->
    <div class="preview-sidebar">
      <div class="preview-header">
        <span>实况预览</span>
        <el-button-group size="small">
          <el-button :type="previewMode === 'mobile' ? 'primary' : ''" @click="previewMode = 'mobile'">📱</el-button>
          <el-button :type="previewMode === 'desktop' ? 'primary' : ''" @click="previewMode = 'desktop'">🖥️</el-button>
        </el-button-group>
        <el-button size="small" @click="openFrontend" circle><el-icon><FullScreen /></el-icon></el-button>
      </div>
      <div class="preview-frame" :class="previewMode">
        <iframe :src="touristUrl + '?_t=' + previewKey" frameborder="0" scrolling="no" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled, FullScreen } from '@element-plus/icons-vue'
import request from '@/utils/request'

const activeTab = ref('header')
const saving = ref(false)
const resetting = ref(false)
const previewMode = ref('mobile')
const previewKey = ref(0)
const touristUrl = import.meta.env.VITE_TOURIST_URL || 'http://localhost:8000'

const form = reactive({
  header_bg: 'rgba(255,255,255,0.85)', header_bg_image: '', header_text_color: '#2c3e50',
  btn_map: 'true', btn_recommend: 'true', btn_video: 'true', btn_action: 'true',
  welcome_title: '您好，我是您的智能导游',
  welcome_text: '嗨，欢迎来到灵山胜境！有什么想了解的，尽管问我哦～',
  welcome_tips: '🕐 表演时间,📏 景点参数,🗺️ 游览路线,⭐ 猜你喜欢',
  brand_title: '灵山胜境 · 智能导游',
  chat_bg: 'transparent', chat_bg_image: '', chat_text_color: '#2c3e50', chat_font_size: '15',
  bubble_ai_bg: '#ffffff', bubble_user_bg: '#4a7c59', bubble_user_text: '#ffffff',
  input_bg: '#ffffff', input_bg_image: '', input_border: '#e5e0d8', input_send_btn: '#4a7c59',
  input_placeholder: '输入您的问题，按 Enter 发送...',
  show_live2d: 'true', map_default_open: 'false',
})

const loadAppearance = async () => {
  try { const res = await request.get('/admin/appearance'); Object.assign(form, res) } catch {}
}
const handleSave = async () => {
  saving.value = true
  try { await request.post('/admin/appearance', { ...form }); ElMessage.success('已保存'); previewKey.value++ } catch {} finally { saving.value = false }
}
const handleResetAll = async () => {
  resetting.value = true
  try { await request.post('/admin/appearance/reset'); await loadAppearance(); ElMessage.success('已恢复默认'); previewKey.value++ } catch {} finally { resetting.value = false }
}

// 背景图
const uploadRef = ref(null); const selectedFile = ref(null)
const uploading = ref(false); const resettingBg = ref(false); const currentBg = ref('')
const loadCurrentBg = async () => {
  try { const res = await request.get('/admin/background'); currentBg.value = res.url || '' } catch { currentBg.value = '' }
}
const handleFileChange = (f) => { selectedFile.value = f.raw }
const handleUpload = async () => {
  if (!selectedFile.value) return; uploading.value = true
  try { const fd = new FormData(); fd.append('file', selectedFile.value); await request.post('/admin/background/upload', fd)
    ElMessage.success('上传成功'); uploadRef.value?.clearFiles(); selectedFile.value = null; await loadCurrentBg(); previewKey.value++ } catch {} finally { uploading.value = false }
}
const handleResetBg = async () => {
  resettingBg.value = true
  try { await request.post('/admin/background/reset'); ElMessage.success('已重置'); currentBg.value = ''; previewKey.value++ } catch {} finally { resettingBg.value = false }
}
const uploadAppearanceImage = async (file, field) => {
  const fd = new FormData(); fd.append('file', file)
  try {
    const res = await request.post('/admin/appearance/upload', fd)
    form[field] = res.url
    ElMessage.success('图片上传成功')
  } catch {}
}

function triggerUpload(field) {
  const inp = document.createElement('input')
  inp.type = 'file'; inp.accept = 'image/*'
  inp.onchange = (e) => { if (e.target.files[0]) uploadAppearanceImage(e.target.files[0], field) }
  inp.click()
}

const openFrontend = () => { window.open(touristUrl, '_blank') }

onMounted(() => { loadAppearance(); loadCurrentBg() })
</script>

<style scoped>
.appearance-page {
  display: flex;
  height: calc(100vh - 100px);
  gap: 24px;
}
.settings-area {
  flex: 1;
  overflow-y: auto;
  padding-right: 8px;
}
.desc { color: #909399; margin-bottom: 16px; }
.color-value { margin-left: 12px; font-size: 13px; color: #909399; font-family: monospace; }

.bg-preview-img {
  background: #f5f7fa; border-radius: 8px; text-align: center; padding: 16px;
}
.bg-preview-img img { max-width: 100%; max-height: 300px; }

/* 右侧预览栏 */
.preview-sidebar {
  width: 400px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 2px 16px rgba(0,0,0,0.08);
  overflow: hidden;
  position: sticky;
  top: 0;
  height: 100%;
}
.preview-sidebar:has(.desktop) {
  width: 520px;
}
.preview-header {
  display: flex; align-items: center; gap: 8px;
  padding: 12px 16px; border-bottom: 1px solid #ebeef5;
  font-size: 14px; font-weight: 600;
}
.preview-frame {
  flex: 1; overflow: hidden;
  background: #f5f7fa;
}
.preview-frame iframe { border: none; }
.preview-frame.mobile iframe { width: 375px; height: 100%; }
.preview-frame.desktop iframe {
  width: 1000px; height: 700px;
  transform: scale(0.52);
  transform-origin: top left;
}
</style>
