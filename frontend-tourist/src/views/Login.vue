<!-- views/Login.vue -->
<template>
  <div class="login-container">
    <div class="login-content">
      <!-- 头部 Logo/标题区 -->
      <div class="header-section">
        <h2 class="welcome-text">欢迎使用景区导览服务AI数字人</h2>
        <p class="sub-text">请登录您的游客中心账号</p>
      </div>

      <!-- 表单卡片 -->
      <div class="form-card">
        <van-tabs v-model:active="activeTab" animated swipeable class="custom-tabs">
          <van-tab title="登录">
            <van-form @submit="handleLogin" class="custom-form">
              <van-field
                v-model="loginForm.username"
                name="用户名"
                placeholder="请输入用户名"
                :rules="[{ required: true, message: '请填写用户名' }]"
                input-align="left"
                class="custom-field"
              >
                <template #left-icon>
                  <van-icon name="user-o" class="field-icon" />
                </template>
              </van-field>
              <van-field
                v-model="loginForm.password"
                type="password"
                name="密码"
                placeholder="请输入密码"
                :rules="[{ required: true, message: '请填写密码' }]"
                input-align="left"
                class="custom-field"
              >
                <template #left-icon>
                  <van-icon name="lock" class="field-icon" />
                </template>
              </van-field>

              <!-- 记住密码 -->
              <div class="remember-me">
                <van-checkbox v-model="rememberMe" icon-size="16px">记住密码</van-checkbox>
              </div>

              <div class="button-group">
                <van-button
                  round
                  block
                  type="primary"
                  native-type="submit"
                  :loading="loginLoading"
                  class="submit-btn"
                >
                  立即登录
                </van-button>
              </div>
            </van-form>
          </van-tab>

          <van-tab title="注册">
            <van-form @submit="handleRegister" class="custom-form">
              <van-field
                v-model="registerForm.username"
                name="用户名"
                placeholder="设置用户名"
                :rules="[{ required: true, message: '请填写用户名' }]"
                input-align="left"
                class="custom-field"
              >
                <template #left-icon>
                  <van-icon name="user-o" class="field-icon" />
                </template>
              </van-field>
              <van-field
                v-model="registerForm.password"
                type="password"
                name="密码"
                placeholder="设置密码"
                :rules="[{ required: true, message: '请填写密码' }]"
                input-align="left"
                class="custom-field"
              >
                <template #left-icon>
                  <van-icon name="lock" class="field-icon" />
                </template>
              </van-field>
              <van-field
                v-model="registerForm.confirmPassword"
                type="password"
                name="确认密码"
                placeholder="再次输入密码"
                :rules="[{ validator: checkPassword, message: '两次密码不一致' }]"
                input-align="left"
                class="custom-field"
              >
                <template #left-icon>
                  <van-icon name="checked" class="field-icon" />
                </template>
              </van-field>

              <div class="button-group">
                <van-button
                  round
                  block
                  type="primary"
                  native-type="submit"
                  :loading="registerLoading"
                  class="submit-btn"
                >
                  立即注册
                </van-button>
              </div>
            </van-form>
          </van-tab>
        </van-tabs>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { showCustomToast } from '@/utils/toast'

const router = useRouter()
const auth = useAuthStore()
const activeTab = ref(0)

// 登录表单
const loginForm = reactive({ username: '', password: '' })
const loginLoading = ref(false)
const rememberMe = ref(false)

// 页面加载时恢复记住的密码
onMounted(() => {
  const savedUsername = localStorage.getItem('tourist_remember_username')
  const savedPassword = localStorage.getItem('tourist_remember_password')
  const isRemember = localStorage.getItem('tourist_remember_me') === 'true'

  if (isRemember && savedUsername && savedPassword) {
    loginForm.username = savedUsername
    loginForm.password = savedPassword
    rememberMe.value = true
  }

  // 如果已经登录，直接跳转到主页
  if (auth.isLoggedIn) {
    const redirect = router.currentRoute.value.query.redirect || '/'
    router.push(redirect)
  }
})

const handleLogin = async () => {
  loginLoading.value = true
  try {
    await auth.login(loginForm.username, loginForm.password)

    // 处理记住密码
    if (rememberMe.value) {
      localStorage.setItem('tourist_remember_username', loginForm.username)
      localStorage.setItem('tourist_remember_password', loginForm.password)
      localStorage.setItem('tourist_remember_me', 'true')
    } else {
      localStorage.removeItem('tourist_remember_username')
      localStorage.removeItem('tourist_remember_password')
      localStorage.removeItem('tourist_remember_me')
    }

    showCustomToast('登录成功', 'success')
    const redirect = router.currentRoute.value.query.redirect || '/'
    router.push(redirect)
  } catch (error) {
    showCustomToast(error.response?.data?.detail || '登录失败，请检查账号和密码', 'fail')
  } finally {
    loginLoading.value = false
  }
}

// 注册表单
const registerForm = reactive({ username: '', password: '', confirmPassword: '' })
const registerLoading = ref(false)

const checkPassword = (val) => val === registerForm.password

const handleRegister = async () => {
  if (registerForm.password !== registerForm.confirmPassword) {
    showCustomToast('两次输入的密码不一致，请重新输入', 'fail')
    return
  }
  registerLoading.value = true
  try {
    await auth.register(registerForm.username, registerForm.password)
    showCustomToast('注册成功，请登录', 'success')
    activeTab.value = 0
    registerForm.username = ''
    registerForm.password = ''
    registerForm.confirmPassword = ''
  } catch (error) {
    showCustomToast(error.response?.data?.detail || '注册失败，请稍后重试', 'fail')
  } finally {
    registerLoading.value = false
  }
}
</script>

<style scoped>
.login-container {
  min-height: 100vh;
  position: relative;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  background-image: url('./LoginBackground.jpg');
  background-size: cover;
  background-position: center;
  background-repeat: no-repeat;
}

.login-content {
  width: 100%;
  max-width: 520px;
  z-index: 1;
  display: flex;
  flex-direction: column;
  gap: 30px;
}

/* 头部区域 */
.header-section {
  text-align: center;
  color: #0c0c0c;
}

.logo-wrapper {
  width: 80px;
  height: 80px;
  margin: 0 auto 20px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  backdrop-filter: blur(10px);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
}

.welcome-text {
  font-size: 28px;
  font-weight: 600;
  margin: 0 0 8px;
  letter-spacing: 1px;
}

.sub-text {
  font-size: 14px;
  opacity: 0.9;
  margin: 0;
}

/* 表单卡片 */
.form-card {
  background: rgba(255, 255, 255, 0.95);
  border-radius: 20px;
  padding: 40px 30px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.35);
  backdrop-filter: blur(10px);
}

/* 自定义 Tab 样式 */
.custom-tabs :deep(.van-tabs__wrap) {
  margin-bottom: 20px;
}

.custom-tabs :deep(.van-tabs__nav) {
  background: transparent;
  padding: 0;
}

.custom-tabs :deep(.van-tab) {
  color: #999;
  font-weight: 500;
  font-size: 16px;
  transition: all 0.3s;
}

.custom-tabs :deep(.van-tab--active) {
  color: #667eea;
  font-weight: 600;
}

.custom-tabs :deep(.van-tabs__line) {
  background: linear-gradient(90deg, #667eea, #764ba2);
  height: 3px;
  border-radius: 2px;
  bottom: 0;
}

/* 表单样式 */
.custom-form {
  padding: 10px 0;
}

.custom-field {
  margin-bottom: 16px;
  background: #f7f8fa;
  border-radius: 12px;
  overflow: hidden;
  transition: all 0.3s;
}

.custom-field:focus-within {
  background: #fff;
  box-shadow: 0 0 0 2px rgba(102, 126, 234, 0.2);
}

.field-icon {
  color: #667eea;
  font-size: 18px;
  margin-right: 8px;
}

.custom-field :deep(.van-field__control) {
  font-size: 15px;
}

/* 记住密码 */
.remember-me {
  padding: 8px 16px;
  margin-bottom: 16px;
  display: flex;
  align-items: center;
}

.remember-me :deep(.van-checkbox__label) {
  font-size: 14px;
  color: #666;
}

/* 按钮组 */
.button-group {
  margin-top: 24px;
  padding: 0 10px;
}

.submit-btn {
  height: 48px;
  font-size: 16px;
  font-weight: 600;
  background: linear-gradient(135deg, #43b903);
  border: none;
  box-shadow: 0 8px 20px rgba(102, 126, 234, 0.3);
  transition: all 0.3s;
}

.submit-btn:active {
  transform: scale(0.98);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.2);
}

/* ========================================
   响应式优化 - 移动端
   ======================================== */

/* 平板及以下（<=768px） */
@media (max-width: 768px) {
  .login-content {
    max-width: 440px;
  }

  .form-card {
    padding: 32px 24px;
  }
}

/* 手机尺寸（<=480px） */
@media (max-width: 480px) {
  .login-container {
    padding: 15px;
    padding-top: calc(15px + env(safe-area-inset-top));
    padding-bottom: calc(15px + env(safe-area-inset-bottom));
  }

  .login-content {
    gap: 24px;
  }

  .form-card {
    padding: 24px 16px;
    border-radius: 16px;
  }

  .welcome-text {
    font-size: 22px;
  }

  .sub-text {
    font-size: 13px;
  }

  /* 优化表单输入框触摸体验 */
  .custom-field {
    margin-bottom: 12px;
    border-radius: 10px;
  }

  .custom-field :deep(.van-field__control) {
    font-size: 14px;
    min-height: 44px; /* 符合 Apple HIG 最小触摸目标 */
  }

  .submit-btn {
    height: 46px;
    font-size: 15px;
    border-radius: 23px;
    -webkit-tap-highlight-color: transparent;
  }

  .submit-btn:active {
    transform: scale(0.97);
    opacity: 0.9;
  }

  /* 记住密码复选框 */
  .remember-me {
    padding: 6px 12px;
    margin-bottom: 12px;
  }
}

/* 超小屏幕（<=360px） */
@media (max-width: 360px) {
  .login-container {
    padding: 10px;
    padding-top: calc(10px + env(safe-area-inset-top));
    padding-bottom: calc(10px + env(safe-area-inset-bottom));
  }

  .form-card {
    padding: 20px 12px;
    border-radius: 12px;
  }

  .welcome-text {
    font-size: 20px;
  }

  .sub-text {
    font-size: 12px;
  }
}

/* 移动端横屏模式 */
@media (max-width: 768px) and (orientation: landscape) {
  .login-container {
    align-items: flex-start;
    padding: 10px;
  }

  .login-content {
    gap: 12px;
    max-width: 480px;
  }

  .form-card {
    padding: 16px 20px;
  }

  .welcome-text {
    font-size: 18px;
    margin: 0;
  }

  .sub-text {
    font-size: 12px;
  }
}
</style>
