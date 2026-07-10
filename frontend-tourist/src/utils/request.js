// utils/request.js
import axios from 'axios'
import { showToast } from 'vant'
import { useAuthStore } from '@/stores/auth'
import router from '@/router'

const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: 0
})

// 请求拦截器：如果已登录，自动附加 Bearer token
request.interceptors.request.use(config => {
  const auth = useAuthStore()
  if (auth.token) {
    config.headers.Authorization = `Bearer ${auth.token}`
  }
  return config
})

// 响应拦截器：统一错误处理 + 401 跳转登录
request.interceptors.response.use(
  response => {
    // 如果是 blob 类型（如音频文件），直接返回完整 response
    if (response.config.responseType === 'blob') {
      return response
    }
    // 否则返回 data
    return response.data
  },
  error => {
    if (error.response?.status === 401) {
      const auth = useAuthStore()
      auth.logout()
      router.push('/login')
    }
    // 复用原有的错误提示
    showToast(error.response?.data?.detail || '请求失败')
    return Promise.reject(error)
  }
)

export default request
