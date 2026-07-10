// stores/auth.js
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import request from '@/utils/request'

export const useAuthStore = defineStore('auth', () => {
  // 初始化时从 localStorage 恢复会话
  const token = ref(localStorage.getItem('tourist_token') || '')
  const touristId = ref(localStorage.getItem('tourist_id') || '')
  const userInfo = ref(JSON.parse(localStorage.getItem('tourist_user_info') || 'null'))

  const isLoggedIn = computed(() => !!token.value)

  // 登录
  async function login(username, password) {
    const formData = new FormData()
    formData.append('username', username)
    formData.append('password', password)

    const res = await request.post('/tourist/login', formData, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
    })
    token.value = res.access_token
    touristId.value = res.tourist_id
    userInfo.value = res.user_info || { username }
    
    // 持久化会话信息
    localStorage.setItem('tourist_token', token.value)
    localStorage.setItem('tourist_id', touristId.value)
    localStorage.setItem('tourist_user_info', JSON.stringify(userInfo.value))
    
    return res
  }

  // 注册
  async function register(username, password) {
    const formData = new FormData()
    formData.append('username', username)
    formData.append('password', password)

    const res = await request.post('/tourist/register', formData, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
    })
    return res
  }

  // 刷新会话（可用于token续期）
  async function refreshSession() {
    try {
      const res = await request.post('/tourist/refresh', {
        token: token.value
      })
      token.value = res.access_token
      localStorage.setItem('tourist_token', token.value)
      return true
    } catch (error) {
      console.error('会话刷新失败:', error)
      return false
    }
  }

  // 更新个人资料（用户名、性别）
  async function updateProfile(username, gender) {
    const body = { username }
    if (gender !== undefined) body.gender = gender
    const res = await request.put('/tourist/profile', body)
    userInfo.value = res.user_info || { username, gender }
    localStorage.setItem('tourist_user_info', JSON.stringify(userInfo.value))
    return res
  }

  // 登出
  function logout() {
    token.value = ''
    touristId.value = ''
    userInfo.value = null
    localStorage.removeItem('tourist_token')
    localStorage.removeItem('tourist_id')
    localStorage.removeItem('tourist_user_info')
  }

  // 检查会话是否有效
  function checkSession() {
    const hasToken = !!token.value
    if (!hasToken) {
      // 清除可能残留的会话信息
      localStorage.removeItem('tourist_token')
      localStorage.removeItem('tourist_id')
      localStorage.removeItem('tourist_user_info')
    }
    return hasToken
  }

  return {
    token,
    touristId,
    userInfo,
    isLoggedIn,
    login,
    register,
    updateProfile,
    logout,
    refreshSession,
    checkSession
  }
})