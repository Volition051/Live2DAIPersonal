<template>
  <!-- Live2D 模型显示容器 -->
  <div class="live2d-container">
    <!-- 背景图层 -->
    <div class="background-layer"></div>
    <canvas ref="liveCanvas"></canvas>
    <!-- 动作切换按钮（右上角） -->
    <div class="motion-controls">
      <van-button
        type="default"
        size="small"
        round
        @click="nextMotion"
        class="motion-btn"
      >
        🎭 换个动作
      </van-button>
    </div>
    <!-- 音频启用提示按钮（浏览器自动播放策略） -->
    <div v-if="showAudioEnableBtn" class="audio-enable-overlay">
      <van-button type="primary" size="small" @click="enableAudio">
        🔊 点击启用音频
      </van-button>
    </div>
  </div>
</template>

<script setup>
import { onMounted, onBeforeUnmount, ref } from 'vue'
import * as PIXI from 'pixi.js'
import { Live2DModel } from 'pixi-live2d-display'
import request from '@/utils/request'
import { createLive2DController, Priority } from '@/core/Live2DController'

// 将 PIXI 挂载到全局 window 对象，供 pixi-live2d-display 使用
window.PIXI = PIXI

const liveCanvas = ref(null) // Canvas 元素引用
let app = null // PixiJS 应用实例
let model = null // Live2D 模型实例
let controller = null // Live2D 核心控制器
let resizeModel = null // 模型尺寸调整函数
let showAudioEnableBtn = ref(false) // 是否显示音频启用按钮
const GROUP = ""               // 默认动作组名（haru 模型为空字符串）
let currentMotionIndex = 0     // 当前播放动作的索引

//  Live2D 模型配置（便于切换不同模型）
const MODEL_CONFIG = {
  // 当前使用的模型路径（相对于 public 目录）
  // 初始值：默认模型，将在 onMounted 中从 API 动态加载
  currentModel: './Resources/haru_greeter_pro_jp/runtime/haru_greeter_t05.model3.json',
  
  // 可选的模型列表
  availableModels: {
    haru: './Resources/haru_greeter_pro_jp/runtime/haru_greeter_t05.model3.json',
    hiyori: './Resources/hiyori-main/hiyori_free_t08.model3.json',
    openSource: './Resources/openSource/openSource.model3.json'
  },
  
  // 模型缩放系数（可根据不同模型调整）
  scaleMultiplier: 0.0003,

  // 模型垂直位置偏移（0-1，相对于容器高度）
  positionYRatio: 0.55
}

/**
 * 从后端 API 获取当前 Live2D 模型配置
 */
async function fetchCurrentModel() {
  try {
    console.log('🔍 正在从服务器获取当前 Live2D 模型配置...')
    const response = await request.get('/tourist/live2d/current-model')
    
    if (response.success && response.model_path) {
      // 后端返回绝对路径 /Resources/... 转为相对路径 ./Resources/...（兼容 file:// 协议）
      let modelPath = response.model_path
      if (modelPath.startsWith('/Resources/')) {
        modelPath = '.' + modelPath
      }
      MODEL_CONFIG.currentModel = modelPath
      console.log(` 已加载服务器配置的模型: ${response.model_path} → ${modelPath}`)
      
      // 如果模型不在 availableModels 中，添加进去
      if (!Object.values(MODEL_CONFIG.availableModels).includes(response.model_path)) {
        // 提取模型名称
        let modelName = 'custom'
        try {
          if (response.model_path.startsWith('./Resources/') || response.model_path.startsWith('/Resources/')) {
            const prefix = response.model_path.startsWith('./') ? './Resources/' : '/Resources/'
            const relativePath = response.model_path.substring(prefix.length)
            const pathParts = relativePath.split('/')
            if (pathParts.length > 0 && pathParts[0]) {
              modelName = pathParts[0]
            }
          }
        } catch (error) {
          console.warn('⚠️ 模型名称提取失败:', error)
        }
        
        MODEL_CONFIG.availableModels[modelName] = response.model_path
        console.log(` 已将新模型添加到可用列表: ${modelName}`)
      }
    } else {
      console.log('ℹ️ 未找到服务器配置，使用默认模型')
    }
  } catch (error) {
    console.error('❌ 获取模型配置失败，使用默认模型:', error)
    // 降级策略：使用默认模型，不阻断应用启动
  }
}

/**
 * 切换模型（动态加载新模型）
 * @param {string} modelName - 模型名称（如 'haru', 'hiyori'）或直接传入路径
 */
async function switchModel(modelName) {
  if (!app) {
    console.error('❌ PixiJS 应用未初始化')
    return
  }
  
  try {
    // 获取模型路径
    let modelPath = modelName
    if (MODEL_CONFIG.availableModels[modelName]) {
      modelPath = MODEL_CONFIG.availableModels[modelName]
    }
    
    console.log(`🔄 正在切换模型: ${modelPath}`)
    
    // 销毁旧控制器和模型
    if (controller) {
      controller.destroy()
      controller = null
    }
    
    if (model) {
      model.destroy()
      model = null
    }
    
    // 加载新模型
    model = await Live2DModel.from(modelPath)
    app.stage.addChild(model)
    
    // 重新注册 Ticker
    Live2DModel.registerTicker(PIXI.Ticker)
    
    // 重新启用交互
    model.eventMode = 'static'
    model.cursor = 'pointer'
    
    // 创建新的控制器
    controller = createLive2DController(model)
    
    // 重新调整尺寸（确保变换矩阵已就绪）
    if (resizeModel) {
      resizeModel()
    }
    
    // ✅ 关键优化：在模型尺寸调整完成后绑定点击事件
    bindModelEvents()
    
    console.log('✅ 模型切换成功:', modelPath)
  } catch (error) {
    console.error('❌ 模型切换失败:', error)
  }
}

/**
 * 绑定模型交互事件
 */
function bindModelEvents() {
  if (!controller) return
  
  // 使用控制器的点击事件绑定
  controller.bindClickEvents(
    () => controller.setRandomExpression(),  // 点击头部：随机表情
    () => controller.startRandomMotion('', Priority.Normal)  // 点击身体：随机动作
  )
}

/**
 * 基于文本长度估算的口型动画（降级方案）
 * @param {string} text - 要说话的文本内容
 */
function speak(text) {
  if (!controller || !text) return
  
  controller.speakWithEstimation(text)
}

/**
 * 基于真实音频时长的口型同步（推荐方案）
 * 支持 OVR LipSync viseme 数据驱动
 * @param {string} text - 要说话的文本内容
 * @param {HTMLAudioElement} audioElement - 音频元素对象
 * @param {object} options - 可选配置 { sentiment, action, lipsData }
 */
function speakWithAudio(text, audioElement, options = {}) {
  if (!controller || !text || !audioElement) return
  
  // 处理情感和动作（如果提供）
  if (options.sentiment !== undefined) {
    controller.setExpressionBySentiment(options.sentiment)
  }
  
  if (options.action) {
    console.log('🎭 接收到动作指令:', options.action)
    controller.performAction(options.action.behavior, options.action.intensity || 1.0)
  }

  // 检查是否有 viseme 数据（来自后端或 Fay）
  const lipsData = options.lipsData || null
  
  // 等待音频元数据加载完成
  if (audioElement.readyState < 2) {
    audioElement.addEventListener('loadedmetadata', () => {
      const duration = audioElement.duration * 1000
      if (!duration || isNaN(duration)) {
        console.warn('⚠️ 无法获取音频时长，使用估算值')
        controller.speakWithEstimation(text)
        return
      }
      
      if (lipsData && lipsData.length > 0) {
        // 使用 viseme 数据驱动（最高精度）
        controller.speakWithVisemes(lipsData, audioElement)
        // ✅ 添加生命周期监听，确保音频结束时口型闭合
  const onEnd = () => {
  controller.lipSync?.reset()  // 开始平滑闭合
  controller.isSpeaking = false
}
  audioElement.addEventListener('ended', onEnd, { once: true })
  audioElement.addEventListener('error', onEnd, { once: true })
      } else {
        // 降级到文本估算模式
        controller.speakWithEstimation(text)
      }
    }, { once: true })
  } else {
    const duration = audioElement.duration * 1000
    if (duration && !isNaN(duration)) {
      if (lipsData && lipsData.length > 0) {
        // 使用 viseme 数据驱动（最高精度）
        controller.speakWithVisemes(lipsData, audioElement)
      } else {
        // 降级到文本估算模式
        controller.speakWithEstimation(text)
      }
    } else {
      controller.speakWithEstimation(text)
    }
  }
}

/**
 * 设置表情
 * @param {string} expressionName - 表情名称 (F01-F08)
 */
function setExpression(expressionName) {
  controller?.setExpression(expressionName)
}

/**
 * 根据情感值设置表情
 * @param {number} sentiment - 情感值 (-2 ~ +2)
 */
function setExpressionBySentiment(sentiment) {
  controller?.setExpressionBySentiment(sentiment)
}

/**
 * 播放随机表情
 */
function setRandomExpression() {
  controller?.setRandomExpression()
}

/**
 * 播放指定动作组中的随机动作
 * @param {string} group - 动作组名称 (如 'TapBody', 'Idle')
 * @param {number} priority - 动作优先级
 */
function startRandomMotion(group, priority = Priority.Normal) {
  controller?.startRandomMotion(group, priority)
}

/**
 * 执行指定行为对应的动作
 * @param {string} behavior - 行为名称（如 'nod', 'wave'）
 * @param {number} intensity - 强度 (0-1)
 */
function performAction(behavior, intensity = 1.0) {
  controller?.performAction(behavior, intensity)
}

/**
 * 循环切换动作
 */
function nextMotion() {
  if (!model) return

  try {
    const MAX_MOTIONS = 5
    currentMotionIndex = (currentMotionIndex + 1) % MAX_MOTIONS
    model.motion(GROUP, currentMotionIndex, { force: true })
    console.log(`🔄 循环播放动作: 索引 ${currentMotionIndex}`)
  } catch (error) {
    console.error('❌ 切换动作失败:', error)
  }
}

/**
 * 启用音频播放（解决浏览器自动播放限制）
 */
function enableAudio() {
  showAudioEnableBtn.value = false
  console.log(' 用户已授权音频播放')
  
  // 创建一个静音音频并播放，以解锁浏览器的自动播放限制
  const silentAudio = new Audio('data:audio/wav;base64,UklGRigAAABXQVZFZm10IBIAAAABAAEARKwAAIhYAQACABAAAABkYXRhAgAAAAEA')
  silentAudio.play().catch(() => {
    // 忽略错误
  })
}

/**
 * 组件挂载时初始化 PixiJS 和 Live2D 模型
 */
onMounted(async () => {
  // 先从 API 获取当前模型配置
  await fetchCurrentModel()

  // 创建 PixiJS 应用实例
  app = new PIXI.Application({
    view: liveCanvas.value, // 绑定到 canvas 元素
    autoStart: true, // 自动启动渲染循环
    resizeTo: liveCanvas.value.parentElement, // 自动适应父容器尺寸
    backgroundAlpha: 0, // 背景透明
    antialias: true, // 启用抗锯齿
  })

  try {
    // 从配置中加载 Live2D 模型（使用可配置的路径）
    model = await Live2DModel.from(MODEL_CONFIG.currentModel)
    app.stage.addChild(model) // 将模型添加到舞台
    console.log(' 模型加载成功:', MODEL_CONFIG.currentModel)

    // 临时暴露模型到全局，方便调试
    window.__model = model

    // 注册 Ticker（确保动画同步）
    Live2DModel.registerTicker(PIXI.Ticker)
    console.log(' Ticker 已注册')

    // 启用交互模式
    model.eventMode = 'static'
    model.cursor = 'pointer'
    console.log(' 交互模式已启用')

    // 创建 Live2D 核心控制器
    controller = createLive2DController(model)
    console.log('✅ Live2DController 已创建')

    // 定义模型尺寸调整函数
    resizeModel = () => {
      const parent = liveCanvas.value.parentElement
      if (!parent || !model) return

      const w = parent.clientWidth
      const h = parent.clientHeight

      // 响应式缩放：桌面端略小，移动端略大
      // 根据视口宽度动态调整缩放系数
      const vw = window.innerWidth
      let responsiveMultiplier
      if (vw >= 1200) {
        responsiveMultiplier = MODEL_CONFIG.scaleMultiplier * 0.83   // 🖥️ 桌面端：缩小
      } else if (vw >= 768) {
        responsiveMultiplier = MODEL_CONFIG.scaleMultiplier * 0.88   // 💻 平板端：适中
      } else if (vw >= 480) {
        responsiveMultiplier = MODEL_CONFIG.scaleMultiplier * 1.15   // 📱 大屏手机：略大
      } else {
        responsiveMultiplier = MODEL_CONFIG.scaleMultiplier * 1.5    // 📱 小屏手机：放大
      }
      model.scale.set(Math.min(w, h) * responsiveMultiplier)
      // 设置模型位置为容器中心
      model.x = w / 2
      // 使用配置中的垂直位置比例
      model.y = h * MODEL_CONFIG.positionYRatio
      // 设置锚点为中心点
      model.anchor.set(0.5, 0.5)
    }

    resizeModel() // 初始调整尺寸
    window.addEventListener('resize', resizeModel) // 监听窗口大小变化

    // ✅ 关键优化：在模型尺寸调整完成后绑定点击事件，确保变换矩阵已就绪
    bindModelEvents()
    console.log('✅ 点击事件已绑定')

    // 播放初始待机动作（索引 0）
    model.motion(GROUP, 0)
    currentMotionIndex = 0
    console.log('✅ 已播放初始待机动作')

    // 在 PixiJS 的 ticker 中添加控制器更新逻辑，每帧执行
    app.ticker.add(() => {
      controller?.update()
    })
    console.log(' 已启用控制器每帧更新（包含禁用眼球/头部/身体鼠标跟随）')

    // 暴露 Live2D 控制方法到全局，方便控制台测试
    window.__live2d = {
      nextMotion,
      startRandomMotion,
      performAction,
      setExpression,
      setExpressionBySentiment,
      setRandomExpression,
      switchModel,
      speak,
      speakWithAudio,
      controller  // 暴露控制器实例
    }
    console.log(' Live2D 方法已暴露到 window.__live2d')
  } catch (error) {
    console.error('Live2D 模型加载失败:', error)
  }
})

/**
 * 组件卸载前清理资源
 */
onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeModel) // 移除窗口大小监听
  
  // 销毁控制器
  if (controller) {
    controller.destroy()
    controller = null
  }
  
  if (model) model.destroy() // 销毁模型实例
  if (app) app.destroy() // 销毁 PixiJS 应用
})

// 暴露方法给父组件调用
defineExpose({ 
  speak, 
  speakWithAudio,
  setExpression,
  setExpressionBySentiment,
  setRandomExpression,
  startRandomMotion,
  performAction,
  nextMotion,
  switchModel,
  controller  // 暴露控制器
})
</script>

<style scoped>
/* Live2D 容器样式 */
.live2d-container {
  width: 100%;
  height: 100%;
  position: relative;
}

/* 背景图层样式 */
.background-layer {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: transparent;
  z-index: 0;
}

/* Canvas 画布样式 */
canvas {
  width: 100%;
  height: 100%;
  display: block; /* 消除 inline 元素的默认间距 */
  position: relative;
  z-index: 1;
}

.motion-controls {
  display: none;
}
.motion-btn {
  background: rgba(255, 255, 255, 0.8);
  backdrop-filter: blur(4px);
  border: 1px solid rgba(0, 0, 0, 0.1);
  font-size: 13px;
  padding: 4px 12px;
}

/*  音频启用按钮覆盖层 */
.audio-enable-overlay {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 10;
}

/* ====================  移动端响应式适配 ==================== */

/* 平板设备 (768px 以下) */
@media screen and (max-width: 768px) {
  .live2d-container {
    min-height: 300px;
  }

  canvas {
    touch-action: none; /* 禁止触摸时的默认行为，提升交互体验 */
  }

  /* 动作按钮在平板上更紧凑 */
  .motion-btn {
    font-size: 12px;
    padding: 3px 10px;
  }
}

/* 手机设备 (480px 以下) - 移动端全屏背景 */
@media screen and (max-width: 480px) {
  .live2d-container {
    width: 100vw;
    height: 100vh;
    height: 100dvh; /* 动态视口高度，避免移动浏览器地址栏遮挡 */
    position: fixed;
    top: 0;
    left: 0;
    z-index: 0;
    contain: layout style paint; /* 提升渲染性能 */
  }

  /* Canvas 全屏显示 */
  canvas {
    width: 100vw;
    height: 100vh;
    height: 100dvh;
    touch-action: none;
    will-change: transform; /* GPU 加速 */
  }

  /* 动作按钮适配安全区域 */
  .motion-controls {
    top: calc(10px + env(safe-area-inset-top));
    right: calc(10px + env(safe-area-inset-right));
  }

  .motion-btn {
    font-size: 12px;
    padding: 4px 10px;
    -webkit-tap-highlight-color: transparent;
  }

  .motion-btn:active {
    transform: scale(0.93);
    opacity: 0.85;
  }

  /* 优化音频按钮在移动端的显示 */
  .audio-enable-overlay :deep(.van-button) {
    font-size: 14px;
    padding: 8px 16px;
    -webkit-tap-highlight-color: transparent;
  }
}

/* 横屏模式优化 */
@media screen and (max-height: 500px) and (orientation: landscape) {
  .live2d-container {
    min-height: 200px;
  }

  .motion-controls {
    top: 6px;
    right: 6px;
  }

  .motion-btn {
    font-size: 11px;
    padding: 2px 8px;
  }
}

/* 安全区域适配（iPhone X 及以上） */
@supports (padding-bottom: env(safe-area-inset-bottom)) {
  @media screen and (max-width: 480px) {
    .live2d-container {
      padding-bottom: env(safe-area-inset-bottom);
    }
  }
}
</style>