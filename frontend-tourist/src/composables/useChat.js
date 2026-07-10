import { ref, nextTick, onBeforeUnmount, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import request from '@/utils/request'
import { useAuthStore } from '@/stores/auth'

export function useChat() {
  // ==================== 路由和认证 ====================
  const router = useRouter()
  const auth = useAuthStore()

  // ==================== DOM 引用 ====================
  const chatContentRef = ref(null)
  const live2dRef = ref(null)
  const videoPlayerRef = ref(null)
  const subtitleContainerRef = ref(null)

  // ==================== 核心状态 ====================
  const loading = ref(false)
  const loadingSeconds = ref(0)
  let loadingTimer = null
  const liveThoughts = ref([])     // 实时思考内容
  let thoughtPoller = null         // 轮询定时器
  const agentMode = ref(false)     // Agent 模式开关
  const showLiveThoughts = ref(false)  // 显示实时思考内容（默认隐藏）
  const inputText = ref('')
  const messageList = ref([])
  const audioPlayer = ref(null)
  const activeThoughts = ref([])
  const isMobile = ref(false)
  const showMap = ref(false)
  const mapFullscreen = ref(false)
  let mapClickTimer = null
  const currentAttraction = ref(null)
  const videoEnabled = ref(false)
  const actionEnabled = ref(false)

  const currentVideo = ref(null)
  const showVideoPanel = ref(false)
  const shownVideos = new Set()
  // 桌面端地图折叠面板 — 之前未声明，现补充
  const showDesktopMap = ref(false)

  // ==================== 字幕状态 ====================
  const subtitleEnabled = ref(false)       // 桌面端字幕开关
  const paragraphs = ref([])               // 移动端：按句切分的段落
  const activeParaIdx = ref(-1)            // 移动端：当前段落索引
  let subtitleAnimationFrame = null

  // 桌面端逐字字幕
  const charSubtitles = ref([])            // 原始逐字数据 [{char, start, end}, ...]
  const activeCharIdx = ref(-1)            // 当前朗读到的字符索引
  let charTrackingFrame = null

  // ==================== GPS 状态 ====================
  const GPS_UPLOAD_INTERVAL = 5000
  let gpsTimer = null
  const AUTO_INTRO_COOLDOWN = 60000
  let lastAutoIntroTime = 0
  let lastKnownAttractionId = null

  // ==================== 天气状态 ====================
  const weather = ref(null)
  let lastWeatherFetch = 0

  // ==================== 语音识别状态 ====================
  const isRecording = ref(false)
  const recordingTime = ref(0)
  let recognition = null
  let recordingTimer = null

  // ==================== 工具函数常量 ====================
  const FN_LABELS = {
    search_knowledge_base: '查询知识库',
    get_weather: '查天气',
    get_scenic_boundary: '景区范围',
    create_plan: '创建计划',
    get_current_plan: '查看进度',
    update_step_status: '更新步骤',
    get_my_visits: '查游览记录',
    get_attraction_boundary: '景点边界',
    zoom_to_attraction: '地图定位',
    plan_route_on_map: '规划路线',
    plan_multi_route_on_map: '多景点路线',
    list_attraction_videos: '查视频',
    find_attraction_id: '查景点ID',
    visitor_gender_stats: '性别统计',
    visitor_age_stats: '年龄统计',
    top_attractions: '热门景点',
    monthly_visitors: '月度客流',
    spending_avg: '消费统计',
    satisfaction_stats: '满意度',
    knowledge_doc_list: '文档列表',
    knowledge_stats: '知识库统计',
    system_health: '系统状态',
    list_project_structure: '目录结构',
    read_file_content: '读取文件',
    project_structure: '项目结构',
    update_project_description: '更新描述',
  }

  // 清理 observation 中的 ID 编码和多余格式
  function cleanObsContent(text) {
    if (!text) return ''
    // 去掉 LS-002: 之类的景点ID前缀，只保留名称
    let cleaned = text.replace(/[A-Z]{2}-\d{3}:\s*/g, '')
    // 去掉括号备注如（灵山胜境）
    cleaned = cleaned.replace(/（[^）]*）/g, '')
    cleaned = cleaned.replace(/\([^)]*\)/g, '')
    return cleaned.trim()
  }

  function extractFnName(content) {
    const m = content.match(/调用工具:\s*(\S+)/)
    if (!m) return content
    return FN_LABELS[m[1]] || m[1]
  }

  function truncateText(text, max) {
    if (!text) return ''
    return text.length > max ? text.slice(0, max) + '...' : text
  }

  // JSON 键名 → 中文映射
  const KEY_LABELS = {
    names: '景点', optimize: '自动优化', attraction_id: '景点ID',
    name: '名称', title: '标题', steps: '步骤', route: '路线',
    from_id: '起点', to_id: '终点', plan_id: '计划ID',
    step_id: '步骤ID', status: '状态', message: '结果',
    latitude: '纬度', longitude: '经度', keyword: '关键词',
    query: '搜索', from_attraction: '起点', to_attraction: '终点',
    attraction_name: '景点名', limit: '数量', max_lines: '行数',
    file_path: '文件路径', description: '描述', root_path: '目录',
    max_depth: '深度', plan_id: '计划', step_order: '步骤号',
  }

  // 清理显示内容中的英文 key 和 snake_case 工具名
  function cleanDisplayText(text) {
    if (!text || typeof text !== 'string') return text || ''
    let cleaned = text
    // 去掉 snake_case 工具名
    cleaned = cleaned.replace(/\b[a-z]+_[a-z]+(?:_[a-z]+)*\b/g, '')
    // 合并多余空格
    cleaned = cleaned.replace(/\s{2,}/g, ' ').trim()
    return cleaned
  }

  // 将思考过程中的 JSON 转为可读文本
  function formatThought(type, content) {
    if (!content) return ''
    // 对所有类型先做基础清理
    content = cleanDisplayText(content)

    // 统一解析：content 可能是对象或 JSON 字符串
    let obj = content
    if (typeof content === 'string') {
      try { obj = JSON.parse(content) } catch { return content }
    }

    if (type === 'action_input') {
      if (typeof obj !== 'object') return String(content)
      const parts = []
      for (const [k, v] of Object.entries(obj)) {
        const label = KEY_LABELS[k] || k
        const val = typeof v === 'boolean' ? (v ? '是' : '否') : String(v)
        parts.push(`${label}: ${val}`)
      }
      return parts.join('，')
    }

    if (type === 'observation') {
      if (typeof obj !== 'object') return String(content)
      if (obj.message) {
        return (obj.status === 'error' ? '❌ ' : '') + obj.message
      }
      const parts = []
      for (const [k, v] of Object.entries(obj)) {
        if (typeof v === 'object' || k === 'status') continue
        const label = KEY_LABELS[k] || k
        parts.push(`${label}: ${v}`)
      }
      return parts.length ? parts.join('，') : String(content)
    }

    return String(content)
  }

  // ==================== 视频状态持久化 ====================
  watch(currentVideo, (v) => {
    if (v) localStorage.setItem('last_video', JSON.stringify(v))
    else localStorage.removeItem('last_video')
  })

  // ==================== Live2D 全局引用 ====================
  // 使用 watcher 替代 onMounted + nextTick，确保无论桌面端还是移动端
  // 的 Live2DViewers 实例变化时都能更新 window.__live2d
  watch(live2dRef, (component) => {
    if (component) {
      window.__live2d = {
        nextMotion: component.nextMotion.bind(component),
        startRandomMotion: component.startRandomMotion.bind(component),
        setExpression: component.setExpression.bind(component),
        setRandomExpression: component.setRandomExpression.bind(component),
        switchModel: component.switchModel.bind(component),
        speak: component.speak.bind(component),
      }
    }
  })

  // ==================== Computed ====================
  const videoSrc = computed(() => {
    if (!currentVideo.value) return ''
    const name = currentVideo.value.name
    if (name.startsWith('http')) return name
    return `http://localhost:8000/videos/${name}`
  })

  const latestAssistantMessage = computed(() => {
    for (let i = messageList.value.length - 1; i >= 0; i--) {
      if (messageList.value[i].role === 'assistant') return messageList.value[i]
    }
    return null
  })

  // ==================== 设备检测 ====================
  const checkMobile = () => {
    isMobile.value = window.innerWidth <= 768
  }

  // ==================== 地图按钮处理（桌面端） ====================
  function handleMapBtnClick() {
    mapClickTimer = setTimeout(() => {
      clearTimeout(mapClickTimer)
      mapClickTimer = null
      mapFullscreen.value = !mapFullscreen.value
      showDesktopMap.value = mapFullscreen.value
      nextTick(() => { setTimeout(() => window.map?.invalidateSize(), 400) })
    }, 250)
  }

  // ==================== 视频错误处理 ====================
  function onVideoError(e) {
    console.warn('[Video] 视频加载失败:', currentVideo.value?.name, '| URL:', videoSrc.value)
    const el = e.target
    if (el) {
      el.style.display = 'none'
      const parent = el.parentElement
      if (parent && !parent.querySelector('.video-error-hint')) {
        const hint = document.createElement('div')
        hint.className = 'video-error-hint'
        hint.innerHTML = `<p>⚠️ 视频文件不存在</p><small>请先在管理端上传 ${currentVideo.value?.name}</small>`
        parent.appendChild(hint)
      }
    }
  }

  // ==================== 滚动 ====================
  const scrollToBottom = async () => {
    await nextTick()
    if (chatContentRef.value) {
      chatContentRef.value.scrollTop = chatContentRef.value.scrollHeight
    }
  }

  // ==================== 退出登录 ====================
  const handleLogout = () => {
    auth.logout()
    router.push('/login')
  }

  // ==================== 推荐 ====================
  const handleRecommend = () => {
    if (loading.value) return
    inputText.value = '个性化推荐'
    handleSend()
  }

  // ==================== GPS 位置 ====================
  const getCurrentPosition = () => {
    return new Promise((resolve) => {
      if (!navigator.geolocation) {
        console.warn('浏览器不支持地理定位')
        resolve(null)
        return
      }
      navigator.geolocation.getCurrentPosition(
        (position) => {
          resolve({
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
          })
        },
        (error) => {
          console.warn('获取位置失败：', error.message)
          resolve(null)
        },
        { enableHighAccuracy: true, timeout: 5000, maximumAge: 60000 }
      )
    })
  }

  // ==================== GPS 自动介绍 ====================
  const handleAutoIntro = async (attractionInfo) => {
    if (!videoEnabled.value) {
      console.log('[AutoIntro] 视频/自动介绍已关闭，跳过')
      return
    }
    if (loading.value) {
      console.log('[AutoIntro] 正在处理其他请求，跳过自动介绍')
      return
    }
    // 避免在手动对话的音频播放期间触发自动介绍，导致 loading 错误显示
    if (audioPlayer.value && !audioPlayer.value.ended && !audioPlayer.value.paused) {
      console.log('[AutoIntro] 音频正在播放中，跳过自动介绍')
      return
    }

    console.log('[AutoIntro] 开始获取AI介绍:', attractionInfo.name)

    currentAttraction.value = {
      name: attractionInfo.name,
      highlights: attractionInfo.highlights,
      attraction_id: attractionInfo.attraction_id,
    }

    loading.value = true

    try {
      const introRes = await request.post('/tourist/attraction-auto-intro', {
        attraction_id: attractionInfo.attraction_id,
      })

      if (videoEnabled.value && !shownVideos.has(attractionInfo.attraction_id) && introRes.video) {
        shownVideos.add(attractionInfo.attraction_id)
        currentVideo.value = introRes.video
        showVideoPanel.value = false
      }

      const rawIntro = introRes.introduction
      console.log('[AutoIntro] AI介绍:', rawIntro)

      const actionMatch = rawIntro.match(/\[动作:(\w+)\]/)
      const autoAction = (actionEnabled.value && actionMatch && actionMatch[1] !== 'none')
        ? { behavior: actionMatch[1], intensity: 0.8 }
        : null
      const introText = actionMatch
        ? rawIntro.replace(/\[动作:\w+\]\s*/g, '')
        : rawIntro

      messageList.value.push({
        role: 'assistant',
        content: introText.replace(/\n/g, '<br/>'),
        thoughts: [],
      })
      loading.value = false
      await scrollToBottom()

      // 停止之前的音频
      if (audioPlayer.value) {
        audioPlayer.value.pause()
        audioPlayer.value = null
        if (live2dRef.value) {
          live2dRef.value.controller?.stopSpeaking()
        }
        clearAllSubtitles()
      }

      const ttsResponse = await request.post('/tourist/text-to-speech-with-visemes', {
        text: introText,
      })
      console.log('[AutoIntro] TTS 响应已接收')

      const audioBase64 = ttsResponse.audio
      const visemesData = ttsResponse.visemes || []
      const subtitlesData = ttsResponse.subtitles || []

      const binaryString = window.atob(audioBase64)
      const bytes = new Uint8Array(binaryString.length)
      for (let i = 0; i < binaryString.length; i++) bytes[i] = binaryString.charCodeAt(i)
      const audioBlob = new Blob([bytes], { type: 'audio/mpeg' })
      const audioUrl = URL.createObjectURL(audioBlob)
      const audio = new Audio(audioUrl)
      audioPlayer.value = audio

      // 字幕数据分发：移动端按句 → 桌面端按句 + 逐字高亮
      console.log('[Subtitle] TTS返回字幕数据:', subtitlesData.length, '字 | isMobile:', isMobile.value, '| 开关:', subtitleEnabled.value)
      if (subtitlesData.length) {
        paragraphs.value = buildParagraphs(subtitlesData)
        activeParaIdx.value = -1
        charSubtitles.value = subtitlesData
        activeCharIdx.value = -1
        if (!isMobile.value && !subtitleEnabled.value) {
          console.log('[Subtitle] 开关未开启，数据已缓存但未追踪。请点击 💬 按钮')
        }
      } else {
        console.log('[Subtitle] TTS 未返回字幕数据（subtitles 为空）')
      }

      audio.addEventListener('play', () => {
        console.log('[AutoIntro] 音频开始播放')
        // 字幕追踪必须在 play 事件里启动，否则 RAF 第一帧看到 paused=true 就退出了
        if (isMobile.value && paragraphs.value.length) {
          startParagraphTracking(audio)
        } else if (!isMobile.value && subtitleEnabled.value && paragraphs.value.length) {
          console.log('[Subtitle] 桌面端 play 事件：句子数', paragraphs.value.length, '，逐字数', charSubtitles.value.length)
          startParagraphTracking(audio)
          startCharTracking(audio)
        }
        if (live2dRef.value) {
          live2dRef.value.speakWithAudio(introText, audio, {
            action: autoAction,
            lipsData: visemesData,
          })
        }
      })

      audio.addEventListener('ended', () => {
        console.log('[AutoIntro] 音频播放结束')
        if (live2dRef.value && live2dRef.value.controller) {
          const controller = live2dRef.value.controller
          controller.stopSpeaking()
          setTimeout(() => {
            controller.closeMouthImmediately()
            console.log('[AutoIntro] Live2D 口型已强制闭合')
          }, 0)
        }
        URL.revokeObjectURL(audioUrl)
        audioPlayer.value = null
        if (isMobile.value) {
          clearAllSubtitles()
          activeParaIdx.value = -1
        }
      })

      audio.addEventListener('error', (e) => {
        console.error('[AutoIntro] 音频加载失败:', e)
        URL.revokeObjectURL(audioUrl)
        audioPlayer.value = null
        clearAllSubtitles()
      })

      audio.load()
      audio.play().catch((err) => {
        console.warn('[AutoIntro] 自动播放被阻止，可能需要用户手动触发', err)
      })
    } catch (err) {
      console.error('[AutoIntro] 自动介绍失败:', err)
      loading.value = false
    }
  }

  // ==================== 天气获取 ====================
  const WEATHER_REFRESH_MS = 600000 // 10 分钟刷新一次
  const weatherIcons = {
    '晴': '☀️', '少云': '🌤️', '多云': '⛅', '阴': '☁️',
    '小雨': '🌧️', '中雨': '🌧️', '大雨': '🌧️', '雷雨': '⛈️',
    '雪': '❄️', '雾': '🌫️', '霾': '🌫️',
  }

  const fetchWeather = async (lat, lon) => {
    const now = Date.now()
    if (now - lastWeatherFetch < WEATHER_REFRESH_MS) return
    lastWeatherFetch = now
    try {
      const res = await fetch(`https://wttr.in/${lat},${lon}?format=j1`)
      const data = await res.json()
      const c = data.current_condition[0]
      const desc = c.weatherDesc[0].value
      weather.value = {
        icon: weatherIcons[desc] || '🌡️',
        desc,
        temp: c.temp_C,
        feelsLike: c.FeelsLikeC,
        humidity: c.humidity,
        windSpeed: c.windspeedKmph,
      }
      console.log('[Weather] 天气已更新:', weather.value)
    } catch (e) {
      console.warn('[Weather] 获取失败:', e.message)
    }
  }

  // ==================== GPS 上传 ====================
  const uploadGPSPosition = async () => {
    const location = await getCurrentPosition()
    try {
      const payload = location
        ? { latitude: location.latitude, longitude: location.longitude }
        : { latitude: null, longitude: null }
      const res = await request.post('/tourist/gps', payload)
      console.log('GPS 已上传', location || '(使用后端有效位置)')

      // 天气刷新
      if (location) fetchWeather(location.latitude, location.longitude)

      const matched = res.matched_attraction
      if (matched && matched.is_new && matched.attraction_id) {
        console.log('[AutoIntro] 检测到新景点:', matched.name, matched.attraction_id)

        const now = Date.now()
        if (now - lastAutoIntroTime < AUTO_INTRO_COOLDOWN) {
          console.log('[AutoIntro] 冷却中，跳过自动介绍')
          return
        }
        if (matched.attraction_id === lastKnownAttractionId) {
          console.log('[AutoIntro] 与上次景点相同，跳过')
          return
        }

        lastAutoIntroTime = now
        lastKnownAttractionId = matched.attraction_id
        await handleAutoIntro(matched)
      } else if (!matched) {
        lastKnownAttractionId = null
        currentAttraction.value = null
      }
    } catch (err) {
      console.warn('上传 GPS 失败', err)
    }
  }

  // ==================== 地图切换（移动端） ====================
  const toggleMap = () => {
    showMap.value = !showMap.value
  }

  const handleMapOverlayClick = () => {
    showMap.value = false
  }

  // ==================== Live2D 动作 ====================
  const handleNextMotion = () => {
    if (live2dRef.value?.nextMotion) {
      live2dRef.value.nextMotion()
    } else {
      console.warn('Live2D 组件未挂载或 nextMotion 未暴露')
    }
  }

  // ==================== 字幕 ====================
  const stopSubtitleUpdate = () => {
    if (subtitleAnimationFrame) {
      cancelAnimationFrame(subtitleAnimationFrame)
      subtitleAnimationFrame = null
    }
  }

  // 清理所有字幕状态（移动端 + 桌面端）
  const clearAllSubtitles = () => {
    stopSubtitleUpdate()
    stopCharTracking()
    paragraphs.value = []
    activeParaIdx.value = -1
    charSubtitles.value = []
    activeCharIdx.value = -1
  }

  const buildParagraphs = (subtitles) => {
    if (!subtitles || subtitles.length === 0) return []

    const MAX_CHARS = 10 // 移动端单行字幕建议上限，超出自动切句
    const result = []
    let seg = [] // 当前积累的字符片段: [{char, start, end}, ...]
    let charIdx = 0 // 全局字符索引（用于桌面端逐字映射）

    // 将 seg 前 count 个字符输出为一个段落，剩余保留
    const flush = (count) => {
      if (seg.length === 0) return
      const take = count || seg.length
      const items = seg.slice(0, take)
      result.push({
        text: items.map((i) => i.char).join(''),
        start: items[0].start,
        end: items[items.length - 1].end,
        charStart: charIdx - seg.length,              // 本段第一个字符的全局索引
        charEnd: charIdx - seg.length + take - 1,      // 本段最后一个字符的全局索引
      })
      seg = seg.slice(take)
    }

    for (const item of subtitles) {
      seg.push(item)
      charIdx++
      const ch = item.char

      // ① 句末标点 → 必定切句（自然断句，时长精准）
      if (/[。！？…——]/.test(ch)) {
        flush()
      }
      // ② 句中停顿 + 已接近上限 → 提前在停顿处切句
      else if (/[，；：]/.test(ch) && seg.length >= MAX_CHARS * 0.6) {
        flush()
      }
      // ③ 超过上限且还没遇到标点 → 强制在最佳位置切句
      else if (seg.length > MAX_CHARS) {
        const text = seg.map((i) => i.char).join('')
        // 尽量在前 MAX_CHARS 范围内找最近的逗号或空格
        let cut = text.slice(0, MAX_CHARS).lastIndexOf('，')
        if (cut < 0) cut = text.slice(0, MAX_CHARS).lastIndexOf(' ')
        // 实在没有就硬切在 MAX_CHARS 位置
        if (cut < 0) cut = MAX_CHARS - 1
        flush(cut + 1) // +1 把分隔符归到上一句
      }
    }

    flush() // 收尾
    return result
  }

  const AUDIO_LATENCY_OFFSET = 80 // 补偿浏览器音频管线延迟（ms），让字幕提前于听到的声音

  const startParagraphTracking = (audio) => {
    if (!audio) return

    let lastIdx = 0 // 从上一次位置继续，避免全量扫描

    const update = () => {
      if (!audio || audio.paused || audio.ended) {
        activeParaIdx.value = -1
        subtitleAnimationFrame = null
        return
      }

      // 加偏移补偿浏览器音频管线延迟
      const currentTime = audio.currentTime * 1000 + AUDIO_LATENCY_OFFSET
      const paras = paragraphs.value
      let idx = -1

      // 从上次位置向前扫（因为时间是单向递增的）
      for (let i = lastIdx; i < paras.length; i++) {
        const para = paras[i]
        if (currentTime >= para.start && currentTime < para.end) {
          idx = i
          lastIdx = i
          break
        }
        // 如果当前时间已经超过这段的结束时间，继续往前
        if (currentTime >= para.end) continue
        // 还没到这段的开始时间，不用继续了
        break
      }
      // 兜底：向前没找到，可能时间回溯了，退一步
      if (idx === -1 && lastIdx > 0 && currentTime < paras[lastIdx].start) {
        for (let i = lastIdx - 1; i >= 0; i--) {
          if (currentTime >= paras[i].start && currentTime < paras[i].end) {
            idx = i
            lastIdx = i
            break
          }
        }
      }

      activeParaIdx.value = idx
      subtitleAnimationFrame = requestAnimationFrame(update)
    }

    stopSubtitleUpdate()
    lastIdx = 0
    subtitleAnimationFrame = requestAnimationFrame(update)
  }

  // ==================== 桌面端逐字字幕追踪 ====================
  const stopCharTracking = () => {
    if (charTrackingFrame) {
      cancelAnimationFrame(charTrackingFrame)
      charTrackingFrame = null
    }
  }

  const startCharTracking = (audio) => {
    if (!audio) return
    console.log('[Subtitle] startCharTracking 启动, 数据长度:', charSubtitles.value.length, '| 偏移:', AUDIO_LATENCY_OFFSET, 'ms')

    let lastIdx = 0 // 从上一次位置继续

    const update = () => {
      if (!audio || audio.paused || audio.ended) {
        activeCharIdx.value = -1
        charTrackingFrame = null
        return
      }

      // 加偏移补偿浏览器音频管线延迟，让高亮比实际听到的声音提前
      const currentTime = audio.currentTime * 1000 + AUDIO_LATENCY_OFFSET
      const chars = charSubtitles.value
      const len = chars.length
      let idx = -1

      // 向前扫（时间单向递增）
      for (let i = lastIdx; i < len; i++) {
        if (currentTime >= chars[i].start && currentTime < chars[i].end) {
          idx = i
          lastIdx = i
          break
        }
        if (currentTime >= chars[i].end) continue
        break
      }
      // 兜底回溯
      if (idx === -1 && lastIdx > 0 && currentTime < chars[lastIdx].start) {
        for (let i = lastIdx - 1; i >= 0; i--) {
          if (currentTime >= chars[i].start && currentTime < chars[i].end) {
            idx = i
            lastIdx = i
            break
          }
        }
      }

      activeCharIdx.value = idx
      charTrackingFrame = requestAnimationFrame(update)
    }

    stopCharTracking()
    lastIdx = 0
    charTrackingFrame = requestAnimationFrame(update)
  }

  const toggleSubtitle = () => {
    subtitleEnabled.value = !subtitleEnabled.value
    console.log('[Subtitle] 开关切换:', subtitleEnabled.value, '| 已有数据:', charSubtitles.value.length, '字')
    if (!subtitleEnabled.value) {
      stopCharTracking()
      charSubtitles.value = []
      activeCharIdx.value = -1
    } else if (charSubtitles.value.length && audioPlayer.value && !audioPlayer.value.paused) {
      // 字幕中途开启：数据已存在且音频正在播放，直接开始追踪
      console.log('[Subtitle] 中途开启，重新绑定音频追踪')
      startCharTracking(audioPlayer.value)
    }
  }

  // ==================== 语音识别 ====================
  const initSpeechRecognition = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SpeechRecognition) {
      console.warn('[Voice] 当前浏览器不支持语音识别功能')
      return null
    }
    const rec = new SpeechRecognition()
    // 移动端 continuous: true 兼容性差，部分浏览器会频繁触发 onend
    // 改为 false，每次识别到停顿后自动结束，由 onend 统一处理
    rec.continuous = false
    rec.interimResults = true
    rec.lang = 'zh-CN'
    return rec
  }

  const toggleVoiceInput = () => {
    console.log('[Voice] toggleVoiceInput 触发, 当前 isRecording:', isRecording.value)
    isRecording.value ? stopRecording() : startRecording()
  }

  const startRecording = () => {
    console.log('[Voice] startRecording 开始')
    recognition = initSpeechRecognition()
    if (!recognition) {
      alert('您的浏览器不支持语音识别功能，请使用 Chrome 或 Edge 浏览器')
      return
    }
    isRecording.value = true
    recordingTime.value = 0
    console.log('[Voice] SpeechRecognition 实例已创建, continuous=', recognition.continuous)

    recordingTimer = setInterval(() => {
      recordingTime.value++
      if (recordingTime.value >= 30) stopRecording()
    }, 1000)

    recognition.onresult = (event) => {
      console.log('[Voice] onresult 触发, resultIndex:', event.resultIndex, 'results:', event.results.length)
      let finalTranscript = ''
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript
        if (event.results[i].isFinal) finalTranscript += transcript
        else inputText.value = transcript
      }
      if (finalTranscript) {
        inputText.value = (inputText.value || '') + finalTranscript
        console.log('[Voice] 最终识别文本:', inputText.value)
      }
    }

    recognition.onerror = (event) => {
      console.error('[Voice] 语音识别错误:', event.error, event.message)
      // 'not-allowed' = 麦克风权限被拒, 'no-speech' = 没检测到语音
      if (event.error === 'not-allowed') {
        alert('麦克风权限被拒绝，请在浏览器设置中允许麦克风访问')
      }
      stopRecording()
    }

    recognition.onend = () => {
      console.log('[Voice] onend 触发, isRecording:', isRecording.value)
      if (isRecording.value) {
        // 移动端 continuous=false 时 onend 是正常的，重启识别即可
        try {
          recognition.start()
          console.log('[Voice] 识别已重启')
        } catch (e) {
          console.warn('[Voice] 重启识别失败:', e.message)
          stopRecording()
        }
      }
    }

    try {
      recognition.start()
      console.log('[Voice] 语音识别已启动')
    } catch (e) {
      console.error('[Voice] recognition.start() 失败:', e.message)
      stopRecording()
    }
  }

  const stopRecording = () => {
    console.log('[Voice] stopRecording, 当前输入文本:', inputText.value)
    isRecording.value = false
    if (recordingTimer) { clearInterval(recordingTimer); recordingTimer = null }
    if (recognition) {
      try { recognition.stop() } catch (e) { /* 忽略已在停止状态 */ }
      recognition = null
    }

    if (inputText.value.trim()) {
      setTimeout(() => handleSend(), 300)
    }
  }

  // ==================== 核心：发送消息 ====================
  const handleSend = async () => {
    const question = inputText.value.trim()
    if (!question || loading.value) return

    // 停止之前的音频播放
    if (audioPlayer.value) {
      console.log('[Chat] 停止上一段音频播放')
      audioPlayer.value.pause()
      audioPlayer.value = null

      if (live2dRef.value) {
        live2dRef.value.controller?.stopSpeaking()
      }

      clearAllSubtitles()
    }

    inputText.value = ''
    messageList.value.push({ role: 'user', content: question })
    await scrollToBottom()

    clearAllSubtitles()
    activeParaIdx.value = -1

    loading.value = true
    loadingSeconds.value = 0
    liveThoughts.value = []
    if (loadingTimer) clearInterval(loadingTimer)
    loadingTimer = setInterval(() => { loadingSeconds.value++ }, 1000)
    // 启动实时思考轮询（每 800ms 拉一次）
    const userId = auth.touristId ? `tourist_${auth.touristId}` : 'tourist_default'
    if (thoughtPoller) clearInterval(thoughtPoller)
    thoughtPoller = setInterval(async () => {
      try {
        const res = await request.get(`/tourist/streaming-thoughts/${userId}`)
        if (res.thoughts && res.thoughts.length > 0) {
          liveThoughts.value = res.thoughts
        }
      } catch (e) { /* 忽略轮询错误 */ }
    }, 800)
    try {
      const location = await getCurrentPosition()
      console.log('[Chat] 获取位置:', location)

      let enhancedQuestion = question

      // 动作关闭：前置禁止指令，让 AI 不输出 [动作:xxx]
      if (!actionEnabled.value) {
        enhancedQuestion = `【本次回答中不要输出[动作:xxx]标记】${enhancedQuestion}`
      }

      const chatRes = await request.post('/tourist/text-chat', {
        question: enhancedQuestion,
        mode: agentMode.value ? 'agent' : 'normal',
        ...(location ? { latitude: location.latitude, longitude: location.longitude } : {}),
      })
      console.log('[Chat] 文本回答:', chatRes.answer)

      const rawAnswer = chatRes.answer
      const thoughts = chatRes.thoughts || []

      const actionMatch = rawAnswer.match(/\[动作:(\w+)\]/)
      console.log('[Action] 解析:', actionMatch?.[1], '| 开关:', actionEnabled.value)
      const action = (actionEnabled.value && actionMatch && actionMatch[1] !== 'none')
        ? { behavior: actionMatch[1], intensity: 0.8 }
        : null
      console.log('[Action] 最终:', action)
      const videoMatch = rawAnswer.match(/\[视频:([\w-]+)\]/)
      console.log('[Video] 解析:', videoMatch?.[1], '| 开关:', videoEnabled.value, '| 已播:', [...shownVideos])
      if (videoMatch && videoEnabled.value) {
        if (videoMatch[1] === 'stop') {
          currentVideo.value = null
          showVideoPanel.value = false
        } else if (!shownVideos.has(videoMatch[1])) {
          try {
            const videoRes = await request.post('/tourist/attraction-auto-intro', {
              attraction_id: videoMatch[1],
            })
            console.log('[Video] API返回:', videoRes.video)
            if (videoRes.video) {
              shownVideos.add(videoMatch[1])
              currentVideo.value = videoRes.video
              showVideoPanel.value = false
            }
          } catch (e) { console.error('[Video] 请求失败:', e) }
        } else {
          console.log('[Video] 已播过，跳过:', videoMatch[1])
        }
      }
      const answerText = rawAnswer
        .replace(/\[动作:\w+\]\s*/g, '')
        .replace(/\[视频:[\w-]+\]\s*/g, '')

      messageList.value.push({
        role: 'assistant',
        content: answerText.replace(/\n/g, '<br/>'),
        thoughts: thoughts,
      })
      // 思考面板默认折叠（用户手动展开）
      loading.value = false
      if (loadingTimer) { clearInterval(loadingTimer); loadingTimer = null }
      if (thoughtPoller) { clearInterval(thoughtPoller); thoughtPoller = null }
      await scrollToBottom()

      const ttsResponse = await request.post('/tourist/text-to-speech-with-visemes', {
          text: answerText,
        })
        console.log('[Chat] TTS 响应:', ttsResponse)

        const audioBase64 = ttsResponse.audio
        const visemesData = ttsResponse.visemes || []
        const subtitlesData = ttsResponse.subtitles || []

      const binaryString = window.atob(audioBase64)
      const bytes = new Uint8Array(binaryString.length)
      for (let i = 0; i < binaryString.length; i++) bytes[i] = binaryString.charCodeAt(i)
      const audioBlob = new Blob([bytes], { type: 'audio/mpeg' })
      const audioUrl = URL.createObjectURL(audioBlob)
      const audio = new Audio(audioUrl)
      audioPlayer.value = audio

      // 字幕数据分发：移动端按句 → 桌面端按句 + 逐字高亮
      console.log('[Subtitle] TTS返回字幕数据:', subtitlesData.length, '字 | isMobile:', isMobile.value, '| 开关:', subtitleEnabled.value)
      if (subtitlesData.length) {
        // 移动端和桌面端都用段落切分
        paragraphs.value = buildParagraphs(subtitlesData)
        activeParaIdx.value = -1
        charSubtitles.value = subtitlesData
        activeCharIdx.value = -1
        if (isMobile.value) {
          startParagraphTracking(audio)
        } else if (subtitleEnabled.value) {
          console.log('[Subtitle] 桌面端：句子数', paragraphs.value.length, '，逐字数', charSubtitles.value.length)
          startParagraphTracking(audio)
          startCharTracking(audio)
        } else {
          console.log('[Subtitle] 开关未开启，数据已缓存但未追踪。请点击 💬 按钮')
        }
      } else {
        console.log('[Subtitle] TTS 未返回字幕数据（subtitles 为空）')
      }

      audio.addEventListener('play', () => {
        console.log('[Chat] 音频开始播放')
        // 字幕追踪必须在 play 事件里启动，否则 RAF 第一帧看到 paused=true 就退出了
        if (isMobile.value && paragraphs.value.length) {
          startParagraphTracking(audio)
        } else if (!isMobile.value && subtitleEnabled.value && paragraphs.value.length) {
          console.log('[Subtitle] 桌面端 play 事件：句子数', paragraphs.value.length, '，逐字数', charSubtitles.value.length)
          startParagraphTracking(audio)
          startCharTracking(audio)
        }
        if (live2dRef.value) {
          live2dRef.value.speakWithAudio(answerText, audio, {
            action,
            lipsData: visemesData,
          })
        }
      })

      audio.addEventListener('ended', () => {
        console.log('[Chat] 音频播放结束')

        if (live2dRef.value && live2dRef.value.controller) {
          const controller = live2dRef.value.controller

          controller.stopSpeaking()

          setTimeout(() => {
            controller.closeMouthImmediately()
            console.log('[Chat] Live2D 口型已强制闭合（二次确认）')
          }, 0)

          console.log('[Chat] Live2D 口型已闭合')
        }

        URL.revokeObjectURL(audioUrl)
        audioPlayer.value = null

        if (isMobile.value) {
          clearAllSubtitles()
          activeParaIdx.value = -1
        }
      })

      audio.addEventListener('error', (e) => {
        console.error('[Chat] 音频加载失败:', e)
        URL.revokeObjectURL(audioUrl)
        audioPlayer.value = null
        clearAllSubtitles()
      })

      audio.load()
      audio.play().catch((err) => {
        console.warn('[Chat] 自动播放被阻止，可能需要用户手动触发', err)
      })
    } catch (err) {
      console.error('[Chat] 请求失败:', err)
      messageList.value.push({
        role: 'assistant',
        content: '抱歉，服务暂时不可用，请稍后再试。',
      })
      loading.value = false
      if (loadingTimer) { clearInterval(loadingTimer); loadingTimer = null }
      if (thoughtPoller) { clearInterval(thoughtPoller); thoughtPoller = null }
      await scrollToBottom()
    }
  }

  // ==================== 合并后的生命周期 ====================
  onMounted(() => {
    // 移动端检测
    checkMobile()
    window.addEventListener('resize', checkMobile)

    // GPS 上传
    uploadGPSPosition()
    gpsTimer = setInterval(uploadGPSPosition, GPS_UPLOAD_INTERVAL)

    // 恢复上次播放的视频
    const saved = localStorage.getItem('last_video')
    if (saved) {
      try {
        const v = JSON.parse(saved)
        currentVideo.value = v
        showVideoPanel.value = false
      } catch (e) { /* 忽略损坏数据 */ }
    }

    console.log('[Chat] 组件挂载完成，移动端模式:', isMobile.value)
  })

  onBeforeUnmount(() => {
    window.removeEventListener('resize', checkMobile)
    if (gpsTimer) clearInterval(gpsTimer)
    if (isRecording.value) stopRecording()
    if (audioPlayer.value) {
      audioPlayer.value.pause()
      audioPlayer.value = null
    }
    clearAllSubtitles()
  })

  // ==================== 返回全部上下文 ====================
  return {
    // 认证与路由
    auth,
    // DOM 引用
    chatContentRef,
    live2dRef,
    videoPlayerRef,
    subtitleContainerRef,
    // 核心状态
    loading,
    loadingSeconds,
    liveThoughts,
    agentMode,
    showLiveThoughts,
    inputText,
    messageList,
    audioPlayer,
    activeThoughts,
    isMobile,
    showMap,
    mapFullscreen,
    currentAttraction,
    weather,
    videoEnabled,
    actionEnabled,
    currentVideo,
    showVideoPanel,
    shownVideos,
    showDesktopMap,
    // 字幕状态
    subtitleEnabled,
    paragraphs,
    activeParaIdx,
    charSubtitles,
    activeCharIdx,
    // 语音状态
    isRecording,
    recordingTime,
    // Computed
    videoSrc,
    latestAssistantMessage,
    // 函数
    checkMobile,
    handleMapBtnClick,
    onVideoError,
    scrollToBottom,
    handleLogout,
    handleRecommend,
    getCurrentPosition,
    uploadGPSPosition,
    toggleMap,
    handleMapOverlayClick,
    handleNextMotion,
    stopSubtitleUpdate,
    clearAllSubtitles,
    buildParagraphs,
    startParagraphTracking,
    stopCharTracking,
    startCharTracking,
    toggleSubtitle,
    toggleVoiceInput,
    handleSend,
    handleAutoIntro,
    extractFnName,
    truncateText,
    formatThought,
    cleanObsContent,
    cleanDisplayText,
  }
}
