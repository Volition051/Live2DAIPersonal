<template>
  <div>
    <h2 style="margin-bottom: 20px;">景点管理 · 经纬度 & 视频</h2>
    <!-- 搜索栏（不变） -->
    <el-form :inline="true" :model="searchForm">
      <el-form-item label="景区名称">
        <el-select v-model="searchForm.scenic_area" placeholder="全部" clearable>
          <el-option label="灵山胜境" value="灵山胜境" />
          <el-option label="拈花湾禅意小镇" value="拈花湾禅意小镇" />
        </el-select>
      </el-form-item>
      <el-form-item label="关键词">
        <el-input v-model="searchForm.search" placeholder="景点名称" clearable />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="fetchData">查询</el-button>
        <el-button @click="resetSearch">重置</el-button>
      </el-form-item>
    </el-form>

    <!-- 表格，增加景点类型列 -->
    <el-table :data="tableData" border stripe v-loading="loading" style="width: 100%">
      <el-table-column prop="scenic_area" label="景区" width="160" />
      <el-table-column prop="attraction_id" label="景点ID" width="100" />
      <el-table-column prop="name" label="景点名称" min-width="160" />
      <el-table-column prop="attraction_type" label="景点类型" width="140" show-overflow-tooltip />
      <el-table-column label="经度范围" width="220">
        <template #default="{ row }">
          <span v-if="row.min_longitude !== null && row.max_longitude !== null">
            {{ row.min_longitude }} ~ {{ row.max_longitude }}
          </span>
          <span v-else style="color: #999;">未设置</span>
        </template>
      </el-table-column>
      <el-table-column label="纬度范围" width="220">
        <template #default="{ row }">
          <span v-if="row.min_latitude !== null && row.max_latitude !== null">
            {{ row.min_latitude }} ~ {{ row.max_latitude }}
          </span>
          <span v-else style="color: #999;">未设置</span>
        </template>
      </el-table-column>
      <el-table-column label="介绍视频" width="200">
        <template #default="{ row }">
          <span v-if="row.video_url" style="color: #67c23a;">✓ {{ row.video_url }}</span>
          <span v-else style="color: #c0c4cc;">未上传</span>
          <span v-if="row.video_duration" style="margin-left:8px;color:#909399;">{{ row.video_duration }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="180" align="center">
        <template #default="{ row }">
          <el-button type="warning" size="small" @click="openEdit(row)">编辑</el-button>
          <el-button type="success" size="small" @click="openVideoUpload(row)">📹 上传视频</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页（不变） -->
    <el-pagination
      v-model:current-page="currentPage"
      :page-size="pageSize"
      :total="total"
      layout="total, prev, pager, next"
      @current-change="handlePageChange"
      style="margin-top: 20px; justify-content: flex-end;"
    />

    <!-- 编辑弹窗 -->
    <el-dialog v-model="editVisible" title="编辑景点信息" width="500px">
      <el-form :model="editForm" label-width="100px">
        <el-form-item label="景点名称">
          <el-input :value="editForm.name" disabled />
        </el-form-item>
        <el-form-item label="景点类型">
          <el-select v-model="editForm.attraction_type" placeholder="请选择类型" clearable allow-create filterable>
            <el-option v-for="t in attractionTypeOptions" :key="t" :label="t" :value="t" />
          </el-select>
        </el-form-item>
        <el-form-item label="视频文件">
          <el-input v-model="editForm.video_url" placeholder="如 LS-001.mp4" clearable />
        </el-form-item>
        <el-form-item label="视频时长">
          <el-input v-model="editForm.video_duration" placeholder="如 3:20" clearable />
        </el-form-item>
        <el-form-item label="最小经度">
          <el-input-number v-model="editForm.min_longitude" :precision="6" :step="0.001" />
        </el-form-item>
        <el-form-item label="最大经度">
          <el-input-number v-model="editForm.max_longitude" :precision="6" :step="0.001" />
        </el-form-item>
        <el-form-item label="最小纬度">
          <el-input-number v-model="editForm.min_latitude" :precision="6" :step="0.001" />
        </el-form-item>
        <el-form-item label="最大纬度">
          <el-input-number v-model="editForm.max_latitude" :precision="6" :step="0.001" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 视频上传弹窗 -->
    <el-dialog v-model="videoVisible" title="上传景点视频" width="450px">
      <el-form label-width="80px">
        <el-form-item label="景点">
          <span>{{ videoForm.name }}</span>
        </el-form-item>
        <el-form-item label="选择文件">
          <input type="file" ref="videoFileInput" accept="video/mp4,video/webm,video/mov" @change="onVideoFileChange" />
        </el-form-item>
        <el-form-item label="时长">
          <el-input v-model="videoForm.duration" placeholder="如 3:20" style="width:150px" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="videoVisible = false">取消</el-button>
        <el-button type="primary" @click="uploadVideo" :loading="videoUploading">上传</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import request from '@/utils/request'

const loading = ref(false)
const tableData = ref([])
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)

const searchForm = reactive({
  scenic_area: '',
  search: ''
})

const editVisible = ref(false)
const editForm = reactive({
  attraction_id: '',
  name: '',
  attraction_type: '',
  video_url: '',
  video_duration: '',
  min_longitude: null,
  max_longitude: null,
  min_latitude: null,
  max_latitude: null
})

// 视频上传
const videoVisible = ref(false)
const videoUploading = ref(false)
const videoFileInput = ref(null)
const videoForm = reactive({
  attraction_id: '',
  name: '',
  duration: '',
  file: null
})

// 景点类型选项（可从后端加载去重值，这里先用您给出的类型列表作为默认选项）
const attractionTypeOptions = ref([
  '博物馆与展馆',
  '动植物园与水族馆',
  '风景名胜与休闲度假',
  '古镇水乡',
  '历史文化',
  '现代地标',
  '主题乐园',
  '自然公园',
  '景区',
  '景点'
])

// 也可以动态从 /admin/db/table/tourist_visit/distinct/attraction_type 加载（可选）
const loadAttractionTypes = async () => {
  try {
    const res = await request.get('/admin/db/table/tourist_visit/distinct/attraction_type')
    if (res.values) {
      attractionTypeOptions.value = res.values
    }
  } catch (e) {
    // 失败则使用默认选项
  }
}

const fetchData = async () => {
  loading.value = true
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize.value,
    }
    if (searchForm.scenic_area) params.scenic_area = searchForm.scenic_area
    if (searchForm.search) params.search = searchForm.search

    const res = await request.get('/admin/attractions', { params })
    tableData.value = res.data
    total.value = res.total
  } catch (error) {
    ElMessage.error('获取景点列表失败')
  } finally {
    loading.value = false
  }
}

const resetSearch = () => {
  searchForm.scenic_area = ''
  searchForm.search = ''
  currentPage.value = 1
  fetchData()
}

const handlePageChange = (page) => {
  currentPage.value = page
  fetchData()
}

const openEdit = (row) => {
  editForm.attraction_id = row.attraction_id
  editForm.name = row.name
  editForm.attraction_type = row.attraction_type || ''
  editForm.video_url = row.video_url || ''
  editForm.video_duration = row.video_duration || ''
  editForm.min_longitude = row.min_longitude
  editForm.max_longitude = row.max_longitude
  editForm.min_latitude = row.min_latitude
  editForm.max_latitude = row.max_latitude
  editVisible.value = true
}

const saveEdit = async () => {
  try {
    await request.put(`/admin/attractions/${editForm.attraction_id}`, {
      attraction_type: editForm.attraction_type || null,
      video_url: editForm.video_url || null,
      video_duration: editForm.video_duration || null,
      min_longitude: editForm.min_longitude,
      max_longitude: editForm.max_longitude,
      min_latitude: editForm.min_latitude,
      max_latitude: editForm.max_latitude
    })
    ElMessage.success('更新成功')
    editVisible.value = false
    fetchData()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '更新失败')
  }
}

const openVideoUpload = (row) => {
  videoForm.attraction_id = row.attraction_id
  videoForm.name = row.name
  videoForm.duration = row.video_duration || ''
  videoForm.file = null
  if (videoFileInput.value) videoFileInput.value.value = ''
  videoVisible.value = true
}

const onVideoFileChange = (e) => {
  videoForm.file = e.target.files[0] || null
}

const uploadVideo = async () => {
  if (!videoForm.file) { ElMessage.warning('请选择视频文件'); return }
  videoUploading.value = true
  try {
    const formData = new FormData()
    formData.append('file', videoForm.file)
    const res = await request.post(
      `/admin/attractions/video/upload?attraction_id=${videoForm.attraction_id}`,
      formData,
      { headers: { 'Content-Type': 'multipart/form-data' } }
    )
    // 同时更新时长
    if (videoForm.duration) {
      await request.put(`/admin/attractions/${videoForm.attraction_id}`, {
        video_duration: videoForm.duration
      })
    }
    ElMessage.success('视频上传成功')
    videoVisible.value = false
    fetchData()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '上传失败')
  } finally {
    videoUploading.value = false
  }
}

onMounted(() => {
  loadAttractionTypes()   // 动态加载类型列表
  fetchData()
})
</script>