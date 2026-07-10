<template>
  <div class="mobile-app">
    <!-- ============================================================ -->
    <!--  PAGE 1: 导游 · AI Guide                                     -->
    <!-- ============================================================ -->
    <transition name="page-fade">
      <div v-show="activeTab === 'guide'" class="page guide-page">
        <!-- Live2D 全屏背景 -->
        <div class="live2d-backdrop" :style="{ backgroundImage: `url(${backgroundUrl})` }">
          <Live2DViewers :ref="setLive2d" />
        </div>

        <!-- 顶部悬浮栏 -->
        <div class="guide-top-bar">
          <div class="top-bar-bg"></div>
          <div class="top-bar-row">
            <div class="guide-location" @click="activeTab = 'discover'">
              <span class="loc-dot"></span>
              <span class="loc-text">{{ currentAttraction?.name || '灵山胜境' }}</span>
              <van-icon name="arrow-down" size="12" color="rgba(255,255,255,0.7)" />
            </div>
            <div class="top-bar-spacer"></div>
            <button class="top-icon-btn" @click="handleNextMotion" :disabled="loading" title="切换表情">
              <van-icon name="smile-o" size="20" color="#fff" />
            </button>
          </div>
        </div>

        <!-- 加载动画 -->
        <transition name="fade">
          <div v-if="loading" class="guide-loading">
            <div class="loading-orb">
              <div class="orb-ring r1"></div>
              <div class="orb-ring r2"></div>
              <div class="orb-ring r3"></div>
              <div class="orb-core">
                <van-loading type="spinner" size="18" color="#667eea" />
              </div>
            </div>
            <span class="loading-label">AI 导游正在思考...</span>
          </div>
        </transition>

        <!-- ====== 字幕 ====== -->
        <div
          v-if="activeParaIdx !== -1 && paragraphs.length"
          class="mobile-subtitle-container"
        >
          <span class="subtitle-para highlight">
            {{ paragraphs[activeParaIdx].text }}
          </span>
        </div>
        <!-- ====== 字幕结束 ====== -->

        <!-- 快捷操作 -->
        <div class="guide-chips">
          <button class="chip" @click="doRecommend" :disabled="loading">
            <span class="chip-emoji">🎯</span> 猜你喜欢
          </button>
          <button class="chip" @click="doQuickAsk('表演时间')" :disabled="loading">
            <span class="chip-emoji">🕐</span> 表演时间
          </button>
          <button class="chip" @click="doQuickAsk('游览路线')" :disabled="loading">
            <span class="chip-emoji">🗺️</span> 游览路线
          </button>
        </div>

        <!-- 底部语音输入 -->
        <div class="guide-voice-bar">
          <div class="voice-button-shell" :class="{ recording: isRecording }">
            <div class="voice-ripple" v-if="isRecording"></div>
            <div class="voice-ripple r2" v-if="isRecording"></div>
            <button
              class="voice-btn-core"
              @click="toggleVoiceInput"
              :disabled="loading"
              :aria-label="isRecording ? '停止录音' : '开始语音输入'"
            >
              <van-icon :name="isRecording ? 'pause-circle-o' : 'volume-o'" size="26" />
            </button>
          </div>
          <span class="voice-hint">
            {{ isRecording ? `${recordingTime}s 正在聆听…` : '轻触语音按钮向我提问' }}
          </span>
        </div>
      </div>
    </transition>

    <!-- ============================================================ -->
    <!--  PAGE 2: 地图 · Map                                          -->
    <!-- ============================================================ -->
    <transition name="page-fade">
      <div v-show="activeTab === 'map'" class="page map-page">
        <div class="map-header-bar">
          <button class="map-back" @click="activeTab = 'guide'">
            <van-icon name="arrow-left" size="22" />
          </button>
          <span class="map-title">景区地图</span>
          <button class="map-locate" @click="focusCurrentLocation">
            <van-icon name="aim" size="20" />
          </button>
        </div>
        <div class="map-stage">
          <MapView />
        </div>
        <!-- 当前景点卡片 -->
        <transition name="slide-up">
          <div v-if="currentAttraction" class="map-info-sheet">
            <div class="sheet-handle"></div>
            <div class="sheet-body">
              <h4>📍 {{ currentAttraction.name }}</h4>
              <p v-if="currentAttraction.highlights">{{ currentAttraction.highlights }}</p>
              <button class="sheet-ask" @click="activeTab = 'guide'; doQuickAsk(currentAttraction.name + '介绍')">
                让导游介绍一下 →
              </button>
            </div>
          </div>
        </transition>
      </div>
    </transition>

    <!-- ============================================================ -->
    <!--  PAGE 3: 发现 · Discover                                     -->
    <!-- ============================================================ -->
    <transition name="page-fade">
      <div v-show="activeTab === 'discover'" class="page discover-page">
        <div class="discover-hero">
          <h1 class="hero-title">发现精彩</h1>
          <p class="hero-sub">探索灵山胜境的每一处美好</p>
        </div>

        <div class="discover-scroll">
          <!-- 天气卡片 -->
          <div v-if="weather" class="d-card weather-card">
            <div class="wc-top">
              <span class="wc-emoji">{{ weather.icon }}</span>
              <div class="wc-main">
                <span class="wc-temp">{{ weather.temp }}°C</span>
                <span class="wc-label">{{ weather.desc }}</span>
              </div>
            </div>
            <div class="wc-meta">
              <span><van-icon name="water-o" /> 湿度 {{ weather.humidity }}%</span>
              <span>🌡️ 体感 {{ weather.feelsLike }}°C</span>
            </div>
          </div>

          <!-- 当前景点 -->
          <div v-if="currentAttraction" class="d-card poi-card" @click="activeTab = 'guide'; doQuickAsk(currentAttraction.name + '介绍')">
            <span class="poi-badge">当前位置</span>
            <h3>{{ currentAttraction.name }}</h3>
            <p v-if="currentAttraction.highlights">{{ currentAttraction.highlights }}</p>
            <span class="poi-arrow">了解更多 →</span>
          </div>

          <!-- 热门问题 -->
          <div class="d-card topics-card">
            <h3 class="card-title">💬 大家都在问</h3>
            <div class="topics-grid">
              <span class="topic-tag" v-for="t in hotTopics" :key="t" @click="activeTab = 'guide'; doQuickAsk(t)">{{ t }}</span>
            </div>
          </div>

          <!-- 特色体验 -->
          <div class="d-card feature-card">
            <h3 class="card-title">✨ 特色体验</h3>
            <div class="feature-row" v-for="f in features" :key="f.title">
              <span class="feat-emoji">{{ f.emoji }}</span>
              <div class="feat-text">
                <strong>{{ f.title }}</strong>
                <span>{{ f.desc }}</span>
              </div>
            </div>
          </div>

          <!-- 底部留白 -->
          <div class="scroll-spacer"></div>
        </div>
      </div>
    </transition>

    <!-- ============================================================ -->
    <!--  PAGE 4: 我的 · Profile                                      -->
    <!-- ============================================================ -->
    <transition name="page-fade">
      <div v-show="activeTab === 'profile'" class="page profile-page">
        <div class="profile-header-card">
          <div class="ph-avatar">
            <div class="avatar-ring">
              <span class="avatar-face">🧑</span>
            </div>
          </div>
          <h2 class="ph-name">{{ auth?.userInfo?.username || '游客' }}</h2>
          <p class="ph-role">景区游客</p>
        </div>

        <div class="profile-scroll">
          <!-- 功能菜单 -->
          <div class="p-menu">
            <div class="p-menu-item" @click="handleNextMotion">
              <span class="pmi-icon">😊</span>
              <span class="pmi-label">切换导游表情</span>
              <van-icon name="arrow" size="14" color="#c0c4cc" />
            </div>
            <div class="p-menu-item" @click="activeTab = 'map'">
              <span class="pmi-icon">🗺️</span>
              <span class="pmi-label">查看景区地图</span>
              <van-icon name="arrow" size="14" color="#c0c4cc" />
            </div>
            <div class="p-menu-item" @click="activeTab = 'discover'">
              <span class="pmi-icon">🧭</span>
              <span class="pmi-label">探索发现</span>
              <van-icon name="arrow" size="14" color="#c0c4cc" />
            </div>
          </div>

          <div class="p-menu">
            <div class="p-menu-item" @click="openVisits">
              <span class="pmi-icon">📋</span>
              <span class="pmi-label">游览记录</span>
              <van-icon name="arrow" size="14" color="#c0c4cc" />
            </div>
            <div class="p-menu-item" @click="openConversations">
              <span class="pmi-icon">💬</span>
              <span class="pmi-label">对话记录</span>
              <van-icon name="arrow" size="14" color="#c0c4cc" />
            </div>
            <div class="p-menu-item" @click="openSettings">
              <span class="pmi-icon">⚙️</span>
              <span class="pmi-label">设置</span>
              <van-icon name="arrow" size="14" color="#c0c4cc" />
            </div>
          </div>

          <div class="p-menu">
            <div class="p-menu-item danger" @click="handleLogout">
              <span class="pmi-icon">🚪</span>
              <span class="pmi-label">退出登录</span>
              <van-icon name="arrow" size="14" color="#ff4757" />
            </div>
          </div>

          <p class="profile-version">灵山胜境 · 智能导游 v1.0</p>
          <div class="scroll-spacer"></div>
        </div>
      </div>
    </transition>

    <!-- ============================================================ -->
    <!--  游览记录 Popup                                               -->
    <!-- ============================================================ -->
    <van-popup
      v-model:show="showVisits"
      position="bottom"
      :style="{ height: '85%', borderRadius: '20px 20px 0 0' }"
      closeable
      round
    >
      <div class="visits-panel">
        <div class="visits-header">
          <h3>📋 游览记录</h3>
          <span class="visits-count" v-if="visits.length">共 {{ visits.length }} 条</span>
        </div>

        <!-- 加载中 -->
        <div v-if="visitsLoading" class="visits-loading">
          <van-loading type="spinner" size="24" color="#667eea" />
          <span>加载中…</span>
        </div>

        <!-- 空状态 -->
        <div v-else-if="visits.length === 0" class="visits-empty">
          <span class="empty-icon">📭</span>
          <p>暂无游览记录</p>
          <span class="empty-hint">去景区逛逛，记录会自动生成</span>
        </div>

        <!-- 记录列表 -->
        <div v-else class="visits-scroll">
          <div
            v-for="item in visits"
            :key="item.id"
            class="visit-card"
          >
            <div class="vc-top">
              <span class="vc-name">📍 {{ item.attraction_name }}</span>
              <span class="vc-date">{{ formatDate(item.visit_date) }}</span>
            </div>
            <div class="vc-meta">
              <span v-if="item.stay_duration !== null && item.stay_duration !== undefined">
                🕐 停留 {{ formatDuration(item.stay_duration) }}
              </span>
              <span v-if="item.total_cost">
                💰 ¥{{ item.total_cost }}
              </span>
              <span v-if="item.satisfaction">
                {{ '⭐'.repeat(item.satisfaction) }}
              </span>
            </div>
            <div class="vc-costs" v-if="item.ticket_cost || item.food_cost || item.shopping_cost">
              <span v-if="item.ticket_cost">🎫 门票 ¥{{ item.ticket_cost }}</span>
              <span v-if="item.food_cost">🍜 餐饮 ¥{{ item.food_cost }}</span>
              <span v-if="item.shopping_cost">🛍️ 购物 ¥{{ item.shopping_cost }}</span>
            </div>
          </div>
          <div class="scroll-spacer"></div>
        </div>
      </div>
    </van-popup>

    <!-- ============================================================ -->
    <!--  设置 Popup                                                    -->
    <!-- ============================================================ -->
    <van-popup
      v-model:show="showSettings"
      position="bottom"
      :style="{ height: '85%', borderRadius: '20px 20px 0 0' }"
      closeable
      round
    >
      <div class="settings-panel">
        <div class="settings-header">
          <h3>⚙️ 设置</h3>
        </div>

        <div class="settings-scroll">
          <!-- ===== 外观设置 ===== -->
          <div class="settings-section">
            <div class="section-title">外观</div>

            <div class="settings-item">
              <div class="si-left">
                <span class="si-icon">🌙</span>
                <div class="si-text">
                  <span class="si-label">暗色模式</span>
                  <span class="si-desc">切换深色/浅色主题</span>
                </div>
              </div>
              <van-switch
                :model-value="darkMode"
                @update:model-value="toggleDarkMode"
                size="26"
                active-color="#667eea"
              />
            </div>

            <div class="settings-item">
              <div class="si-left">
                <span class="si-icon">🔤</span>
                <div class="si-text">
                  <span class="si-label">字体大小</span>
                  <span class="si-desc">当前: {{ fontSizeLabel }}</span>
                </div>
              </div>
              <div class="font-size-picker">
                <button class="fs-btn" @click="setFontSize(-1)" :disabled="fontSizeIdx <= 0">A-</button>
                <span class="fs-val">{{ fontSizeLabel }}</span>
                <button class="fs-btn" @click="setFontSize(1)" :disabled="fontSizeIdx >= fontSizes.length - 1">A+</button>
              </div>
            </div>
          </div>

          <!-- ===== 账户设置 ===== -->
          <div class="settings-section">
            <div class="section-title">账户</div>

            <div class="settings-item" @click="showUsernameEdit = true">
              <div class="si-left">
                <span class="si-icon">👤</span>
                <div class="si-text">
                  <span class="si-label">修改用户名</span>
                  <span class="si-desc">当前: {{ auth?.userInfo?.username || '游客' }}</span>
                </div>
              </div>
              <van-icon name="arrow" size="14" color="#c0c4cc" />
            </div>

            <div class="settings-item" @click="showGenderPicker = true">
              <div class="si-left">
                <span class="si-icon">⚧</span>
                <div class="si-text">
                  <span class="si-label">性别</span>
                  <span class="si-desc">{{ auth?.userInfo?.gender || '未设置' }}</span>
                </div>
              </div>
              <van-icon name="arrow" size="14" color="#c0c4cc" />
            </div>
          </div>

          <!-- ===== 数据管理 ===== -->
          <div class="settings-section">
            <div class="section-title">数据</div>

            <div class="settings-item" @click="handleClearCache">
              <div class="si-left">
                <span class="si-icon">🗑️</span>
                <div class="si-text">
                  <span class="si-label">清除缓存</span>
                  <span class="si-desc">清除本地保存的临时数据</span>
                </div>
              </div>
              <van-icon name="arrow" size="14" color="#c0c4cc" />
            </div>
          </div>

          <!-- ===== 关于 ===== -->
          <div class="settings-section">
            <div class="section-title">关于</div>

            <div class="settings-item about-item">
              <div class="si-left">
                <span class="si-icon">📱</span>
                <div class="si-text">
                  <span class="si-label">灵山胜境 · 智能导游</span>
                  <span class="si-desc">版本 v1.0 · Build 2026</span>
                </div>
              </div>
            </div>
          </div>

          <div class="scroll-spacer"></div>
        </div>
      </div>
    </van-popup>

    <!-- ============================================================ -->
    <!--  修改用户名 Popup                                             -->
    <!-- ============================================================ -->
    <van-popup
      v-model:show="showUsernameEdit"
      position="bottom"
      :style="{ borderRadius: '20px 20px 0 0' }"
      closeable
      round
    >
      <div class="username-edit-panel">
        <h3>修改用户名</h3>
        <p class="ue-hint">输入新的用户名（仅支持中英文、数字、下划线）</p>
        <van-field
          v-model="editUsername"
          placeholder="请输入新用户名"
          maxlength="20"
          clearable
          :rules="[{ required: true, message: '用户名不能为空' }]"
        />
        <div class="ue-actions">
          <van-button round block type="primary" @click="handleUpdateUsername" :loading="updatingUsername">
            确认修改
          </van-button>
        </div>
      </div>
    </van-popup>

    <!-- ============================================================ -->
    <!--  性别选择 Popup                                                -->
    <!-- ============================================================ -->
    <van-popup
      v-model:show="showGenderPicker"
      position="bottom"
      :style="{ borderRadius: '20px 20px 0 0' }"
      closeable
      round
    >
      <div class="username-edit-panel">
        <h3>选择性别</h3>
        <van-radio-group v-model="editGender" class="gender-radio-group">
          <van-cell-group inset>
            <van-cell title="男" clickable @click="editGender = '男'">
              <template #right-icon>
                <van-radio name="男" />
              </template>
            </van-cell>
            <van-cell title="女" clickable @click="editGender = '女'">
              <template #right-icon>
                <van-radio name="女" />
              </template>
            </van-cell>
            <van-cell title="其他" clickable @click="editGender = '其他'">
              <template #right-icon>
                <van-radio name="其他" />
              </template>
            </van-cell>
          </van-cell-group>
        </van-radio-group>
        <div class="ue-actions" style="margin-top: 16px;">
          <van-button round block plain @click="editGender = ''; showGenderPicker = false">不设置</van-button>
          <van-button round block type="primary" @click="handleUpdateGender" style="margin-top: 8px;">确认</van-button>
        </div>
      </div>
    </van-popup>

    <!-- ============================================================ -->
    <!--  对话记录 Popup                                               -->
    <!-- ============================================================ -->
    <van-popup
      v-model:show="showConversations"
      position="bottom"
      :style="{ height: '85%', borderRadius: '20px 20px 0 0' }"
      closeable
      round
    >
      <div class="conversations-panel">
        <div class="conversations-header">
          <h3>💬 对话记录</h3>
          <span class="conversations-count" v-if="conversations.length">共 {{ conversations.length }} 条</span>
        </div>

        <!-- 加载中 -->
        <div v-if="conversationsLoading" class="conversations-loading">
          <van-loading type="spinner" size="24" color="#667eea" />
          <span>加载中…</span>
        </div>

        <!-- 空状态 -->
        <div v-else-if="conversations.length === 0" class="conversations-empty">
          <span class="empty-icon">💬</span>
          <p>暂无对话记录</p>
          <span class="empty-hint">与AI导游聊天后，记录将保存在这里</span>
        </div>

        <!-- 对话列表 -->
        <div v-else class="conversations-scroll">
          <div
            v-for="item in conversations"
            :key="item.id"
            class="conv-card"
            @click="toggleConvDetail(item.id)"
          >
            <div class="cc-top">
              <span class="cc-question-label">🙋 问</span>
              <span class="cc-text">{{ truncateConvText(item.question) }}</span>
              <span class="cc-date">{{ formatConvDate(item.created_at) }}</span>
            </div>
            <transition name="conv-expand">
              <div v-if="expandedConvs.has(item.id)" class="cc-answer">
                <div class="cc-answer-label">🤖 答</div>
                <div class="cc-answer-text" v-html="formatConvAnswer(item.answer)"></div>
              </div>
            </transition>
          </div>
          <div class="scroll-spacer"></div>
        </div>
      </div>
    </van-popup>

    <!-- ============================================================ -->
    <!--  底部导航栏 · Bottom Tab Bar                                  -->
    <!-- ============================================================ -->
    <nav class="bottom-nav">
      <div class="nav-inner">
        <button
          v-for="t in tabs"
          :key="t.key"
          class="nav-item"
          :class="{ active: activeTab === t.key }"
          @click="switchTab(t.key)"
        >
          <span class="nav-emoji">{{ t.emoji }}</span>
          <span class="nav-label">{{ t.label }}</span>
          <span v-if="activeTab === t.key" class="nav-dot"></span>
        </button>
      </div>
    </nav>
  </div>
</template>

<script setup>
import { ref, inject, onMounted, nextTick, watch, computed } from 'vue'
import Live2DViewers from '@/components/Live2DViewers.vue'
import MapView from '@/views/MapView.vue'
import request from '@/utils/request'
import { showConfirmDialog, showToast } from 'vant'

// ═══════════════════════════════════════════════════════════════
//  Inject chat context (same as before)
// ═══════════════════════════════════════════════════════════════
const ctx = inject('chatContext')

const {
  loading,
  inputText,
  isRecording,
  recordingTime,
  paragraphs,
  activeParaIdx,
  showMap,
  live2dRef,
  currentAttraction,
  weather,
  auth,
  handleLogout,
  handleNextMotion,
  handleRecommend,
  handleSend,
  toggleVoiceInput,
} = ctx

// ═══════════════════════════════════════════════════════════════
//  Background
// ═══════════════════════════════════════════════════════════════
const backgroundUrl = ref(import.meta.env.BASE_URL + 'background.jpg')

onMounted(async () => {
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
  } catch { /* fallback to default */ }
})

// ═══════════════════════════════════════════════════════════════
//  Tab navigation
// ═══════════════════════════════════════════════════════════════
const activeTab = ref('guide')
const tabs = [
  { key: 'guide',    emoji: '🤖', label: '导游' },
  { key: 'map',      emoji: '🗺️', label: '地图' },
  { key: 'discover', emoji: '🧭', label: '发现' },
  { key: 'profile',  emoji: '👤', label: '我的' },
]

function switchTab(key) {
  activeTab.value = key
  // Keep map state in sync
  if (key === 'map') {
    showMap.value = true
    // v-show 切换后容器从 display:none 变为可见，Leaflet 需要重新计算尺寸
    nextTick(() => {
      setTimeout(() => {
        window.map?.invalidateSize()
      }, 200)
    })
  } else {
    showMap.value = false
  }
}

// ═══════════════════════════════════════════════════════════════
//  Quick actions (set inputText → handleSend)
// ═══════════════════════════════════════════════════════════════
function doRecommend() {
  handleRecommend()
}

function doQuickAsk(question) {
  if (loading.value) return
  inputText.value = question
  handleSend()
}

// ═══════════════════════════════════════════════════════════════
//  Map page helpers
// ═══════════════════════════════════════════════════════════════
function focusCurrentLocation() {
  // Trigger map to pan to current GPS position
  if (window.map && ctx.getCurrentPosition) {
    ctx.getCurrentPosition().then(pos => {
      if (pos && window.map) {
        window.map.setView([pos.latitude, pos.longitude], 16)
      }
    })
  }
}

// ═══════════════════════════════════════════════════════════════
//  Discover page data
// ═══════════════════════════════════════════════════════════════
const hotTopics = [
  '景点介绍', '历史文化', '游玩攻略',
  '美食推荐', '交通指南', '拍照打卡',
]

const features = [
  { emoji: '🤖', title: 'AI 智能导游',  desc: '随时随地为您讲解景区知识' },
  { emoji: '🗣️', title: '语音交互',    desc: '无需打字，说话就能提问' },
  { emoji: '🗺️', title: '实时地图',    desc: '精准导航，轻松游览不迷路' },
  { emoji: '🎬', title: '视频联动',    desc: '讲解同步展示精彩视频内容' },
]

// ═══════════════════════════════════════════════════════════════
//  游览记录
// ═══════════════════════════════════════════════════════════════
const showVisits = ref(false)
const visits = ref([])
const visitsLoading = ref(false)

async function fetchVisits() {
  visitsLoading.value = true
  try {
    const res = await request.get('/tourist/visits')
    visits.value = Array.isArray(res) ? res : (res.visits || [])
  } catch (e) {
    console.warn('获取游览记录失败:', e)
    visits.value = []
  } finally {
    visitsLoading.value = false
  }
}

function openVisits() {
  showVisits.value = true
  if (visits.value.length === 0) {
    fetchVisits()
  }
}

function formatDate(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  const m = d.getMonth() + 1
  const day = d.getDate()
  return `${d.getFullYear()}/${m.toString().padStart(2, '0')}/${day.toString().padStart(2, '0')}`
}

function formatDuration(hours) {
  if (hours == null) return ''
  if (hours < 1) return `${Math.round(hours * 60)} 分钟`
  return `${hours.toFixed(1)} 小时`
}

// ═══════════════════════════════════════════════════════════════
//  对话记录
// ═══════════════════════════════════════════════════════════════
const showConversations = ref(false)
const conversations = ref([])
const conversationsLoading = ref(false)
const expandedConvs = ref(new Set())

async function fetchConversations() {
  conversationsLoading.value = true
  try {
    const res = await request.get('/tourist/conversations', { params: { limit: 50 } })
    conversations.value = res.items || []
  } catch (e) {
    console.warn('获取对话记录失败:', e)
    conversations.value = []
  } finally {
    conversationsLoading.value = false
  }
}

function openConversations() {
  showConversations.value = true
  if (conversations.value.length === 0) {
    fetchConversations()
  }
}

function toggleConvDetail(id) {
  const s = new Set(expandedConvs.value)
  if (s.has(id)) {
    s.delete(id)
  } else {
    s.add(id)
  }
  expandedConvs.value = s
}

function truncateConvText(text) {
  if (!text) return ''
  const cleaned = cleanConvText(text)
  return cleaned.length > 40 ? cleaned.slice(0, 40) + '…' : cleaned
}

// 过滤对话记录中的系统提示词（如动作禁止前缀、视频/动作标记等）
function cleanConvText(text) {
  if (!text) return ''
  return text
    .replace(/^【[^】]*】\s*/gm, '')            // 移除【...】前缀（支持多行）
    .replace(/\[动作:\w+\]\s*/g, '')            // 移除 [动作:xxx] 标记
    .replace(/\[视频:[\w-]+\]\s*/g, '')         // 移除 [视频:xxx] 标记
    .replace(/\n\n\(当前用户经纬度.*?\)\s*/g, '')  // 移除 GPS 坐标注入
    .trim()
}

// 格式化答案文本用于显示（清理标记 + 换行转<br/>）
function formatConvAnswer(text) {
  const cleaned = cleanConvText(text)
  // 转义 HTML 后转换换行
  return cleaned
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\n/g, '<br/>')
}

function formatConvDate(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  const now = new Date()
  const diffMs = now - d
  const diffMin = Math.floor(diffMs / 60000)
  const diffHr = Math.floor(diffMs / 3600000)
  const diffDay = Math.floor(diffMs / 86400000)

  if (diffMin < 1) return '刚刚'
  if (diffMin < 60) return `${diffMin}分钟前`
  if (diffHr < 24) return `${diffHr}小时前`
  if (diffDay < 7) return `${diffDay}天前`

  const m = d.getMonth() + 1
  const day = d.getDate()
  return `${m.toString().padStart(2, '0')}/${day.toString().padStart(2, '0')}`
}

// ═══════════════════════════════════════════════════════════════
//  设置
// ═══════════════════════════════════════════════════════════════
const showSettings = ref(false)
const showUsernameEdit = ref(false)
const editUsername = ref('')
const updatingUsername = ref(false)
const showGenderPicker = ref(false)
const editGender = ref('')

// 暗色模式
const darkMode = ref(localStorage.getItem('tourist_dark_mode') === 'true')

function applyDarkMode() {
  const app = document.querySelector('.mobile-app')
  if (darkMode.value) {
    app?.classList.add('dark')
    document.documentElement.classList.add('dark')
  } else {
    app?.classList.remove('dark')
    document.documentElement.classList.remove('dark')
  }
}

function toggleDarkMode(val) {
  darkMode.value = val
  localStorage.setItem('tourist_dark_mode', val ? 'true' : 'false')
  applyDarkMode()
}

// 字体大小
const fontSizes = ['小', '标准', '大', '超大']
const fontSizesMap = { 0: 0.875, 1: 1.0, 2: 1.125, 3: 1.25 }
const fontSizeIdx = ref(parseInt(localStorage.getItem('tourist_font_size_idx') || '1'))
const fontSizeLabel = computed(() => fontSizes[fontSizeIdx.value] || '标准')

function applyFontSize() {
  const scale = fontSizesMap[fontSizeIdx.value] || 1.0
  const el = document.querySelector('.mobile-app')
  if (el) {
    ;(el).style.setProperty('--font-scale', scale)
  }
}

function setFontSize(delta) {
  const next = fontSizeIdx.value + delta
  if (next < 0 || next >= fontSizes.length) return
  fontSizeIdx.value = next
  localStorage.setItem('tourist_font_size_idx', String(next))
  applyFontSize()
}

// 打开设置面板
function openSettings() {
  editUsername.value = auth?.userInfo?.username || ''
  editGender.value = auth?.userInfo?.gender || ''
  showSettings.value = true
}

// 修改用户名
async function handleUpdateUsername() {
  const name = editUsername.value.trim()
  if (!name) return
  if (name === auth?.userInfo?.username) {
    showUsernameEdit.value = false
    return
  }
  updatingUsername.value = true
  try {
    await auth.updateProfile(name, editGender.value)
    showUsernameEdit.value = false
    showSettings.value = false
  } catch (e) {
    console.warn('修改用户名失败:', e)
  } finally {
    updatingUsername.value = false
  }
}

// 修改性别
async function handleUpdateGender() {
  const name = editUsername.value.trim() || auth?.userInfo?.username || '游客'
  try {
    await auth.updateProfile(name, editGender.value)
    showGenderPicker.value = false
  } catch (e) {
    console.warn('修改性别失败:', e)
  }
}

// 清除缓存
async function handleClearCache() {
  try {
    await showConfirmDialog({
      title: '清除缓存',
      message: '将清除本地保存的临时数据，登录状态和设置项不会受影响。确定继续吗？',
      confirmButtonText: '确定清除',
      cancelButtonText: '取消',
      confirmButtonColor: '#ff4757',
    })
  } catch {
    return // 用户取消
  }

  // 保留登录状态和核心设置的缓存 keys
  const keepKeys = [
    'tourist_token', 'tourist_id', 'tourist_user_info',
    'tourist_dark_mode', 'tourist_font_size_idx',
    'tourist_remember_me', 'tourist_remember_username', 'tourist_remember_password',
  ]
  const removed = []
  for (let i = localStorage.length - 1; i >= 0; i--) {
    const key = localStorage.key(i)
    if (key && !keepKeys.includes(key) && key.startsWith('tourist_')) {
      removed.push(key)
      localStorage.removeItem(key)
    }
  }
  // 也清理 sessionStorage
  for (let i = sessionStorage.length - 1; i >= 0; i--) {
    const key = sessionStorage.key(i)
    if (key) sessionStorage.removeItem(key)
  }
  showToast({ message: `已清除 ${removed.length} 项缓存数据`, icon: 'success', duration: 2000 })
}

// 初始化暗色模式和字体大小
onMounted(() => {
  applyDarkMode()
  applyFontSize()
})

// ═══════════════════════════════════════════════════════════════
//  Ref bindings (unchanged from original)
// ═══════════════════════════════════════════════════════════════
function setLive2d(el) {
  live2dRef.value = el
}
</script>

<style scoped>
/* ═══════════════════════════════════════════════════════════════
   CSS Custom Properties
   ═══════════════════════════════════════════════════════════════ */
.mobile-app {
  --primary: #667eea;
  --primary-dark: #5a6fd6;
  --accent: #764ba2;
  --gradient: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  --gradient-warm: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
  --gradient-cool: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
  --bg: #f4f6fb;
  --card: #ffffff;
  --text: #1e1e2e;
  --text-secondary: #6b7280;
  --text-muted: #9ca3af;
  --shadow-sm: 0 1px 3px rgba(0,0,0,.06), 0 1px 2px rgba(0,0,0,.04);
  --shadow-md: 0 4px 16px rgba(0,0,0,.08), 0 2px 6px rgba(0,0,0,.04);
  --shadow-lg: 0 12px 32px rgba(0,0,0,.12), 0 4px 12px rgba(0,0,0,.06);
  --radius-sm: 10px;
  --radius-md: 16px;
  --radius-lg: 24px;
  --nav-height: 68px;
  --safe-bottom: env(safe-area-inset-bottom, 0px);

  position: fixed;
  inset: 0;
  display: flex;
  flex-direction: column;
  background: var(--bg);
  overflow: hidden;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC',
    'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
  -webkit-font-smoothing: antialiased;
}

/* ═══════════════════════════════════════════════════════════════
   Page Transition
   ═══════════════════════════════════════════════════════════════ */
.page-fade-enter-active,
.page-fade-leave-active {
  transition: opacity .25s ease, transform .25s ease;
}
.page-fade-enter-from {
  opacity: 0;
  transform: translateY(8px);
}
.page-fade-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

/* ═══════════════════════════════════════════════════════════════
   Generic Page Shell
   ═══════════════════════════════════════════════════════════════ */
.page {
  position: absolute;
  inset: 0;
  bottom: calc(var(--nav-height) + var(--safe-bottom));
  overflow: hidden;
}

/* ═══════════════════════════════════════════════════════════════
   PAGE 1 — 导游 · Guide
   ═══════════════════════════════════════════════════════════════ */
.guide-page {
  background: #000;
}

/* Live2D backdrop */
.live2d-backdrop {
  position: absolute;
  inset: 0;
  background-size: cover;
  background-position: center;
  background-repeat: no-repeat;
  pointer-events: none;
}
.live2d-backdrop :deep(canvas) {
  pointer-events: auto;
}

/* Top bar — glass */
.guide-top-bar {
  position: absolute;
  top: 0; left: 0; right: 0;
  z-index: 10;
  padding-top: env(safe-area-inset-top, 8px);
}
.top-bar-bg {
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, rgba(0,0,0,.35) 0%, transparent 100%);
  pointer-events: none;
}
.top-bar-row {
  position: relative;
  display: flex;
  align-items: center;
  padding: 8px 16px 6px;
  gap: 12px;
}
.guide-location {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px 6px 10px;
  background: rgba(255,255,255,.18);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-radius: 20px;
  border: 1px solid rgba(255,255,255,.22);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}
.loc-dot {
  width: 8px; height: 8px;
  border-radius: 50%;
  background: #4ade80;
  box-shadow: 0 0 8px rgba(74,222,128,.6);
}
.loc-text {
  color: #fff;
  font-size: 14px;
  font-weight: 500;
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.top-bar-spacer { flex: 1; }
.top-icon-btn {
  width: 38px; height: 38px;
  border-radius: 50%;
  border: 1px solid rgba(255,255,255,.25);
  background: rgba(255,255,255,.15);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  transition: background .2s;
}
.top-icon-btn:active { background: rgba(255,255,255,.3); }

/* Loading orb */
.guide-loading {
  position: absolute;
  top: 40%;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 20;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}
.loading-orb {
  position: relative;
  width: 72px; height: 72px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.orb-ring {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  border: 2px solid rgba(102,126,234,.25);
  animation: orb-pulse 2s ease-out infinite;
}
.orb-ring.r2 { animation-delay: .6s; }
.orb-ring.r3 { animation-delay: 1.2s; }
.orb-core {
  width: 40px; height: 40px;
  border-radius: 50%;
  background: rgba(255,255,255,.92);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 20px rgba(102,126,234,.25);
}
@keyframes orb-pulse {
  0%   { transform: scale(.6); opacity: .8; }
  100% { transform: scale(1.8); opacity: 0; }
}
.loading-label {
  font-size: 14px;
  color: rgba(255,255,255,.85);
  font-weight: 500;
  letter-spacing: .5px;
}

/* ====== 字幕 · EXACT PRESERVATION ====== */
.mobile-subtitle-container {
  position: fixed;
  bottom: 240px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 15;
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border-radius: 20px;
  /* 增大水平内边距，防止文字滚动时贴边被"挡" */
  padding: 12px 28px;
  max-width: 88vw;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
  display: flex;
  justify-content: center;
  align-items: center;
  white-space: nowrap;
  overflow-x: auto;
  overflow-y: hidden;
  scrollbar-width: none;
  -ms-overflow-style: none;
  /* 让滚动内容两端有渐隐效果，避免硬切 */
  --fade-width: 16px;
  mask-image: linear-gradient(
    90deg,
    transparent 0%,
    black var(--fade-width),
    black calc(100% - var(--fade-width)),
    transparent 100%
  );
  -webkit-mask-image: linear-gradient(
    90deg,
    transparent 0%,
    black var(--fade-width),
    black calc(100% - var(--fade-width)),
    transparent 100%
  );
}
.mobile-subtitle-container::-webkit-scrollbar {
  display: none;
}
.subtitle-para {
  font-size: 16px;
  color: #333;
  font-weight: normal;
  padding: 4px 8px;
  border-radius: 8px;
  background: transparent;
  display: inline-block;
  white-space: nowrap;
}
/* ====== 字幕结束 ====== */

/* Quick chips */
.guide-chips {
  position: absolute;
  bottom: 210px;
  left: 0; right: 0;
  display: flex;
  justify-content: center;
  gap: 10px;
  padding: 0 20px;
  z-index: 5;
  flex-wrap: wrap;
}
.chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 9px 16px;
  border-radius: 20px;
  border: 1px solid rgba(255,255,255,.35);
  background: rgba(255,255,255,.18);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  color: #fff;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  transition: all .2s;
  white-space: nowrap;
}
.chip:active {
  background: rgba(255,255,255,.32);
  transform: scale(.95);
}
.chip-emoji { font-size: 15px; }

/* Voice bar */
.guide-voice-bar {
  position: absolute;
  bottom: 0; left: 0; right: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 0 0 36px 0;
  z-index: 10;
  background: linear-gradient(180deg, transparent 0%, rgba(0,0,0,.35) 100%);
}
.voice-button-shell {
  position: relative;
  width: 72px; height: 72px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.voice-btn-core {
  width: 64px; height: 64px;
  border-radius: 50%;
  border: 2px solid rgba(255,255,255,.5);
  background: rgba(255,255,255,.2);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  transition: all .25s ease;
  position: relative;
  z-index: 2;
}
.voice-btn-core:active { transform: scale(.92); }
.voice-button-shell.recording .voice-btn-core {
  border-color: #ff6b7a;
  background: rgba(255,71,87,.22);
  box-shadow: 0 0 32px rgba(255,71,87,.35);
  animation: voice-beat 1.2s ease-in-out infinite;
}
@keyframes voice-beat {
  0%, 100% { transform: scale(1); }
  15%  { transform: scale(1.06); }
  30%  { transform: scale(1); }
  45%  { transform: scale(1.05); }
  60%  { transform: scale(1); }
}
.voice-ripple {
  position: absolute;
  inset: -8px;
  border-radius: 50%;
  border: 2px solid rgba(255,71,87,.3);
  animation: ripple-out 1.8s ease-out infinite;
  z-index: 1;
}
.voice-ripple.r2 { animation-delay: .9s; }
@keyframes ripple-out {
  0%   { transform: scale(.7); opacity: .9; }
  100% { transform: scale(1.7); opacity: 0; }
}
.voice-hint {
  font-size: 13px;
  color: rgba(255,255,255,.7);
  font-weight: 400;
  letter-spacing: .4px;
}

/* ═══════════════════════════════════════════════════════════════
   PAGE 2 — 地图 · Map
   ═══════════════════════════════════════════════════════════════ */
.map-page {
  display: flex;
  flex-direction: column;
  background: #e8ecf1;
}
.map-header-bar {
  display: flex;
  align-items: center;
  padding: 8px 12px;
  padding-top: calc(8px + env(safe-area-inset-top, 8px));
  gap: 12px;
  background: #fff;
  z-index: 5;
  box-shadow: 0 1px 4px rgba(0,0,0,.06);
}
.map-back, .map-locate {
  width: 38px; height: 38px;
  border-radius: 50%;
  border: none;
  background: var(--bg);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--text);
  -webkit-tap-highlight-color: transparent;
  transition: background .2s;
}
.map-back:active, .map-locate:active { background: #e2e6ed; }
.map-title {
  flex: 1;
  font-size: 17px;
  font-weight: 600;
  color: var(--text);
  text-align: center;
}
.map-stage {
  flex: 1;
  position: relative;
  overflow: hidden;
}
.map-stage :deep(.map-container),
.map-stage :deep(#map) {
  width: 100% !important;
  height: 100% !important;
}

/* Info sheet above map */
.map-info-sheet {
  position: absolute;
  bottom: 0; left: 0; right: 0;
  background: #fff;
  border-radius: 20px 20px 0 0;
  box-shadow: 0 -6px 24px rgba(0,0,0,.1);
  z-index: 8;
  padding: 10px 20px 20px;
  padding-bottom: calc(20px + env(safe-area-inset-bottom, 0px));
}
.sheet-handle {
  width: 36px; height: 4px;
  border-radius: 2px;
  background: #d1d5db;
  margin: 0 auto 12px;
}
.sheet-body h4 { font-size: 15px; margin: 0 0 4px; color: var(--text); }
.sheet-body p  { font-size: 13px; color: var(--text-secondary); margin: 0 0 10px; line-height: 1.5; }
.sheet-ask {
  background: var(--gradient);
  border: none;
  color: #fff;
  padding: 8px 20px;
  border-radius: 18px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
}

/* slide-up transition */
.slide-up-enter-active, .slide-up-leave-active {
  transition: transform .3s cubic-bezier(.4,0,.2,1), opacity .3s;
}
.slide-up-enter-from, .slide-up-leave-to {
  transform: translateY(100%);
  opacity: 0;
}

/* ═══════════════════════════════════════════════════════════════
   PAGE 3 — 发现 · Discover
   ═══════════════════════════════════════════════════════════════ */
.discover-page {
  display: flex;
  flex-direction: column;
  background: var(--bg);
}
.discover-hero {
  padding: 28px 20px 12px;
  padding-top: calc(28px + env(safe-area-inset-top, 8px));
  background: #fff;
}
.hero-title {
  font-size: 26px;
  font-weight: 700;
  color: var(--text);
  margin: 0 0 4px;
  letter-spacing: -.3px;
}
.hero-sub {
  font-size: 14px;
  color: var(--text-secondary);
  margin: 0;
}
.discover-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 14px 16px 0;
  -webkit-overflow-scrolling: touch;
}
.d-card {
  background: var(--card);
  border-radius: var(--radius-md);
  padding: 18px;
  margin-bottom: 14px;
  box-shadow: var(--shadow-sm);
}
.card-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text);
  margin: 0 0 12px;
}

/* Weather */
.weather-card { overflow: hidden; position: relative; }
.weather-card::before {
  content: '';
  position: absolute;
  top: -30px; right: -30px;
  width: 120px; height: 120px;
  border-radius: 50%;
  background: var(--gradient-cool);
  opacity: .12;
}
.wc-top {
  display: flex;
  align-items: center;
  gap: 14px;
  position: relative;
  z-index: 1;
}
.wc-emoji { font-size: 40px; }
.wc-temp { font-size: 38px; font-weight: 700; color: var(--text); line-height: 1; }
.wc-label { font-size: 14px; color: var(--text-secondary); display: block; margin-top: 2px; }
.wc-meta {
  display: flex;
  gap: 18px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #f3f4f6;
  font-size: 12px;
  color: var(--text-muted);
  position: relative;
  z-index: 1;
}
.wc-meta span { display: flex; align-items: center; gap: 4px; }

/* POI */
.poi-card {
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  transition: transform .2s;
  position: relative;
  overflow: hidden;
}
.poi-card:active { transform: scale(.98); }
.poi-badge {
  display: inline-block;
  font-size: 11px;
  font-weight: 600;
  color: #667eea;
  background: rgba(102,126,234,.1);
  padding: 3px 10px;
  border-radius: 10px;
  margin-bottom: 8px;
}
.poi-card h3 { font-size: 16px; margin: 0 0 4px; color: var(--text); }
.poi-card p  { font-size: 13px; color: var(--text-secondary); margin: 0 0 8px; line-height: 1.5; }
.poi-arrow { font-size: 13px; color: #667eea; font-weight: 500; }

/* Topics */
.topics-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.topic-tag {
  font-size: 13px;
  padding: 7px 14px;
  border-radius: 16px;
  background: #f3f4f6;
  color: var(--text);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  transition: all .2s;
}
.topic-tag:active {
  background: var(--gradient);
  color: #fff;
}

/* Features */
.feature-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 0;
}
.feature-row + .feature-row { border-top: 1px solid #f3f4f6; }
.feat-emoji { font-size: 28px; flex-shrink: 0; }
.feat-text { display: flex; flex-direction: column; gap: 2px; }
.feat-text strong { font-size: 14px; color: var(--text); }
.feat-text span  { font-size: 12px; color: var(--text-muted); }

/* ═══════════════════════════════════════════════════════════════
   PAGE 4 — 我的 · Profile
   ═══════════════════════════════════════════════════════════════ */
.profile-page {
  display: flex;
  flex-direction: column;
  background: var(--bg);
}
.profile-header-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 32px 20px 24px;
  padding-top: calc(32px + env(safe-area-inset-top, 8px));
  background: #fff;
  position: relative;
  overflow: hidden;
}
.profile-header-card::after {
  content: '';
  position: absolute;
  top: -60px; left: 50%;
  transform: translateX(-50%);
  width: 260px; height: 260px;
  border-radius: 50%;
  background: var(--gradient);
  opacity: .06;
}
.ph-avatar { position: relative; z-index: 1; margin-bottom: 12px; }
.avatar-ring {
  width: 72px; height: 72px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea, #764ba2, #f093fb);
  padding: 3px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.avatar-face {
  width: 100%; height: 100%;
  border-radius: 50%;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 32px;
}
.ph-name {
  font-size: 20px;
  font-weight: 600;
  color: var(--text);
  margin: 0 0 2px;
  position: relative;
  z-index: 1;
}
.ph-role {
  font-size: 13px;
  color: var(--text-muted);
  margin: 0;
  position: relative;
  z-index: 1;
}
.profile-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  -webkit-overflow-scrolling: touch;
}

/* Menu groups */
.p-menu {
  background: #fff;
  border-radius: var(--radius-sm);
  overflow: hidden;
  margin-bottom: 12px;
  box-shadow: var(--shadow-sm);
}
.p-menu-item {
  display: flex;
  align-items: center;
  padding: 14px 16px;
  gap: 12px;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  transition: background .15s;
}
.p-menu-item:active { background: #f9fafb; }
.p-menu-item + .p-menu-item { border-top: 1px solid #f3f4f6; }
.p-menu-item.danger:active { background: #fef2f2; }
.pmi-icon { font-size: 20px; flex-shrink: 0; }
.pmi-label { flex: 1; font-size: 14px; color: var(--text); }
.danger .pmi-label { color: #ff4757; }

.profile-version {
  text-align: center;
  font-size: 12px;
  color: var(--text-muted);
  margin: 20px 0 8px;
}

/* ═══════════════════════════════════════════════════════════════
   Bottom Navigation
   ═══════════════════════════════════════════════════════════════ */
.bottom-nav {
  position: absolute;
  bottom: 0; left: 0; right: 0;
  z-index: 50;
  padding-bottom: var(--safe-bottom);
  background: rgba(255,255,255,.92);
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  border-top: 1px solid rgba(0,0,0,.06);
}
.nav-inner {
  display: flex;
  height: var(--nav-height);
  padding: 0 8px;
}
.nav-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 3px;
  border: none;
  background: transparent;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  position: relative;
  transition: all .2s;
}
.nav-emoji {
  font-size: 22px;
  transition: transform .25s cubic-bezier(.34,1.56,.64,1);
}
.nav-item.active .nav-emoji {
  transform: scale(1.15);
}
.nav-label {
  font-size: 11px;
  font-weight: 500;
  color: var(--text-muted);
  transition: color .2s;
}
.nav-item.active .nav-label {
  color: var(--primary);
  font-weight: 600;
}
.nav-dot {
  position: absolute;
  bottom: 6px;
  width: 4px; height: 4px;
  border-radius: 50%;
  background: var(--primary);
}

/* ═══════════════════════════════════════════════════════════════
   Shared: fade transition
   ═══════════════════════════════════════════════════════════════ */
.fade-enter-active, .fade-leave-active {
  transition: opacity .3s ease;
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
}

/* ═══════════════════════════════════════════════════════════════
   Scroll spacer
   ═══════════════════════════════════════════════════════════════ */
.scroll-spacer { height: 20px; }

/* ═══════════════════════════════════════════════════════════════
   Dark Mode
   ═══════════════════════════════════════════════════════════════ */
.mobile-app.dark {
  --bg: #1a1a2e;
  --card: #16213e;
  --text: #e4e4e7;
  --text-secondary: #a1a1aa;
  --text-muted: #71717a;
  --shadow-sm: 0 1px 3px rgba(0,0,0,.3), 0 1px 2px rgba(0,0,0,.2);
  --shadow-md: 0 4px 16px rgba(0,0,0,.4), 0 2px 6px rgba(0,0,0,.3);
  --shadow-lg: 0 12px 32px rgba(0,0,0,.5), 0 4px 12px rgba(0,0,0,.4);
}

.mobile-app.dark .guide-page {
  background: #0d1117;
}

/* 暗色模式下白色背景的页面组件 */
.mobile-app.dark .profile-header-card,
.mobile-app.dark .discover-hero,
.mobile-app.dark .map-header-bar {
  background: #16213e;
}

.mobile-app.dark .p-menu {
  background: #16213e;
  box-shadow: 0 1px 3px rgba(0,0,0,.3);
}

.mobile-app.dark .p-menu-item:active {
  background: #1e2d4a;
}

.mobile-app.dark .p-menu-item + .p-menu-item {
  border-top-color: #1e2d4a;
}

.mobile-app.dark .map-page {
  background: #1a1a2e;
}

.mobile-app.dark .map-back,
.mobile-app.dark .map-locate {
  background: #1e2d4a;
  color: #e4e4e7;
}

.mobile-app.dark .map-back:active,
.mobile-app.dark .map-locate:active {
  background: #253552;
}

.mobile-app.dark .map-info-sheet {
  background: #16213e;
}

.mobile-app.dark .sheet-handle {
  background: #3f3f5c;
}

.mobile-app.dark .bottom-nav {
  background: rgba(22,33,62,.94);
  border-top-color: rgba(255,255,255,.08);
}

.mobile-app.dark .nav-label {
  color: #71717a;
}

.mobile-app.dark .nav-item.active .nav-label {
  color: #8b9cf7;
}

/* 深色模式下的卡片背景 */
.mobile-app.dark .d-card {
  background: #16213e;
  box-shadow: 0 1px 3px rgba(0,0,0,.3);
}

.mobile-app.dark .wc-meta {
  border-top-color: #1e2d4a;
}

.mobile-app.dark .topic-tag {
  background: #1e2d4a;
  color: #e4e4e7;
}

.mobile-app.dark .topic-tag:active {
  background: var(--gradient);
  color: #fff;
}

.mobile-app.dark .feature-row + .feature-row {
  border-top-color: #1e2d4a;
}

/* 发现页 Hero 按钮 */
.mobile-app.dark .poi-badge {
  background: rgba(102,126,234,.2);
  color: #8b9cf7;
}

/* ==================== 字体缩放 ==================== */
.mobile-app {
  --font-scale: 1.0;
  font-size: calc(14px * var(--font-scale));
}

.mobile-app .ph-name { font-size: calc(20px * var(--font-scale)); }
.mobile-app .hero-title { font-size: calc(26px * var(--font-scale)); }
.mobile-app .pmi-label { font-size: calc(14px * var(--font-scale)); }
.mobile-app .nav-label { font-size: calc(11px * var(--font-scale)); }
.mobile-app .loc-text { font-size: calc(14px * var(--font-scale)); }
.mobile-app .loading-label { font-size: calc(14px * var(--font-scale)); }
.mobile-app .chip { font-size: calc(13px * var(--font-scale)); }
.mobile-app .voice-hint { font-size: calc(13px * var(--font-scale)); }
.mobile-app .subtitle-para { font-size: calc(16px * var(--font-scale)); }
.mobile-app .hero-sub { font-size: calc(14px * var(--font-scale)); }
.mobile-app .card-title { font-size: calc(15px * var(--font-scale)); }
.mobile-app .d-card p, .mobile-app .d-card .topic-tag { font-size: calc(13px * var(--font-scale)); }
.mobile-app .feature-row strong { font-size: calc(14px * var(--font-scale)); }
.mobile-app .feature-row span { font-size: calc(12px * var(--font-scale)); }
.mobile-app .ph-role { font-size: calc(13px * var(--font-scale)); }
.mobile-app .sheet-body h4 { font-size: calc(15px * var(--font-scale)); }
.mobile-app .sheet-body p { font-size: calc(13px * var(--font-scale)); }
.mobile-app .vc-name { font-size: calc(15px * var(--font-scale)); }
.mobile-app .profile-version { font-size: calc(12px * var(--font-scale)); }
.mobile-app .map-title { font-size: calc(17px * var(--font-scale)); }

/* ═══════════════════════════════════════════════════════════════
   设置面板
   ═══════════════════════════════════════════════════════════════ */
.settings-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg);
}

.settings-header {
  flex-shrink: 0;
  padding: 20px 20px 8px;
}

.settings-header h3 {
  font-size: 20px;
  font-weight: 700;
  color: var(--text);
  margin: 0;
}

.settings-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 0 16px;
  -webkit-overflow-scrolling: touch;
}

.settings-section {
  margin-bottom: 8px;
}

.section-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  padding: 16px 4px 8px;
}

.settings-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  background: var(--card);
  border-radius: 12px;
  margin-bottom: 1px;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  transition: background .15s;
}

.settings-item:active {
  background: var(--bg);
}

.si-left {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
  min-width: 0;
}

.si-icon {
  font-size: 22px;
  flex-shrink: 0;
}

.si-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.si-label {
  font-size: 15px;
  font-weight: 500;
  color: var(--text);
}

.si-desc {
  font-size: 12px;
  color: var(--text-muted);
}

/* Font size picker */
.font-size-picker {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.fs-btn {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: 1.5px solid var(--primary);
  background: transparent;
  color: var(--primary);
  font-size: 14px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  transition: all .2s;
}

.fs-btn:active:not(:disabled) {
  background: var(--primary);
  color: #fff;
}

.fs-btn:disabled {
  opacity: .35;
  cursor: not-allowed;
}

/* 性别选择 */
.gender-radio-group {
  margin: 12px 0;
}

.fs-val {
  font-size: 13px;
  color: var(--text-secondary);
  min-width: 32px;
  text-align: center;
}

/* About item */
.about-item {
  cursor: default;
}

/* ==================== 用户名编辑面板 ==================== */
.username-edit-panel {
  padding: 24px 20px 20px;
  padding-bottom: calc(20px + env(safe-area-inset-bottom, 0px));
  background: var(--bg);
}

.username-edit-panel h3 {
  font-size: 18px;
  font-weight: 600;
  color: var(--text);
  margin: 0 0 8px;
}

.ue-hint {
  font-size: 13px;
  color: var(--text-muted);
  margin: 0 0 16px;
}

.username-edit-panel :deep(.van-field) {
  background: var(--card);
  border-radius: 10px;
  margin-bottom: 16px;
}

.ue-actions {
  padding: 0 4px;
}

.ue-actions :deep(.van-button--primary) {
  background: var(--gradient);
  border: none;
}

/* ═══════════════════════════════════════════════════════════════
   游览记录 Popup
   ═══════════════════════════════════════════════════════════════ */
.visits-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #f4f6fb;
}
.visits-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  padding: 20px 20px 12px;
  flex-shrink: 0;
}
.visits-header h3 {
  font-size: 20px;
  font-weight: 700;
  color: #1e1e2e;
  margin: 0;
}
.visits-count {
  font-size: 13px;
  color: #9ca3af;
}
.visits-loading {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: #6b7280;
  font-size: 14px;
}
.visits-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #9ca3af;
}
.visits-empty .empty-icon { font-size: 48px; }
.visits-empty p { font-size: 16px; margin: 0; color: #6b7280; }
.visits-empty .empty-hint { font-size: 13px; }

.visits-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 0 16px;
  -webkit-overflow-scrolling: touch;
}
.visit-card {
  background: #fff;
  border-radius: 14px;
  padding: 16px;
  margin-bottom: 10px;
  box-shadow: 0 1px 3px rgba(0,0,0,.04);
}
.vc-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}
.vc-name {
  font-size: 15px;
  font-weight: 600;
  color: #1e1e2e;
}
.vc-date {
  font-size: 12px;
  color: #9ca3af;
  flex-shrink: 0;
}
.vc-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 13px;
  color: #6b7280;
}
.vc-costs {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid #f3f4f6;
  font-size: 12px;
  color: #9ca3af;
}

/* ═══════════════════════════════════════════════════════════════
   对话记录 Popup
   ═══════════════════════════════════════════════════════════════ */
.conversations-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #f4f6fb;
}

.conversations-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  padding: 20px 20px 12px;
  flex-shrink: 0;
}

.conversations-header h3 {
  font-size: 20px;
  font-weight: 700;
  color: #1e1e2e;
  margin: 0;
}

.conversations-count {
  font-size: 13px;
  color: #9ca3af;
}

.conversations-loading {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: #6b7280;
  font-size: 14px;
}

.conversations-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #9ca3af;
}

.conversations-empty .empty-icon { font-size: 48px; }
.conversations-empty p { font-size: 16px; margin: 0; color: #6b7280; }
.conversations-empty .empty-hint { font-size: 13px; }

.conversations-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 0 16px;
  -webkit-overflow-scrolling: touch;
}

.conv-card {
  background: #fff;
  border-radius: 14px;
  padding: 14px 16px;
  margin-bottom: 10px;
  box-shadow: 0 1px 3px rgba(0,0,0,.04);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  transition: transform .15s;
}
.conv-card:active { transform: scale(.985); }

.cc-top {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.cc-question-label {
  font-size: 15px;
  flex-shrink: 0;
  margin-top: 1px;
}

.cc-text {
  flex: 1;
  font-size: 14px;
  font-weight: 500;
  color: #1e1e2e;
  line-height: 1.4;
  min-width: 0;
}

.cc-date {
  font-size: 11px;
  color: #9ca3af;
  flex-shrink: 0;
  margin-top: 2px;
  white-space: nowrap;
}

.cc-answer {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #f3f4f6;
  display: flex;
  gap: 8px;
}

.cc-answer-label {
  font-size: 15px;
  flex-shrink: 0;
  margin-top: 1px;
}

.cc-answer-text {
  flex: 1;
  font-size: 13px;
  color: #4a5568;
  line-height: 1.6;
  word-break: break-word;
}

/* Conversation expand animation */
.conv-expand-enter-active,
.conv-expand-leave-active {
  transition: all .25s ease;
  overflow: hidden;
}
.conv-expand-enter-from,
.conv-expand-leave-to {
  opacity: 0;
  max-height: 0;
  margin-top: 0;
  padding-top: 0;
}
.conv-expand-enter-to,
.conv-expand-leave-from {
  opacity: 1;
  max-height: 500px;
}
</style>

<!-- 非 scoped 样式：覆盖 teleport 到 body 的弹窗 -->
<style>
/* 暗色模式下 teleport 弹窗（设置、游览记录等）的背景色 */
.dark .settings-panel,
.dark .visits-panel {
  background: #1a1a2e;
}

.dark .settings-header h3,
.dark .visits-header h3 {
  color: #e4e4e7;
}

.dark .settings-item {
  background: #16213e;
}

.dark .settings-item:active {
  background: #1a1a2e;
}

.dark .si-label {
  color: #e4e4e7;
}

.dark .si-desc {
  color: #71717a;
}

.dark .section-title {
  color: #71717a;
}

.dark .visits-count {
  color: #71717a;
}

.dark .visits-loading {
  color: #a1a1aa;
}

.dark .visits-empty {
  color: #71717a;
}

.dark .visits-empty p {
  color: #a1a1aa;
}

.dark .visit-card {
  background: #16213e;
  box-shadow: 0 1px 3px rgba(0,0,0,.3);
}

.dark .vc-name {
  color: #e4e4e7;
}

.dark .vc-date {
  color: #71717a;
}

.dark .vc-meta {
  color: #a1a1aa;
}

.dark .vc-costs {
  color: #71717a;
  border-top-color: #1e2d4a;
}

.dark .username-edit-panel {
  background: #1a1a2e;
}

.dark .username-edit-panel h3 {
  color: #e4e4e7;
}

.dark .username-edit-panel .ue-hint {
  color: #71717a;
}

.dark .username-edit-panel .van-field {
  background: #16213e;
  color: #e4e4e7;
}

.dark .username-edit-panel .van-field__control {
  color: #e4e4e7;
}

/* 暗色模式 - 对话记录 */
.dark .conversations-panel {
  background: #1a1a2e;
}

.dark .conversations-header h3 {
  color: #e4e4e7;
}

.dark .conversations-count {
  color: #71717a;
}

.dark .conversations-loading {
  color: #a1a1aa;
}

.dark .conversations-empty {
  color: #71717a;
}

.dark .conversations-empty p {
  color: #a1a1aa;
}

.dark .conv-card {
  background: #16213e;
  box-shadow: 0 1px 3px rgba(0,0,0,.3);
}

.dark .cc-text {
  color: #e4e4e7;
}

.dark .cc-date {
  color: #71717a;
}

.dark .cc-answer {
  border-top-color: #1e2d4a;
}

.dark .cc-answer-text {
  color: #a1a1aa;
}

/* Vant popup close button in dark mode */
.dark .van-popup__close-icon {
  color: #71717a;
}
</style>
