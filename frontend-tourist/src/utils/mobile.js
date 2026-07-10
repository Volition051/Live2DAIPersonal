/**
 * 移动端工具函数库
 * 提供设备检测、触摸优化等实用功能
 */

/**
 * 检测设备类型
 * @returns {Object} 设备信息对象
 */
export function detectDevice() {
  const ua = navigator.userAgent
  const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(ua)
  const isIOS = /iPhone|iPad|iPod/i.test(ua)
  const isAndroid = /Android/i.test(ua)
  const isWechat = /MicroMessenger/i.test(ua)
  
  // 获取屏幕宽度
  const screenWidth = window.screen.width
  const screenHeight = window.screen.height
  
  return {
    isMobile,
    isIOS,
    isAndroid,
    isWechat,
    screenWidth,
    screenHeight,
    isTablet: isMobile && (screenWidth >= 768 || /iPad/i.test(ua)),
    isPhone: isMobile && screenWidth < 768
  }
}

/**
 * 检查是否支持触摸
 * @returns {boolean}
 */
export function isTouchSupported() {
  return 'ontouchstart' in window || 
         navigator.maxTouchPoints > 0 || 
         navigator.msMaxTouchPoints > 0
}

/**
 * 防止页面滚动穿透（用于弹窗等场景）
 * @param {boolean} prevent - 是否阻止滚动
 */
export function preventScrollThrough(prevent = true) {
  if (prevent) {
    document.body.style.overflow = 'hidden'
    document.body.style.position = 'fixed'
    document.body.style.width = '100%'
  } else {
    document.body.style.overflow = ''
    document.body.style.position = ''
    document.body.style.width = ''
  }
}

/**
 * 安全地调用振动 API
 * @param {number|number[]} pattern - 振动模式
 */
export function vibrate(pattern = 50) {
  if ('vibrate' in navigator) {
    try {
      navigator.vibrate(pattern)
    } catch (e) {
      console.warn('振动 API调用失败:', e)
    }
  }
}

/**
 * 复制到剪贴板（移动端兼容方案）
 * @param {string} text - 要复制的文本
 * @returns {Promise<boolean>}
 */
export async function copyToClipboard(text) {
  try {
    // 优先使用现代 API
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(text)
      return true
    }
    
    // 降级方案
    const textarea = document.createElement('textarea')
    textarea.value = text
    textarea.style.position = 'fixed'
    textarea.style.opacity = '0'
    document.body.appendChild(textarea)
    textarea.select()
    
    const success = document.execCommand('copy')
    document.body.removeChild(textarea)
    
    return success
  } catch (e) {
    console.error('复制失败:', e)
    return false
  }
}

/**
 * 获取安全的顶部/底部间距（适配刘海屏）
 * @param {'top' | 'bottom'} position - 位置
 * @returns {string} CSS 值
 */
export function getSafeAreaInset(position = 'bottom') {
  return `env(safe-area-inset-${position}, 0px)`
}

/**
 * 监听横竖屏切换
 * @param {Function} callback - 回调函数，接收 orientation 参数 ('portrait' | 'landscape')
 * @returns {Function} 取消监听的函数
 */
export function onOrientationChange(callback) {
  const handleOrientation = () => {
    const orientation = window.innerWidth > window.innerHeight ? 'landscape' : 'portrait'
    callback(orientation)
  }
  
  window.addEventListener('resize', handleOrientation)
  window.addEventListener('orientationchange', handleOrientation)
  
  // 立即执行一次
  handleOrientation()
  
  // 返回取消监听的函数
  return () => {
    window.removeEventListener('resize', handleOrientation)
    window.removeEventListener('orientationchange', handleOrientation)
  }
}

/**
 * 判断是否为小屏幕设备
 * @param {number} breakpoint - 断点值，默认 768
 * @returns {boolean}
 */
export function isSmallScreen(breakpoint = 768) {
  return window.innerWidth <= breakpoint
}

/**
 * 防抖函数（适用于移动端触摸事件）
 * @param {Function} func - 要执行的函数
 * @param {number} wait - 等待时间（毫秒）
 * @returns {Function}
 */
export function debounce(func, wait = 300) {
  let timeout
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout)
      func(...args)
    }
    clearTimeout(timeout)
    timeout = setTimeout(later, wait)
  }
}

/**
 * 节流函数（适用于滚动等高频事件）
 * @param {Function} func - 要执行的函数
 * @param {number} limit - 限制时间（毫秒）
 * @returns {Function}
 */
export function throttle(func, limit = 200) {
  let inThrottle
  return function(...args) {
    if (!inThrottle) {
      func.apply(this, args)
      inThrottle = true
      setTimeout(() => inThrottle = false, limit)
    }
  }
}

/**
 * 检测网络状态
 * @returns {Object} 网络状态信息
 */
export function getNetworkStatus() {
  const connection = navigator.connection || 
                     navigator.mozConnection || 
                     navigator.webkitConnection
  
  if (connection) {
    return {
      type: connection.effectiveType, // 'slow-2g', '2g', '3g', '4g'
      downlink: connection.downlink, // 下行速度 (Mbps)
      rtt: connection.rtt, // 往返时延 (ms)
      saveData: connection.saveData // 是否启用数据节省模式
    }
  }
  
  return {
    type: navigator.onLine ? 'online' : 'offline',
    online: navigator.onLine
  }
}

/**
 * 请求全屏（适用于视频播放等场景）
 * @param {HTMLElement} element - 要全屏的元素
 */
export async function requestFullscreen(element) {
  try {
    if (element.requestFullscreen) {
      await element.requestFullscreen()
    } else if (element.webkitRequestFullscreen) {
      await element.webkitRequestFullscreen()
    } else if (element.msRequestFullscreen) {
      await element.msRequestFullscreen()
    }
  } catch (e) {
    console.error('全屏请求失败:', e)
  }
}

/**
 * 退出全屏
 */
export async function exitFullscreen() {
  try {
    if (document.exitFullscreen) {
      await document.exitFullscreen()
    } else if (document.webkitExitFullscreen) {
      await document.webkitExitFullscreen()
    } else if (document.msExitFullscreen) {
      await document.msExitFullscreen()
    }
  } catch (e) {
    console.error('退出全屏失败:', e)
  }
}
