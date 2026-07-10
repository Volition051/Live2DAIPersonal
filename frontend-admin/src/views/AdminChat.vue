<template>
  <div class="admin-chat-container">
    <div class="chat-window" ref="chatWindow">
      <div v-for="(msg, idx) in messages" :key="idx" class="message-item">
        <div class="role">{{ msg.role === 'user' ? '管理员' : 'AI助手' }}</div>
        <!-- 思考流程（仅 AI 消息且非临时消息且有 thoughts） -->
        <div
          v-if="msg.role === 'assistant' && !msg._pending && msg.thoughts && msg.thoughts.length"
          class="thoughts"
        >
          <el-collapse v-model="activeThoughts">
            <el-collapse-item :title="'💭 思考过程 (' + msg.thoughts.length + ' 步)' + (totalThoughtTime(msg) ? ' · ' + formatDuration(totalThoughtTime(msg)) : '')" :name="'msg-' + idx">
              <div
                v-for="(step, sIdx) in msg.thoughts"
                :key="sIdx"
                class="step"
                :class="'step-' + step.type"
              >
                <span class="step-time" v-if="step.duration_ms != null">{{ formatDuration(step.duration_ms) }}</span>
                <span class="step-icon">{{ stepIcon(step.type) }}</span>
                <span class="step-content">{{ step.content }}</span>
              </div>
            </el-collapse-item>
          </el-collapse>
        </div>
        <div
          class="content"
          :class="{ 'pending-text': msg._pending }"
          v-html="renderedContent(msg.content)"
        ></div>
      </div>
    </div>
    <div class="input-area">
      <el-input
        v-model="question"
        placeholder="输入问题，例如：今日游客性别分布"
        @keyup.enter="send"
        :disabled="loading"
      />
      <el-button type="primary" @click="send" :loading="loading">发送</el-button>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick } from 'vue'
import request from '@/utils/request' // 确保你的 request 是 axios 实例

const messages = ref([
  {
    role: 'assistant',
    content: '👋 你好，我是景区系统管理员助手。<br>我可以帮你：<br>• 查看游客统计（性别/年龄/消费/满意度）<br>• 查询知识库状态与文档列表<br>• 检查系统健康（数据库、向量库）<br>• 浏览项目结构或查看代码文件<br>请直接向我提问',
    thoughts: []
  }
])
const question = ref('')
const loading = ref(false)
const activeThoughts = ref([])
const chatWindow = ref(null)
const pendingMsgIndex = ref(-1)

const scrollToBottom = () => {
  nextTick(() => {
    if (chatWindow.value) chatWindow.value.scrollTop = chatWindow.value.scrollHeight
  })
}

const stepIcon = (type) => {
  const icons = {
    thought: '💡',
    action: '🔧',
    action_input: '📥',
    observation: '👁️',
    final_answer: ''
  }
  return icons[type] || '📌'
}

const renderedContent = (content) => {
  if (!content) return ''
  return content.replace(/\n/g, '<br>')
}

// ---- 思考耗时 ----
function formatDuration(ms) {
  if (ms == null || ms < 0) return ''
  if (ms < 1000) return `${ms}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  const min = Math.floor(ms / 60000)
  const sec = ((ms % 60000) / 1000).toFixed(0)
  return `${min}m${sec}s`
}
function totalThoughtTime(msg) {
  if (!msg.thoughts || !msg.thoughts.length) return 0
  return msg.thoughts[msg.thoughts.length - 1].duration_ms || 0
}

const send = async () => {
  const q = question.value.trim()
  if (!q || loading.value) return
  question.value = ''
  messages.value.push({ role: 'user', content: q })
  loading.value = true

  // 插入临时消息
  const tempMsg = {
    role: 'assistant',
    content: '⏳ 正在思考，请稍候...',
    thoughts: [],
    _pending: true
  }
  messages.value.push(tempMsg)
  const tempIdx = messages.value.length - 1
  pendingMsgIndex.value = tempIdx

  try {
    // ★ 关键修改：设置 60 秒超时（单位毫秒）
    const res = await request.post('/admin/text-chat', { question: q }, { timeout: 600000 })
    const answer = res.answer
    const thoughts = res.thoughts || []

    // 用真实回复替换临时消息
    messages.value.splice(tempIdx, 1, { role: 'assistant', content: answer, thoughts })

    // 自动展开思考面板
    if (thoughts.length > 0) {
      const panelName = `msg-${tempIdx}`
      if (!activeThoughts.value.includes(panelName)) {
        activeThoughts.value.push(panelName)
      }
    }
  } catch (e) {
    // 根据错误类型给出不同提示
    let errorMsg = '请求失败，请稍后重试'
    if (e.code === 'ECONNABORTED' || e.message?.includes('timeout')) {
      errorMsg = '请求超时，请尝试简化问题或稍后再试'
    }
    messages.value.splice(tempIdx, 1, { role: 'assistant', content: errorMsg })
  } finally {
    loading.value = false
    pendingMsgIndex.value = -1
    scrollToBottom()
  }
}
</script>

<style scoped>
/* 样式保持不变 */
.admin-chat-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #f5f7fa;
}
.chat-window {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}
.message-item {
  margin-bottom: 12px;
  background: #fff;
  border-radius: 8px;
  padding: 10px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.05);
}
.role {
  font-weight: bold;
  color: #409eff;
  margin-bottom: 4px;
}
.thoughts {
  margin-bottom: 8px;
  background: #f9fafb;
  border-radius: 6px;
  padding: 6px 10px;
}
.step {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 4px 0;
  border-bottom: 1px solid #f0f0f0;
  font-size: 13px;
  line-height: 1.5;
}
.step:last-child {
  border-bottom: none;
}
.step-icon {
  flex-shrink: 0;
  width: 20px;
  text-align: center;
}
.step-time {
  flex-shrink: 0;
  font-size: 11px;
  color: #999;
  background: #f5f5f5;
  padding: 1px 6px;
  border-radius: 8px;
  white-space: nowrap;
  margin-right: 4px;
}
.step-content {
  white-space: pre-wrap;
  word-break: break-word;
  flex: 1;
}
.step-thought .step-content   { color: #555; }
.step-action .step-content    { color: #1a73e8; }
.step-action_input .step-content { color: #22863a; font-family: monospace; }
.step-observation .step-content { color: #6f42c1; }
.step-final_answer .step-content { color: #d63384; font-weight: 500; }

.input-area {
  display: flex;
  padding: 12px;
  background: #fff;
  border-top: 1px solid #eee;
}
.input-area .el-input {
  margin-right: 8px;
}
.content {
  padding: 8px 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}
.pending-text {
  color: #909399;
  font-style: italic;
  animation: pulse 1.5s infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
</style>