<template>
  <router-view />
</template>

<script setup>
import { onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { showConfirmDialog } from 'vant'
import { startSessionMonitor, stopSessionMonitor, clearAllSessionData } from '@/utils/session'

const router = useRouter()
const auth = useAuthStore()

// 会话超时处理函数
const handleSessionTimeout = async () => {
  try {
    await showConfirmDialog({
      title: '会话已过期',
      message: '您已超过30分钟未操作，需要重新登录',
      confirmButtonText: '重新登录',
      cancelButtonText: '取消',
      showCancelButton: true
    })
    
    // 用户确认后登出并跳转到登录页
    auth.logout()
    clearAllSessionData()
    router.push('/login')
  } catch (error) {
    // 用户取消，仍然登出
    auth.logout()
    clearAllSessionData()
    router.push('/login')
  }
}

// 组件挂载时启动会话监控
onMounted(() => {
  if (auth.isLoggedIn) {
    startSessionMonitor(handleSessionTimeout)
  }
})

// 组件卸载时停止会话监控
onUnmounted(() => {
  stopSessionMonitor()
})
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body, #app {
  width: 100%;
  height: 100%;
  overflow: hidden;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

/* ==================== 全局移动端优化样式 ==================== */

/* 移除点击高亮和长按菜单（提升触摸体验） */
* {
  -webkit-tap-highlight-color: transparent; /* 移除点击高亮 */
  -webkit-touch-callout: none; /* 禁用长按菜单 */
}

/* 默认允许文本选择（支持复制功能） */
body {
  user-select: text;
  -webkit-user-select: text;
}

/* 允许输入框和文本域的文本选择 */
input, textarea {
  user-select: text;
  -webkit-user-select: text;
}

/* 特定元素禁止文本选择（如按钮、图标等） */
button, .van-button, .icon, [role="button"] {
  user-select: none;
  -webkit-user-select: none;
}

/* 优化滚动条样式 */
::-webkit-scrollbar {
  width: 4px;
  height: 4px;
}

::-webkit-scrollbar-track {
  background: transparent;
}

::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.2);
  border-radius: 2px;
}

::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 0, 0, 0.3);
}

/* 启用硬件加速滚动（iOS） */
* {
  -webkit-overflow-scrolling: touch;
}

/* 防止图片拖拽 */
img {
  -webkit-user-drag: none;
  pointer-events: auto;
}

/* 优化按钮点击反馈 */
button, .van-button {
  transition: all 0.15s ease;
  cursor: pointer;
}

button:active, .van-button:active {
  transform: scale(0.98);
  opacity: 0.9;
}

/* 防止 iOS 输入框自动缩放（确保表单字体 >= 16px） */
@media (max-width: 768px) {
  input, textarea, select, .van-field__control {
    font-size: 16px !important;
  }
}

/* 防止快速双击缩放 */
@media (max-width: 768px) {
  html {
    touch-action: manipulation;
  }
}

/* 横屏模式提示（可选） */
@media screen and (orientation: landscape) and (max-height: 500px) {
  /* 可以在这里添加横屏提示样式 */
}

/* 安全区域全局适配 */
@supports (padding-bottom: env(safe-area-inset-bottom)) {
  body {
    padding-bottom: env(safe-area-inset-bottom);
  }
}

/* 安全区域顶部适配（刘海屏等） */
@supports (padding-top: env(safe-area-inset-top)) {
  body {
    padding-top: env(safe-area-inset-top);
  }
}

/* iOS 弹性滚动边界锁定 */
@media (max-width: 768px) {
  html, body {
    overscroll-behavior: none;
    -webkit-overflow-scrolling: auto;
  }
}

/* 深色模式支持（可选） */
@media (prefers-color-scheme: dark) {
  /* 强制 Vant Toast 在暗色模式下保持可读 */
  .van-toast {
    color-scheme: light;
  }
  .van-toast__text {
    color: #323233 !important;  /* Vant 默认文字色，暗色模式下不被覆盖 */
  }
}

/* 减少动画偏好设置支持 */
@media (prefers-reduced-motion: reduce) {
  * {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}

/* 提升移动端渲染性能的全局优化 */
@media (max-width: 768px) {
  /* 为常见的动画元素预开启 GPU 加速 */
  .van-popup,
  .van-overlay,
  .van-toast {
    will-change: transform, opacity;
  }

  /* 优化移动端弹窗层级 */
  .van-popup {
    -webkit-backface-visibility: hidden;
    backface-visibility: hidden;
  }
}
</style>