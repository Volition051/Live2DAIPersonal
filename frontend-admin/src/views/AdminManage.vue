<template>
  <div>
    <el-button type="primary" @click="openCreateDialog">新增管理员</el-button>
    
    <el-table :data="adminList" style="margin-top: 20px" v-loading="loading">
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="username" label="用户名" />
      <el-table-column label="角色">
        <template #default="{ row }">
          <el-tag :type="row.is_superadmin ? 'danger' : ''">
            {{ row.is_superadmin ? '超级管理员' : '普通管理员' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="150">
        <template #default="{ row }">
          <el-button 
            size="small" type="danger" 
            :disabled="row.is_superadmin && isOnlySuper(row)" 
            @click="handleDelete(row)"
          >
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 创建对话框 -->
    <el-dialog v-model="createVisible" title="创建管理员" width="400px">
      <el-form :model="form" :rules="rules" ref="formRef">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" type="password" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" @click="createAdmin">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'

const API = axios.create({ baseURL: 'http://localhost:8000' }) // 根据实际地址调整

// Token 注入
API.interceptors.request.use(config => {
  const token = localStorage.getItem('admin_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

const loading = ref(false)
const adminList = ref([])
const createVisible = ref(false)
const form = ref({ username: '', password: '' })
const formRef = ref(null)
const rules = {
  username: [{ required: true, message: '请输入用户名' }],
  password: [{ required: true, message: '请输入密码', min: 6 }]
}

const fetchList = async () => {
  loading.value = true
  try {
    const res = await API.get('/admin/manage/list')
    adminList.value = res.data
  } catch (e) {
    ElMessage.error('加载管理员列表失败')
  } finally {
    loading.value = false
  }
}

const isOnlySuper = (row) => {
  // 如果只有这一个超级管理员，不允许删除（按钮已禁用，再判断一次）
  const superCount = adminList.value.filter(u => u.is_superadmin).length
  return superCount <= 1
}

const openCreateDialog = () => {
  form.value = { username: '', password: '' }
  createVisible.value = true
}

const createAdmin = async () => {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  try {
    await API.post('/admin/manage/create', form.value)
    ElMessage.success('管理员创建成功')
    createVisible.value = false
    fetchList()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '创建失败')
  }
}

const handleDelete = (row) => {
  ElMessageBox.confirm(`确定要删除管理员“${row.username}”吗？`, '警告', {
    type: 'warning'
  }).then(async () => {
    try {
      await API.delete(`/admin/manage/${row.id}`)
      ElMessage.success('已删除')
      fetchList()
    } catch (e) {
      ElMessage.error(e.response?.data?.detail || '删除失败')
    }
  })
}

onMounted(fetchList)
</script>