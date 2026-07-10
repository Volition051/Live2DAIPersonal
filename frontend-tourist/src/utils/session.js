// utils/session.js
/**
 * 会话管理工具
 * 提供自动登出、会话超时检测等功能
 */

const SESSION_TIMEOUT = 30 * 60 * 1000 // 30分钟超时（毫秒）
const ACTIVITY_EVENTS = ['mousedown', 'mousemove', 'keydown', 'scroll', 'touchstart']

let inactivityTimer = null
let lastActivityTime = Date.now()

/**
 * 启动会话超时监控
 * @param {Function} onTimeout - 超时回调函数
 */
export function startSessionMonitor(onTimeout) {
  // 清除之前的定时器
  stopSessionMonitor()
  
  // 重置最后活动时间
  lastActivityTime = Date.now()
  
  // 监听用户活动
  ACTIVITY_EVENTS.forEach(event => {
    window.addEventListener(event, resetInactivityTimer, { passive: true })
  })
  
  // 启动定时器
  inactivityTimer = setInterval(() => {
    const inactiveTime = Date.now() - lastActivityTime
    if (inactiveTime >= SESSION_TIMEOUT) {
      console.log('会话已超时，自动登出')
      stopSessionMonitor()
      onTimeout && onTimeout()
    }
  }, 60000) // 每分钟检查一次
}

/**
 * 停止会话超时监控
 */
export function stopSessionMonitor() {
  if (inactivityTimer) {
    clearInterval(inactivityTimer)
    inactivityTimer = null
  }
  
  // 移除事件监听
  ACTIVITY_EVENTS.forEach(event => {
    window.removeEventListener(event, resetInactivityTimer)
  })
}

/**
 * 重置不活动计时器
 */
function resetInactivityTimer() {
  lastActivityTime = Date.now()
}

/**
 * 检查会话是否有效
 * @returns {boolean}
 */
export function isSessionValid() {
  const token = localStorage.getItem('tourist_token')
  return !!token
}

/**
 * 获取剩余会话时间（秒）
 * @returns {number}
 */
export function getRemainingSessionTime() {
  const inactiveTime = Date.now() - lastActivityTime
  const remainingTime = Math.max(0, SESSION_TIMEOUT - inactiveTime)
  return Math.floor(remainingTime / 1000)
}

/**
 * 延长会话（刷新最后活动时间）
 */
export function extendSession() {
  lastActivityTime = Date.now()
}

/**
 * 清理所有会话数据
 */
export function clearAllSessionData() {
  // 清除游客端会话
  localStorage.removeItem('tourist_token')
  localStorage.removeItem('tourist_id')
  localStorage.removeItem('tourist_user_info')
  
  // 可选：不清除记住密码的数据
  // localStorage.removeItem('tourist_remember_username')
  // localStorage.removeItem('tourist_remember_password')
  // localStorage.removeItem('tourist_remember_me')
}

/**
 * 管理员端会话管理
 */
export const adminSession = {
  /**
   * 检查管理员会话是否有效
   */
  isValid() {
    return !!localStorage.getItem('admin_token')
  },
  
  /**
   * 获取超级管理员状态
   */
  isSuperAdmin() {
    return localStorage.getItem('is_superadmin') === 'true'
  },
  
  /**
   * 清理管理员会话数据
   */
  clear() {
    localStorage.removeItem('admin_token')
    localStorage.removeItem('is_superadmin')
  }
}
