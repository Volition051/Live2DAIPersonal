<template>
  <el-container style="height: 100vh;">
    <el-aside :width="isCollapse ? '64px' : '200px'" class="sidebar-aside" style="transition: width 0.3s;">
      <el-menu
        :default-active="$route.path"
        router
        background-color="#304156"
        text-color="#fff"
        active-text-color="#409eff"
        :collapse="isCollapse"
        style="height:100%; border-right: none;"
      >
        <el-menu-item index="/knowledge">
          <el-icon><Document /></el-icon>
          <span>知识库列表</span>
        </el-menu-item>
        <el-menu-item index="/upload">
          <el-icon><Upload /></el-icon>
          <span>上传资料</span>
        </el-menu-item>
        <el-menu-item index="/visitor-stats">
          <el-icon><DataAnalysis /></el-icon>
          <span>游客统计</span>
        </el-menu-item>
        <el-menu-item index="/admin-chat">
          <el-icon><ChatDotRound /></el-icon>
          <span>AI 助手</span>
        </el-menu-item>
        <el-menu-item v-if="isSuperAdmin" index="/dashboard">
          <el-icon><Monitor /></el-icon>
          <span>数据大屏</span>
        </el-menu-item>
        <el-menu-item v-if="isSuperAdmin" index="/sentiment-report">
          <el-icon><TrendCharts /></el-icon>
          <span>感受度报告</span>
        </el-menu-item>
        <el-menu-item v-if="isSuperAdmin" index="/admin-manage">
          <el-icon><UserFilled /></el-icon>
          <span>管理员管理</span>
        </el-menu-item>
        <el-menu-item v-if="isSuperAdmin" index="/database">
          <el-icon><Grid /></el-icon>
          <span>数据库管理</span>
        </el-menu-item>
        <el-menu-item v-if="isSuperAdmin" index="/attractions">
          <el-icon><VideoCamera /></el-icon>
          <span>景点 & 视频管理</span>
        </el-menu-item>
        <el-menu-item v-if="isSuperAdmin" index="/Live2DController">
          <el-icon><ChatDotRound /></el-icon>
          <span>数字人管理</span>
        </el-menu-item>
        <el-menu-item v-if="isSuperAdmin" index="/audio-settings">
          <el-icon><Microphone /></el-icon>
          <span>音频设置</span>
        </el-menu-item>
        <el-menu-item v-if="isSuperAdmin" index="/appearance-settings">
          <el-icon><Picture /></el-icon>
          <span>前端外观</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header style="display:flex; justify-content:space-between; align-items:center;">
        <el-button
          text
          @click="isCollapse = !isCollapse"
          style="font-size:20px;"
        >
          <el-icon v-if="isCollapse"><Expand /></el-icon>
          <el-icon v-else><Fold /></el-icon>
        </el-button>
        <el-button type="text" @click="handleLogout">退出登录</el-button>
      </el-header>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Document, Upload, DataAnalysis, ChatDotRound,
  UserFilled, Grid, MapLocation, Monitor, Microphone, VideoCamera, Picture, TrendCharts,
  Fold, Expand
} from '@element-plus/icons-vue'

const router = useRouter()
const isSuperAdmin = ref(false)
const isCollapse = ref(false)

onMounted(() => {
  isSuperAdmin.value = localStorage.getItem('is_superadmin') === 'true'
})

const handleLogout = () => {
  ElMessageBox.confirm('确定要退出登录吗？', '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(() => {
    localStorage.removeItem('admin_token')
    localStorage.removeItem('is_superadmin')
    ElMessage.success('已退出登录')
    router.push('/login')
  })
}
</script>

<style scoped>
.el-header {
  height: 60px;
  line-height: 60px;
  background: #fff;
  border-bottom: 1px solid #eee;
}

.sidebar-aside {
  height: 100%;
  background-color: #304156;
  overflow: hidden;
}
</style>
