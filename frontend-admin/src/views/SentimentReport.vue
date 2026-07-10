<template>
  <div class="report-container">
    <!-- 页面标题 + 时间范围选择 -->
    <div class="report-header">
      <h2 style="margin: 0;">游客感受度报告</h2>
      <div style="display:flex;align-items:center;gap:12px;">
        <span style="color:#909399;font-size:13px;">
          报告周期：{{ reportData.period?.start }} ~ {{ reportData.period?.end }}
        </span>
        <el-radio-group v-model="period" @change="fetchReport" size="small">
          <el-radio-button value="7d">近7天</el-radio-button>
          <el-radio-button value="30d">近30天</el-radio-button>
          <el-radio-button value="90d">近90天</el-radio-button>
        </el-radio-group>
        <el-button @click="fetchReport" type="primary" size="small" :loading="loading">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <!-- 概览卡片 -->
    <el-row :gutter="16" style="margin-top: 16px;">
      <el-col :span="4">
        <div class="overview-card bg-blue">
          <div class="overview-value">{{ reportData.totalInteractions }}</div>
          <div class="overview-label">总交互量</div>
        </div>
      </el-col>
      <el-col :span="4">
        <div class="overview-card bg-green">
          <div class="overview-value">{{ sentimentCounts.positive }}</div>
          <div class="overview-label">正面反馈</div>
        </div>
      </el-col>
      <el-col :span="4">
        <div class="overview-card bg-gray">
          <div class="overview-value">{{ sentimentCounts.neutral }}</div>
          <div class="overview-label">中性咨询</div>
        </div>
      </el-col>
      <el-col :span="4">
        <div class="overview-card bg-orange">
          <div class="overview-value">{{ sentimentCounts.negative }}</div>
          <div class="overview-label">负面反馈</div>
        </div>
      </el-col>
      <el-col :span="4">
        <div class="overview-card bg-red">
          <div class="overview-value">{{ sentimentCounts.complaint }}</div>
          <div class="overview-label">投诉建议</div>
        </div>
      </el-col>
      <el-col :span="4">
        <div class="overview-card bg-purple">
          <div class="overview-value">{{ favorableRate }}%</div>
          <div class="overview-label">好评率</div>
        </div>
      </el-col>
    </el-row>

    <!-- 图表区域 -->
    <el-row :gutter="16" style="margin-top: 16px;">
      <!-- 游客关注话题 -->
      <el-col :span="12">
        <el-card class="report-card">
          <template #header>
            <div class="card-header">
              <span>游客关注话题分析</span>
              <el-tooltip content="基于对话关键词匹配统计游客最关注的话题类别" placement="top">
                <el-icon style="cursor:help;color:#909399;"><QuestionFilled /></el-icon>
              </el-tooltip>
            </div>
          </template>
          <v-chart :option="topicOption" autoresize style="height: 380px;" />
        </el-card>
      </el-col>
      <!-- 情感分布 -->
      <el-col :span="12">
        <el-card class="report-card">
          <template #header>
            <span>游客情感分布</span>
          </template>
          <v-chart :option="sentimentPieOption" autoresize style="height: 380px;" />
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-top: 16px;">
      <!-- 每日交互趋势 -->
      <el-col :span="16">
        <el-card class="report-card">
          <template #header>
            <span>每日交互量趋势</span>
          </template>
          <v-chart :option="dailyOption" autoresize style="height: 350px;" />
        </el-card>
      </el-col>
      <!-- 每日情感趋势 -->
      <el-col :span="8">
        <el-card class="report-card">
          <template #header>
            <span>每日情感趋势</span>
          </template>
          <v-chart :option="sentimentTrendOption" autoresize style="height: 350px;" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 热门问题 + 服务建议 -->
    <el-row :gutter="16" style="margin-top: 16px;">
      <el-col :span="12">
        <el-card class="report-card">
          <template #header>
            <span>热门问题 TOP15</span>
          </template>
          <div style="max-height: 420px; overflow-y: auto;">
            <div
              v-for="(item, idx) in reportData.hotQuestions"
              :key="idx"
              class="hot-item"
            >
              <span class="hot-rank" :class="'rank-' + (idx + 1)">{{ idx + 1 }}</span>
              <span class="hot-text">{{ item.question }}</span>
              <el-tag size="small" type="info">{{ item.count }}次</el-tag>
            </div>
            <el-empty v-if="!reportData.hotQuestions?.length" description="暂无数据" />
          </div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card class="report-card">
          <template #header>
            <span>智能服务建议</span>
          </template>
          <div style="max-height: 420px; overflow-y: auto;">
            <div
              v-for="(item, idx) in reportData.serviceSuggestions"
              :key="idx"
              class="suggestion-item"
              :class="'suggestion-' + item.level"
            >
              <div class="suggestion-header">
                <el-tag
                  :type="item.level === 'error' ? 'danger' : item.level === 'warning' ? 'warning' : 'info'"
                  size="small"
                  effect="dark"
                >
                  {{ item.category }}
                </el-tag>
                <el-tag
                  :type="item.level === 'error' ? 'danger' : item.level === 'warning' ? 'warning' : 'info'"
                  size="small"
                >
                  {{ levelLabel(item.level) }}
                </el-tag>
              </div>
              <p class="suggestion-content">{{ item.content }}</p>
            </div>
            <el-empty v-if="!reportData.serviceSuggestions?.length" description="暂无建议" />
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import VChart from 'vue-echarts'
import 'echarts'
import { Refresh, QuestionFilled } from '@element-plus/icons-vue'
import request from '@/utils/request'

const period = ref('30d')
const loading = ref(false)

const reportData = reactive({
  period: null,
  totalInteractions: 0,
  dailyTrend: [],
  attentionTopics: [],
  sentimentDistribution: [],
  sentimentTrend: [],
  hotQuestions: [],
  serviceSuggestions: []
})

// 情感计数
const sentimentCounts = computed(() => {
  const map = { positive: 0, negative: 0, neutral: 0, complaint: 0 }
  reportData.sentimentDistribution.forEach(item => {
    if (item.name.includes('正面')) map.positive = item.value
    else if (item.name.includes('负面')) map.negative = item.value
    else if (item.name.includes('中性')) map.neutral = item.value
    else if (item.name.includes('投诉')) map.complaint = item.value
  })
  return map
})

const favorableRate = computed(() => {
  const total = reportData.totalInteractions || 1
  return ((sentimentCounts.value.positive / total) * 100).toFixed(1)
})

const levelLabel = (level) => {
  const map = { error: '紧急', warning: '注意', info: '建议' }
  return map[level] || level
}

// === 图表配置 ===
const topicOption = computed(() => ({
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
  grid: { left: 100, right: 40, top: 10, bottom: 20 },
  xAxis: {
    type: 'value',
    name: '提及次数',
    nameTextStyle: { color: '#999' }
  },
  yAxis: {
    type: 'category',
    data: reportData.attentionTopics.map(t => t.topic).reverse(),
    axisLabel: { fontSize: 13 }
  },
  series: [{
    type: 'bar',
    data: reportData.attentionTopics.map(t => ({
      value: t.count,
      itemStyle: {
        color: t.percentage > 10 ? '#f56c6c' : t.percentage > 5 ? '#e6a23c' : '#409eff'
      }
    })).reverse(),
    label: {
      show: true,
      position: 'right',
      formatter: (p) => reportData.attentionTopics[reportData.attentionTopics.length - 1 - p.dataIndex]?.percentage + '%'
    },
    barMaxWidth: 30
  }]
}))

const sentimentPieOption = computed(() => ({
  tooltip: {
    trigger: 'item',
    formatter: '{b}: {c} 次 ({d}%)'
  },
  legend: { bottom: 0, textStyle: { fontSize: 12 } },
  series: [{
    type: 'pie',
    radius: ['50%', '75%'],
    center: ['50%', '45%'],
    avoidLabelOverlap: false,
    itemStyle: { borderRadius: 4, borderColor: '#fff', borderWidth: 2 },
    label: { show: true, formatter: '{b}\n{d}%' },
    data: reportData.sentimentDistribution
  }]
}))

const dailyOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  grid: { left: 50, right: 30, top: 10, bottom: 30 },
  xAxis: {
    type: 'category',
    data: reportData.dailyTrend.map(d => d.date),
    axisLabel: { rotate: 30, fontSize: 11 }
  },
  yAxis: { type: 'value', name: '交互量' },
  dataZoom: [
    { type: 'slider', bottom: 0, height: 20, start: 0, end: 100 }
  ],
  series: [{
    type: 'bar',
    data: reportData.dailyTrend.map(d => d.count),
    itemStyle: {
      color: {
        type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
        colorStops: [
          { offset: 0, color: '#409eff' },
          { offset: 1, color: '#a0cfff' }
        ]
      },
      borderRadius: [3, 3, 0, 0]
    }
  }, {
    type: 'line',
    data: reportData.dailyTrend.map(d => d.count),
    smooth: true,
    lineStyle: { color: '#f56c6c', width: 1.5 },
    itemStyle: { color: '#f56c6c' },
    symbol: 'none'
  }]
}))

const sentimentTrendOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  legend: { bottom: 0, textStyle: { fontSize: 10 } },
  grid: { left: 45, right: 15, top: 15, bottom: 40 },
  xAxis: {
    type: 'category',
    data: reportData.sentimentTrend.map(d => d.date),
    axisLabel: { fontSize: 9, rotate: 30 }
  },
  yAxis: { type: 'value' },
  series: [
    {
      name: '正面',
      type: 'bar',
      stack: 'total',
      data: reportData.sentimentTrend.map(d => d.positive),
      itemStyle: { color: '#67C23A' },
      barWidth: '60%'
    },
    {
      name: '中性',
      type: 'bar',
      stack: 'total',
      data: reportData.sentimentTrend.map(d => d.neutral),
      itemStyle: { color: '#909399' }
    },
    {
      name: '负面',
      type: 'bar',
      stack: 'total',
      data: reportData.sentimentTrend.map(d => d.negative),
      itemStyle: { color: '#F56C6C' }
    }
  ]
}))

const fetchReport = async () => {
  loading.value = true
  try {
    const res = await request.get('/admin/reports/sentiment', {
      params: { period: period.value }
    })
    Object.assign(reportData, res)
  } catch (e) {
    console.error('获取感受度报告失败', e)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchReport()
})
</script>

<style scoped>
.report-container {
  padding: 20px;
  background: #f5f7fa;
  min-height: 100vh;
}

.report-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #fff;
  padding: 16px 20px;
  border-radius: 8px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}

/* === 概览卡片 === */
.overview-card {
  text-align: center;
  padding: 20px 12px;
  border-radius: 10px;
  color: #fff;
  min-height: 100px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.overview-value {
  font-size: 28px;
  font-weight: bold;
}

.overview-label {
  font-size: 13px;
  margin-top: 4px;
  opacity: 0.9;
}

.bg-blue   { background: linear-gradient(135deg, #409eff, #337ecc); }
.bg-green  { background: linear-gradient(135deg, #67C23A, #529b2e); }
.bg-gray   { background: linear-gradient(135deg, #909399, #73767a); }
.bg-orange { background: linear-gradient(135deg, #e6a23c, #c78b2e); }
.bg-red    { background: linear-gradient(135deg, #f56c6c, #d94f4f); }
.bg-purple { background: linear-gradient(135deg, #a855f7, #9333ea); }

/* === 图表卡片 === */
.report-card {
  border-radius: 8px;
}

.report-card :deep(.el-card__header) {
  padding: 14px 18px;
  font-weight: 600;
  border-bottom: 1px solid #ebeef5;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* === 热门问题 === */
.hot-item {
  display: flex;
  align-items: center;
  padding: 10px 12px;
  border-bottom: 1px solid #f0f0f0;
  gap: 10px;
}
.hot-item:last-child { border-bottom: none; }
.hot-item:hover { background: #f5f7fa; }

.hot-rank {
  width: 22px;
  height: 22px;
  line-height: 22px;
  text-align: center;
  border-radius: 4px;
  background: #dcdfe6;
  color: #fff;
  font-size: 11px;
  font-weight: bold;
  flex-shrink: 0;
}

.hot-item:nth-child(1) .hot-rank { background: #f56c6c; }
.hot-item:nth-child(2) .hot-rank { background: #e6a23c; }
.hot-item:nth-child(3) .hot-rank { background: #67c23a; }

.hot-text {
  flex: 1;
  font-size: 13px;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* === 服务建议 === */
.suggestion-item {
  padding: 14px 16px;
  margin-bottom: 12px;
  border-radius: 8px;
  border-left: 4px solid #909399;
  background: #fafafa;
}

.suggestion-item:last-child { margin-bottom: 0; }

.suggestion-error   { border-left-color: #f56c6c; background: #fef0f0; }
.suggestion-warning { border-left-color: #e6a23c; background: #fdf6ec; }
.suggestion-info    { border-left-color: #409eff; background: #ecf5ff; }

.suggestion-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.suggestion-content {
  margin: 0;
  font-size: 13px;
  line-height: 1.7;
  color: #606266;
}
</style>
