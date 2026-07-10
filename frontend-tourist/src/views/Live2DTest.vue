<template>
  <div class="test-container">
    <!-- 左侧：Live2D 显示区 -->
    <div class="model-panel">
      <div class="model-wrapper">
        <canvas ref="liveCanvas"></canvas>
      </div>
      <div class="model-info-bar">
        <span>{{ modelName }}</span>
        <span class="fps">FPS: {{ fps }}</span>
      </div>
    </div>

    <!-- 右侧：控制面板 -->
    <div class="control-panel">
      <div class="panel-header">
        <h2>🔧 肢体动作控制台</h2>
        <button class="back-btn" @click="$router.push('/')">← 返回导游</button>
      </div>

      <!-- 标签切换 -->
      <div class="tab-bar">
        <button v-for="tab in visibleTabs" :key="tab.key" :class="['tab', { active: activeTab === tab.key }]" @click="activeTab = tab.key">
          {{ tab.icon }} {{ tab.label }}
        </button>
      </div>

      <div class="tab-content">
        <!-- ========== 身体参数 Tab ========== -->
        <div v-if="activeTab === 'body'" class="param-grid">
          <div v-for="p in bodyParams" :key="p.id" class="param-item">
            <div class="param-header">
              <span class="param-name">{{ p.label }}</span>
              <span class="param-value">{{ p.value.toFixed(3) }}</span>
              <button class="reset-btn" @click="resetParam(p)">↺</button>
            </div>
            <input type="range" :min="p.min" :max="p.max" step="0.001" :value="p.value" @input="onParamChange(p, $event)" class="param-slider" />
            <div class="param-range">
              <span>{{ p.min.toFixed(1) }}</span>
              <span>{{ p.max.toFixed(1) }}</span>
            </div>
          </div>
          <div v-if="bodyParams.length === 0" class="empty-hint">未检测到身体相关参数</div>
        </div>

        <!-- ========== 所有参数 Tab ========== -->
        <div v-if="activeTab === 'all'" class="param-grid">
          <div class="param-search">
            <input v-model="paramFilter" placeholder="🔍 过滤参数名..." class="filter-input" />
          </div>
          <div v-for="p in filteredParams" :key="p.id" class="param-item">
            <div class="param-header">
              <span class="param-name" :title="p.id">{{ p.label }}</span>
              <span class="param-value">{{ p.value.toFixed(3) }}</span>
              <button class="reset-btn" @click="resetParam(p)">↺</button>
            </div>
            <input type="range" :min="p.min" :max="p.max" step="0.001" :value="p.value" @input="onParamChange(p, $event)" class="param-slider" />
          </div>
        </div>

        <!-- ========== 动作 Tab ========== -->
        <div v-if="activeTab === 'motion'" class="motion-section">
          <div class="section-title">🎬 可用动作 ({{ motionGroups.length }}组)</div>
          <div class="motion-groups">
            <div v-for="group in motionGroups" :key="group" class="motion-group-card">
              <div class="group-name">{{ group }} [{{ foundMotionData[group]?.length || 0 }}个]</div>
              <div class="motion-buttons">
                <button v-for="idx in (foundMotionData[group] || [])" :key="idx"
                  class="motion-btn" @click="playMotion(group, idx)" :disabled="loading">
                  {{ idx }}
                </button>
              </div>
            </div>
          </div>
          <div v-if="motionGroups.length === 0" class="empty-hint">未探测到动作数据</div>
          <div v-if="motionGroups.length === 1" class="motion-tip">
            ⚠️ 该模型只含一组动作。不同模型的动画资源不同，如需更多动作请更换模型。
          </div>

          <div class="section-title">🎭 语义动作</div>
          <div class="action-grid">
            <button v-for="a in semanticActions" :key="a.key" class="action-btn" @click="playSemanticAction(a.key)" :disabled="loading">
              <span class="action-icon">{{ a.icon }}</span>
              <span class="action-label">{{ a.label }}</span>
            </button>
          </div>
        </div>

        <!-- ========== 表情 Tab ========== -->
        <div v-if="activeTab === 'expression'" class="expression-section">
          <div class="section-title">😊 表情控制</div>
          <div class="expr-grid">
            <button v-for="expr in expressions" :key="expr.id" class="expr-btn" @click="setExpression(expr.id)" :disabled="loading">
              <span class="expr-icon">{{ expr.icon }}</span>
              <span class="expr-name">{{ expr.label }}</span>
              <span class="expr-id">{{ expr.id }}</span>
            </button>
          </div>
        </div>

        <!-- ========== 部件 Tab ========== -->
        <div v-if="activeTab === 'parts'" class="parts-section">
          <div class="section-title">🧩 部件透明度控制</div>
          <div v-for="p in partsList" :key="p.id" class="part-item">
            <div class="part-header">
              <span class="part-name" :title="p.id">{{ p.label }}</span>
              <span class="part-value">{{ (p.value * 100).toFixed(0) }}%</span>
            </div>
            <input type="range" min="0" max="1" step="0.01" :value="p.value" @input="onPartChange(p, $event)" class="part-slider" />
          </div>
          <div v-if="partsList.length === 0" class="empty-hint">未检测到部件数据</div>
        </div>
      </div>

      <!-- 快捷操作 -->
      <div class="quick-actions">
        <button class="quick-btn reset-all" @click="resetAllParams">🔄 重置全部参数</button>
        <button class="quick-btn stop-motion" @click="stopAllMotions">⏹ 停止所有动作</button>
        <button class="quick-btn" @click="randomBodyMotion">🎲 随机动作</button>
        <button class="quick-btn" @click="toggleAutoBreath">{{ autoBreathing ? '⏸ 停止呼吸' : '▶ 呼吸动画' }}</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import * as PIXI from 'pixi.js'
import { Live2DModel } from 'pixi-live2d-display'
import request from '@/utils/request'
import { Live2DController } from '@/core/Live2DController'

window.PIXI = PIXI

// ==================== 状态 ====================
const liveCanvas = ref(null)
const modelName = ref('加载中...')
const fps = ref(0)
const activeTab = ref('body')
const loading = ref(false)
const autoBreathing = ref(false)
const paramFilter = ref('')
let app = null
let model = null
let controller = null
let resizeModel = null
let breathInterval = null
let frameCount = 0
let lastFpsTime = performance.now()
let controllerEnabled = true   // controller.update() 开关

// 参数列表
const allParams = ref([])
const partsList = ref([])

const tabs = [
  { key: 'body', label: '身体', icon: '🦾' },
  { key: 'all', label: '全部参数', icon: '📊' },
  { key: 'motion', label: '动作', icon: '🎬' },
  { key: 'expression', label: '表情', icon: '😊' },
  { key: 'parts', label: '部件', icon: '🧩' },
]

const visibleTabs = computed(() => tabs.filter(t => {
  if (t.key === 'expression') return hasExpressions.value
  if (t.key === 'parts') return partsList.value.length > 0
  return true
}))

const hasExpressions = ref(false)
// 表情探测 — 检查内部 expressionManager 是否存在
function probeExpressions() {
  const em = model?.internalModel?.motionManager?.expressionManager
  if (em) {
    hasExpressions.value = true
    // 探测可用表情列表
    const exprNames = em._expressions || em.expressions || []
    console.log('😊 表情可用:', exprNames.length ? exprNames : '未知名称')
  } else {
    hasExpressions.value = false
    console.log('⚠️ 该模型无表情数据 (expressionManager 为空)')
  }
}

// 身体相关参数关键词
const BODY_KEYWORDS = ['arm', 'hand', 'body', 'angle', 'breath', 'bust', 'shoulder', 'leg', 'foot', 'waist']

// ==================== 计算属性 ====================
const bodyParams = computed(() => allParams.value.filter(p => BODY_KEYWORDS.some(kw => p.id.toLowerCase().includes(kw))))

const filteredParams = computed(() => {
  if (!paramFilter.value) return allParams.value
  const f = paramFilter.value.toLowerCase()
  return allParams.value.filter(p => p.id.toLowerCase().includes(f) || p.label.toLowerCase().includes(f))
})

// 动作探测
const motionGroups = ref([])
const foundMotionData = ref({})

const semanticActions = [
  { key: 'nod', icon: '🙂', label: '点头' },
  { key: 'wave', icon: '👋', label: '挥手' },
  { key: 'invite', icon: '🫴', label: '邀请' },
  { key: 'reject', icon: '🙅', label: '摇头' },
  { key: 'think', icon: '🤔', label: '思考' },
  { key: 'question', icon: '❓', label: '疑问' },
  { key: 'explain', icon: '📖', label: '解释' },
  { key: 'celebrate', icon: '🎉', label: '庆祝' },
  { key: 'sad', icon: '😢', label: '悲伤' },
]

const expressions = [
  { id: 'F01', icon: '😊', label: '微笑' },
  { id: 'F02', icon: '😄', label: '开心' },
  { id: 'F03', icon: '😢', label: '悲伤' },
  { id: 'F04', icon: '🥳', label: '非常开心' },
  { id: 'F05', icon: '😲', label: '惊讶' },
  { id: 'F06', icon: '😠', label: '生气' },
  { id: 'F07', icon: '😐', label: '无表情' },
  { id: 'F08', icon: '😜', label: '调皮' },
]

// ==================== Live2D 初始化 ====================
onMounted(async () => {
  app = new PIXI.Application({
    view: liveCanvas.value,
    autoStart: true,
    resizeTo: liveCanvas.value.parentElement,
    backgroundAlpha: 0,
    antialias: true,
  })

  try {
    // 获取当前模型配置
    let modelPath = '/Resources/haru_greeter_pro_jp/runtime/haru_greeter_t05.model3.json'
    try {
      const res = await request.get('/tourist/live2d/current-model')
      if (res.success && res.model_path) modelPath = res.model_path
    } catch (e) { /* 使用默认 */ }

    model = await Live2DModel.from(modelPath)
    app.stage.addChild(model)
    modelName.value = modelPath.split('/').pop() || 'Live2D Model'

    Live2DModel.registerTicker(PIXI.Ticker)
    model.eventMode = 'static'
    model.cursor = 'pointer'

    controller = new Live2DController(model)

    // 尺寸调整
    resizeModel = () => {
      const parent = liveCanvas.value.parentElement
      if (!parent || !model) return
      const w = parent.clientWidth
      const h = parent.clientHeight
      model.scale.set(Math.min(w, h) * 0.0004)
      model.x = w / 2
      model.y = h * 0.7
      model.anchor.set(0.5, 0.5)
    }
    resizeModel()
    window.addEventListener('resize', resizeModel)

    // 扫描参数
    scanParameters()

    // 帧循环（手动调参时禁用 controller）
    app.ticker.add(() => {
      if (controllerEnabled) controller?.update()
      frameCount++
      const now = performance.now()
      if (now - lastFpsTime >= 1000) {
        fps.value = frameCount
        frameCount = 0
        lastFpsTime = now
        // 实时刷新参数值
        if (activeTab.value === 'body' || activeTab.value === 'all') {
          refreshParamValues()
        }
      }
    })

    console.log('✅ Live2D 测试页初始化完成')
  } catch (error) {
    console.error('❌ 模型加载失败:', error)
    modelName.value = '加载失败: ' + error.message
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeModel)
  if (breathInterval) clearInterval(breathInterval)
  controller?.destroy()
  model?.destroy()
  app?.destroy()
})

// ==================== 参数扫描 (Cubism 5) ====================

// Cubism 5 无 getParameterIds()，需要用 getParameterIndex() 逐个探测
// 从模型 motion3.json 文件中提取的真实参数 ID
const CANDIDATE_PARAMS = [
  // === 头部角度 ===
  'ParamAngleX', 'ParamAngleY', 'ParamAngleZ',
  // === 身体 ===
  'ParamBodyAngleX', 'ParamBodyAngleY', 'ParamBodyAngleZ',
  'ParamBodyUpper',
  // === 手臂（真实名称）===
  'ParamArmLA', 'ParamArmLB', 'ParamArmRA', 'ParamArmRB',
  // === 手部 ===
  'ParamHandAngleL', 'ParamHandAngleR', 'ParamHandChangeR', 'ParamHandDhangeL',
  // === 眼睛 ===
  'ParamEyeBallX', 'ParamEyeBallY', 'ParamEyeBallForm',
  'ParamEyeLOpen', 'ParamEyeROpen', 'ParamEyeForm',
  'ParamEyeLSmile', 'ParamEyeRSmile',
  // === 眉毛 ===
  'ParamBrowLAngle', 'ParamBrowLForm', 'ParamBrowLX', 'ParamBrowLY',
  'ParamBrowRAngle', 'ParamBrowRForm', 'ParamBrowRX', 'ParamBrowRY',
  // === 口型 ===
  'ParamMouthOpenY', 'ParamMouthForm',
  // === 面部 ===
  'ParamFaceForm',
  // === 呼吸 / 胸部 ===
  'ParamBreath', 'ParamBustY',
  // === 头发 ===
  'ParamHairFront', 'ParamHairBack', 'ParamHairSide',
  // === Haru 特有 ===
  'ParamTere', 'ParamTear', 'ParamScarf',
]

function scanParameters() {
  if (!model?.internalModel?.coreModel) return
  const coreModel = model.internalModel.coreModel
  allParams.value = []
  partsList.value = []

  try {
    const paramCount = coreModel.getParameterCount()
    console.log(`📊 模型参数总数: ${paramCount}`)

    // Cubism 5: 用 getParameterIndex 探测已知 ID
    for (const pid of CANDIDATE_PARAMS) {
      try {
        const idx = coreModel.getParameterIndex(pid)
        if (idx >= 0 && idx < paramCount) {
          const val = coreModel.getParameterValueByIndex(idx)
          const min = coreModel.getParameterMinimumValue(idx)
          const max = coreModel.getParameterMaximumValue(idx)
          const def = coreModel.getParameterDefaultValue(idx)
          allParams.value.push({
            id: pid,
            idx: idx,
            label: pid.replace(/^(Param|PARAM)_?/, '').replace(/([A-Z])/g, ' $1').trim(),
            value: Number(val) || 0,
            default: Number(def) || 0,
            min: Number(min) ?? -1,
            max: Number(max) ?? 1,
          })
        }
      } catch (e) { /* 参数不存在 */ }
    }

    console.log(`✅ 参数扫描: 发现 ${allParams.value.length} 个已知参数 (共 ${paramCount} 个)`)

    // 按 idx 排序
    allParams.value.sort((a, b) => a.idx - b.idx)

    // 扫描部件
    try {
      const partCount = coreModel.getPartCount?.() ?? 0
      if (partCount > 0) {
        const PART_IDS = ['PartArmL', 'PartArmR', 'PartHairFront', 'PartHairBack', 'PartBody', 'PartDress', 'PartSkirt', 'PartAcc', 'PartRibbon', 'PartItem']
        for (const pid of PART_IDS) {
          try {
            const idx = coreModel.getPartIndex?.(pid)
            if (idx >= 0 && idx < partCount) {
              const opacity = coreModel.getPartOpacityByIndex?.(idx) ?? 1
              partsList.value.push({
                id: pid,
                idx,
                label: pid.replace(/^Part/, '').replace(/([A-Z])/g, ' $1').trim(),
                value: Number(opacity),
                default: Number(opacity),
              })
            }
          } catch (e) { /* */ }
        }
      }
    } catch (e) { /* parts 可选 */ }

    console.log(`🧩 部件扫描: ${partsList.value.length} 个`)
  } catch (e) {
    console.error('参数扫描失败:', e)
  }

  detectMotionGroups()
  probeExpressions()
}

// ==================== 动作组探测 ====================
function detectMotionGroups() {
  if (!model) return
  const result = {}

  // 方法1: 从 model3.json 的 Motions 读真实数量
  try {
    if (model._modelJson?.FileReferences?.Motions) {
      const motions = model._modelJson.FileReferences.Motions
      for (const [group, list] of Object.entries(motions)) {
        if (Array.isArray(list)) {
          result[group] = Array.from({ length: list.length }, (_, i) => i)
        }
      }
      console.log('✅ 从 model3.json Motions 读取')
    }
  } catch (e) { /* */ }

  // 方法2: 读取 motionManager 内部数据
  if (Object.keys(result).length === 0) {
    try {
      const mm = model.internalModel?.motionManager
      if (mm?._motions instanceof Map) {
        for (const [group, list] of mm._motions) {
          result[group] = Array.from({ length: list.length }, (_, i) => i)
        }
      }
    } catch (e) { /* */ }
  }

  // 合并 '' 和 'Idle'（pixi-live2d-display 别名）
  const emptyLen = result['']?.length || 0
  const idleLen = result['Idle']?.length || 0
  if (emptyLen > 0) {
    result['Idle'] = [...Array(Math.max(emptyLen, idleLen)).keys()]
    delete result['']
  }

  foundMotionData.value = result
  motionGroups.value = Object.keys(result)
  console.log('🎬 动作组:', Object.entries(result).map(([g, is]) => `${g}[${is.length}]`).join(', '))
}

function refreshParamValues() {
  if (!model?.internalModel?.coreModel || allParams.value.length === 0) return
  const coreModel = model.internalModel.coreModel
  try {
    for (const p of allParams.value) {
      const idx = p.idx ?? coreModel.getParameterIndex(p.id)
      if (idx >= 0) p.value = Number(coreModel.getParameterValueByIndex(idx)) || 0
    }
  } catch (e) { /* */ }
}

// ==================== 参数设置（兼容多版本） ====================
let motionStoppedForManual = false

function setParamOnModel(paramId, value) {
  // 首次手动调参自动停止动作
  if (!motionStoppedForManual) {
    stopAllMotions()
    motionStoppedForManual = true
  }
  const coreModel = model?.internalModel?.coreModel
  if (!coreModel) return false

  // 方法1: Cubism 4 标准 API
  try {
    if (typeof coreModel.setParameterValueById === 'function') {
      coreModel.setParameterValueById(paramId, value)
      return true
    }
  } catch (e) { /* */ }

  // 方法2: Cubism 5 C API 回退
  try {
    if (coreModel._ptr && window.CubismCore) {
      const cs = window.CubismCore
      const count = cs.csmGetParameterCount(coreModel._ptr)
      const rawIds = cs.csmGetParameterIds(coreModel._ptr)
      for (let i = 0; i < count; i++) {
        if (cs.UTF8ToString(rawIds[i]) === paramId) {
          const vals = cs.csmGetParameterValues(coreModel._ptr)
          vals[i] = value
          cs.csmSetParameterValues(coreModel._ptr, vals)
          return true
        }
      }
    }
  } catch (e) { /* */ }

  // 方法3: 通过索引
  try {
    const all = allParams.value
    const idx = all.findIndex(p => p.id === paramId)
    if (idx >= 0 && typeof coreModel.setParameterValueByIndex === 'function') {
      coreModel.setParameterValueByIndex(idx, value)
      return true
    }
  } catch (e) { /* */ }

  return false
}

function onParamChange(param, event) {
  const value = parseFloat(event.target.value)
  param.value = value
  setParamOnModel(param.id, value)
}

function resetParam(param) {
  const defaultValue = param.default
  param.value = defaultValue
  setParamOnModel(param.id, defaultValue)
}

function resetAllParams() {
  for (const p of allParams.value) {
    p.value = p.default
    setParamOnModel(p.id, p.default)
  }
  console.log('🔄 所有参数已重置')
}

// ==================== 部件控制 ====================
function onPartChange(part, event) {
  const value = parseFloat(event.target.value)
  part.value = value
  const coreModel = model?.internalModel?.coreModel
  if (!coreModel) return
  try {
    if (typeof coreModel.setPartOpacityById === 'function') {
      coreModel.setPartOpacityById(part.id, value)
    }
  } catch (e) { /* */ }
}

// ==================== 动作控制 ====================
function playMotion(group, index) {
  if (!model) return
  controllerEnabled = true
  motionStoppedForManual = false
  loading.value = true
  try {
    model.motion(group, index, { force: true })
    console.log(`🎬 播放动作: "${group}"_${index}`)
  } catch (e) {
    console.warn('动作播放失败:', e)
  }
  setTimeout(() => { loading.value = false }, 500)
}

function playSemanticAction(actionKey) {
  if (!model) return
  loading.value = true
  const maxIdx = (foundMotionData.value['Idle']?.length || foundMotionData.value['']?.length || 27) - 1
  // 不同语义动作映射到 Idle 组的不同索引（m01-m26 是不同的动作）
  const idxMap = { nod: 1, reject: 2, wave: 3, think: 4, question: 5, invite: 6, explain: 7, celebrate: 8, sad: 9 }
  const idx = Math.min(idxMap[actionKey] || 0, maxIdx)
  try {
    model.motion('', idx, { force: true })
    console.log(`🎭 语义动作: ${actionKey} → Idle[${idx}]`)
  } catch (e) {
    console.warn('语义动作失败:', e.message)
  }
  setTimeout(() => { loading.value = false }, 800)
}

function stopAllMotions() {
  if (!model) return
  controllerEnabled = false  // 禁用每帧参数覆盖
  motionStoppedForManual = true
  try {
    const mm = model.internalModel?.motionManager
    if (mm?.stopAllMotions) {
      mm.stopAllMotions()
    }
    console.log('⏹ 动作已停止，参数滑块可用')
  } catch(e) {
    console.warn('停止动作失败:', e.message)
  }
}

function randomBodyMotion() {
  const groups = motionGroups.value.filter(g => g && g !== 'Idle')
  if (groups.length === 0) {
    // fallback: 用 Idle 组
    const indices = foundMotionData.value[''] || foundMotionData.value['Idle'] || [0,1,2]
    const idx = indices[Math.floor(Math.random() * indices.length)]
    playMotion('', idx)
    return
  }
  const group = groups[Math.floor(Math.random() * groups.length)]
  const indices = foundMotionData.value[group] || [0]
  const idx = indices[Math.floor(Math.random() * indices.length)]
  playMotion(group, idx)
}

// ==================== 表情控制 ====================
function setExpression(exprId) {
  if (!model) return
  loading.value = true

  // 首次调用时探测表情存储结构
  if (!window.__exprProbed) {
    window.__exprProbed = true
    const em = model.internalModel?.expressionManager
    if (em) {
      console.log('🔍 expressionManager keys:', Object.keys(em))
      // 尝试读取表达式列表
      if (em._expressions) {
        console.log('📋 _expressions:', Array.isArray(em._expressions) ? em._expressions : Object.keys(em._expressions))
      }
      if (em._expressionIds) console.log('📋 _expressionIds:', em._expressionIds)
      if (em.expressions) console.log('📋 expressions:', em.expressions)
      // 打印所有非私有属性
      const props = Object.getOwnPropertyNames(em).concat(Object.getOwnPropertyNames(Object.getPrototypeOf(em)))
      console.log('🔍 expressionManager 全部属性:', props)
    } else {
      console.log('⚠️ expressionManager 不存在，尝试其他路径...')
      // 探测 model.internalModel 下可能的表达式路径
      const im = model.internalModel
      if (im) {
        const keys = Object.keys(im)
        console.log('🔍 internalModel keys:', keys)
        for (const k of keys) {
          if (k.toLowerCase().includes('expr')) {
            console.log(`  找到: internalModel.${k}`, typeof im[k], Object.keys(im[k] || {}))
          }
        }
      }
    }
  }

  try {
    model.expression(exprId)
    console.log(`😊 表情设置: ${exprId}`)
  } catch (e1) {
    try {
      model.internalModel?.expressionManager?.setExpression?.(exprId)
      console.log(`😊 表情设置(mgr): ${exprId}`)
    } catch (e2) {
      console.warn(`表情 ${exprId} 不可用:`, e1.message || e2.message)
    }
  }
  setTimeout(() => { loading.value = false }, 300)
}

// ==================== 呼吸动画 ====================
function toggleAutoBreath() {
  if (autoBreathing.value) {
    clearInterval(breathInterval)
    autoBreathing.value = false
  } else {
    autoBreathing.value = true
    let phase = 0
    breathInterval = setInterval(() => {
      if (!model?.internalModel?.coreModel) return
      phase += 0.05
      const breathValue = Math.sin(phase) * 0.3
      model.internalModel.coreModel.setParameterValueById('ParamBreath', breathValue)
    }, 30)
  }
}
</script>

<style scoped>
.test-container {
  width: 100vw;
  height: 100vh;
  display: flex;
  background: #1a1a2e;
  color: #e0e0e0;
  overflow: hidden;
}

/* ---- 左侧模型面板 ---- */
.model-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: linear-gradient(180deg, #16213e 0%, #0f3460 100%);
  border-right: 1px solid #2a2a4a;
}

.model-wrapper {
  flex: 1;
  position: relative;
  overflow: hidden;
}

.model-wrapper canvas {
  width: 100%;
  height: 100%;
}

.model-info-bar {
  display: flex;
  justify-content: space-between;
  padding: 8px 16px;
  font-size: 13px;
  background: rgba(0,0,0,0.3);
  color: #8892b0;
}

.fps {
  color: #64ffda;
  font-weight: 600;
}

/* ---- 右侧控制面板 ---- */
.control-panel {
  width: 420px;
  display: flex;
  flex-direction: column;
  background: #1e2746;
  overflow: hidden;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 18px;
  border-bottom: 1px solid #2a2a4a;
}

.panel-header h2 {
  margin: 0;
  font-size: 17px;
  color: #ccd6f6;
}

.back-btn {
  padding: 6px 14px;
  border: 1px solid #3a3a5a;
  background: transparent;
  color: #8892b0;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  transition: all 0.2s;
}

.back-btn:hover {
  border-color: #64ffda;
  color: #64ffda;
}

/* ---- 标签栏 ---- */
.tab-bar {
  display: flex;
  border-bottom: 1px solid #2a2a4a;
  padding: 0 8px;
  background: #16213e;
}

.tab {
  flex: 1;
  padding: 10px 4px;
  border: none;
  background: transparent;
  color: #8892b0;
  font-size: 13px;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: all 0.2s;
}

.tab:hover { color: #ccd6f6; }

.tab.active {
  color: #64ffda;
  border-bottom-color: #64ffda;
}

/* ---- Tab 内容 ---- */
.tab-content {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}

.tab-content::-webkit-scrollbar { width: 4px; }
.tab-content::-webkit-scrollbar-thumb { background: #3a3a5a; border-radius: 2px; }

/* ---- 参数网格 ---- */
.param-grid {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.param-item {
  background: #16213e;
  border-radius: 8px;
  padding: 10px 12px;
  border: 1px solid #2a2a4a;
}

.param-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.param-name {
  flex: 1;
  font-size: 12px;
  color: #ccd6f6;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.param-value {
  font-size: 11px;
  color: #64ffda;
  font-family: monospace;
  min-width: 50px;
  text-align: right;
}

.reset-btn {
  padding: 2px 6px;
  font-size: 10px;
  border: 1px solid #3a3a5a;
  background: transparent;
  color: #8892b0;
  border-radius: 4px;
  cursor: pointer;
}

.reset-btn:hover { color: #ff6b6b; border-color: #ff6b6b; }

.param-slider {
  width: 100%;
  height: 4px;
  -webkit-appearance: none;
  appearance: none;
  background: #2a2a4a;
  border-radius: 2px;
  outline: none;
}

.param-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: #64ffda;
  cursor: pointer;
  border: 2px solid #1e2746;
}

.param-range {
  display: flex;
  justify-content: space-between;
  font-size: 10px;
  color: #5a6a8a;
  margin-top: 2px;
}

/* ---- 过滤输入 ---- */
.param-search {
  margin-bottom: 8px;
}

.filter-input {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #2a2a4a;
  border-radius: 6px;
  background: #16213e;
  color: #ccd6f6;
  font-size: 13px;
  outline: none;
  box-sizing: border-box;
}

.filter-input:focus { border-color: #64ffda; }

/* ---- 动作 ---- */
.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #ccd6f6;
  margin: 14px 0 8px;
  padding-bottom: 6px;
  border-bottom: 1px solid #2a2a4a;
}

.motion-group-card {
  background: #16213e;
  border-radius: 8px;
  padding: 10px;
  margin-bottom: 8px;
  border: 1px solid #2a2a4a;
}

.group-name {
  font-size: 12px;
  color: #64ffda;
  margin-bottom: 8px;
  font-family: monospace;
}

.motion-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.motion-btn {
  width: 34px;
  height: 26px;
  border: 1px solid #3a3a5a;
  background: transparent;
  color: #8892b0;
  font-size: 11px;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.15s;
}

.motion-btn:hover:not(:disabled) {
  background: #64ffda;
  color: #1a1a2e;
  border-color: #64ffda;
}

.motion-btn:disabled { opacity: 0.3; }

/* ---- 语义动作 ---- */
.action-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 6px;
}

.action-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 10px 6px;
  border: 1px solid #2a2a4a;
  background: #16213e;
  color: #ccd6f6;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.action-btn:hover:not(:disabled) {
  background: #1e3a5f;
  border-color: #64ffda;
  transform: translateY(-1px);
}

.action-icon { font-size: 22px; }
.action-label { font-size: 11px; }

/* ---- 表情 ---- */
.expr-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 6px;
}

.expr-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 10px 4px;
  border: 1px solid #2a2a4a;
  background: #16213e;
  color: #ccd6f6;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.expr-btn:hover:not(:disabled) {
  background: #1e3a5f;
  border-color: #64ffda;
}

.expr-icon { font-size: 24px; }
.expr-name { font-size: 11px; }
.expr-id { font-size: 10px; color: #5a6a8a; font-family: monospace; }

/* ---- 部件 ---- */
.part-item {
  background: #16213e;
  border-radius: 8px;
  padding: 10px 12px;
  margin-bottom: 8px;
  border: 1px solid #2a2a4a;
}

.part-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 6px;
}

.part-name {
  font-size: 12px;
  color: #ccd6f6;
}

.part-value {
  font-size: 11px;
  color: #64ffda;
  font-family: monospace;
}

.part-slider {
  width: 100%;
  height: 4px;
  -webkit-appearance: none;
  appearance: none;
  background: #2a2a4a;
  border-radius: 2px;
  outline: none;
}

.part-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: #ffd700;
  cursor: pointer;
  border: 2px solid #1e2746;
}

/* ---- 快捷操作 ---- */
.quick-actions {
  display: flex;
  gap: 6px;
  padding: 12px;
  border-top: 1px solid #2a2a4a;
  background: #16213e;
}

.quick-btn {
  flex: 1;
  padding: 8px 6px;
  border: 1px solid #3a3a5a;
  background: transparent;
  color: #8892b0;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.quick-btn:hover {
  border-color: #64ffda;
  color: #64ffda;
}

.reset-all:hover {
  border-color: #ff6b6b;
  color: #ff6b6b;
}

.stop-motion:hover {
  border-color: #ffd700;
  color: #ffd700;
}

/* ---- 空提示 ---- */
.empty-hint {
  text-align: center;
  padding: 30px;
  color: #5a6a8a;
  font-size: 14px;
}
</style>
