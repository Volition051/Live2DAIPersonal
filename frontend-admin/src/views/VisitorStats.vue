<template>
  <div class="stats-container">
    <el-row :gutter="20">
      <el-col :span="12">
        <div ref="genderChart" style="height:300px"></div>
      </el-col>
      <el-col :span="12">
        <div ref="ageChart" style="height:300px"></div>
      </el-col>
    </el-row>
    <el-row :gutter="20" style="margin-top:20px">
      <el-col :span="12">
        <div ref="attractionChart" style="height:300px"></div>
      </el-col>
      <el-col :span="12">
        <div ref="monthlyChart" style="height:300px"></div>
      </el-col>
    </el-row>
    <el-row :gutter="20" style="margin-top:20px">
      <el-col :span="12">
        <div ref="spendingChart" style="height:300px"></div>
      </el-col>
      <el-col :span="12">
        <div ref="satisfactionChart" style="height:300px"></div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import * as echarts from 'echarts'
import request from '@/utils/request'

const genderChart = ref(null)
const ageChart = ref(null)
const attractionChart = ref(null)
const monthlyChart = ref(null)
const spendingChart = ref(null)
const satisfactionChart = ref(null)

const initChart = async (endpoint, refEl, chartType, title) => {
  const res = await request.get(`/admin/visitor/stats/${endpoint}`)
  const chart = echarts.init(refEl.value)
  let option = {}
  if (chartType === 'pie') {
    option = {
      title: { text: title, left: 'center' },
      tooltip: { trigger: 'item' },
      series: [{ type: 'pie', radius: '60%', data: res }]
    }
  } else if (chartType === 'bar') {
    const x = res.map(i => i.name || i.month || i.score || Object.keys(i)[0])
    const y = res.map(i => i.value || i.count || Object.values(i)[0])
    option = {
      title: { text: title, left: 'center' },
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: x, axisLabel: { rotate: 45 } },
      yAxis: { type: 'value' },
      series: [{ type: 'bar', data: y }]
    }
  } else if (chartType === 'line') {
    option = {
      title: { text: title, left: 'center' },
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: res.map(i => i.month) },
      yAxis: { type: 'value' },
      series: [{ type: 'line', data: res.map(i => i.count), smooth: true }]
    }
  }
  chart.setOption(option)
}

onMounted(() => {
  initChart('gender', genderChart, 'pie', '性别分布')
  initChart('age', ageChart, 'pie', '年龄分布')
  initChart('attraction-top', attractionChart, 'bar', '热门景点TOP10')
  initChart('monthly', monthlyChart, 'line', '月度客流量')
  initChart('spending', spendingChart, 'bar', '消费构成（人均）')
  initChart('satisfaction', satisfactionChart, 'bar', '满意度分布')
})
</script>

<style scoped>
.stats-container {
  padding: 20px;
}
</style>