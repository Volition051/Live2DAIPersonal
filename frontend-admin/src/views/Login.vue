<template>
  <div class="login-container">
    <div class="login-box">
      <h2>景区AI导览数字人后台管理系统</h2>
      <el-form :model="form" label-width="80px" style="margin-top: 30px;">
        <el-form-item label="用户名">
          <el-input v-model="form.username" placeholder="请输入管理员账号" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" placeholder="请输入密码" @keyup.enter="handleLogin" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" style="width: 100%;" @click="handleLogin" :loading="loading">
            登录
          </el-button>
        </el-form-item>
      </el-form>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import request from '@/utils/request'

const router = useRouter()
const loading = ref(false)
const rememberMe = ref(false)
const form = ref({
  username: '',
  password: ''
})
  

const handleLogin = async () => {
  if (!form.value.username || !form.value.password) {
    ElMessage.warning('请输入账号和密码')
    return
  }

  loading.value = true
  try {
    // 调用登录接口
    const formData = new FormData()
    formData.append('username', form.value.username)
    formData.append('password', form.value.password)
    const res = await request.post('/admin/login', formData)

    // 保存 token
    const token = res.access_token || res.token
    if (token) {
      localStorage.setItem('admin_token', token)
      // 保存超级管理员标志
      if (res.is_superadmin !== undefined) {
        localStorage.setItem('is_superadmin', res.is_superadmin ? 'true' : 'false')
      }
    }

    ElMessage.success('登录成功')
    router.push('/knowledge')
  } catch (err) {
    console.error(err)
    ElMessage.error(err.response?.data?.detail || '登录失败，请检查账号和密码')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-container {
  width: 100vw;
  height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  align-items: center;
  justify-content: center;
}
.login-box {
  width: 400px;
  padding: 40px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 10px 30px rgba(0,0,0,0.1);
  color: #333;
}
.login-box h2 {
  text-align: center;
  color: #333;
  font-weight: 600;
}
/* 确保表单标签和输入框文字为深色 */
.login-box :deep(.el-form-item__label) {
  color: #333;
}
.login-box :deep(.el-input__inner) {
  color: #333;
}
</style>