<template>
  <div class="dashboard-container" ref="dashboardRef">
    <!-- 全屏控制按钮 -->
    <div class="dashboard-toolbar">
      <h2 style="margin: 0; color: #fff;">灵山胜境 · 数据大屏</h2>
      <div style="display:flex;align-items:center;gap:12px;">
        <span style="color:#ccc;font-size:13px;">{{ currentTime }}</span>
        <el-button
          type="primary"
          :icon="isFullscreen ? 'Close' : 'FullScreen'"
          @click="toggleFullscreen"
          circle
          size="large"
        />
      </div>
    </div>

    <!-- 第一行数据卡片：游客数据 -->
    <div class="stats-cards">
      <div class="stat-card card-blue">
        <div class="stat-value">{{ dashboardData.totalVisitors }}</div>
        <div class="stat-label">累计游客</div>
      </div>
      <div class="stat-card card-green">
        <div class="stat-value">{{ dashboardData.todayVisitors }}</div>
        <div class="stat-label">今日游客</div>
      </div>
      <div class="stat-card card-purple">
        <div class="stat-value">¥{{ dashboardData.avgSpending }}</div>
        <div class="stat-label">人均消费</div>
      </div>
      <div class="stat-card card-orange">
        <div class="stat-value">{{ dashboardData.avgSatisfaction }}</div>
        <div class="stat-label">整体满意度</div>
      </div>
    </div>

    <!-- 第二行数据卡片：服务数据 -->
    <div class="stats-cards" style="margin-top: 16px;">
      <div class="stat-card card-teal">
        <div class="stat-value">{{ dashboardData.todayInteractions }}</div>
        <div class="stat-label">今日服务人次</div>
      </div>
      <div class="stat-card card-indigo">
        <div class="stat-value">{{ dashboardData.weeklyInteractions }}</div>
        <div class="stat-label">本周服务人次</div>
      </div>
      <div class="stat-card card-cyan">
        <div class="stat-value">{{ dashboardData.totalInteractions }}</div>
        <div class="stat-label">累计服务人次</div>
      </div>
      <div class="stat-card card-pink">
        <div class="stat-value">{{ dashboardData.todaySatisfaction }}</div>
        <div class="stat-label">今日满意度</div>
      </div>
    </div>

    <!-- 图表区域 -->
    <el-row :gutter="20" style="margin-top: 20px;">
      <el-col :span="12">
        <el-card class="chart-card">
          <template #header>
            <span class="chart-title">景点热度 TOP10</span>
          </template>
          <v-chart :option="topAttractionsOption" autoresize style="height: 350px;" />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card class="chart-card">
          <template #header>
            <span class="chart-title">游客性别分布</span>
          </template>
          <v-chart :option="genderOption" autoresize style="height: 350px;" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 热门问答 + 满意度趋势 -->
    <el-row :gutter="20" style="margin-top: 20px;">
      <el-col :span="12">
        <el-card class="chart-card">
          <template #header>
            <span class="chart-title">热门问答 TOP10</span>
          </template>
          <div style="max-height:350px;overflow-y:auto;">
            <div
              v-for="(item, idx) in dashboardData.popularQuestions"
              :key="idx"
              class="question-item"
            >
              <span class="question-rank">{{ idx + 1 }}</span>
              <span class="question-text">{{ item.question }}</span>
              <span class="question-count">{{ item.count }}次</span>
            </div>
            <el-empty v-if="!dashboardData.popularQuestions?.length" description="暂无数据" />
          </div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card class="chart-card">
          <template #header>
            <span class="chart-title">满意度趋势（近8周）</span>
          </template>
          <v-chart :option="weeklySatOption" autoresize style="height: 350px;" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 月度客流 + 今日时段分布 -->
    <el-row :gutter="20" style="margin-top: 20px;">
      <el-col :span="14">
        <el-card class="chart-card">
          <template #header>
            <span class="chart-title">月度客流量趋势</span>
          </template>
          <v-chart :option="monthlyOption" autoresize style="height: 350px;" />
        </el-card>
      </el-col>
      <el-col :span="10">
        <el-card class="chart-card">
          <template #header>
            <span class="chart-title">今日服务时段分布</span>
          </template>
          <v-chart :option="hourlyOption" autoresize style="height: 350px;" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onBeforeUnmount, computed } from 'vue'
import VChart from 'vue-echarts'
import 'echarts'
import request from '@/utils/request'

const dashboardRef = ref(null)
const isFullscreen = ref(false)
const currentTime = ref('')

const dashboardData = reactive({
  totalVisitors: 0,
  todayVisitors: 0,
  avgSpending: 0,
  avgSatisfaction: 0,
  todaySatisfaction: 0,
  todayInteractions: 0,
  weeklyInteractions: 0,
  totalInteractions: 0,
  topAttractions: [],
  genderDistribution: [],
  monthlyTrend: [],
  popularQuestions: [],
  weeklySatisfaction: [],
  hourlyDistribution: []
})

let timerInterval = null

// === 图表配置 ===
const topAttractionsOption = computed(() => ({
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
  grid: { left: 100, right: 20, top: 10, bottom: 20 },
  xAxis: { type: 'value' },
  yAxis: {
    type: 'category',
    data: dashboardData.topAttractions.map(a => a.name).reverse(),
    axisLabel: { width: 100, overflow: 'truncate', color: '#fff' }
  },
  series: [{
    type: 'bar',
    data: dashboardData.topAttractions.map(a => a.count).reverse(),
    itemStyle: {
      color: {
        type: 'linear', x: 0, y: 0, x2: 1, y2: 0,
        colorStops: [
          { offset: 0, color: '#36D1DC' },
          { offset: 1, color: '#5B86E5' }
        ]
      },
      borderRadius: [0, 4, 4, 0]
    }
  }]
}))

const genderOption = computed(() => ({
  tooltip: { trigger: 'item' },
  legend: { orient: 'vertical', left: 'left', textStyle: { color: '#fff' } },
  series: [{
    type: 'pie',
    radius: ['45%', '72%'],
    center: ['55%', '50%'],
    data: dashboardData.genderDistribution.map(g => ({ name: g.name, value: g.value })),
    emphasis: { itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0, 0, 0, 0.5)' } },
    label: { color: '#fff', formatter: '{b}: {c} ({d}%)' },
    itemStyle: { borderColor: 'rgba(0,0,0,0.2)', borderWidth: 1 }
  }]
}))

const monthlyOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  grid: { left: 50, right: 30, top: 10, bottom: 30 },
  xAxis: {
    type: 'category',
    data: dashboardData.monthlyTrend.map(m => m.month),
    axisLabel: { color: '#fff', rotate: 30 }
  },
  yAxis: { type: 'value', axisLabel: { color: '#fff' } },
  series: [{
    type: 'line',
    data: dashboardData.monthlyTrend.map(m => m.count),
    smooth: true,
    areaStyle: {
      color: {
        type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
        colorStops: [
          { offset: 0, color: 'rgba(64, 158, 255, 0.4)' },
          { offset: 1, color: 'rgba(64, 158, 255, 0.02)' }
        ]
      }
    },
    itemStyle: { color: '#409eff' },
    lineStyle: { width: 2 }
  }]
}))

const weeklySatOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  grid: { left: 50, right: 30, top: 20, bottom: 30 },
  xAxis: {
    type: 'category',
    data: dashboardData.weeklySatisfaction.map(w => w.week),
    axisLabel: { color: '#fff' }
  },
  yAxis: { type: 'value', min: 0, max: 5, axisLabel: { color: '#fff' } },
  series: [{
    type: 'line',
    data: dashboardData.weeklySatisfaction.map(w => w.avg),
    smooth: true,
    itemStyle: { color: '#67C23A' },
    lineStyle: { width: 3 },
    areaStyle: {
      color: {
        type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
        colorStops: [
          { offset: 0, color: 'rgba(103, 194, 58, 0.3)' },
          { offset: 1, color: 'rgba(103, 194, 58, 0.02)' }
        ]
      }
    },
    markLine: {
      silent: true,
      data: [{ type: 'average', name: '均值', label: { color: '#fff' } }],
      lineStyle: { color: '#E6A23C', type: 'dashed' }
    }
  }]
}))

const hourlyOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  grid: { left: 50, right: 20, top: 10, bottom: 30 },
  xAxis: {
    type: 'category',
    data: dashboardData.hourlyDistribution.map(h => h.hour),
    axisLabel: { color: '#fff' }
  },
  yAxis: { type: 'value', axisLabel: { color: '#fff' } },
  series: [{
    type: 'bar',
    data: dashboardData.hourlyDistribution.map(h => h.count),
    itemStyle: {
      color: {
        type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
        colorStops: [
          { offset: 0, color: '#f093fb' },
          { offset: 1, color: '#f5576c' }
        ]
      },
      borderRadius: [4, 4, 0, 0]
    }
  }]
}))

// === 数据获取 ===
const fetchDashboard = async () => {
  try {
    const res = await request.get('/admin/dashboard')
    Object.assign(dashboardData, res)
  } catch (e) {
    console.error('获取大屏数据失败', e)
  }
}

// === 全屏切换 ===
const toggleFullscreen = async () => {
  const el = dashboardRef.value
  if (!el) return
  if (!isFullscreen.value) {
    await el.requestFullscreen()
  } else {
    if (document.fullscreenElement) {
      await document.exitFullscreen()
    }
  }
}

const onFullscreenChange = () => {
  isFullscreen.value = !!document.fullscreenElement
}

// === 实时时钟 ===
const updateTime = () => {
  const now = new Date()
  currentTime.value = now.toLocaleString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit'
  })
}

onMounted(() => {
  fetchDashboard()
  document.addEventListener('fullscreenchange', onFullscreenChange)
  updateTime()
  timerInterval = setInterval(() => {
    updateTime()
    // 每60秒自动刷新数据
    if (new Date().getSeconds() === 0) {
      fetchDashboard()
    }
  }, 1000)
})

onBeforeUnmount(() => {
  document.removeEventListener('fullscreenchange', onFullscreenChange)
  if (timerInterval) clearInterval(timerInterval)
})
</script>

<style scoped>
.dashboard-container {
  background: linear-gradient(135deg, #0f2027, #203a43, #2c5364);
  min-height: 100vh;
  height: 100vh;
  overflow-y: auto;
  padding: 20px;
  box-sizing: border-box;
  color: #fff;
}

.dashboard-container:not(:fullscreen) {
  height: auto;
  min-height: 100vh;
}

.dashboard-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

/* === 数据卡片 === */
.stats-cards {
  display: flex;
  gap: 20px;
  justify-content: center;
  flex-wrap: wrap;
}

.stat-card {
  flex: 1;
  min-width: 150px;
  text-align: center;
  background: rgba(255, 255, 255, 0.12);
  backdrop-filter: blur(5px);
  border-radius: 12px;
  padding: 20px;
  color: #fff;
  border-top: 3px solid transparent;
  transition: transform 0.2s;
}

.stat-card:hover {
  transform: translateY(-2px);
}

.card-blue  { border-top-color: #409eff; }
.card-green { border-top-color: #67C23A; }
.card-purple { border-top-color: #a855f7; }
.card-orange { border-top-color: #E6A23C; }
.card-teal { border-top-color: #14b8a6; }
.card-indigo { border-top-color: #6366f1; }
.card-cyan { border-top-color: #06b6d4; }
.card-pink { border-top-color: #ec4899; }

.stat-value {
  font-size: 32px;
  font-weight: bold;
}

.stat-label {
  font-size: 13px;
  margin-top: 5px;
  opacity: 0.85;
}

/* === 图表卡片 === */
.chart-card {
  background: rgba(255, 255, 255, 0.08) !important;
  border: 1px solid rgba(255, 255, 255, 0.15) !important;
  color: #fff;
}

:deep(.chart-card .el-card__header) {
  background: rgba(0, 0, 0, 0.2);
  border-bottom: 1px solid rgba(255, 255, 255, 0.2);
  color: #fff;
  padding: 12px 16px;
}

:deep(.chart-card .el-card__body) {
  color: #fff;
}

.chart-title {
  color: #fff;
  font-weight: bold;
  font-size: 15px;
}

/* === 热门问答列表 === */
.question-item {
  display: flex;
  align-items: center;
  padding: 10px 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  transition: background 0.2s;
}
.question-item:hover {
  background: rgba(255, 255, 255, 0.06);
}
.question-item:last-child {
  border-bottom: none;
}

.question-rank {
  width: 24px;
  height: 24px;
  line-height: 24px;
  text-align: center;
  border-radius: 50%;
  background: rgba(64, 158, 255, 0.3);
  color: #fff;
  font-size: 12px;
  font-weight: bold;
  margin-right: 12px;
  flex-shrink: 0;
}
.question-item:nth-child(1) .question-rank { background: #f56c6c; }
.question-item:nth-child(2) .question-rank { background: #e6a23c; }
.question-item:nth-child(3) .question-rank { background: #67c23a; }

.question-text {
  flex: 1;
  color: #ddd;
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.question-count {
  color: #909399;
  font-size: 12px;
  margin-left: 12px;
  flex-shrink: 0;
}
</style>
