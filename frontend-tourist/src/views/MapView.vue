<template>
  <div class="map-container">
    <div id="map"></div>
    <div class="route-info" v-if="routeText">{{ routeText }}</div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import axios from 'axios'
import request from '@/utils/request'

// 图标 - 使用字符串路径，兼容 file:// 协议
const base = import.meta.env.BASE_URL || './'
const iconUrl = base + 'marker-icon.png'
const iconRetinaUrl = base + 'marker-icon-2x.png'
const shadowUrl = base + 'marker-shadow.png'

delete L.Icon.Default.prototype._getIconUrl
L.Icon.Default.mergeOptions({ iconUrl, iconRetinaUrl, shadowUrl })

const defaultIcon = L.icon({
  iconUrl, iconRetinaUrl, shadowUrl,
  iconSize: [25, 41], iconAnchor: [12, 41], popupAnchor: [1, -34]
})

const map = ref(null)
const routeText = ref('')
let routeLayer = null
let selectedId = null          // 仅用于传统“两步选择”的起点ID
const markerMap = {}           // 景点ID -> Marker
let roadLayer = null
let ws = null
let userMarker = null          // 显示用户位置的标记（模拟或真实）
let positionInterval = null
let simulateInterval = null

// 位置数据
let simulatedPosition = null   // { lat, lng } 来自后端模拟
let currentRealLat = null
let currentRealLng = null

// 景区边界
const SCENIC_LON_MIN = 120.070
const SCENIC_LON_MAX = 120.110
const SCENIC_LAT_MIN = 31.412
const SCENIC_LAT_MAX = 31.432

function isInScenic(lat, lng) {
  return lat >= SCENIC_LAT_MIN && lat <= SCENIC_LAT_MAX && lng >= SCENIC_LON_MIN && lng <= SCENIC_LON_MAX
}

// ==================== 工具：获取当前有效位置（模拟优先）====================
function getCurrentPosition() {
  if (simulatedPosition) {
    return { lat: simulatedPosition.lat, lng: simulatedPosition.lng }
  }
  if (currentRealLat != null && currentRealLng != null) {
    return { lat: currentRealLat, lng: currentRealLng }
  }
  return null
}

// ==================== 模拟位置拉取 ====================
async function fetchSimulatedPosition() {
  const token = localStorage.getItem('tourist_token')
  if (!token) {
    simulatedPosition = null
    return
  }
  const touristId = localStorage.getItem('tourist_id') || '3'
  try {
    const res = await fetch(
      `http://localhost:8000/tourist/simulation/position?tourist_id=${touristId}`,
      { headers: { 'Authorization': `Bearer ${token}` } }
    )
    const data = await res.json()
    if (data.position) {
      simulatedPosition = { lat: data.position.lat, lng: data.position.lng }
    } else {
      simulatedPosition = null
    }
  } catch (e) {
    console.warn('获取模拟位置失败', e)
    simulatedPosition = null
  }
}

// ==================== 刷新用户标记（优先模拟位置）====================
function refreshDisplayMarker() {
  // 严格检查地图实例、容器尺寸、内部 panes 是否就绪
  if (!map.value) return
  const container = map.value.getContainer()
  if (!container) return
  // v-show 隐藏时容器尺寸为 0，Leaflet 内部 panes 可能已被销毁
  if (container.offsetWidth === 0 && container.offsetHeight === 0) return
  if (!map.value._panes || !map.value._panes.markerPane) return

  const pos = getCurrentPosition()
  if (!pos) {
    if (userMarker) {
      map.value.removeLayer(userMarker)
      userMarker = null
    }
    return
  }

  const { lat, lng } = pos
  const inScenic = isInScenic(lat, lng)
  let popupText, iconColor

  if (simulatedPosition) {
    popupText = '📍 模拟位置'
    iconColor = '#ff6600' // 橙色
  } else {
    popupText = inScenic ? ' 您已在景区内' : '📍 我的位置（景区外）'
    iconColor = inScenic ? '#07c160' : '#1989fa'
  }

  const html = `<div style="background-color: ${iconColor}; width: 16px; height: 16px; border-radius: 50%; border: 3px solid white; box-shadow: 0 0 8px rgba(0,0,0,0.5);"></div>`
  const icon = L.divIcon({
    className: 'user-marker',
    html,
    iconSize: [16, 16],
    iconAnchor: [8, 8]
  })

  try {
    if (!userMarker) {
      userMarker = L.marker([lat, lng], { icon, zIndexOffset: 1000 }).addTo(map.value)
      userMarker.bindPopup(popupText)
    } else {
      userMarker.setLatLng([lat, lng])
      userMarker.setIcon(icon)
      userMarker.setPopupContent(popupText)
    }
  } catch (error) {
    console.warn('刷新用户标记失败:', error)
    // 清理失败的标记
    if (userMarker) {
      try {
        map.value.removeLayer(userMarker)
      } catch (e) {}
      userMarker = null
    }
  }
}

// ==================== 真实GPS更新 ====================
async function updateUserPosition() {
  if (!map.value) return
  try {
    const pos = await new Promise((resolve, reject) => {
      navigator.geolocation.getCurrentPosition(resolve, reject, {
        enableHighAccuracy: true,
        timeout: 5000,
        maximumAge: 60000
      })
    })
    currentRealLat = pos.coords.latitude
    currentRealLng = pos.coords.longitude
  } catch (e) {
    console.warn('获取真实位置失败', e.message)
  }
  refreshDisplayMarker()
}

// ==================== 原有工具函数 ====================
function safeClosePopup() {
  if (map.value) map.value.closePopup()
}

function safeFitBounds(bounds, options = {}) {
  if (!map.value || !bounds || !bounds.isValid()) return
  safeClosePopup()
  try {
    map.value.fitBounds(bounds, { animate: true, duration: 0.5, ...options })
  } catch (e) {
    console.warn('fitBounds 出错，改用 setView', e)
    const center = bounds.getCenter()
    map.value.setView(center, map.value.getZoom())
  }
}

// ==================== 基于坐标的路径规划（新增） ====================
async function planRouteFromCoords(fromLat, fromLng, toLat, toLng) {
  if (routeLayer) { map.value.removeLayer(routeLayer); routeLayer = null }
  safeClosePopup()
  try {
    const res = await request.get(`/map/route/from_coords`, {
      params: {
        from_lat: fromLat,
        from_lng: fromLng,
        to_lat: toLat,
        to_lng: toLng
      }
    })
    const data = res
    if (data.error) { routeText.value = `无法到达：${data.error}`; return }
    const line = L.polyline(
      data.coordinates.map(c => [c[1], c[0]]),
      { color: 'red', weight: 5, opacity: 0.8 }
    ).addTo(map.value)
    routeLayer = line
    const bounds = line.getBounds()
    if (bounds.isValid()) safeFitBounds(bounds.pad(0.2))
    routeText.value = `路径距离：${data.distance} 米`
  } catch (e) { routeText.value = '路径规划失败' }
}

// ==================== 传统景点间路径规划 ====================
async function planRoute(fromId, toId) {
  if (routeLayer) { map.value.removeLayer(routeLayer); routeLayer = null }
  safeClosePopup()
  try {
    const res = await request.get(`/map/route?from_id=${fromId}&to_id=${toId}`)
    const data = res
    if (data.error) { routeText.value = `无法到达：${data.error}`; return }
    const line = L.polyline(
      data.coordinates.map(c => [c[1], c[0]]),
      { color: 'red', weight: 5, opacity: 0.8 }
    ).addTo(map.value)
    routeLayer = line
    const bounds = line.getBounds()
    if (bounds.isValid()) safeFitBounds(bounds.pad(0.2))
    routeText.value = `路径距离：${data.distance} 米`
  } catch (e) { routeText.value = '路径规划失败' }
}

// ==================== 生命周期 ====================
let resizeObserver = null

onMounted(async () => {
  map.value = L.map('map', { zoomControl: true }).setView([31.422, 120.088], 14)
  window.map = map.value // 调试用

  map.value.setMaxBounds([[31.412, 120.070], [31.432, 120.110]])
  map.value.setMinZoom(13)

  // 监听容器尺寸变化：v-show 切换时自动修复地图尺寸
  const container = map.value.getContainer()
  if (container) {
    resizeObserver = new ResizeObserver(() => {
      map.value?.invalidateSize()
    })
    resizeObserver.observe(container)
  }

  L.tileLayer(import.meta.env.VITE_API_BASE_URL + '/tiles/{z}/{x}/{y}.png', {
    attribution: '本地离线瓦片', maxZoom: 18, maxNativeZoom: 16
  }).addTo(map.value)

  // 道路网络
  roadLayer = L.geoJSON(null, {
    style: () => ({ color: '#3388ff', weight: 2, opacity: 0.5 })
  }).addTo(map.value)
  try {
    const res = await request.get('/map/road_network')
    roadLayer.addData(res)
  } catch (e) { console.error('路网加载失败', e) }

  // 景点标记 & 双击交互（核心修改） ↓
  try {
    const res = await request.get('/map/pois')
    const geojson = res
    L.geoJSON(geojson, {
      pointToLayer: (feature, latlng) => {
        const marker = L.marker(latlng, { icon: defaultIcon })
        const id = feature.properties.id
        markerMap[id] = marker

        // ------ 修改后的双击逻辑 ------
        marker.on('dblclick', async () => {
          // 1. 获取当前用户位置（模拟优先）
          const userPos = getCurrentPosition()

          if (!selectedId) {
            // 没有手动选择的起点
            if (userPos) {
              // 有用户位置 → 直接从此位置导航到双击的景点
              const toLat = latlng.lat
              const toLng = latlng.lng
              routeText.value = '规划中...'
              await planRouteFromCoords(userPos.lat, userPos.lng, toLat, toLng)
            } else {
              // 无用户位置 → 进入传统两步选择模式
              selectedId = id
              routeText.value = `起点：${feature.properties.name}，请双击终点`
              // 高亮起点（可选）
              marker.setIcon(L.icon({
                iconUrl: base + 'marker-icon-start.png',  // 可替换为起点专用图标，如没有则保留原样
                iconSize: [25, 41], iconAnchor: [12, 41], popupAnchor: [1, -34]
              }))
            }
          } else {
            // 已有一个起点 → 传统两步选择的终点
            const toId = id
            const fromId = selectedId
            selectedId = null
            // 重置所有图标
            Object.values(markerMap).forEach(m => m.setIcon(defaultIcon))
            routeText.value = '规划中...'
            await planRoute(fromId, toId)
          }
        })
        // 单击弹出景点名
        marker.bindPopup(feature.properties.name)
        return marker
      }
    }).addTo(map.value)

    // 自动缩放至所有景点
    const allMarkers = Object.values(markerMap)
    if (allMarkers.length) {
      const group = L.featureGroup(allMarkers)
      const bounds = group.getBounds()
      if (bounds.isValid()) safeFitBounds(bounds.pad(0.1))
    }
  } catch (e) { console.error('景点加载失败', e) }

  // WebSocket 连接（保持不变）
  ws = new WebSocket('ws://localhost:8000/map/ws/control')
  ws.onmessage = (event) => {
    try {
      const cmd = JSON.parse(event.data)
      if (cmd.action === 'zoomIn') map.value.zoomIn()
      else if (cmd.action === 'zoomOut') map.value.zoomOut()
      else if (cmd.action === 'setView') map.value.setView([cmd.lat, cmd.lng], cmd.zoom)
      else if (cmd.action === 'fitBounds') {
        map.value.fitBounds([[cmd.southWest[0], cmd.southWest[1]], [cmd.northEast[0], cmd.northEast[1]]])
      } else if (cmd.action === 'drawRoute') {
        if (routeLayer) { map.value.removeLayer(routeLayer); routeLayer = null }
        if (cmd.route && cmd.route.length > 0) {
          const latlngs = cmd.route.map(c => [c[1], c[0]])
          routeLayer = L.polyline(latlngs, { color: 'red', weight: 5, opacity: 0.8 }).addTo(map.value)
          const bounds = routeLayer.getBounds()
          if (bounds.isValid()) safeFitBounds(bounds.pad(0.2))
          routeText.value = `路径距离：${cmd.distance || '?'} 米`
        }
      }
    } catch (e) { console.error('WS 消息处理出错', e) }
  }
  ws.onerror = () => console.error('WebSocket 错误')
  ws.onclose = () => console.log('WebSocket 断开')

  // 启动定位和模拟轮询
  // 使用 nextTick 确保 DOM 完全渲染后再更新标记
  await fetchSimulatedPosition()
  
  // 延迟执行，确保 Leaflet 内部 DOM 操作完成
  setTimeout(() => {
    refreshDisplayMarker()
  }, 100)

  simulateInterval = setInterval(async () => {
    await fetchSimulatedPosition()
    refreshDisplayMarker()
  }, 2000)

  await updateUserPosition()
  positionInterval = setInterval(updateUserPosition, 5000)
})

onBeforeUnmount(() => {
  if (ws) ws.close()
  if (positionInterval) clearInterval(positionInterval)
  if (simulateInterval) clearInterval(simulateInterval)
  if (resizeObserver) resizeObserver.disconnect()
  if (map.value) map.value.remove()
})
</script>

<style scoped>
.map-container {
  width: 100%;
  height: 100%;
  position: relative;
}

#map {
  width: 100%;
  height: 100%;
}

.route-info {
  position: absolute;
  bottom: 20px;
  left: 20px;
  background: white;
  padding: 10px 15px;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.3);
  z-index: 1000;
  font-size: 14px;
}
</style>