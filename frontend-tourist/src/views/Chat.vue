<template>
  <div class="chat-container" :class="{ 'desktop-layout': !isMobile }">
    <!-- ==================== 桌面端布局 ==================== -->
    <template v-if="!isMobile">
      <!-- 左侧主区域 -->
      <div class="main-area">
        <!-- 顶部导航栏 -->
        <header class="desktop-header" :style="headerStyle">
          <div class="header-brand">
            <span class="brand-icon">🏔️</span>
            <span class="brand-title">{{ appearance.brand_title || '灵山胜境 · 智能导游' }}</span>
          </div>
          <div class="header-actions">
            <button v-if="appearance.btn_map !== 'false'" class="header-btn" :class="{ active: mapFullscreen }"@click="handleMapBtnClick" title="地图">
              <span class="btn-icon">🗺️</span>
              <span class="btn-label">地图</span>
            </button>
            <button v-if="appearance.btn_recommend !== 'false'" class="header-btn" @click="handleRecommend" :disabled="loading" title="智能推荐">
              <span class="btn-icon">🎯</span>
              <span class="btn-label">推荐</span>
            </button>
            <button v-if="appearance.btn_video !== 'false'" class="header-btn" :class="{ active: videoEnabled }" @click="videoEnabled = !videoEnabled" title="视频联动 & 自动介绍">
              <span class="btn-icon">🎬</span>
              <span class="btn-label">视频</span>
            </button>
            <button v-if="appearance.btn_action !== 'false'" class="header-btn" :class="{ active: actionEnabled }" @click="actionEnabled = !actionEnabled" title="肢体动作">
              <span class="btn-icon">🙋</span>
              <span class="btn-label">动作</span>
            </button>
            <button class="header-btn" :class="{ active: subtitleEnabled }" @click="toggleSubtitle" title="字幕">
              <span class="btn-icon">💬</span>
              <span class="btn-label">字幕</span>
            </button>
            <div class="header-divider"></div>
            <span class="header-user">👤 {{ auth.userInfo?.username || '游客' }}</span>
            <button class="header-btn logout-btn" @click="handleLogout">
              <span class="btn-label">退出</span>
            </button>
          </div>
        </header>

        <!-- 地图折叠面板（始终渲染，CSS 切换可见性） -->
        <div class="desktop-map-panel" :class="{ collapsed: !showDesktopMap, fullscreen: mapFullscreen }">
          <button v-if="mapFullscreen" class="map-fullscreen-close" @click="mapFullscreen = false; showDesktopMap = false; nextTick(() => { setTimeout(() => window.map?.invalidateSize(), 400) })">✕ 退出全屏</button>
          <MapView />
        </div>

        <!-- 聊天区域 -->
        <div class="desktop-chat-body" :style="chatBodyStyle">
          <div class="chat-content" ref="chatContentRef">
            <!-- 欢迎消息 + 景点提示卡片 -->
            <div v-if="messageList.length === 0" class="welcome-section">
              <div class="welcome-card">
                <div class="welcome-avatar">👩‍💼</div>
                <h2>{{ appearance.welcome_title || '您好，我是您的智能导游' }}</h2>
                <p>{{ appearance.welcome_text || '嗨，欢迎来到灵山胜境！有什么想了解的，尽管问我哦～' }}</p>
                <div class="welcome-tips">
                  <span
                    v-for="tip in (appearance.welcome_tips || '🕐 表演时间,📏 景点参数,🗺️ 游览路线,⭐ 猜你喜欢').split(',')"
                    :key="tip"
                    class="tip-chip"
                    @click="handleTipClick(tip)"
                  >{{ tip.trim() }}</span>
                </div>
              </div>
            </div>

            <!-- 当前景点信息卡（视频/自动介绍开启时显示） -->
            <div v-if="currentAttraction && videoEnabled" class="attraction-info-card">
              <div class="attraction-card-header">
                <span class="attraction-dot"></span>
                <span>您现在位于</span>
              </div>
              <div class="attraction-card-body">
                <h3>{{ currentAttraction.name }}</h3>
                <p v-if="currentAttraction.highlights">{{ currentAttraction.highlights }}</p>
              </div>
            </div>

            <!-- 视频联动卡片 -->
            <div v-if="currentVideo && videoEnabled" class="video-card" :class="{ expanded: showVideoPanel }">
              <div class="video-card-bar" @click="showVideoPanel = !showVideoPanel">
                <span class="video-bar-icon">🎬</span>
                <span class="video-bar-title">{{ currentVideo.name }}</span>
                <span class="video-bar-duration">⏱ {{ currentVideo.duration }}</span>
                <span v-if="!showVideoPanel" class="video-bar-badge">▶ 点击播放</span>
                <span v-else class="video-bar-badge playing">▶ 播放中</span>
                <span class="video-bar-arrow">{{ showVideoPanel ? '▲' : '▼' }}</span>
                <button class="video-close-btn" @click.stop="currentVideo = null; showVideoPanel = false">✕</button>
              </div>
              <div v-if="showVideoPanel" class="video-card-body">
                <video
                  ref="videoPlayerRef"
                  :src="videoSrc"
                  class="video-player"
                  autoplay
                  muted
                  loop
                  playsinline
                  @error="onVideoError"
                ></video>
              </div>
            </div>

            <!-- 对话消息列表 -->
            <div class="message-list">
              <div v-for="(msg, index) in messageList" :key="index" :class="['message-item', msg.role]">
                <div class="message-avatar">
                  <span v-if="msg.role === 'assistant'">👩‍💼</span>
                  <span v-else>👤</span>
                </div>
                <div class="message-body">
                  <div class="message-bubble">
                    <div v-if="msg.role === 'assistant' && msg.thoughts && msg.thoughts.length" class="thoughts-panel">
                      <van-collapse v-model="activeThoughts">
                        <van-collapse-item :name="index">
                          <template #title>
                            💭 {{ thoughtSummary(msg) }}
                          </template>
                          <div v-for="(step, sIdx) in msg.thoughts" :key="sIdx" class="thought-step">
                            <span class="t-time" v-if="step.duration_ms != null">{{ formatDuration(step.duration_ms) }}</span>
                            <template v-if="step.type === 'thought'">
                              <span class="t-label">🤔</span><span>{{ cleanDisplayText(step.content) }}</span>
                            </template>
                            <template v-else-if="step.type === 'action'">
                              <span class="t-label">🔧</span><span class="t-fn">{{ extractFnName(step.content) }}</span>
                            </template>
                            <template v-else-if="step.type === 'action_input'">
                              <span class="t-label">📝</span><span class="t-json-text">{{ formatThought(step.type, step.content) }}</span>
                            </template>
                            <template v-else-if="step.type === 'observation'">
                              <span class="t-label">📋</span>
                              <span class="t-obs" :class="{ expanded: expandedObs.has(step.step + '_' + sIdx) }" @click="toggleObs(step.step, sIdx)">
                                <span v-if="expandedObs.has(step.step + '_' + sIdx)" v-html="formatObsHtml(step.raw_content || step.content)"></span>
                                <span v-else>{{ cleanObsContent(formatThought(step.type, step.content)) }}</span>
                                <span v-if="(step.raw_content || step.content).length > 80" class="obs-expand-hint">
                                  {{ expandedObs.has(step.step + '_' + sIdx) ? '收起' : '展开' }}
                                </span>
                              </span>
                            </template>
                            <template v-else-if="step.type === 'final_answer'">
                              <span class="t-label">💬</span><span>{{ truncateText(step.content, 80) }}</span>
                            </template>
                          </div>
                        </van-collapse-item>
                      </van-collapse>
                    </div>
                    <div class="bubble-text" v-html="msg.content"></div>
                  </div>
                </div>
              </div>
              <div v-if="loading" class="message-item assistant">
                <div class="message-avatar"><span>👩‍💼</span></div>
                <div class="message-body">
                  <div class="message-bubble typing-bubble" style="flex-direction:column;align-items:flex-start;gap:8px;">
                    <div style="display:flex;align-items:center;gap:8px;">
                      <span class="typing-dots">●●●</span>
                      <span class="typing-text">正在思考{{ loadingSeconds > 0 ? ' · ' + formatDuration(loadingSeconds * 1000) : '' }}...</span>
                      <button
                        v-if="liveActions.length > 0"
                        class="live-toggle-btn"
                        :class="{ active: showLiveThoughts }"
                        @click.stop="showLiveThoughts = !showLiveThoughts"
                        :title="showLiveThoughts ? '隐藏思考细节' : '显示思考细节'"
                      >{{ showLiveThoughts ? '🔽' : '🔼' }}</button>
                    </div>
                    <div v-if="showLiveThoughts && liveActions.length > 0" class="live-thought-box">
                      <div v-for="(t, i) in liveActions.slice(-2)" :key="i" class="live-thought-line">
                        <span class="live-t-icon">{{ t.type === 'action' ? '🔧' : '📋' }}</span>
                        <span class="live-t-text">{{ cleanLiveText(t) }}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 底部输入区域 -->
          <div class="desktop-input-area">
            <div class="mode-toggle" v-if="!isMobile">
              <button
                class="mode-btn"
                :class="{ active: agentMode }"
                @click="agentMode = !agentMode"
                :title="agentMode ? 'Agent模式：完整工具 · 点击切换为快速问答' : '快速问答：仅知识库 · 点击切换为Agent模式'"
              >
                <span class="mode-icon">{{ agentMode ? '🤖' : '💬' }}</span>
                <span class="mode-label">{{ agentMode ? 'Agent 模式' : '快速问答' }}</span>
                <span class="mode-hint">{{ agentMode ? '路线 · 天气 · 推荐' : '仅知识库查询' }}</span>
              </button>
            </div>
            <div class="input-wrapper">
              <button class="voice-btn" :class="{ recording: isRecording }" @click="toggleVoiceInput" :disabled="loading">
                <span>{{ isRecording ? `⏺ ${recordingTime}s` : '🎤' }}</span>
              </button>
              <input
                v-model="inputText"
                class="chat-input"
                :placeholder="appearance.input_placeholder || '输入您的问题，按 Enter 发送...'"
                @keyup.enter="handleSend"
                :disabled="loading"
              />
              <button
                class="send-btn"
                @click="handleSend"
                :disabled="!inputText.trim() || loading"
              >
                <span v-if="loading" class="send-spinner"></span>
                <span v-else>📤</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧 Live2D 数字人展示区 -->
      <div v-if="appearance.show_live2d !== 'false'" class="character-panel">
        <div class="character-backdrop" :style="{ backgroundImage: `url(${backgroundUrl})` }"></div>
        <div class="panel-info">
          <!-- 天气 -->
          <div v-if="weather" class="info-card weather">
            <span class="info-icon">{{ weather.icon }}</span>
            <div class="info-text">
              <div class="info-title">{{ weather.desc }} {{ weather.temp }}°C</div>
              <div class="info-desc">湿度 {{ weather.humidity }}%  体感 {{ weather.feelsLike }}°C</div>
            </div>
          </div>
        </div>
        <div
          class="character-container"
          :class="{ dragging: isDragging }"
          @mousedown="onLive2dMouseDown"
          @wheel.prevent="onLive2dWheel"
        >
          <div
            class="live2d-transform"
            :style="{
              transform: `translate(${live2dOffset.x}px, ${live2dOffset.y}px) scale(${live2dScale})`,
              transition: isDragging ? 'none' : 'transform 0.25s ease',
              cursor: isDragging ? 'grabbing' : 'grab',
            }"
          >
            <Live2DViewers ref="live2dRef" />
          </div>
        </div>

        <!-- ====== 桌面端字幕条 — 数字人下方毛玻璃胶囊 ====== -->
        <div
          v-if="subtitleEnabled && currentParaChars.length"
          class="desktop-subtitle-bar"
        >
          <div class="subtitle-text-wrap" ref="subtitleWrapRef">
            <span
              v-for="ch in currentParaChars"
              :key="ch.globalIdx"
              class="subtitle-char"
              :class="{
                'char-active': ch.globalIdx === activeCharIdx,
                'char-spoken': ch.globalIdx < activeCharIdx,
              }"
            >{{ ch.char }}</span>
          </div>
        </div>

        <div class="character-label">
          <span class="label-dot"></span>
          AI 导游 · 小灵
          <button class="reset-live2d-btn" @click="handleNextMotion" title="切换数字人动作">🎭 换动作</button>
          <button class="reset-live2d-btn" @click="resetLive2d" title="重置数字人位置和大小">↺ 重置</button>
        </div>
      </div>
    </template>

    <!-- ==================== 移动端布局 ==================== -->
    <ChatMobile v-if="isMobile" />
  </div>
</template>

<script setup>
import { provide, nextTick, reactive, ref, onMounted, onBeforeUnmount, computed, watch } from 'vue'
import { useChat } from '@/composables/useChat'
import Live2DViewers from '@/components/Live2DViewers.vue'
import MapView from '@/views/MapView.vue'
import ChatMobile from '@/views/ChatMobile.vue'
import request from '@/utils/request'

// 创建共享状态，提供给子组件
const ctx = useChat()
provide('chatContext', ctx)

// 解构桌面模板需要的变量
const {
  isMobile,
  messageList,
  loading,
  loadingSeconds,
  liveThoughts,
  agentMode,
  showLiveThoughts,
  inputText,
  activeThoughts,
  currentAttraction,
  weather,
  videoEnabled,
  actionEnabled,
  currentVideo,
  showVideoPanel,
  videoSrc,
  chatContentRef,
  live2dRef,
  videoPlayerRef,
  showDesktopMap,
  mapFullscreen,
  auth,
  isRecording,
  recordingTime,
  handleMapBtnClick,
  handleRecommend,
  handleLogout,
  handleSend,
  toggleVoiceInput,
  extractFnName,
  truncateText,
  formatThought,
  cleanObsContent,
  cleanDisplayText,
  onVideoError,
  handleNextMotion,
  subtitleEnabled,
  charSubtitles,
  activeCharIdx,
  paragraphs,
  activeParaIdx,
  toggleSubtitle,
} = ctx

// ==================== 思考面板展开/收起 ====================
const expandedObs = reactive(new Set())
function toggleObs(step, idx) {
  const key = step + '_' + idx
  expandedObs.has(key) ? expandedObs.delete(key) : expandedObs.add(key)
}
function formatObsHtml(text) {
  if (!text) return ''
  let html = text
  // 来源标签 → 蓝色小标签
  html = html.replace(/\[来源:\s*([^\]]+)\]/g, '<span class="obs-src-tag">$1</span>')
  // 分隔符 → 分割线
  html = html.replace(/\n?---\n?/g, '<span class="obs-divider"></span>')
  // 换行
  html = html.replace(/\n/g, '<br/>')
  return html
}

// ==================== 思考耗时工具函数 ====================
function formatDuration(ms) {
  if (ms == null || ms < 0) return ''
  if (ms < 1000) return `${ms}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  const min = Math.floor(ms / 60000)
  const sec = ((ms % 60000) / 1000).toFixed(0)
  return `${min}m${sec}s`
}

function totalThoughtTime(msg) {
  if (!msg.thoughts || !msg.thoughts.length) return 0
  const last = msg.thoughts[msg.thoughts.length - 1]
  return last.duration_ms || 0
}
function thoughtSummary(msg) {
  if (!msg.thoughts || !msg.thoughts.length) return '思考过程'
  const actions = msg.thoughts.filter(t => t.type === 'action').map(t => extractFnName(t.content))
  const total = formatDuration(totalThoughtTime(msg))
  const parts = [`思考过程 · ${total}`]
  if (actions.length > 0) {
    parts.push(`· ${actions.length} 步`)
  }
  return parts.join(' ')
}

// ==================== 加载时实时思考过滤 ====================
const liveActions = computed(() => {
  return liveThoughts.value.filter(t => t.type === 'action' || t.type === 'observation')
})
function cleanLiveText(t) {
  let text = t.content || ''
  // 去掉 JSON
  if (typeof text === 'string' && text.startsWith('{')) {
    try { const obj = JSON.parse(text); text = Object.values(obj).join(' ') } catch {}
  }
  // 去掉 snake_case 工具名
  text = text.replace(/\b[a-z]+_[a-z]+(?:_[a-z]+)*\b/g, '')
  // 去掉 "调用工具:" 前缀
  text = text.replace(/调用工具:\s*/g, '')
  text = text.replace(/\s{2,}/g, ' ').trim()
  return text.length > 50 ? text.slice(0, 50) + '...' : text
}

// ==================== Live2D 拖拽 & 缩放 ====================
const live2dOffset = reactive({ x: 0, y: 40 })
const live2dScale = ref(1.2)
const isDragging = ref(false)
const backgroundUrl = ref(import.meta.env.BASE_URL + 'background.jpg')
const appearance = ref({})

// 从后端获取外观设置 & 背景图
const fetchAppearance = async () => {
  try {
    const res = await request.get('/tourist/appearance')
    appearance.value = res
  } catch { /* 使用默认值 */ }
}

const headerStyle = computed(() => {
  const s = {}
  if (appearance.value.header_bg_image) {
    s.backgroundImage = `url(${appearance.value.header_bg_image})`
    s.backgroundSize = 'cover'
  } else if (appearance.value.header_bg) {
    s.background = appearance.value.header_bg
  }
  if (appearance.value.header_text_color) {
    s.color = appearance.value.header_text_color
  }
  return s
})

const chatBodyStyle = computed(() => {
  const s = {}
  if (appearance.value.chat_bg && appearance.value.chat_bg !== 'transparent') {
    s.backgroundColor = appearance.value.chat_bg
  }
  if (appearance.value.chat_bg_image) {
    s.backgroundImage = `url(${appearance.value.chat_bg_image})`
    s.backgroundSize = 'cover'
  }
  // CSS 变量传给子元素
  if (appearance.value.chat_text_color) s['--chat-text'] = appearance.value.chat_text_color
  if (appearance.value.chat_font_size) s['--chat-font-size'] = appearance.value.chat_font_size + 'px'
  if (appearance.value.bubble_ai_bg) s['--bubble-ai-bg'] = appearance.value.bubble_ai_bg
  if (appearance.value.bubble_user_bg) s['--bubble-user-bg'] = appearance.value.bubble_user_bg
  if (appearance.value.bubble_user_text) s['--bubble-user-text'] = appearance.value.bubble_user_text
  if (appearance.value.input_bg) s['--input-bg'] = appearance.value.input_bg
  if (appearance.value.input_border) s['--input-border'] = appearance.value.input_border
  if (appearance.value.input_send_btn) s['--input-send-btn'] = appearance.value.input_send_btn
  if (appearance.value.input_bg_image) s['--input-bg-image'] = `url(${appearance.value.input_bg_image})`
  return s
})

function handleTipClick(tip) {
  const text = tip.replace(/^[^\s]+\s*/, '') || tip  // 去掉 emoji 前缀
  if (tip.includes('猜你喜欢')) { handleRecommend(); return }
  inputText.value = text || tip
  handleSend()
}
const fetchBackground = async () => {
  try {
    const res = await request.get('/tourist/background')
    if (res.url) {
      // 后端返回绝对路径 /static/... 转为完整URL（兼容 file:// 协议）
      let url = res.url
      if (url.startsWith('/')) {
        url = (import.meta.env.VITE_API_BASE_URL || '') + url
      }
      backgroundUrl.value = url
    }
  } catch { /* 使用默认背景 */ }
}
let dragStart = { x: 0, y: 0 }
let offsetStart = { x: 0, y: 0 }

function onLive2dMouseDown(e) {
  if (e.button !== 0) return
  isDragging.value = true
  dragStart = { x: e.clientX, y: e.clientY }
  offsetStart = { x: live2dOffset.x, y: live2dOffset.y }
}

function onLive2dMouseMove(e) {
  if (!isDragging.value) return
  live2dOffset.x = offsetStart.x + (e.clientX - dragStart.x)
  live2dOffset.y = offsetStart.y + (e.clientY - dragStart.y)
}

function onLive2dMouseUp() {
  isDragging.value = false
}

function onLive2dWheel(e) {
  const delta = e.deltaY > 0 ? -0.05 : 0.05
  live2dScale.value = Math.max(0.3, Math.min(2.5, live2dScale.value + delta))
}

function resetLive2d() {
  live2dOffset.x = 0
  live2dOffset.y = 40
  live2dScale.value = 1.2
}

// ==================== 字幕自动滚动（移动端风格平滑滑动）====================
const subtitleWrapRef = ref(null)
let subtitleScrollTimer = null

// 当前段落的所有字符（移动端风格：一次显示一句，句中逐字高亮）
const currentParaChars = computed(() => {
  if (activeParaIdx.value < 0 || !paragraphs.value.length) return []
  const para = paragraphs.value[activeParaIdx.value]
  if (!para || para.charStart == null) return []
  return charSubtitles.value.slice(para.charStart, para.charEnd + 1).map((ch, i) => ({
    ...ch,
    globalIdx: para.charStart + i,
  }))
})

watch(activeCharIdx, (globalIdx) => {
  if (globalIdx < 0 || !subtitleWrapRef.value) return
  // 映射：全局字符索引 → 当前段落内的 span 索引
  const para = paragraphs.value[activeParaIdx.value]
  if (!para || para.charStart == null) return
  const localIdx = globalIdx - para.charStart
  const container = subtitleWrapRef.value
  const spans = container.children
  if (localIdx < 0 || localIdx >= spans.length) return

  const activeSpan = spans[localIdx]
  const containerW = container.clientWidth
  const scrollX = container.scrollLeft
  const spanLeft = activeSpan.offsetLeft
  const spanRight = spanLeft + activeSpan.offsetWidth

  // 只在字接近边缘 30% 时才触发滑动，避免频繁抖动
  const leftZone = scrollX + containerW * 0.3
  const rightZone = scrollX + containerW * 0.7
  if (spanLeft >= leftZone && spanRight <= rightZone) return

  // 防抖：50ms 内只执行一次
  if (subtitleScrollTimer) return
  subtitleScrollTimer = setTimeout(() => { subtitleScrollTimer = null }, 50)

  // 目标位置：当前字居中
  const target = spanLeft - containerW / 2 + activeSpan.offsetWidth / 2
  container.scrollTo({ left: Math.max(0, target), behavior: 'smooth' })
})

onMounted(() => {
  document.addEventListener('mousemove', onLive2dMouseMove)
  document.addEventListener('mouseup', onLive2dMouseUp)
  fetchAppearance()
  fetchBackground()
})

onBeforeUnmount(() => {
  document.removeEventListener('mousemove', onLive2dMouseMove)
  document.removeEventListener('mouseup', onLive2dMouseUp)
})
</script>

<style scoped>
/* ========================================
   全局基础变量
   ======================================== */
:root {
  --header-height: 56px;
  --primary: #4a7c59;
  --primary-light: #6b9e78;
  --accent: #c8a45c;
  --bg: #f8f6f2;
  --card-bg: #ffffff;
  --text: #2c3e50;
  --text-light: #6b7280;
  --border: #e5e0d8;
  --shadow-sm: 0 1px 3px rgba(0,0,0,0.06);
  --shadow-md: 0 4px 16px rgba(0,0,0,0.08);
  --shadow-lg: 0 8px 32px rgba(0,0,0,0.12);
  --radius: 16px;
  --radius-sm: 10px;
  --transition: 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

/* ========================================
   桌面端布局容器
   ======================================== */
.desktop-layout {
  width: 100vw;
  height: 100vh;
  display: flex;
  background: var(--bg);
  overflow: hidden;
}

/* ---- 左侧主区域 (65%) ---- */
.main-area {
  flex: 0 0 65%;
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: var(--bg);
  position: relative;
  z-index: 1;
  overflow: hidden; /* 裁剪负 margin 的地图面板 */
}

/* ---- 顶部导航栏 ---- */
.desktop-header {
  height: var(--header-height);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  background: rgba(255,255,255,0.85);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
  z-index: 10;
}

.header-brand {
  display: flex;
  align-items: center;
  gap: 10px;
}

.brand-icon {
  font-size: 26px;
}

.brand-title {
  font-size: 17px;
  font-weight: 700;
  color: var(--text);
  letter-spacing: 0.5px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.header-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 7px 14px;
  border: 1px solid var(--border);
  background: #fff;
  border-radius: 20px;
  cursor: pointer;
  font-size: 13px;
  color: var(--text-light);
  transition: var(--transition);
}

.header-btn:hover:not(:disabled) {
  background: var(--primary);
  border-color: var(--primary);
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(74,124,89,0.25);
}

.header-btn.active {
  background-color: #409eff;
  border-color: #409eff;
  color: #ffffff;
}

.header-btn.active:hover {
  background-color: #66b1ff;
  border-color: #66b1ff;
  color: #ffffff;
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(64,158,255,0.25);
}

.btn-icon {
 font-size: 15px;
 }

.header-divider {
  width: 1px;
  height: 20px;
  background: var(--border);
  margin: 0 6px;
}

.header-user {
  font-size: 14px;
  color: var(--text);
  font-weight: 500;
}

.logout-btn {
  color: #999;
  font-size: 12px;
}

.logout-btn:hover {
  color: #e74c3c;
  border-color: #e74c3c;
}

/* ---- 地图折叠面板 ---- */
.desktop-map-panel {
  height: 280px;
  flex-shrink: 0;
  border-bottom: 1px solid var(--border);
  background: #e8e4db;
  position: relative;
  transition: margin 0.35s ease, opacity 0.3s ease;
}

/* 折叠：用负 margin + 透明隐藏，保留尺寸让 Leaflet 正常渲染 */
.desktop-map-panel.collapsed {
  margin-top: -280px;
  opacity: 0;
  pointer-events: none;
}

/* 展开 */
.desktop-map-panel:not(.collapsed) {
  margin-top: 0;
  opacity: 1;
  pointer-events: auto;
}

/* 全屏模式 — 覆盖头部以下区域 */
.desktop-map-panel.fullscreen {
  position: absolute;
  top: 56px; /* 头部高度 */
  left: 0; right: 0; bottom: 0;
  height: auto;
  z-index: 5; /* 低于头部 z-index:10 */
  margin-top: 0 !important;
  opacity: 1 !important;
  pointer-events: auto !important;
  border: none;
  border-radius: 0;
}

.map-fullscreen-close {
  position: absolute;
  top: 12px;
  right: 16px;
  z-index: 101;
  background: rgba(0,0,0,0.7);
  color: #fff;
  border: none;
  padding: 8px 16px;
  border-radius: 8px;
  font-size: 14px;
  cursor: pointer;
}
.map-fullscreen-close:hover { background: #e74c3c; }

.desktop-map-panel :deep(.map-container) {
  width: 100%;
  height: 100%;
}

.desktop-map-panel :deep(#map) {
  width: 100%;
  height: 100% !important;
}

/* ---- 头部按钮增强 ---- */
.header-btn {
  position: relative;
  overflow: visible;
}

@keyframes fullscreenPulse {
  0%, 100% { box-shadow: 0 0 8px rgba(33,150,243,0.4); }
  50% { box-shadow: 0 0 20px rgba(33,150,243,0.7); }
}

/* ---- 聊天主体 ---- */
.desktop-chat-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  position: relative;
}

/* ---- 聊天内容滚动区 ---- */
.desktop-chat-body .chat-content {
  flex: 1;
  overflow-y: auto;
  padding: 20px 28px 10px;
}

.desktop-chat-body .chat-content::-webkit-scrollbar {
  width: 5px;
}

.desktop-chat-body .chat-content::-webkit-scrollbar-track {
  background: transparent;
}

.desktop-chat-body .chat-content::-webkit-scrollbar-thumb {
  background: rgba(0,0,0,0.1);
  border-radius: 3px;
}

/* ---- 欢迎卡片 ---- */
.welcome-section {
  display: flex;
  justify-content: center;
  padding: 40px 0 24px;
}

.welcome-card {
  text-align: center;
  background: #fff;
  border-radius: 20px;
  padding: 36px 40px;
  box-shadow: var(--shadow-md);
  max-width: 480px;
  width: 100%;
}

.welcome-avatar {
  font-size: 52px;
  margin-bottom: 12px;
}

.welcome-card h2 {
  font-size: 20px;
  color: var(--text);
  margin: 0 0 8px;
  font-weight: 600;
}

.welcome-card p {
  color: var(--text-light);
  font-size: 15px;
  line-height: 1.6;
  margin: 0 0 20px;
}

.welcome-tips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
}

.tip-chip {
  display: inline-block;
  padding: 8px 16px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 20px;
  font-size: 13px;
  color: var(--text);
  cursor: pointer;
  transition: var(--transition);
  user-select: none;
}

.tip-chip:hover {
  background: var(--primary);
  border-color: var(--primary);
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(74,124,89,0.25);
}

/* ---- 视频联动卡片（可折叠） ---- */
.video-card {
  background: #1a1a2e;
  border-radius: 10px;
  margin-bottom: 16px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.3);
  animation: cardSlideIn 0.4s ease-out;
  overflow: hidden;
  border: 1px solid #e74c3c;
}

.video-card-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  cursor: pointer;
  user-select: none;
  transition: background 0.2s;
}

.video-card-bar:hover {
  background: rgba(231,76,60,0.1);
}

.video-bar-icon { font-size: 20px; }

.video-bar-title {
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  flex: 1;
}

.video-bar-duration {
  color: #8892b0;
  font-size: 13px;
}

.video-bar-badge {
  background: #e74c3c;
  color: #fff;
  padding: 3px 10px;
  border-radius: 12px;
  font-size: 11px;
  animation: dotPulse 1.5s infinite;
}

.video-bar-arrow {
  color: #8892b0;
  font-size: 12px;
}

.video-close-btn {
  background: none;
  border: none;
  color: rgba(255,255,255,0.4);
  font-size: 16px;
  cursor: pointer;
  padding: 4px 8px;
  margin-left: 4px;
  border-radius: 4px;
  transition: all 0.15s;
}
.video-close-btn:hover {
  color: #fff;
  background: rgba(231,76,60,0.3);
}

.video-card-body {
  border-top: 1px solid rgba(255,255,255,0.1);
}

.video-player {
  width: 100%;
  max-height: 340px;
  display: block;
  background: #000;
}

.video-error-hint {
  text-align: center;
  padding: 30px 20px;
  color: #ff6b6b;
  background: #1a1a2e;
}
.video-error-hint p { margin: 0 0 8px; font-size: 15px; }
.video-error-hint small { color: #8892b0; font-size: 12px; }

/* ---- 当前景点信息卡 ---- */
.attraction-info-card {
  background: linear-gradient(135deg, #4a7c59, #5a8f6a);
  border-radius: var(--radius);
  padding: 16px 20px;
  margin-bottom: 16px;
  box-shadow: 0 4px 16px rgba(74,124,89,0.25);
  animation: cardSlideIn 0.4s ease-out;
}

@keyframes cardSlideIn {
  from { opacity: 0; transform: translateY(-12px); }
  to   { opacity: 1; transform: translateY(0); }
}

.attraction-card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: rgba(255,255,255,0.8);
  text-transform: uppercase;
  letter-spacing: 1px;
  margin-bottom: 6px;
}

.attraction-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #8fdb8f;
  box-shadow: 0 0 8px rgba(143,219,143,0.6);
  animation: dotPulse 2s infinite;
}

@keyframes dotPulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.attraction-card-body h3 {
  color: #fff;
  font-size: 18px;
  font-weight: 700;
  margin: 0 0 4px;
}

.attraction-card-body p {
  color: rgba(255,255,255,0.9);
  font-size: 13px;
  line-height: 1.5;
  margin: 0;
}

/* ---- 消息列表 ---- */
.message-list {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding-bottom: 8px;
}

/* ---- 单条消息 ---- */
.message-item {
  display: flex;
  gap: 12px;
  max-width: 88%;
  animation: messageSlideIn 0.35s ease-out;
}

@keyframes messageSlideIn {
  from { opacity: 0; transform: translateY(10px); }
  to   { opacity: 1; transform: translateY(0); }
}

.message-item.user {
  align-self: flex-end;
  flex-direction: row-reverse;
}

/* ---- 头像 ---- */
.message-avatar {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  background: #fff;
  box-shadow: var(--shadow-sm);
}

.message-item.assistant .message-avatar {
  background: linear-gradient(135deg, #e8f5e9, #c8e6c9);
}

.message-item.user .message-avatar {
  background: linear-gradient(135deg, #e3f2fd, #bbdefb);
}

/* ---- 消息主体 ---- */
.message-body {
  display: flex;
  flex-direction: column;
}

/* ---- 消息气泡 ---- */
.message-bubble {
  padding: 14px 18px;
  border-radius: 18px;
  line-height: 1.65;
  font-size: var(--chat-font-size, 15px);
  box-shadow: var(--shadow-sm);
}

.message-item.assistant .message-bubble {
  background: var(--bubble-ai-bg, #fff);
  color: var(--chat-text, var(--text));
  border-top-left-radius: 6px;
  box-shadow: var(--shadow-md);
}

.message-item.user .message-bubble {
  background: var(--bubble-user-bg, linear-gradient(135deg, #4a7c59, #5a8f6a));
  color: var(--bubble-user-text, #fff);
  border-top-right-radius: 6px;
}

/* ---- 思考过程 ---- */
.thoughts-panel {
  margin-bottom: 10px;
  font-size: 13px;
  background: #f9fafb;
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid #eee;
}

.thought-step {
  padding: 6px 12px;
  font-size: 12px;
  line-height: 1.6;
  color: #6b7280;
  border-bottom: 1px solid #f0f0f0;
  display: flex;
  align-items: flex-start;
  gap: 6px;
}

.thought-step:last-child {
  border-bottom: none;
}

.thought-total-time {
  font-size: 12px;
  color: #999;
  font-weight: normal;
  margin-left: 4px;
}

.t-time {
  flex-shrink: 0;
  font-size: 10px;
  color: #aaa;
  background: #f5f5f5;
  padding: 1px 6px;
  border-radius: 8px;
  white-space: nowrap;
  min-width: 44px;
  text-align: center;
}

.t-label {
  flex-shrink: 0;
  font-size: 11px;
  opacity: 0.6;
}

.t-fn {
  color: #e67e22;
  font-weight: 600;
  font-family: monospace;
  font-size: 12px;
  background: #fff3e0;
  padding: 1px 6px;
  border-radius: 4px;
}

.t-json {
  color: #2e7d32;
  font-family: monospace;
  font-size: 11px;
  background: #e8f5e9;
  padding: 2px 6px;
  border-radius: 4px;
  word-break: break-all;
}

.t-json-text {
  color: #2e7d32;
  font-size: 12px;
}

.t-obs {
  color: #546e7a;
  font-size: 11px;
  line-height: 1.6;
  cursor: pointer;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  transition: all 0.2s;
}
.t-obs:hover {
  background: #eef2f8;
  border-radius: 4px;
}
.t-obs.expanded {
  -webkit-line-clamp: unset;
  display: block;
  overflow: visible;
  background: #f5f7fb;
  border-radius: 8px;
  padding: 8px 10px;
  border: 1px solid #e8ecf3;
  max-height: 500px;
  overflow-y: auto;
  font-size: 12px;
  line-height: 1.8;
  color: #4a5568;
  white-space: pre-line;
}
.t-obs.expanded::-webkit-scrollbar { width: 4px; }
.t-obs.expanded::-webkit-scrollbar-thumb { background: #d0d5dd; border-radius: 2px; }
.obs-src-tag {
  display: inline-block;
  background: #e8edf5;
  color: #4a6fa5;
  font-size: 10px;
  padding: 1px 8px;
  border-radius: 10px;
  margin-bottom: 4px;
  font-weight: 500;
}
.obs-divider {
  display: block;
  height: 1px;
  background: #e0e4ea;
  margin: 8px 0;
}
.obs-expand-hint {
  color: #667eea;
  font-size: 10px;
  cursor: pointer;
  white-space: nowrap;
  margin-left: 4px;
  font-weight: 500;
}

/* ---- 打字动画 ---- */
.typing-bubble {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 14px 20px;
}

.typing-dots {
  color: var(--primary);
  letter-spacing: 2px;
  animation: typingBounce 1.4s infinite;
}

@keyframes typingBounce {
  0%, 60%, 100% { opacity: 0.3; }
  30% { opacity: 1; }
}

.typing-text {
  color: var(--text-light);
  font-size: 14px;
}

.live-toggle-btn {
  background: none;
  border: 1px solid #e0e0e0;
  border-radius: 12px;
  padding: 2px 8px;
  font-size: 12px;
  cursor: pointer;
  opacity: 0.5;
  transition: all 0.2s;
}
.live-toggle-btn:hover,
.live-toggle-btn.active {
  opacity: 1;
  border-color: #667eea;
  background: #f0f2ff;
}

.live-thought-box {
  width: 100%;
  background: #f8f9fa;
  border-radius: 10px;
  padding: 8px 12px;
  border-left: 3px solid #e0c36a;
}

.live-thought-line {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  padding: 3px 0;
  font-size: 12px;
  color: #555;
  line-height: 1.5;
}

.live-thought-line + .live-thought-line {
  border-top: 1px solid #eee;
  margin-top: 3px;
  padding-top: 6px;
}

.live-t-icon {
  flex-shrink: 0;
  font-size: 13px;
}

.live-t-text {
  flex: 1;
  word-break: break-word;
  min-width: 0;
}

/* ---- 模式切换按钮 ---- */
.mode-toggle {
  display: flex;
  justify-content: center;
  margin-bottom: 8px;
}

.mode-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 14px;
  border: 1.5px solid #e0e0e0;
  background: #fafafa;
  border-radius: 20px;
  cursor: pointer;
  font-size: 12px;
  color: #999;
  transition: all 0.25s ease;
}

.mode-btn:hover {
  border-color: #bbb;
  color: #666;
}

.mode-btn.active {
  background: linear-gradient(135deg, #667eea, #764ba2);
  border-color: #667eea;
  color: #fff;
  box-shadow: 0 2px 8px rgba(102,126,234,0.3);
}

.mode-icon {
  font-size: 14px;
}

.mode-label {
  font-weight: 600;
}

.mode-hint {
  font-size: 11px;
  opacity: 0.7;
}

.mode-btn.active .mode-hint {
  opacity: 0.85;
}

/* ---- 底部输入区 ---- */
.desktop-input-area {
  flex-shrink: 0;
  padding: 12px 24px 18px;
  background: rgba(255,255,255,0.8);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-top: 1px solid var(--border);
}

.input-wrapper {
  display: flex;
  align-items: center;
  gap: 10px;
  background: var(--input-bg-image, none) center/cover no-repeat, var(--input-bg, #fff);
  border: 2px solid var(--input-border, var(--border));
  border-radius: 28px;
  padding: 6px 6px 6px 18px;
  box-shadow: var(--shadow-sm);
  transition: var(--transition);
}

.input-wrapper:focus-within {
  border-color: var(--primary);
  box-shadow: 0 0 0 4px rgba(74,124,89,0.08);
}

.voice-btn {
  width: 40px;
  height: 40px;
  border: none;
  background: var(--bg);
  border-radius: 50%;
  cursor: pointer;
  font-size: 17px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: var(--transition);
  flex-shrink: 0;
}

.voice-btn:hover {
  background: #e8f5e9;
}

.voice-btn.recording {
  background: #fce4ec;
  animation: recordingPulse 1.2s infinite;
}


@keyframes recordingPulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(231,76,60,0.3); }
  50% { box-shadow: 0 0 0 10px rgba(231,76,60,0); }
}

.chat-input {
  flex: 1;
  border: none;
  outline: none;
  font-size: 15px;
  color: var(--text);
  background: transparent;
  min-width: 0;
}

.chat-input::placeholder {
  color: #bbb;
}

.send-btn {
  width: 42px;
  height: 42px;
  border: none;
  background: var(--input-send-btn, var(--primary));
  border-radius: 50%;
  cursor: pointer;
  font-size: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: var(--transition);
  flex-shrink: 0;
  color: #fff;
}

.send-btn:hover:not(:disabled) {
  background: var(--primary-light);
  transform: scale(1.05);
  box-shadow: 0 4px 12px rgba(74,124,89,0.3);
}

.send-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.send-spinner {
  width: 18px;
  height: 18px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ---- 右侧 Live2D 角色面板 (35%) ---- */
.character-panel {
  flex: 1;
  height: 100vh;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.character-backdrop {
  position: absolute;
  inset: 0;
  background-image: url('./background.jpg');
  background-size: cover;
  background-position: center;
  background-repeat: no-repeat;
  z-index: 0;
}

.character-container {
  position: relative;
  z-index: 1;
  width: 100%;
  height: calc(100% - 120px);
  margin-top: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  user-select: none;
}

.live2d-transform {
  width: 100%;
  height: 100%;
  will-change: transform;
}

.character-container.dragging .live2d-transform {
  cursor: grabbing;
}

.character-label {
  position: absolute;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 6px;
  background: rgba(255,255,255,0.85);
  backdrop-filter: blur(8px);
  padding: 6px 16px;
  border-radius: 20px;
  font-size: 13px;
  color: var(--text-light);
  font-weight: 500;
  box-shadow: var(--shadow-sm);
  white-space: nowrap;
  z-index: 2;
}

.reset-live2d-btn {
  background: none;
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 2px 10px;
  font-size: 11px;
  color: var(--text-light);
  cursor: pointer;
  transition: var(--transition);
}

.reset-live2d-btn:hover {
  background: var(--primary);
  border-color: var(--primary);
  color: #fff;
}

.label-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #5cc76f;
  box-shadow: 0 0 6px rgba(92,199,111,0.5);
}

/* ---- 右侧信息卡片 ---- */
.panel-info {
  position: absolute;
  top: 16px;
  left: 16px;
  right: 16px;
  z-index: 2;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.info-card {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  background: rgba(255,255,255,0.85);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border-radius: 14px;
  padding: 12px 16px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.06);
}

.info-card.attraction {
  border-left: 3px solid var(--primary);
}

.info-card.weather {
  border-left: 3px solid #667eea;
}

.info-icon {
  font-size: 22px;
  flex-shrink: 0;
  line-height: 1;
}

.info-text {
  flex: 1;
  min-width: 0;
}

.info-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 2px;
}

.info-desc {
  font-size: 12px;
  color: var(--text-light);
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

/* ═══════════════════════════════════════════════════════════════
   桌面端字幕条 — 数字人下方毛玻璃胶囊
   ═══════════════════════════════════════════════════════════════ */
.desktop-subtitle-bar {
  position: absolute;
  bottom: 80px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 15;
  background: rgba(255, 255, 255, 0.88);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border-radius: 18px;
  padding: 10px 24px;
  max-width: 88%;
  box-shadow: 0 2px 16px rgba(0, 0, 0, 0.12);
  /* 两端渐隐 */
  --fade: 18px;
  mask-image: linear-gradient(90deg, transparent 0%, black var(--fade), black calc(100% - var(--fade)), transparent 100%);
  -webkit-mask-image: linear-gradient(90deg, transparent 0%, black var(--fade), black calc(100% - var(--fade)), transparent 100%);
}
.subtitle-text-wrap {
  text-align: center;
  line-height: 1.7;
  max-width: 100%;
  overflow-x: auto;
  overflow-y: hidden;
  white-space: nowrap;
  scrollbar-width: none;
  -ms-overflow-style: none;
}
.subtitle-text-wrap::-webkit-scrollbar { display: none; }

.subtitle-char {
  font-size: 18px;
  font-weight: 500;
  color: rgba(0, 0, 0, 0.35);
  letter-spacing: 1px;
  transition: color 0.12s ease, text-shadow 0.12s ease, font-weight 0.12s ease;
  display: inline;
}
/* 已读过的字 — 变深 */
.subtitle-char.char-spoken {
  color: rgba(0, 0, 0, 0.6);
}
/* 当前正在读的字 — 金色高亮 */
.subtitle-char.char-active {
  color: #d4940a;
  font-weight: 700;
  font-size: 20px;
  text-shadow: 0 0 10px rgba(212, 148, 10, 0.45);
}
</style>
