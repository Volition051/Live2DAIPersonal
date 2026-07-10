<template>
  <div class="admin-map-container">
    <!-- 顶部工具栏 -->
    <div class="map-toolbar">
      <div class="toolbar-left">
        <el-icon :size="18"><Location /></el-icon>
        <span class="toolbar-title">游客位置监控</span>
        <el-tag type="success" size="small" effect="dark">在线: {{ onlineCount }}</el-tag>
      </div>
      <div class="toolbar-center">
        <span class="legend-item"><i class="legend-dot" style="background:#07c160"></i>真实·景区内</span>
        <span class="legend-item"><i class="legend-dot" style="background:#1989fa"></i>真实·景区外</span>
        <span class="legend-item"><i class="legend-dot" style="background:#ff6600"></i>模拟位置</span>
        <span class="legend-item"><i class="legend-dot" style="background:#999"></i>离线(>60s)</span>
      </div>
      <div class="toolbar-right">
        <el-tag :type="wsConnected ? 'success' : 'danger'" size="small" effect="dark">
          {{ wsConnected ? '实时连接' : '轮询模式' }}
        </el-tag>
      </div>
    </div>

    <!-- Leaflet 地图 -->
    <div id="admin-map"></div>

    <!-- 底部状态栏 -->
    <div class="status-bar">
      <span><el-icon><User /></el-icon> 真实GPS: <b>{{ realCount }}</b></span>
      <span><el-icon><VideoPlay /></el-icon> 模拟: <b>{{ simCount }}</b></span>
      <span><el-icon><MapLocation /></el-icon> 景区内: <b>{{ inScenicCount }}</b></span>
      <span><el-icon><Warning /></el-icon> 景区外: <b>{{ outScenicCount }}</b></span>
      <span><el-icon><Clock /></el-icon> {{ lastUpdateTime }}</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import axios from 'axios'
import { Location, User, VideoPlay, MapLocation, Warning, Clock } from '@element-plus/icons-vue'

// ====== 图标修复 ======
import iconUrl from '/marker-icon.png'
import iconRetinaUrl from '/marker-icon-2x.png'
import shadowUrl from '/marker-shadow.png'

delete L.Icon.Default.prototype._getIconUrl
L.Icon.Default.mergeOptions({ iconUrl, iconRetinaUrl, shadowUrl })

const defaultIcon = L.icon({
  iconUrl, iconRetinaUrl, shadowUrl,
  iconSize: [25, 41], iconAnchor: [12, 41], popupAnchor: [1, -34]
})

// ====== 状态 ======
const map = ref(null)
const wsConnected = ref(false)
const onlineCount = ref(0)
const realCount = ref(0)
const simCount = ref(0)
const inScenicCount = ref(0)
const outScenicCount = ref(0)
const lastUpdateTime = ref('--')

let roadLayer = null
let poiLayer = null
const touristMarkers = {}  // tourist_id -> { marker, data, updatedAt }
let ws = null
let pollInterval = null
const STALE_THRESHOLD_MS = 60000  // 60秒未更新视为离线

// ====== API 基础请求 ======
function apiGet(url, params = {}) {
  const token = localStorage.getItem('admin_token')
  return axios.get(url, {
    params,
    headers: { 'Authorization': `Bearer ${token}` }
  }).then(r => r.data)
}

// ====== 创建游客图标 ======
function createTouristIcon(positionType, inScenic, isStale) {
  let bgColor, statusColor
  if (isStale) {
    bgColor = '#999'
    statusColor = '#666'
  } else if (positionType === 'simulated') {
    bgColor = '#ff9800'
    statusColor = '#ff6600'
  } else if (inScenic) {
    bgColor = '#4caf50'
    statusColor = '#07c160'
  } else {
    bgColor = '#2196f3'
    statusColor = '#1989fa'
  }

  const html = `
    <div style="position: relative; text-align: center;">
      <div style="width: 28px; height: 28px; border-radius: 50%;
           background: ${bgColor}; border: 3px solid white;
           box-shadow: 0 2px 6px rgba(0,0,0,0.4);
           display: flex; align-items: center; justify-content: center;
           font-size: 14px; color: white; font-weight: bold;">🧑</div>
      <div style="width: 8px; height: 8px; border-radius: 50%;
           background: ${statusColor}; border: 2px solid white;
           position: absolute; bottom: 0; right: -2px;
           box-shadow: 0 1px 3px rgba(0,0,0,0.3);"></div>
    </div>`

  return L.divIcon({
    className: 'tourist-marker',
    html,
    iconSize: [32, 40],
    iconAnchor: [16, 40],
    popupAnchor: [0, -40]
  })
}

// ====== 更新统计 ======
function updateStats() {
  const now = Date.now()
  let real = 0, sim = 0, inSc = 0, outSc = 0, online = 0

  Object.values(touristMarkers).forEach(tm => {
    const isStale = (now - tm.updatedAt) > STALE_THRESHOLD_MS
    if (tm.data.positionType === 'real_gps') real++
    else if (tm.data.positionType === 'simulated') sim++
    if (tm.data.inScenic) inSc++
    else outSc++
    if (!isStale) online++
  })

  realCount.value = real
  simCount.value = sim
  inScenicCount.value = inSc
  outScenicCount.value = outSc
  onlineCount.value = online
  lastUpdateTime.value = new Date().toLocaleTimeString()
}

// ====== 更新/添加游客标记 ======
function upsertTouristMarker(touristData, isInitial = false) {
  const { tourist_id, display_id, username, lat, lng, position_type, in_scenic } = touristData
  const id = tourist_id
  const markerId = `tourist-${id}`
  const now = Date.now()

  // 检查是否过期
  const isStale = touristMarkers[markerId]
    ? (now - touristMarkers[markerId].updatedAt) > STALE_THRESHOLD_MS
    : false

  const popupContent = `
    <div style="min-width: 140px;">
      <b>${display_id || 'ID:' + id}</b> — ${username}<br/>
      <span style="font-size: 12px; color: #666;">
        坐标: ${lat.toFixed(6)}, ${lng.toFixed(6)}<br/>
        类型: ${position_type === 'simulated' ? '📍 模拟' : '📡 真实GPS'}<br/>
        状态: ${in_scenic ? '✅ 景区内' : '🌐 景区外'}
      </span>
    </div>`

  if (touristMarkers[markerId]) {
    // 更新已有标记
    const tm = touristMarkers[markerId]
    tm.marker.setLatLng([lat, lng])
    tm.marker.setIcon(createTouristIcon(position_type, in_scenic, isStale))
    tm.marker.setPopupContent(popupContent)
    tm.data = { positionType: position_type, inScenic: in_scenic }
    tm.updatedAt = now
  } else {
    // 创建新标记
    const icon = createTouristIcon(position_type, in_scenic, false)
    const marker = L.marker([lat, lng], { icon, zIndexOffset: 500 }).addTo(map.value)
    marker.bindPopup(popupContent)
    marker.on('click', () => {
      if (map.value) map.value.setView([lat, lng], map.value.getZoom())
    })

    touristMarkers[markerId] = {
      marker,
      data: { positionType: position_type, inScenic: in_scenic },
      updatedAt: now
    }
  }

  updateStats()
}

// ====== 清除过期标记 ======
function cleanupStaleMarkers() {
  const now = Date.now()
  Object.entries(touristMarkers).forEach(([id, tm]) => {
    if ((now - tm.updatedAt) > STALE_THRESHOLD_MS) {
      // 变灰
      tm.marker.setIcon(
        createTouristIcon(tm.data.positionType, tm.data.inScenic, true)
      )
    }
  })
  updateStats()
}

// ====== 加载所有位置 ======
async function loadAllPositions() {
  try {
    const data = await apiGet('/admin/map/positions')
    if (!map.value || !map.value.getContainer()) return
    data.positions.forEach(pos => {
      upsertTouristMarker({
        tourist_id: pos.tourist_id,
        display_id: pos.display_id,
        username: pos.username,
        lat: pos.lat,
        lng: pos.lng,
        position_type: pos.position_type,
        in_scenic: pos.in_scenic
      }, true)
    })
  } catch (e) {
    console.warn('加载游客位置失败:', e.message)
  }
}

// ====== WebSocket 连接 ======
function connectPositionWebSocket() {
  ws = new WebSocket('ws://localhost:8000/map/ws/positions')

  ws.onopen = () => {
    wsConnected.value = true
    console.log('📡 位置 WebSocket 已连接')
  }

  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data)
      if (msg.type === 'position_update') {
        upsertTouristMarker({
          tourist_id: msg.tourist_id,
          display_id: msg.display_id,
          username: msg.username,
          lat: msg.lat,
          lng: msg.lng,
          position_type: msg.position_type,
          in_scenic: msg.in_scenic
        })
      }
    } catch (e) {
      console.warn('WS 消息解析失败:', e)
    }
  }

  ws.onerror = () => {
    console.warn('位置 WebSocket 错误，切换到轮询模式')
    wsConnected.value = false
  }

  ws.onclose = () => {
    wsConnected.value = false
    console.log('位置 WebSocket 断开，5秒后重连...')
    setTimeout(connectPositionWebSocket, 5000)
  }
}

// ====== 生命周期 ======
onMounted(async () => {
  await nextTick()

  // 初始化地图
  map.value = L.map('admin-map', { zoomControl: true }).setView([31.422, 120.088], 14)
  window.adminMap = map.value // 调试用

  L.tileLayer('/tiles/{z}/{x}/{y}.png', {
    attribution: '本地离线瓦片', maxZoom: 18, maxNativeZoom: 16
  }).addTo(map.value)

  // 加载路网
  roadLayer = L.geoJSON(null, {
    style: () => ({ color: '#3388ff', weight: 2, opacity: 0.5 })
  }).addTo(map.value)
  try {
    const res = await axios.get('/map/road_network')
    roadLayer.addData(res.data)
  } catch (e) { console.error('路网加载失败', e) }

  // 加载景点
  try {
    const res = await axios.get('/map/pois')
    L.geoJSON(res.data, {
      pointToLayer: (feature, latlng) => {
        const marker = L.marker(latlng, { icon: defaultIcon })
        marker.bindPopup(feature.properties.name)
        return marker
      }
    }).addTo(map.value)
  } catch (e) { console.error('景点加载失败', e) }

  // 加载游客位置
  await loadAllPositions()

  // 连接 WebSocket
  connectPositionWebSocket()

  // 轮询兜底 + 过期清理
  pollInterval = setInterval(async () => {
    if (!wsConnected.value) {
      await loadAllPositions()
    }
    cleanupStaleMarkers()
  }, 5000)
})

onBeforeUnmount(() => {
  if (ws) {
    ws.onclose = null  // 避免重连
    ws.close()
  }
  if (pollInterval) clearInterval(pollInterval)
  if (map.value) map.value.remove()
})
</script>

<style scoped>
.admin-map-container {
  width: 100%;
  height: calc(100vh - 60px);
  position: relative;
  overflow: hidden;
}

#admin-map {
  width: 100%;
  height: 100%;
}

/* 顶部工具栏 */
.map-toolbar {
  position: absolute;
  top: 10px;
  left: 10px;
  right: 10px;
  z-index: 1000;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  border-radius: 10px;
  padding: 8px 16px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.15);
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.toolbar-title {
  font-size: 16px;
  font-weight: bold;
  color: #303133;
}

.toolbar-center {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #606266;
  white-space: nowrap;
}

.legend-dot {
  display: inline-block;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  border: 2px solid white;
  box-shadow: 0 0 4px rgba(0, 0, 0, 0.3);
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* 底部状态栏 */
.status-bar {
  position: absolute;
  bottom: 10px;
  left: 10px;
  right: 10px;
  z-index: 1000;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  border-radius: 10px;
  padding: 6px 16px;
  box-shadow: 0 -2px 12px rgba(0, 0, 0, 0.15);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 24px;
  font-size: 13px;
  color: #606266;
}

.status-bar b {
  color: #303133;
}
</style>
