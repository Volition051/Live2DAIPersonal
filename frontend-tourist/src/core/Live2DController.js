/**
 * Live2D 核心控制器 - 基于技术文档重构
 * 
 * 核心功能：
 * 1. 参数控制系统（绝对设置 vs 相对添加）
 * 2. 口型同步系统（LipSync）
 * 3. 动作控制系统（优先级管理）
 * 4. 表情控制系统
 * 5. 交互状态管理
 */

// ==================== 常量定义 ====================

/**
 * 动作优先级常量
 */
export const Priority = {
  None: 0,      // 无优先级
  Idle: 1,      // 待机动作（最低）
  Normal: 2,    // 普通动作
  Force: 3      // 强制动作（最高）
}

/**
 * OVR LipSync Viseme 映射表（15种口型音素）
 * 参考: https://developer.oculus.com/documentation/unity/audio-ovrlipsync/
 */
export const VISeme_MAPPING = {
  // 静音 / 闭嘴
  sil: 0.00,

  // 双唇爆破音 — 双唇紧闭后爆开
  PP: 0.20,

  // 唇齿擦音 — 下唇轻触上齿
  FF: 0.22,

  // 鼻音 — 轻微张嘴
  nn: 0.30,

  // 齿擦音 — 舌尖可见
  TH: 0.38,

  // 齿龈爆破音 — 舌尖抵上颚
  DD: 0.42,

  // 塞擦音 — 较宽开口
  CH: 0.48,

  // 咝音 — 牙齿闭合、嘴唇拉伸
  SS: 0.35,

  // 近闭前元音
  ih: 0.50,

  // 软腭爆破音 — 口腔后部
  kk: 0.55,

  // 中前元音
  E: 0.68,

  // 中后圆唇元音
  oh: 0.72,

  // 开后元音 — 最大张嘴
  aa: 0.85,

  // 闭后圆唇元音
  ou: 0.78
}

/**
 * 音素分类 — 用于自适应平滑决策
 */
const VISEME_CLASS = {
  PLOSIVE:  new Set(['PP', 'DD', 'kk']),
  FRICATIVE: new Set(['FF', 'TH', 'SS', 'CH']),
  VOWEL:    new Set(['aa', 'E', 'ih', 'oh', 'ou']),
  NASAL:    new Set(['nn']),
  SILENCE:  new Set(['sil'])
}

/**
 * 口型形状映射 (ParamMouthForm)
 * 负值 = 圆唇/噘嘴, 正值 = 咧嘴/拉伸, 零 = 中性
 */
const MOUTH_FORM_MAPPING = {
  sil:  0.0,
  PP:  -0.25,   // 双唇紧闭，微噘
  FF:  -0.15,   // 下唇触齿，微圆
  TH:   0.15,   // 舌尖可见，微咧
  DD:   0.05,   // 齿龈位，近中性
  CH:   0.25,   // 宽塞擦音，拉伸
  SS:   0.30,   // 咝音微笑状拉伸
  nn:  -0.05,   // 鼻音，近中性
  kk:  -0.20,   // 软腭位，后部圆唇
  E:    0.35,   // 中前元音，宽咧
  ih:   0.25,   // 前元音，拉伸
  aa:   0.10,   // 开后元音，微宽
  oh:  -0.45,   // 中后圆唇元音
  ou:  -0.55,   // 闭后圆唇，强烈噘嘴
}

/**
 * 自适应平滑常量
 */
const SMOOTHING = {
  ATTACK_BASE:  0.55,    // 张嘴基础速度（快速）
  RELEASE_BASE: 0.18,    // 闭嘴基础速度（缓慢）
  VOWEL_HOLD:   0.12,    // 元音持续期间极慢变化
  MOUTH_FORM:   0.25,    // 口型变化稍慢于开合
  IDLE_BREATH:  0.04,    // 空闲呼吸极慢速
  JITTER_AMP:   0.008,   // 基础微动幅度
}

/**
 * 情感值 → 表情映射规则
 */
export const SENTIMENT_TO_EXPRESSION = {
  veryHappy: 'F04',   // Sentiment >= 1.5
  happy: 'F01',       // Sentiment >= 0.3
  neutral: 'F01',     // 默认微笑
  angry: 'F02',       // Sentiment <= -0.3
  sad: 'F03'          // Sentiment <= -0.7
}

/**
 * 语义动作映射表（Haru模型示例）
 */
// Haru 模型所有动作在 "" (空字符串) 组中，索引 0=idle, 1-26=m01~m26
export const ACTION_MAP = {
  nod:       { group: '', candidates: [1, 3] },
  wave:      { group: '', candidates: [5] },
  invite:    { group: '', candidates: [6] },
  reject:    { group: '', candidates: [2, 4] },
  think:     { group: '', candidates: [11, 12] },
  question:  { group: '', candidates: [18, 12] },
  explain:   { group: '', candidates: [7, 8] },
  celebrate: { group: '', candidates: [9, 10] },
  sad:       { group: '', candidates: [13, 14] },
}

// ==================== 缓动工具函数 ====================

/**
 * Easing 函数集 — 纯数学运算，无内存分配
 */
const Easing = {
  /** 二次缓出 — 减速至零 */
  easeOutQuad(t) {
    return 1 - (1 - t) * (1 - t)
  },

  /** 三次缓入缓出 — 加速后减速 */
  easeInOutCubic(t) {
    return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2
  },

  /** Smoothstep — 经典 S 曲线 */
  smoothstep(t) {
    const x = Math.max(0, Math.min(1, t))
    return x * x * (3 - 2 * x)
  }
}

// ==================== 口型同步器 ====================

/**
 * LipSync 口型同步器
 * 
 * 关键技术点：
 * - 使用 Date.now() 或自定义时间提供者计算播放进度
 * - 遍历 LipData[] 找到当前应显示的音素（Viseme）
 * - 采用线性插值平滑过渡，避免突变
 * - 播放结束后自动归零
 */
export class LipSync {
  constructor(setMouthCallback, setMouthFormCallback = null) {
    // 核心回调
    this.setMouthValue = setMouthCallback
    this.setMouthFormValue = setMouthFormCallback || (() => {})

    // --- 现有状态（保持不变）---
    this.currentLips = null
    this.startTime = 0
    this.totalDuration = 0
    this.smoothingFactor = 0.3  // 平滑因子（保留向后兼容）
    this.currentLipValue = 0.0
    this.elapsedTimeProvider = null

    // --- 新增：自适应平滑状态 ---
    this.currentMouthForm = 0.0
    this.prevVisemeKey = null
    this.transitionStartTime = 0
    this.transitionStartOpen = 0.0
    this.transitionStartForm = 0.0
    this._manualSmoothingOverride = false

    // --- 新增：微动状态 ---
    this.jitterPhase = Math.random() * Math.PI * 2

    // --- 新增：空闲呼吸状态 ---
    this.breathingPhase = Math.random() * Math.PI * 2
    this.isIdle = true
    this.idleTransitionStartValue = 0.0
    this.idleTransitionStartTime = 0
    this._idleTransitionActive = false
  }

  /**
   * 启动口型同步
   * @param {Array} lips - Viseme数据数组 [{Lip: "aa", Time: 100}, ...]
   * @param {Function} elapsedTimeProvider - 可选的时间提供者（如 audio.currentTime）
   */
  startLipSync(lips, elapsedTimeProvider = null) {
    if (!lips || lips.length === 0) {
      console.warn('⚠️ LipSync: 空的 viseme 数据')
      return
    }

    this.currentLips = lips
    this.startTime = Date.now()
    this.elapsedTimeProvider = elapsedTimeProvider
    this.totalDuration = lips.reduce((sum, lip) => sum + lip.Time, 0)
    this.currentLipValue = 0.0

    // --- 新增：重置增强状态 ---
    this.currentMouthForm = 0.0
    this.prevVisemeKey = null
    this.transitionStartTime = performance.now()
    this.transitionStartOpen = 0.0
    this.transitionStartForm = 0.0
    this.jitterPhase = Math.random() * Math.PI * 2
    this.isIdle = false
    this._idleTransitionActive = false
    
    console.log(`🎤 LipSync 启动，共 ${lips.length} 个 viseme，总时长 ${this.totalDuration}ms`)
  }

  /**
   * 更新口型（每帧调用）
   *
   * 核心调度器 — 分派到以下路径：
   *   A) 无语音 + 过渡中 → _updateIdleTransition()
   *   B) 无语音 + 空闲   → _updateBreathing()
   *   C) 有语音          → _resolveVisemeContext() → 协同发音 + 自适应平滑 + 微动
   */
  update() {
    // --- PATH A/B: 无活跃语音数据 ---
    if (!this.currentLips) {
      if (this._idleTransitionActive) {
        this._updateIdleTransition()
      } else {
        this.isIdle = true
        this._updateBreathing()
      }
      return
    }

    // --- PATH C: 活跃语音 ---
    this.isIdle = false
    this._idleTransitionActive = false

    // 计算已播放时间
    const elapsed = this._getElapsed()

    // 检查是否播放完成
    if (elapsed >= this.totalDuration) {
      this.currentLips = null
      this._beginIdleTransition()
      return
    }

    // 解析当前时间在 viseme 时间线中的位置（含前瞻 2 个 viseme）
    const ctx = this._resolveVisemeContext(elapsed)

    // 检测 viseme 切换，记录过渡起始状态
    if (ctx.targetKey !== this.prevVisemeKey) {
      this._beginTransition()
    }
    this.prevVisemeKey = ctx.targetKey

    // 计算协同发音混合后的目标值
    const coartOpen = this._computeCoarticulatedOpen(ctx)
    const coartForm = this._computeCoarticulatedForm(ctx)

    // 方向感知 + 音素分类感知的自适应平滑
    this._applyAdaptiveSmoothing(coartOpen, coartForm, ctx.targetKey)

    // 持续音素的微动抖动
    const jitter = this._computeMicroJitter(ctx.targetKey)

    // 钳制并设置最终值
    const finalOpen = Math.max(0, Math.min(1, this.currentLipValue + jitter))
    const finalForm = Math.max(-1, Math.min(1, this.currentMouthForm))

    this.setMouthValue(finalOpen)
    this.setMouthFormValue(finalForm)
  }

  // ========== 内部辅助方法 ==========

  /**
   * 获取已播放时间（毫秒）
   */
  _getElapsed() {
    return this.elapsedTimeProvider
      ? this.elapsedTimeProvider() * 1000
      : Date.now() - this.startTime
  }

  /**
   * 解析当前时间点在 viseme 时间线中的上下文
   * 返回当前 viseme + 前瞻 2 个 viseme（用于协同发音）
   */
  _resolveVisemeContext(elapsed) {
    let accumulated = 0
    let targetIdx = -1
    let timeIntoCurrent = 0

    for (let i = 0; i < this.currentLips.length; i++) {
      const prevAccum = accumulated
      accumulated += this.currentLips[i].Time
      if (elapsed <= accumulated) {
        targetIdx = i
        timeIntoCurrent = elapsed - prevAccum
        break
      }
    }

    // 安全回退：使用最后一个 viseme
    if (targetIdx === -1) {
      targetIdx = this.currentLips.length - 1
      timeIntoCurrent = this.currentLips[targetIdx].Time
    }

    const target = this.currentLips[targetIdx]
    const next1 = this.currentLips[targetIdx + 1] || null
    const next2 = this.currentLips[targetIdx + 2] || null

    return {
      targetKey: target.Lip,
      targetOpen: this.visemeToValue(target.Lip),
      targetForm: MOUTH_FORM_MAPPING[target.Lip] ?? 0.0,
      currentDuration: target.Time,
      timeInto: timeIntoCurrent,
      nextKey: next1 ? next1.Lip : null,
      nextOpen: next1 ? this.visemeToValue(next1.Lip) : null,
      nextForm: next1 ? (MOUTH_FORM_MAPPING[next1.Lip] ?? 0.0) : null,
      nextDuration: next1 ? next1.Time : 0,
      next2Key: next2 ? next2.Lip : null,
      next2Open: next2 ? this.visemeToValue(next2.Lip) : null,
      next2Form: next2 ? (MOUTH_FORM_MAPPING[next2.Lip] ?? 0.0) : null,
    }
  }

  /**
   * 记录 viseme 切换时的起始状态（用于缓动计算）
   */
  _beginTransition() {
    this.transitionStartOpen = this.currentLipValue
    this.transitionStartForm = this.currentMouthForm
    this.transitionStartTime = performance.now()
  }

  /**
   * 协同发音混合 — 计算 ParamMouthOpenY 的 anticipatory coarticulation
   *
   * 当前 viseme 最后 35% 时间向前一个 viseme 缓入缓出混合
   */
  _computeCoarticulatedOpen(ctx) {
    const { targetOpen, nextOpen, currentDuration, timeInto } = ctx

    // 没有下一个 viseme，无需协同发音
    if (nextOpen === null) return targetOpen

    // 在边界前 35% 开始混合
    const blendStartRatio = 0.65
    const progress = currentDuration > 0 ? timeInto / currentDuration : 1.0

    if (progress <= blendStartRatio) return targetOpen

    // 映射到 0..1 的混合窗口
    const rawBlend = (progress - blendStartRatio) / (1.0 - blendStartRatio)
    const blendWeight = Easing.easeInOutCubic(rawBlend)

    return targetOpen + (nextOpen - targetOpen) * blendWeight
  }

  /**
   * 协同发音混合 — 计算 ParamMouthForm 的 anticipatory coarticulation
   */
  _computeCoarticulatedForm(ctx) {
    const { targetForm, nextForm, currentDuration, timeInto } = ctx

    if (nextForm === null) return targetForm

    const blendStartRatio = 0.65
    const progress = currentDuration > 0 ? timeInto / currentDuration : 1.0

    if (progress <= blendStartRatio) return targetForm

    const rawBlend = (progress - blendStartRatio) / (1.0 - blendStartRatio)
    const blendWeight = Easing.easeInOutCubic(rawBlend)

    return targetForm + (nextForm - targetForm) * blendWeight
  }

  /**
   * 获取音素分类
   */
  _getVisemeClass(visemeKey) {
    for (const [cls, set] of Object.entries(VISEME_CLASS)) {
      if (set.has(visemeKey)) return cls
    }
    return 'SILENCE'
  }

  /**
   * 方向感知 + 音素分类感知的自适应平滑
   *
   * 核心逻辑：
   *   - 张嘴（attack）快、闭嘴（release）慢
   *   - 爆破音张嘴更快、元音闭嘴更慢
   *   - 叠加缓入缓出曲线
   */
  _applyAdaptiveSmoothing(targetOpen, targetForm, visemeKey) {
    // 手动平滑模式（向后兼容）
    if (this._manualSmoothingOverride) {
      const distO = targetOpen - this.currentLipValue
      this.currentLipValue += distO * this.smoothingFactor
      this.currentMouthForm += (targetForm - this.currentMouthForm) * this.smoothingFactor
      return
    }

    const distOpen = targetOpen - this.currentLipValue
    const isOpening = distOpen > 0
    const vClass = this._getVisemeClass(visemeKey)

    // --- 确定基础平滑因子 ---
    let factor
    if (isOpening) {
      factor = SMOOTHING.ATTACK_BASE
      // 爆破音：更快张嘴（爆开效果）
      if (vClass === 'PLOSIVE') factor = 0.65
    } else {
      factor = SMOOTHING.RELEASE_BASE
      // 元音：更慢闭嘴（口腔保持）
      if (vClass === 'VOWEL') factor = 0.10
    }

    // --- 叠加过渡缓动曲线 ---
    const elapsed = performance.now() - this.transitionStartTime
    const transitionWindow = 150 // 典型过渡窗口（毫秒）
    const t = Math.min(elapsed / transitionWindow, 1.0)

    // 缓入缓出：过渡开始加速，接近目标时减速
    const easedFactor = factor * (1.0 + 0.3 * Easing.easeInOutCubic(t))

    // --- 应用平滑 ---
    this.currentLipValue += distOpen * easedFactor

    // --- 口型变化：简单平滑（无需方向偏置）---
    const distForm = targetForm - this.currentMouthForm
    this.currentMouthForm += distForm * SMOOTHING.MOUTH_FORM
  }

  /**
   * 微动抖动 — 持续元音/鼻音期间的微小随机振动
   *
   * 使用三频非谐波正弦叠加，避免明显的周期性
   * 仅对元音和鼻音生效（爆破音/擦音持续时间太短）
   */
  _computeMicroJitter(visemeKey) {
    const vClass = this._getVisemeClass(visemeKey)
    if (vClass !== 'VOWEL' && vClass !== 'NASAL') return 0.0

    // 幅度随张嘴程度缩放（嘴越大微动越明显）
    const amplitude = SMOOTHING.JITTER_AMP + this.currentLipValue * 0.012

    // 推进相位
    this.jitterPhase += 0.12

    // 三频非谐波叠加（避免明显的周期性）
    return (
      Math.sin(this.jitterPhase) * amplitude * 0.55 +
      Math.sin(this.jitterPhase * 2.3 + 1.7) * amplitude * 0.30 +
      Math.sin(this.jitterPhase * 0.7 + 3.1) * amplitude * 0.15
    )
  }

  /**
   * 开始从说话状态到呼吸状态的过渡
   */
  _beginIdleTransition() {
    this._idleTransitionActive = true
    this.idleTransitionStartValue = this.currentLipValue
    this.idleTransitionStartTime = performance.now()
  }

  /**
   * 更新说话→呼吸的过渡动画
   * 使用 400ms easeOutQuad 避免突然切断
   */
  _updateIdleTransition() {
    const elapsed = performance.now() - this.idleTransitionStartTime
    const duration = 400 // 过渡持续毫秒
    const t = Math.min(elapsed / duration, 1.0)
    const easedT = Easing.easeOutQuad(t)

    // 目标：呼吸基线
    const breathingBaseline = this._getBreathingOffset()
    const target = easedT * breathingBaseline + (1 - easedT) * this.idleTransitionStartValue

    this.currentLipValue += (target - this.currentLipValue) * 0.25
    this.currentMouthForm += (0 - this.currentMouthForm) * 0.20

    this.setMouthValue(this.currentLipValue)
    this.setMouthFormValue(this.currentMouthForm)

    // 过渡完成
    if (t >= 1.0 && Math.abs(this.currentLipValue - breathingBaseline) < 0.005) {
      this._idleTransitionActive = false
      this.isIdle = true
    }
  }

  /**
   * 更新空闲呼吸动画
   * ~0.25Hz 极慢速循环，吸气时微张嘴
   */
  _updateBreathing() {
    this.breathingPhase += 0.025

    const breathOffset = this._getBreathingOffset()

    // 极慢平滑
    this.currentLipValue += (breathOffset - this.currentLipValue) * SMOOTHING.IDLE_BREATH
    this.currentMouthForm += (0 - this.currentMouthForm) * SMOOTHING.IDLE_BREATH * 0.5

    const clampedOpen = Math.max(0, this.currentLipValue)

    this.setMouthValue(clampedOpen)
    this.setMouthFormValue(this.currentMouthForm)
  }

  /**
   * 计算当前呼吸偏移值
   * 吸气（正弦波 > 0）：微张嘴 ~0.035
   * 呼气（正弦波 < 0）：接近闭合 ~0.008
   */
  _getBreathingOffset() {
    const wave = Math.sin(this.breathingPhase)
    return wave > 0 ? wave * 0.035 : wave * 0.008
  }

  /**
   * Viseme 名称转换为口型开合值
   * @param {string} viseme - Viseme 名称
   * @returns {number} 口型开合值 (0-1)
   */
  visemeToValue(viseme) {
    return VISeme_MAPPING[viseme] !== undefined ? VISeme_MAPPING[viseme] : 0.0
  }

  /**
   * 设置平滑因子
   * @param {number} factor - 平滑因子 (0-1)，越大响应越快
   *
   * 设置后启用手动平滑模式，覆盖自适应平滑逻辑
   */
  setSmoothingFactor(factor) {
    this.smoothingFactor = Math.max(0, Math.min(1, factor))
    this._manualSmoothingOverride = true
    console.log(`🔧 LipSync 平滑因子设置为: ${this.smoothingFactor}（手动模式）`)
  }

  /**
   * 重置口型同步器
   * 清空语音数据并平滑过渡到空闲呼吸（而非瞬间归零）
   */
  reset() {
    this.currentLips = null
    // 不归零 currentLipValue — 让它自然衰减到呼吸状态
    if (!this.isIdle) {
      this._beginIdleTransition()
    }
  }
}

// ==================== Live2D 核心控制器 ====================

/**
 * Live2DController - Live2D 核心控制器
 * 
 * 封装所有 Live2D 控制逻辑，提供统一的 API 接口
 */
export class Live2DController {
  constructor(model) {
    this.model = model
    this.lipSync = null
    this.isSpeaking = false
    this.disableTracking = false // 默认不禁用，让动作动画控制参数
    
    // 初始化口型同步器
    this.initLipSync()
    
    console.log(' Live2DController 初始化完成')
  }

  /**
   * 初始化口型同步器
   */
  initLipSync() {
    this.lipSync = new LipSync(
      (value) => {
        // 必须使用绝对设置，防止被表情覆盖
        this.setParameterAbsolute('ParamMouthOpenY', value)
      },
      (value) => {
        // 口型形状：负值=圆唇，正值=咧嘴
        this.setParameterAbsolute('ParamMouthForm', value)
      }
    )
  }

  /**
   * 设置参数（绝对设置 - 用于口型、表情等）
   * @param {string} paramId - 参数ID
   * @param {number} value - 参数值
   */
  setParameterAbsolute(paramId, value) {
    if (!this.model?.internalModel?.coreModel) return
    
    try {
      this.model.internalModel.coreModel.setParameterValueById(paramId, value)
    } catch (error) {
      console.warn(`⚠️ 设置参数失败 [${paramId}]:`, error)
    }
  }

  /**
   * 添加参数（相对添加 - 用于拖拽、呼吸等）
   * @param {string} paramId - 参数ID
   * @param {number} delta - 增量值
   * @param {number} weight - 权重 (0-1)
   */
  addParameterRelative(paramId, delta, weight = 1.0) {
    if (!this.model?.internalModel?.coreModel) return
    
    try {
      this.model.internalModel.coreModel.addParameterValueById(paramId, delta, weight)
    } catch (error) {
      console.warn(`⚠️ 添加参数失败 [${paramId}]:`, error)
    }
  }

  /**
   * 禁用眼球、头部和身体跟踪
   * 在动画循环中持续调用，压制库的自动交互逻辑
   */
  disableEyeAndHeadTracking() {
    if (!this.model || !this.disableTracking) return
    
    const coreModel = this.model.internalModel?.coreModel
    if (!coreModel) return
    
    try {
      // 设置眼球参数为中间值（正视前方）
      coreModel.setParameterValueById('ParamEyeBallX', 0)
      coreModel.setParameterValueById('ParamEyeBallY', 0)
      
      // 设置头部角度参数为中间值（正视前方）
      coreModel.setParameterValueById('ParamAngleX', 0)
      coreModel.setParameterValueById('ParamAngleY', 0)
      coreModel.setParameterValueById('ParamAngleZ', 0)
      
      // 设置身体旋转参数为中间值（保持身体正直）
      coreModel.setParameterValueById('ParamBodyAngleX', 0)
      coreModel.setParameterValueById('ParamBodyAngleY', 0)
      coreModel.setParameterValueById('ParamBodyAngleZ', 0)
      
      // 如果模型有 ParamBodyAngleY2，也重置它
      try {
        coreModel.setParameterValueById('ParamBodyAngleY2', 0)
      } catch (e) {
        // 忽略不存在的参数
      }
    } catch (error) {
      // 静默失败，避免控制台过多警告
    }
  }

  /**
   * 启动口型同步（基于 Viseme 数据）
   * @param {Array} lipsData - Viseme数据数组
   * @param {HTMLAudioElement} audioElement - 可选的音频元素（用于精确时间同步）
   */
  speakWithVisemes(lipsData, audioElement = null) {
    if (!lipsData || lipsData.length === 0) {
      console.warn('⚠️ 没有 viseme 数据，使用文本估算模式')
      return
    }

    this.isSpeaking = true
    
    // 如果提供了音频元素，使用其 currentTime 作为时间源
    const timeProvider = audioElement 
      ? () => audioElement.currentTime 
      : null
    
    this.lipSync.startLipSync(lipsData, timeProvider)
    console.log('🗣️ 开始 Viseme 驱动口型同步')
  }

  /**
   * 基于文本长度估算的口型动画（降级方案）
   * @param {string} text - 要说话的文本内容
   */
  speakWithEstimation(text) {
    if (!text) return
    
    this.isSpeaking = true
    
    // 根据文本长度估算说话时长（最短1.5秒，最长8秒）
    const duration = Math.min(8000, Math.max(1500, text.length * 120))
    
    // 生成模拟的 viseme 序列
    const visemeSequence = [
      'sil', 'aa', 'oh', 'E', 'ih', 'SS', 'TH', 
      'aa', 'ou', 'kk', 'DD', 'FF', 'PP', 'sil'
    ]
    
    const lipsData = []
    const visemeDuration = duration / visemeSequence.length
    
    visemeSequence.forEach(viseme => {
      lipsData.push({ Lip: viseme, Time: visemeDuration })
    })
    
    this.lipSync.startLipSync(lipsData)
    console.log(`🗣️ 开始估算口型动画，时长: ${duration}ms`)
  }

  /**
   * 停止口型同步
   */
  stopSpeaking() {
    this.isSpeaking = false
    this.lipSync.reset()
    
    // ✅ 关键修复：直接强制闭合嘴巴，不依赖平滑过渡
    this.closeMouthImmediately()
    
    console.log('🔇 停止口型同步')
  }

  /**
   * 立即闭合嘴巴（强制设置，无平滑过渡）
   */
  closeMouthImmediately() {
    if (!this.model?.internalModel?.coreModel) return
    
    try {
      // 直接设置 ParamMouthOpenY 为 0，完全闭合
      this.model.internalModel.coreModel.setParameterValueById('ParamMouthOpenY', 0)
      
      // 如果模型有 ParamMouthForm 参数，也重置为默认值（通常为 0 或 -1）
      try {
        this.model.internalModel.coreModel.setParameterValueById('ParamMouthForm', 0)
      } catch (e) {
        // 忽略不存在的参数
      }
      
      console.log('👄 已强制闭合嘴巴')
    } catch (error) {
      console.warn('⚠️ 强制闭合嘴巴失败:', error)
    }
  }

  /**
   * 每帧更新（应在 PixiJS ticker 中调用）
   */
  update() {
    // 更新口型同步
    this.lipSync.update()
    
    // 禁用眼球/头部跟踪
    this.disableEyeAndHeadTracking()
  }

  /**
   * 设置表情
   * @param {string} expressionName - 表情名称 (F01-F08)
   */
  setExpression(expressionName) {
    if (!this.model) return
    
    try {
      const expressionManager = this.model.internalModel?.expressionManager
      if (expressionManager) {
        expressionManager.setExpression(expressionName)
        console.log(` 表情已设置: ${expressionName}`)
      } else {
        console.warn('⚠️ 表情管理器不可用')
      }
    } catch (error) {
      console.error('❌ 设置表情失败:', error)
    }
  }

  /**
   * 根据情感值设置表情
   * @param {number} sentiment - 情感值 (-2 ~ +2)
   */
  setExpressionBySentiment(sentiment) {
    let expressionName = SENTIMENT_TO_EXPRESSION.neutral
    
    if (sentiment >= 1.5) {
      expressionName = SENTIMENT_TO_EXPRESSION.veryHappy
    } else if (sentiment >= 0.3) {
      expressionName = SENTIMENT_TO_EXPRESSION.happy
    } else if (sentiment <= -0.7) {
      expressionName = SENTIMENT_TO_EXPRESSION.sad
    } else if (sentiment <= -0.3) {
      expressionName = SENTIMENT_TO_EXPRESSION.angry
    }
    
    console.log(`😊 设置表情: ${expressionName} (sentiment: ${sentiment})`)
    this.setExpression(expressionName)
  }

  /**
   * 播放随机表情
   */
  setRandomExpression() {
    if (!this.model) return
    
    const expressions = ['F01', 'F02', 'F03', 'F04', 'F05', 'F06', 'F07', 'F08']
    const randomExpr = expressions[Math.floor(Math.random() * expressions.length)]
    this.setExpression(randomExpr)
  }

  /**
   * 播放指定动作组中的随机动作
   * @param {string} group - 动作组名称 (如 'TapBody', 'Idle')
   * @param {number} priority - 动作优先级
   */
  startRandomMotion(group, priority = Priority.Normal) {
    if (!this.model) return

    try {
      // 通过尝试不同索引来确定实际动作数量
      const MAX_MOTIONS = 27
      const randomIndex = Math.floor(Math.random() * MAX_MOTIONS)
      this.model.motion(group, randomIndex, { force: true })
      console.log(`🎬 播放随机动作: ${group}_${randomIndex}`)
    } catch (error) {
      console.error('❌ 播放动作失败:', error)
    }
  }

  /**
   * 播放指定行为对应的动作
   * @param {string} behavior - 行为名称（如 'nod', 'wave'）
   * @param {number} intensity - 强度 (0-1)
   */
  performAction(behavior, intensity = 1.0) {
    const actionConfig = ACTION_MAP[behavior]
    if (!actionConfig) {
      console.warn(`⚠️ 未找到行为映射: ${behavior}`)
      return
    }

    const { group, candidates } = actionConfig
    const randomIndex = candidates[Math.floor(Math.random() * candidates.length)]
    
    // 根据强度决定优先级
    const priority = intensity > 0.8 ? Priority.Force : Priority.Normal
    
    this.model.motion(group, randomIndex, { force: priority === Priority.Force })
    console.log(`🎭 执行动作: ${behavior} (强度: ${intensity})`)
  }

  /**
   * 绑定点击交互事件
   * @param {Function} onHeadClick - 点击头部的回调
   * @param {Function} onBodyClick - 点击身体的回调
   */
  bindClickEvents(onHeadClick, onBodyClick) {
    if (!this.model) return
    
    this.model.removeAllListeners('pointertap')
    
    this.model.on('pointertap', (event) => {
      if (!this.model) return
      
      // ✅ 安全检查：确保模型已完全初始化
      if (!this.model.transform || !this.model.worldTransform) {
        console.warn('⚠️ 模型变换矩阵未就绪，忽略点击事件')
        return
      }
      
      try {
        // 获取点击位置相对于模型的坐标
        const localPos = this.model.toLocal(event.global)
        const modelHeight = this.model.height
        
        // 简单判断点击区域（上半部分为头部，下半部分为身体）
        const headThreshold = modelHeight * 0.4
        
        if (localPos.y < headThreshold) {
          // 点击头部
          console.log('👆 点击头部')
          onHeadClick?.()
        } else {
          // 点击身体
          console.log('👆 点击身体')
          onBodyClick?.()
        }
      } catch (error) {
        console.warn('⚠️ 处理点击事件失败:', error)
      }
    })
  }

  /**
   * 销毁控制器
   */
  destroy() {
    this.stopSpeaking()
    this.model = null
    this.lipSync = null
    console.log('🗑️ Live2DController 已销毁')
  }
}

// ==================== 导出默认实例工厂 ====================

/**
 * 创建 Live2DController 实例
 * @param {object} model - Live2D 模型实例
 * @returns {Live2DController} 控制器实例
 */
export function createLive2DController(model) {
  return new Live2DController(model)
}
