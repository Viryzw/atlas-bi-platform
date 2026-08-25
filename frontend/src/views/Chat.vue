<template>
  <div class="chat-container">
    <el-card class="chat-card">
      <div class="api-config-bar">
        <div>
          <strong>DeepSeek API</strong>
          <span :class="['api-status', apiConfigured ? 'configured' : 'missing']">
            {{ apiConfigured ? '已配置API' : '请配置API' }}
          </span>
        </div>
        <el-select v-model="currentUserId" class="user-select" size="small" @change="handleUserChange">
          <el-option v-for="user in users" :key="user.id" :label="`${user.username}（ID ${user.id}）`" :value="user.id" />
        </el-select>
        <el-input v-model="apiKey" type="password" show-password placeholder="请输入 DeepSeek API Key" autocomplete="new-password" />
        <button :class="['api-config-button', { modify: apiConfigured }]" :disabled="configLoading" @click="saveApiConfiguration">
          {{ configLoading ? '保存中…' : (apiConfigured ? '修改' : '配置') }}
        </button>
      </div>
      <div class="message-area" ref="messageArea">
        <div v-for="(msg, idx) in messages" :key="idx" class="message-item" :class="msg.role">
          <div class="avatar">{{ msg.role === 'user' ? '👤' : '🤖' }}</div>
          <div class="content">
            <div class="answer-text">{{ msg.content }}</div>
            <details v-if="msg.plan" class="analysis-details">
              <summary>查看查询计划与 SQL</summary>
              <div class="plan-grid">
                <span><b>意图</b>{{ msg.plan.intent }}</span>
                <span><b>请求类型</b>{{ msg.plan.request_type }}</span>
                <span><b>分析类型</b>{{ msg.plan.analysis_type }}</span>
                <span><b>结果行数</b>{{ msg.data?.row_count ?? msg.data?.rows?.length ?? 0 }}</span>
                <span v-if="msg.plan.matched_metrics?.length"><b>命中指标</b>{{ msg.plan.matched_metrics.map(metric => metric.name).join('、') }}</span>
                <span v-if="msg.plan.metric_validation"><b>口径校验</b>{{ validationLabel(msg.plan.metric_validation.status) }}</span>
              </div>
              <pre v-if="msg.sql" class="sql-block">{{ msg.sql }}</pre>
            </details>
            <div v-if="msg.data?.columns?.length" class="artifact-heading">
              <strong>查询结果</strong>
              <el-button
                text
                type="primary"
                size="small"
                :loading="exportingTableIndex === idx"
                @click="downloadTable(msg, idx)"
              >导出 XLSX</el-button>
            </div>
            <div v-if="msg.data?.columns?.length" class="result-table-wrap">
              <table class="result-table">
                <thead><tr><th v-for="column in msg.data.columns" :key="column">{{ column }}</th></tr></thead>
                <tbody>
                  <tr v-for="(row, rowIndex) in msg.data.rows.slice(0, 10)" :key="rowIndex">
                    <td v-for="(cell, cellIndex) in row" :key="cellIndex">{{ cell }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div v-if="msg.chartOption" class="artifact-heading">
              <strong>可视化图表</strong>
              <el-button text type="primary" size="small" @click="downloadChart(msg, idx)">下载 PNG</el-button>
            </div>
            <div v-if="msg.chartOption" :ref="el => setChartRef(el, idx)" class="chart-container"></div>
          </div>
        </div>
      </div>
      <div class="input-area">
        <el-input
          v-model="question"
          placeholder="请输入您的问题，例如：七月份的销售额是多少？"
          @keyup.enter="sendQuestion"
        />
        <el-button type="primary" @click="sendQuestion" :loading="loading">发送</el-button>
        <el-button :type="isListening ? 'danger' : 'warning'" @click="toggleVoice">
          {{ isListening ? '停止录音' : '语音' }}
        </el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, nextTick, onBeforeUnmount, onMounted } from 'vue'
import { getLlmConfigStatus, getUsers, queryAgent, saveLlmConfig } from '../api'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { downloadUrl, exportRowsToXlsx, safeFileName } from '../utils/exportArtifacts'

const question = ref('')
const loading = ref(false)
const exportingTableIndex = ref(null)
const isListening = ref(false)
const users = ref([])
const currentUserId = ref(Number(window.localStorage.getItem('atlas-current-user-id')) || 1)
const apiKey = ref('')
const apiConfigured = ref(false)
const configLoading = ref(false)
let voiceRecognition = null
let voiceSendAfterStop = false
const messages = ref([
  { role: 'assistant', content: '您好！直接提出经营问题，我会先生成并执行安全 SQL，再基于真实结果完成分析和图表。' }
])

const chartRefs = {}  // 存储图表DOM引用

const setChartRef = (el, idx) => {
  if (el) {
    chartRefs[idx] = el
  }
}

const scrollToBottom = () => {
  const area = document.querySelector('.message-area')
  if (area) area.scrollTop = area.scrollHeight
}

const validationLabel = (status) => ({
  passed: '已通过',
  reference_only: '参考口径',
  not_matched: '未命中指标'
}[status] || status)

const loadApiConfiguration = async () => {
  try {
    const { data } = await getLlmConfigStatus(currentUserId.value)
    apiConfigured.value = Boolean(data.configured)
  } catch {
    apiConfigured.value = false
  }
}

const loadUsers = async () => {
  try {
    const { data } = await getUsers()
    users.value = data
    if (data.length && !data.some(user => Number(user.id) === Number(currentUserId.value))) {
      currentUserId.value = Number(data[0].id)
      window.localStorage.setItem('atlas-current-user-id', String(currentUserId.value))
    }
  } catch {
    users.value = []
  }
}

const handleUserChange = async () => {
  window.localStorage.setItem('atlas-current-user-id', String(currentUserId.value))
  apiKey.value = ''
  await loadApiConfiguration()
}

const saveApiConfiguration = async () => {
  const value = apiKey.value.trim()
  if (!value) {
    ElMessage.warning('请输入 DeepSeek API Key')
    return
  }
  const wasConfigured = apiConfigured.value
  configLoading.value = true
  try {
    const { data } = await saveLlmConfig(currentUserId.value, value)
    apiConfigured.value = Boolean(data.configured)
    apiKey.value = ''
    ElMessage.success(wasConfigured ? 'API Key 已更新，后端配置已刷新' : 'API Key 已配置，后端配置已刷新')
  } catch (error) {
    const detail = error.response?.data?.detail
    ElMessage.error((typeof detail === 'object' ? detail.message : detail) || 'API 配置保存失败')
  } finally {
    configLoading.value = false
  }
}

const downloadChart = (message, idx) => {
  const chartEl = chartRefs[idx]
  const chart = chartEl && echarts.getInstanceByDom(chartEl)
  if (!chart) {
    ElMessage.warning('图表尚未就绪，请稍后重试')
    return
  }
  const title = message.plan?.chart_title || message.plan?.intent || '智能问数图表'
  const imageUrl = chart.getDataURL({
    type: 'png',
    pixelRatio: 2,
    backgroundColor: '#ffffff'
  })
  downloadUrl(imageUrl, `${safeFileName(title, '智能问数图表')}.png`)
  ElMessage.success('图表 PNG 已开始下载')
}

const downloadTable = async (message, idx) => {
  exportingTableIndex.value = idx
  try {
    const title = message.plan?.intent || message.plan?.chart_title || '智能问数结果'
    const rowCount = await exportRowsToXlsx(message.data, title)
    ElMessage.success(`表格 XLSX 已开始下载，共 ${rowCount} 行`)
  } catch (error) {
    ElMessage.error(`XLSX 导出失败：${error.message}`)
  } finally {
    exportingTableIndex.value = null
  }
}

const sendQuestion = async () => {
  if (isListening.value) {
    stopVoice(true)
    return
  }
  if (!apiConfigured.value) {
    ElMessage.error('请配置API')
    return
  }
  const q = question.value.trim()
  if (!q) return
  question.value = ''
  messages.value.push({ role: 'user', content: q })
  loading.value = true
  try {
    const res = await queryAgent(q, currentUserId.value)
    const data = res.data
    const answer = data.answer || data.message || '分析完成，但没有返回文字结论'
    const chartOption = typeof data.chart_config === 'string' ? JSON.parse(data.chart_config) : data.chart_config
    messages.value.push({
      role: 'assistant',
      content: answer,
      plan: data.plan,
      sql: data.sql,
      data: data.data,
      chartOption
    })
    await nextTick()
    // 渲染图表
    const lastIdx = messages.value.length - 1
    const chartEl = chartRefs[lastIdx]
    if (chartEl && chartOption) {
      const chart = echarts.init(chartEl)
      chart.setOption(chartOption)
    }
    scrollToBottom()
  } catch (e) {
    const detail = e.response?.data?.detail
    const message = typeof detail === 'object' ? detail.message : detail
    const errorText = message || e.message || '请求失败，请检查网络'
    ElMessage.error(errorText)
    messages.value.push({ role: 'assistant', content: `本次分析没有完成：${errorText}` })
  } finally {
    loading.value = false
  }
}

// 语音识别（使用 Web Speech API）
const stopVoice = (sendAfterStop = false, abort = false) => {
  if (!voiceRecognition) return
  voiceSendAfterStop = sendAfterStop
  try {
    if (abort) voiceRecognition.abort()
    else voiceRecognition.stop()
  } catch {
    voiceRecognition = null
    voiceSendAfterStop = false
    isListening.value = false
  }
}

const startVoice = () => {
  if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
    ElMessage.warning('当前浏览器不支持语音识别')
    return
  }
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
  const recognition = new SpeechRecognition()
  const existingText = question.value
  recognition.lang = 'zh-CN'
  recognition.continuous = true
  recognition.interimResults = true
  let finalTranscript = ''
  voiceRecognition = recognition
  voiceSendAfterStop = false
  isListening.value = true
  recognition.onstart = () => ElMessage.info('正在聆听，再次点击“停止录音”即可结束')
  recognition.onresult = (event) => {
    let interimTranscript = ''
    for (let index = event.resultIndex; index < event.results.length; index += 1) {
      const text = event.results[index][0].transcript
      if (event.results[index].isFinal) finalTranscript += text
      else interimTranscript += text
    }
    question.value = `${existingText}${finalTranscript}${interimTranscript}`
  }
  recognition.onerror = (event) => {
    if (event.error !== 'aborted') ElMessage.error(`语音识别失败：${event.error || '请重试'}`)
  }
  recognition.onend = () => {
    const shouldSend = voiceSendAfterStop
    voiceRecognition = null
    voiceSendAfterStop = false
    isListening.value = false
    if (shouldSend && question.value.trim()) sendQuestion()
    else ElMessage.success(question.value.trim() ? '语音输入已停止，可编辑后发送' : '语音输入已停止')
  }
  try {
    recognition.start()
  } catch (error) {
    voiceRecognition = null
    isListening.value = false
    ElMessage.error(`无法启动语音输入：${error.message}`)
  }
}

const toggleVoice = () => {
  if (isListening.value) stopVoice()
  else startVoice()
}

onMounted(async () => {
  await loadUsers()
  await loadApiConfiguration()
  scrollToBottom()
})

onBeforeUnmount(() => stopVoice(false, true))
</script>

<style scoped>
.chat-container {
  height: calc(100vh - 120px);
}
.chat-card {
  height: 100%;
  display: flex;
  flex-direction: column;
}
.message-area {
  flex: 1;
  overflow-y: auto;
  padding: 10px 20px;
  max-height: calc(100vh - 260px);
}
.message-item {
  display: flex;
  margin-bottom: 15px;
}
.message-item .avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: #f0f0f0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  margin-right: 10px;
  flex-shrink: 0;
}
.message-item .content {
  background: #f4f4f5;
  padding: 10px 15px;
  border-radius: 8px;
  max-width: 80%;
  word-wrap: break-word;
}
.api-config-bar {
  display: grid;
  grid-template-columns: auto 180px minmax(220px, 1fr) auto;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-bottom: 1px solid #dcdfe6;
  background: #fff;
}
.api-config-bar > div:first-child {
  display: flex;
  flex-direction: column;
  min-width: 110px;
}
.api-status {
  margin-top: 2px;
  font-size: 12px;
  font-weight: 700;
}
.api-status.missing { color: #c13b4c; }
.api-status.configured { color: #12805c; }
.api-config-button {
  min-height: 32px;
  padding: 0 12px;
  border: 1px solid #dcdfe6;
  border-radius: 6px;
  background: #fff;
  color: #111827;
  cursor: pointer;
  font-weight: 700;
}
.api-config-button.modify { color: #c78a00; }
.api-config-button:disabled { cursor: wait; opacity: .55; }
@media (max-width: 900px) {
  .api-config-bar { grid-template-columns: 1fr 1fr; }
}
.answer-text {
  white-space: pre-wrap;
}
.analysis-details {
  margin-top: 10px;
  border: 1px solid #dcdfe6;
  border-radius: 8px;
  overflow: hidden;
}
.analysis-details summary {
  padding: 8px 10px;
  color: #3157d5;
  cursor: pointer;
  font-weight: 700;
}
.plan-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  padding: 0 10px 10px;
}
.plan-grid span {
  display: flex;
  flex-direction: column;
}
.plan-grid b {
  color: #909399;
  font-size: 12px;
}
.sql-block {
  margin: 0 10px 10px;
  padding: 10px;
  overflow-x: auto;
  border-radius: 6px;
  background: #182234;
  color: #dbe5f6;
  white-space: pre-wrap;
}
.result-table-wrap {
  max-width: 100%;
  margin-top: 10px;
  overflow-x: auto;
}
.artifact-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 10px;
  color: #606266;
  font-size: 13px;
}
.result-table {
  width: 100%;
  border-collapse: collapse;
  background: white;
}
.result-table th,
.result-table td {
  padding: 7px 9px;
  border: 1px solid #ebeef5;
  text-align: left;
  white-space: nowrap;
}
.message-item.user {
  flex-direction: row-reverse;
}
.message-item.user .avatar {
  margin-right: 0;
  margin-left: 10px;
  background: #409EFF;
  color: white;
}
.message-item.user .content {
  background: #ecf5ff;
}
.chart-container {
  width: 100%;
  height: 300px;
  margin-top: 10px;
}
.input-area {
  display: flex;
  gap: 10px;
  padding: 10px 0;
  border-top: 1px solid #dcdfe6;
}
.input-area .el-input {
  flex: 1;
}
</style>
