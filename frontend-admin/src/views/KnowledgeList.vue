<template>
  <div class="page-container">
    <!-- ===== 1. 顶部概览卡片 ===== -->
    <el-row :gutter="20" style="margin-bottom: 20px;">
      <el-col :span="8">
        <el-card shadow="hover">
          <el-statistic title="文档总数" :value="stats.total_docs" />
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover">
          <el-statistic title="向量分片总数" :value="stats.total_chunks" />
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover">
          <div style="text-align: center;">
            <div style="font-size: 14px; color: #999;">最近上传</div>
            <div style="font-size: 24px; font-weight: bold; margin-top: 8px;">{{ latestUpload }}</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- ===== 2. 知识库列表表格 ===== -->
    <el-card>
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span>知识库列表</span>
          <el-button type="primary" @click="$router.push('/upload')">
            <el-icon><Plus /></el-icon>
            上传新资料
          </el-button>
        </div>
      </template>

      <el-table
        :data="knowledgeList"
        v-loading="loading"
        style="width: 100%"
        empty-text="暂无数据，请上传景区资料"
      >
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="filename" label="文件名" />
        <el-table-column prop="file_type" label="文件类型" width="120" />
        <el-table-column prop="created_at" label="上传时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" size="small" @click="openChunks(row)">查看分片</el-button>
            <el-button type="danger" size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- ===== 3. 柱状图：每个文档的分片数 ===== -->
    <el-card style="margin-top: 20px;">
      <template #header>
        <span>知识库向量分片统计</span>
      </template>
      <div ref="chartRef" style="width: 100%; height: 300px;"></div>
    </el-card>

    <!-- ===== 4. 分片查看弹窗 ===== -->
    <el-dialog
      v-model="chunksDialogVisible"
      :title="'文档分片列表 - ' + currentDocFilename"
      width="80%"
      top="5vh"
    >
      <el-table
        :data="chunkItems"
        v-loading="chunksLoading"
        border
        max-height="500"
        empty-text="该文档暂无分片数据"
      >
        <el-table-column prop="chunk_id" label="Chunk ID" width="200" show-overflow-tooltip />
        <el-table-column label="内容" min-width="300">
          <template #default="{ row }">
            <div style="display: flex; align-items: center;">
              <span style="
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
                max-width: 350px;
                display: inline-block;
                margin-right: 8px;
              ">{{ row.content || '(无内容)' }}</span>
              <el-button type="primary" link size="small" @click="showFullContent(row.content)">
                查看全文
              </el-button>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="元数据" width="150">
          <template #default="{ row }">
            {{ safeJsonStringify(row.metadata) }}
          </template>
        </el-table-column>
      </el-table>

      <div style="display: flex; justify-content: center; margin-top: 15px;">
        <el-pagination
          v-model:current-page="chunksPage"
          :page-size="chunksPageSize"
          :total="chunksTotal"
          layout="prev, pager, next"
          @current-change="fetchChunks"
        />
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, nextTick, watch } from 'vue'
import * as echarts from 'echarts'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import request from '@/utils/request'

const loading = ref(false)
const knowledgeList = ref([])

// 格式化日期
const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

// 安全的 JSON 序列化（模板中调用）
const safeJsonStringify = (obj) => {
  try {
    return JSON.stringify(obj)
  } catch {
    return '{}'
  }
}

// 获取知识库列表
const fetchKnowledgeList = async () => {
  loading.value = true
  try {
    const res = await request.get('/admin/knowledge/list')
    knowledgeList.value = res
  } catch (error) {
    console.error('获取列表失败:', error)
  } finally {
    loading.value = false
  }
}

// 删除文档
const handleDelete = (row) => {
  ElMessageBox.confirm(
    `确定要删除 "${row.filename}" 吗？`,
    '提示',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }
  ).then(async () => {
    try {
      await request.delete(`/admin/knowledge/${row.id}`)
      ElMessage.success('删除成功')
      fetchKnowledgeList()
      fetchStats()
    } catch (e) {
      ElMessage.error('删除失败，请重试')
    }
  }).catch(() => {})
}

// ==================== 统计相关 ====================
const stats = reactive({
  total_docs: 0,
  total_chunks: 0,
  docs: []
})
const chartRef = ref(null)
let chartInstance = null

const latestUpload = ref('--')
const updateLatest = () => {
  if (knowledgeList.value.length > 0) {
    const last = knowledgeList.value[0]
    latestUpload.value = formatDate(last.created_at)
  } else {
    latestUpload.value = '--'
  }
}

const fetchStats = async () => {
  try {
    const res = await request.get('/admin/knowledge/stats')
    stats.total_docs = res.docs.length
    stats.total_chunks = res.total_chunks
    stats.docs = res.docs
    nextTick(() => renderChart())
  } catch (e) {
    console.error('获取统计失败:', e)
  }
}

const renderChart = () => {
  if (!chartRef.value) return
  if (!chartInstance) {
    chartInstance = echarts.init(chartRef.value)
  }
  const names = stats.docs.map(d => d.filename.length > 12 ? d.filename.slice(0,12)+'...' : d.filename)
  const data = stats.docs.map(d => d.chunk_count)
  chartInstance.setOption({
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: names, axisLabel: { rotate: 30 } },
    yAxis: { type: 'value', name: '分片数' },
    series: [{ data, type: 'bar', itemStyle: { color: '#409EFF' } }],
    grid: { left: '5%', right: '5%', bottom: '15%' }
  })
}

// ==================== 分片查看相关 ====================
const chunksDialogVisible = ref(false)
const currentDocId = ref(null)
const currentDocFilename = ref('')
const chunkItems = ref([])
const chunksPage = ref(1)
const chunksPageSize = 20
const chunksTotal = ref(0)
const chunksLoading = ref(false)

const openChunks = (row) => {
  currentDocId.value = row.id
  currentDocFilename.value = row.filename
  chunksPage.value = 1
  chunksDialogVisible.value = true
  fetchChunks()
}

const fetchChunks = async () => {
  if (!currentDocId.value) return
  chunksLoading.value = true
  try {
    const res = await request.get(`/admin/knowledge/${currentDocId.value}/chunks`, {
      params: {
        page: chunksPage.value,
        page_size: chunksPageSize
      }
    })
    // 调试：浏览器控制台可查看响应结构
    console.log('分片响应:', res)
    chunkItems.value = res?.items || []
    chunksTotal.value = res?.total || 0
  } catch (e) {
    ElMessage.error('获取分片失败')
    console.error('分片请求异常:', e)
  } finally {
    chunksLoading.value = false
  }
}

const showFullContent = (content) => {
  ElMessageBox.alert(content || '(无内容)', '分片全文', {
    confirmButtonText: '关闭',
    customClass: 'chunk-fulltext-msgbox'
  })
}

watch(knowledgeList, () => {
  updateLatest()
}, { immediate: true })

onMounted(async () => {
  await fetchKnowledgeList()
  fetchStats()
})
</script>

<style scoped>
.page-container {
  padding: 0;
}
</style>

<style>
.chunk-fulltext-msgbox {
  width: 700px;
  max-width: 90vw;
}
</style>