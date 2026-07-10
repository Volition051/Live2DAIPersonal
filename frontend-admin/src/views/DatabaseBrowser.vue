<template>
  <el-container style="height: calc(100vh - 60px);">
    <!-- 左侧表列表 -->
    <el-aside width="220px" style="background: #f5f7fa; padding: 10px; overflow-y: auto;">
      <h3>数据库表</h3>
      <el-menu :default-active="currentTable" @select="handleTableSelect">
        <el-menu-item v-for="t in tables" :key="t" :index="t">
          {{ t }}
        </el-menu-item>
      </el-menu>
    </el-aside>

    <!-- 右侧数据表格 -->
    <el-main>
      <div v-if="!currentTable" style="text-align: center; margin-top: 100px; color: #999;">
        请从左侧选择一张表
      </div>
      <div v-else>
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <h3>{{ currentTable }} 表数据</h3>
          <el-button type="primary" @click="openCreateDialog">新增记录</el-button>
        </div>

        <!-- 搜索栏 -->
        <div style="margin-bottom: 12px; display: flex; align-items: center; gap: 8px;">
          <span>搜索：</span>
          <el-select
            v-model="searchColumn"
            placeholder="搜索列（全部）"
            clearable
            style="width: 180px;"
          >
            <el-option label="所有文本列" value="" />
            <el-option
              v-for="col in searchableColumns"
              :key="col"
              :label="col"
              :value="col"
            />
          </el-select>
          <el-input
            v-model="searchKeyword"
            placeholder="请输入关键词"
            clearable
            style="width: 220px;"
            @keyup.enter="handleSearch"
          />
          <el-button type="primary" @click="handleSearch" :loading="loading">
            查询
          </el-button>
          <el-button @click="resetSearch">重置</el-button>
        </div>

        <!-- 景点类型统计（仅对 tourist_visit 表显示） -->
        <div v-if="currentTable === 'tourist_visit'" style="margin-bottom: 12px;">
          <span style="margin-right: 8px;">景点类型：</span>
          <el-tag
            v-for="type in distinctTypes"
            :key="type"
            :type="selectedType === type ? 'primary' : 'info'"
            style="cursor: pointer; margin-right: 6px;"
            @click="selectedType = selectedType === type ? '' : type"
          >
            {{ type }}
          </el-tag>
          <span v-if="distinctTypes.length === 0" style="color: #999;">暂无数据</span>
        </div>

        <div class="table-wrapper">
          <el-table
            :data="rows"
            border
            stripe
            style="width: 100%"
            :max-height="500"
            v-loading="loading"
          >
            <el-table-column
              v-for="col in columns"
              :key="col"
              :prop="col"
              :label="col"
              :min-width="120"
              show-overflow-tooltip
            />
            <!-- 操作列 -->
            <el-table-column label="操作" width="160" fixed="right">
              <template #default="{ row }">
                <el-button size="small" @click="openEditDialog(row)">编辑</el-button>
                <el-button size="small" type="danger" @click="deleteRow(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <div style="margin-top: 15px; text-align: right;">
          <el-pagination
            v-model:current-page="page"
            :page-size="pageSize"
            :total="total"
            layout="total, prev, pager, next"
            @current-change="loadData"
          />
        </div>
      </div>

      <!-- 新增/编辑对话框 -->
      <el-dialog v-model="dialogVisible" :title="dialogTitle" width="600px">
        <el-form :model="formData" label-width="120px">
          <el-form-item
            v-for="col in columnsDetail"
            :key="col.name"
            :label="col.name"
          >
            <el-input
              v-model="formData[col.name]"
              :disabled="isEdit && col.primary_key"
              :placeholder="col.autoincrement && !isEdit ? '自增（留空自动生成）' : ''"
            />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" @click="submitForm">确定</el-button>
        </template>
      </el-dialog>
    </el-main>
  </el-container>
</template>

<script setup>
import { ref, onMounted, reactive, computed } from 'vue'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'

const tables = ref([])
const currentTable = ref('')
const columns = ref([])
const columnsDetail = ref([])
const primaryKeys = ref([])
const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)

// 搜索状态
const searchKeyword = ref('')
const searchColumn = ref('')

// 对话框状态
const dialogVisible = ref(false)
const dialogTitle = ref('')
const formData = reactive({})
const isEdit = ref(false)
const currentEditRow = ref(null)

// 景点类型统计
const distinctTypes = ref([])
const selectedType = ref('')

// 可供搜索的列（文本类型）
const searchableColumns = computed(() => {
  if (!columnsDetail.value.length) return []
  return columnsDetail.value
    .filter(col => {
      const t = col.type.toLowerCase()
      return t.includes('char') || t.includes('text') || t.includes('varchar')
    })
    .map(col => col.name)
})

// 加载表列表
const loadTables = async () => {
  try {
    const res = await axios.get('/admin/db/tables', {
      headers: { Authorization: `Bearer ${localStorage.getItem('admin_token')}` }
    })
    tables.value = res.data.tables
  } catch (e) {
    console.error(e)
  }
}

// 加载 attraction_type 唯一值（仅对 tourist_visit 表）
const loadDistinctTypes = async () => {
  if (currentTable.value !== 'tourist_visit') return
  try {
    const res = await axios.get(`/admin/db/table/tourist_visit/distinct/attraction_type`, {
      headers: { Authorization: `Bearer ${localStorage.getItem('admin_token')}` }
    })
    distinctTypes.value = res.data.values || []
  } catch (e) {
    console.error(e)
  }
}

// 选择表
const handleTableSelect = (table) => {
  currentTable.value = table
  page.value = 1
  searchKeyword.value = ''
  searchColumn.value = ''
  loadData()
  if (table === 'tourist_visit') {
    loadDistinctTypes()
  } else {
    distinctTypes.value = []
    selectedType.value = ''
  }
}

// 加载分页数据（包含搜索参数）
const loadData = async () => {
  if (!currentTable.value) return
  loading.value = true
  try {
    const params = {
      page: page.value,
      page_size: pageSize.value,
    }
    if (searchKeyword.value) {
      params.search = searchKeyword.value
      if (searchColumn.value) {
        params.search_column = searchColumn.value
      }
    }
    const res = await axios.get(`/admin/db/table/${currentTable.value}/data`, {
      params,
      headers: { Authorization: `Bearer ${localStorage.getItem('admin_token')}` }
    })
    columns.value = res.data.columns
    columnsDetail.value = res.data.columns_detail || []
    primaryKeys.value = res.data.primary_keys || []
    rows.value = res.data.rows
    total.value = res.data.total
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

// 搜索按钮
const handleSearch = () => {
  page.value = 1
  loadData()
}

// 重置搜索
const resetSearch = () => {
  searchKeyword.value = ''
  searchColumn.value = ''
  page.value = 1
  loadData()
}

// 清空表单数据
const clearFormData = () => {
  Object.keys(formData).forEach(key => delete formData[key])
  columnsDetail.value.forEach(col => {
    formData[col.name] = col.autoincrement ? null : ''
  })
}

// 新增记录
const openCreateDialog = () => {
  isEdit.value = false
  dialogTitle.value = `新增记录 - ${currentTable.value}`
  clearFormData()
  dialogVisible.value = true
}

// 编辑记录
const openEditDialog = (row) => {
  isEdit.value = true
  dialogTitle.value = `编辑记录 - ${currentTable.value}`
  currentEditRow.value = row
  clearFormData()
  Object.keys(row).forEach(key => {
    formData[key] = row[key]
  })
  dialogVisible.value = true
}

// 提交表单
const submitForm = async () => {
  const payload = {}
  for (const key in formData) {
    if (formData[key] !== null && formData[key] !== '') {
      payload[key] = formData[key]
    }
  }

  try {
    if (isEdit.value) {
      primaryKeys.value.forEach(pk => {
        if (!(pk in payload)) {
          payload[pk] = currentEditRow.value[pk]
        }
      })
      await axios.put(`/admin/db/table/${currentTable.value}/data`, payload, {
        headers: { Authorization: `Bearer ${localStorage.getItem('admin_token')}` }
      })
      ElMessage.success('更新成功')
    } else {
      await axios.post(`/admin/db/table/${currentTable.value}/data`, payload, {
        headers: { Authorization: `Bearer ${localStorage.getItem('admin_token')}` }
      })
      ElMessage.success('新增成功')
    }
    dialogVisible.value = false
    loadData()
  } catch (e) {
    const detail = e.response?.data?.detail || '操作失败'
    ElMessage.error(detail)
  }
}

// 删除记录
const deleteRow = (row) => {
  ElMessageBox.confirm('确认删除这条记录吗？', '警告', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(async () => {
    const pkPayload = {}
    primaryKeys.value.forEach(pk => {
      pkPayload[pk] = row[pk]
    })
    try {
      await axios.delete(`/admin/db/table/${currentTable.value}/data`, {
        data: pkPayload,
        headers: { Authorization: `Bearer ${localStorage.getItem('admin_token')}` }
      })
      ElMessage.success('删除成功')
      loadData()
    } catch (e) {
      const detail = e.response?.data?.detail || '删除失败'
      ElMessage.error(detail)
    }
  }).catch(() => {})
}

onMounted(() => {
  loadTables()
})
</script>

<style scoped>
.table-wrapper {
  overflow-x: auto;
}
.el-table {
  min-width: 800px;
}
</style>