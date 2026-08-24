import { createClientId } from './client-id.js'

const viewRoot = document.querySelector('#view-root')
const pageTitle = document.querySelector('#page-title')
const backendStatus = document.querySelector('#backend-status')
const sidebar = document.querySelector('#sidebar')
const sidebarBackdrop = document.querySelector('#sidebar-backdrop')
const modalLayer = document.querySelector('#modal-layer')
const toastLayer = document.querySelector('#toast-layer')
const logoutButton = document.querySelector('#logout-button')
const userAvatar = document.querySelector('.user-avatar')

function storedAuthUser() {
  try {
    return JSON.parse(window.localStorage.getItem('atlas-auth-user') || 'null')
  } catch {
    return null
  }
}

const viewTitles = {
  dashboard: '经营驾驶舱',
  chat: '智能问数',
  history: '问数历史',
  chartdetail: '图表详情',
  reports: '分析报告',
  reporteditor: '报表编辑',
  enterprises: '企业管理',
  departments: '部门管理',
  metrics: '指标知识库',
  datasources: '数据源管理',
  users: '用户管理'
}

const demoDashboard = {
  kpis: [
    { id: 1, name: '销售额', value: 2864300, unit: '¥', delta: 12.6 },
    { id: 2, name: '订单总量', value: 12846, unit: '单', delta: 8.2 },
    { id: 3, name: '活跃客户', value: 2189, unit: '人', delta: 5.4 },
    { id: 4, name: '订单完成率', value: 92.4, unit: '%', delta: -1.3 }
  ],
  primaryMetric: { id: 1, name: '销售额', unit: '¥' },
  dimension: { field: 'region', selected: null },
  totalSales: 2864300,
  orderCount: 12846,
  customerCount: 2189,
  completionRate: 92.4,
  deltas: { totalSales: 12.6, orderCount: 8.2, customerCount: 5.4, completionRate: -1.3 },
  trendData: {
    x: ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月'],
    y: [248, 231, 274, 289, 312, 301, 338, 366].map((value) => value * 10000)
  },
  pieData: [
    { name: '华东区域', value: 36 },
    { name: '华南区域', value: 27 },
    { name: '华北区域', value: 21 },
    { name: '其他区域', value: 16 }
  ],
  insights: {
    status: 'sample',
    message: '',
    items: [
      { title: '样例增长洞察', content: '样例数据中最近两个月销售额保持增长。', recommendation: '恢复后端后请依据真实数据复核增长来源。' },
      { title: '样例结构洞察', content: '样例数据中的经营贡献存在一定集中度。', recommendation: '恢复后端后请按真实厂商结构进一步拆分。' },
      { title: '样例履约洞察', content: '样例完成率需要持续跟踪。', recommendation: '恢复后端后请检查未完成订单。' }
    ]
  }
}

const demoRecords = {
  enterprises: [],
  departments: [],
  metrics: [],
  datasources: [],
  users: [
    { id: 1, username: 'admin', password: '', role: 'admin' },
    { id: 2, username: 'analyst_01', password: '', role: 'analyst' },
    { id: 3, username: 'viewer_01', password: '', role: 'user' }
  ]
}

const managementConfig = {
  enterprises: {
    title: '企业管理',
    description: '维护企业目录；展开企业可查看其下属的全部数据源。',
    buttonLabel: '新增企业',
    endpoint: '/api/admin/enterprises/',
    searchPlaceholder: '搜索企业名称',
    fields: [{ name: 'name', label: '企业名称', type: 'text', required: true, placeholder: '例如：Atlas 集团' }]
  },
  departments: {
    title: '部门管理',
    description: '按企业维护可展开的部门树；点击部门可查看该部门直属员工与任务。',
    buttonLabel: '新增部门',
    endpoint: '/api/admin/departments/',
    searchPlaceholder: '搜索部门名称或所属企业',
    fields: [
      { name: 'name', label: '部门名称', type: 'text', required: true, placeholder: '例如：经营分析部' },
      { name: 'enterprise_id', label: '所属企业', type: 'enterprise-select', required: true },
      { name: 'parent_id', label: '归属层级', type: 'department-parent-select', nullable: true }
    ]
  },
  metrics: {
    title: '指标知识库',
    description: '逻辑指标统一维护，并按数据源配置独立 SQL 口径，\n让 AI 准确理解不同企业的数据结构。',
    buttonLabel: '新建指标',
    endpoint: '/api/admin/metrics/',
    searchPlaceholder: '搜索指标名称、主题或口径',
    fields: [
      { name: 'name', label: '指标名称', type: 'text', required: true, placeholder: '例如：销售额' },
      { name: 'aliases', label: '别名', type: 'text', placeholder: '多个别名用逗号分隔，例如：GMV,成交额' },
      { name: 'topic', label: '主题（业务域）', type: 'topic-select', required: true, default: '未分类' },
      { name: 'unit', label: '单位', type: 'text', placeholder: '例如：¥、%、单' },
      { name: 'description', label: '口径说明', type: 'textarea', full: true, placeholder: '说明统计范围、时间口径和业务含义' },
      { name: 'sql_expr', label: 'SQL 表达式', type: 'textarea', full: true, required: true, placeholder: '例如：SUM(amount)' },
      { name: 'data_source_id', label: '绑定数据源', type: 'data-source-select', required: true },
      { name: 'base_table', label: '事实表', type: 'text', placeholder: '例如：orders' },
      { name: 'time_field', label: '时间字段', type: 'text', placeholder: '例如：created_at' },
      { name: 'dimension_field', label: '默认维度字段', type: 'text', placeholder: '例如：customer_name' },
      { name: 'dashboard_enabled', label: '用于驾驶舱', type: 'boolean', default: true, options: [['true', '是'], ['false', '否']] }
    ]
  },
  datasources: {
    title: '数据源管理',
    description: '上传单数据库 SQL 初始化文件，平台会自动建设业务库、配置只读访问并生成指标。',
    buttonLabel: '上传 SQL 接入',
    endpoint: '/api/admin/data_sources/',
    searchPlaceholder: '搜索名称、类型、主机或数据库',
    fields: [
      { name: 'name', label: '数据源名称', type: 'text', required: true, placeholder: '例如：经营分析数据库' },
      { name: 'enterprise_id', label: '所属企业', type: 'enterprise-select', required: true },
      { name: 'db_type', label: '数据库类型', type: 'select', required: true, default: 'mysql', options: [['mysql', 'MySQL'], ['postgresql', 'PostgreSQL']] },
      { name: 'host', label: '主机地址', type: 'text', required: true, default: 'localhost' },
      { name: 'port', label: '端口', type: 'number', required: true, default: 3306, min: 1, max: 65535 },
      { name: 'database', label: '数据库名', type: 'text', required: true }
    ]
  },
  users: {
    title: '用户管理',
    description: '维护分析平台的用户和角色，当前后端支持管理员、分析师和普通用户。',
    buttonLabel: '新增用户',
    endpoint: '/api/admin/users/',
    searchPlaceholder: '搜索用户名或角色',
    fields: [
      { name: 'username', label: '用户名', type: 'text', required: true, placeholder: '输入登录用户名' },
      { name: 'password', label: '密码', type: 'password', required: true, placeholder: '输入登录密码' },
      { name: 'role', label: '角色', type: 'select', required: true, default: 'analyst', options: [['admin', '管理员'], ['analyst', '分析师'], ['user', '普通用户']] }
    ]
  }
}

function storedUserId() {
  const value = Number(window.localStorage.getItem('atlas-current-user-id'))
  return Number.isInteger(value) && value > 0 ? value : 1
}

function storedDashboardDataSourceId() {
  const value = Number(window.localStorage.getItem('atlas-dashboard-data-source-id'))
  return Number.isInteger(value) && value > 0 ? value : null
}

function storedDashboardPeriod() {
  const value = window.localStorage.getItem('atlas-dashboard-period')
  return ['year', 'six_months', 'quarter', 'all'].includes(value) ? value : 'year'
}

function initialChatMessages() {
  return [{
    id: createClientId(),
    role: 'assistant',
    text: '你好，我是 Atlas 数据分析助手。直接提出经营问题，我会结合业务指标和真实数据完成分析、图表和报告。'
  }]
}

const state = {
  authToken: window.localStorage.getItem('atlas-auth-token') || '',
  currentUser: storedAuthUser(),
  view: 'dashboard',
  backendOnline: false,
  backendChecked: false,
  backendHealthFailures: 0,
  dashboard: structuredClone(demoDashboard),
  dashboardIsDemo: true,
  dashboardError: '',
  dashboardLoading: false,
  dashboardInsightsLoading: false,
  dashboardConfigurationStale: false,
  dashboardRequestId: 0,
  dashboardDataSources: structuredClone(demoRecords.datasources),
  selectedDataSourceId: storedDashboardDataSourceId(),
  dashboardPeriod: storedDashboardPeriod(),
  dashboardDimensionValue: null,
  records: {
    enterprises: structuredClone(demoRecords.enterprises),
    departments: structuredClone(demoRecords.departments),
    metrics: structuredClone(demoRecords.metrics),
    datasources: structuredClone(demoRecords.datasources),
    users: structuredClone(demoRecords.users)
  },
  recordsFromApi: { enterprises: false, departments: false, metrics: false, datasources: false, users: false },
  loaded: { enterprises: false, departments: false, metrics: false, datasources: false, users: false },
  enterprises: structuredClone(demoRecords.enterprises),
  expandedEnterpriseIds: [],
  expandedDepartmentIds: [],
  currentDepartmentId: null,
  departmentWorkspace: null,
  departmentWorkspaceLoading: false,
  departmentWorkspaceMode: 'employees',
  knowledgeStatus: null,
  knowledgeDocuments: [],
  knowledgeDocumentsLoaded: false,
  expandedKnowledgeSourceIds: [],
  expandedKnowledgeCategoryKeys: [],
  rebuildingKnowledge: false,
  dataSourceImportJob: null,
  dataSourceImportModalOpen: false,
  dataSourceImportDismissed: false,
  dataSourceImportPollingTimer: null,
  dataSourceImportUploadController: null,
  metricCatalogMode: window.localStorage.getItem('atlas-metric-catalog-mode') === 'metric' ? 'metric' : 'datasource',
  expandedMetricGroupKeys: [],
  metricDashboardUpdatingIds: [],
  currentUserId: storedAuthUser()?.id || storedUserId(),
  currentConversationId: null,
  conversations: [],
  conversationsLoaded: false,
  historyLoading: false,
  llmConfigStatus: null,
  llmConfigLoading: false,
  chatLoading: false,
  voiceRecognition: null,
  voiceListening: false,
  voiceSendAfterStop: false,
  voiceSilentEnd: false,
  messages: initialChatMessages(),
  chartDetail: null,
  chartDetailType: 'auto',
  chartDetailRowIndexes: [],
  chartDetailLimit: 'all',
  reportDrafts: [],
  reportDraftsLoaded: false,
  reportDraftsLoading: false,
  currentReport: null,
  reportPreview: null,
  reportSaving: false,
  charts: new Set()
}

const DASHBOARD_CACHE_PREFIX = 'atlas-dashboard-cache:'

function dashboardCacheKey({
  sourceId = state.selectedDataSourceId,
  period = state.dashboardPeriod,
  dimension = state.dashboardDimensionValue
} = {}) {
  return `${DASHBOARD_CACHE_PREFIX}${state.currentUserId || 'anonymous'}:${sourceId || 'none'}:${period}:${dimension || 'all'}`
}

function readDashboardCache(key = dashboardCacheKey()) {
  try {
    const cached = JSON.parse(window.sessionStorage.getItem(key) || 'null')
    if (!cached?.dashboard || cached.dashboard.insights?.status === 'pending' || cached.dashboard.insights?.status === 'error') return null
    return cached.dashboard
  } catch {
    return null
  }
}

function writeDashboardCache(key, dashboard) {
  if (!dashboard || state.dashboardIsDemo || ['pending', 'error'].includes(dashboard.insights?.status)) return
  try {
    window.sessionStorage.setItem(key, JSON.stringify({ dashboard, savedAt: Date.now() }))
  } catch {
    // A full or disabled browser storage must not break the dashboard.
  }
}

function clearDashboardCache(key = null) {
  try {
    if (key) {
      window.sessionStorage.removeItem(key)
      return
    }
    const keys = []
    for (let index = 0; index < window.sessionStorage.length; index += 1) {
      const candidate = window.sessionStorage.key(index)
      if (candidate?.startsWith(DASHBOARD_CACHE_PREFIX)) keys.push(candidate)
    }
    keys.forEach((candidate) => window.sessionStorage.removeItem(candidate))
  } catch {
    // Cache invalidation is best effort.
  }
}

function invalidateDashboardConfiguration() {
  clearDashboardCache()
  state.dashboardRequestId += 1
  state.dashboardLoading = false
  state.dashboardInsightsLoading = false
  state.dashboardConfigurationStale = true
  state.dashboardDimensionValue = null
  state.reportPreview = null
  state.dashboard = {
    ...state.dashboard,
    kpis: [],
    primaryMetric: null,
    dimension: null,
    trendData: { x: [], y: [] },
    pieData: [],
    insights: { status: 'pending', message: '正在按最新看板配置加载', items: [] }
  }
}

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;')
}

function formatNumber(value) {
  const number = Number(value || 0)
  return new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 1 }).format(number)
}

function formatCurrency(value) {
  const number = Number(value || 0)
  if (Math.abs(number) >= 100000000) return `¥${(number / 100000000).toFixed(2)}亿`
  if (Math.abs(number) >= 10000) return `¥${(number / 10000).toFixed(1)}万`
  return new Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'CNY', maximumFractionDigits: 0 }).format(number)
}

function currentTime() {
  return new Intl.DateTimeFormat('zh-CN', { hour: '2-digit', minute: '2-digit' }).format(new Date())
}

function safeFileName(value, fallback) {
  const normalized = String(value || fallback)
    .replace(/[\\/:*?"<>|]/g, '-')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 80)
  return normalized || fallback
}

function downloadUrl(url, filename) {
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.append(link)
  link.click()
  link.remove()
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  downloadUrl(url, filename)
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}

function exportChartAsPng(message) {
  const chartElement = document.querySelector(`#message-chart-${CSS.escape(message.id)}`)
  const chart = chartElement && window.echarts?.getInstanceByDom(chartElement)
  if (!chart) {
    toast('图表尚未就绪，请稍后重试', 'warning')
    return
  }
  const title = message.plan?.chart_title || message.plan?.intent || '智能问数图表'
  const imageUrl = chart.getDataURL({
    type: 'png',
    pixelRatio: 2,
    backgroundColor: '#ffffff'
  })
  downloadUrl(imageUrl, `${safeFileName(title, '智能问数图表')}.png`)
  toast('图表 PNG 已开始下载', 'success')
}

function exportChartElementAsPng(element, title = '图表') {
  const chart = element && window.echarts?.getInstanceByDom(element)
  if (!chart) {
    toast('图表尚未就绪，请稍后重试', 'warning')
    return
  }
  downloadUrl(chart.getDataURL({ type: 'png', pixelRatio: 2, backgroundColor: '#ffffff' }), `${safeFileName(title, '图表')}.png`)
  toast('图表 PNG 已开始下载', 'success')
}

function excelCellValue(value) {
  if (value === null || value === undefined) return null
  if (typeof value === 'number' || typeof value === 'boolean') return value
  if (value instanceof Date) return value
  if (typeof value === 'object') return JSON.stringify(value)

  const text = String(value)
  if (/^\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)?$/.test(text)) {
    const date = new Date(text)
    if (!Number.isNaN(date.getTime())) return date
  }
  return text
}

async function exportTableAsXlsx(message) {
  const columns = Array.isArray(message.data?.columns) ? message.data.columns : []
  const rows = Array.isArray(message.data?.rows) ? message.data.rows : []
  if (!columns.length) {
    toast('当前消息没有可导出的表格', 'warning')
    return
  }
  if (!window.ExcelJS) {
    toast('XLSX 导出组件加载失败，请刷新页面后重试', 'error')
    return
  }

  const workbook = new window.ExcelJS.Workbook()
  workbook.creator = 'Atlas BI'
  workbook.created = new Date()
  const worksheet = workbook.addWorksheet('查询结果', {
    views: [{ state: 'frozen', ySplit: 1 }]
  })
  worksheet.addRow(columns.map((column) => String(column)))
  rows.forEach((row) => worksheet.addRow(columns.map((_, index) => excelCellValue(row?.[index]))))
  worksheet.autoFilter = {
    from: { row: 1, column: 1 },
    to: { row: 1, column: columns.length }
  }

  const headerRow = worksheet.getRow(1)
  headerRow.height = 24
  headerRow.font = { bold: true, color: { argb: 'FFFFFFFF' } }
  headerRow.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FF3157D5' } }
  headerRow.alignment = { vertical: 'middle', horizontal: 'left' }

  worksheet.columns.forEach((column, columnIndex) => {
    const values = [columns[columnIndex], ...rows.map((row) => row?.[columnIndex])]
    const width = Math.min(40, Math.max(12, ...values.map((value) => String(value ?? '').length + 2)))
    column.width = width
    const populated = rows.map((row) => row?.[columnIndex]).filter((value) => value !== null && value !== undefined)
    if (populated.length && populated.every((value) => typeof value === 'number')) {
      column.numFmt = populated.some((value) => !Number.isInteger(value)) ? '#,##0.00' : '#,##0'
    } else if (column.values.slice(2).some((value) => value instanceof Date)) {
      column.numFmt = 'yyyy-mm-dd hh:mm:ss'
    }
  })

  const buffer = await workbook.xlsx.writeBuffer()
  const title = message.plan?.intent || message.plan?.chart_title || '智能问数结果'
  downloadBlob(
    new Blob([buffer], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' }),
    `${safeFileName(title, '智能问数结果')}.xlsx`
  )
  toast(`表格 XLSX 已开始下载，共 ${rows.length} 行`, 'success')
}

function toast(message, type = 'info', duration = 3200) {
  const element = document.createElement('div')
  element.className = `toast ${type}`
  element.innerHTML = `<div>${escapeHtml(message)}</div>`
  toastLayer.append(element)
  window.setTimeout(() => element.remove(), duration)
}

function disposeCharts() {
  state.charts.forEach((chart) => chart.dispose())
  state.charts.clear()
}

function createChart(element, option) {
  if (!element || !window.echarts) return null
  const chart = window.echarts.init(element)
  chart.setOption(option)
  state.charts.add(chart)
  return chart
}

window.addEventListener('resize', () => {
  state.charts.forEach((chart) => chart.resize())
})

async function apiRequest(path, options = {}) {
  const controller = new AbortController()
  const externalSignal = options.signal
  const abortFromCaller = () => controller.abort()
  if (externalSignal) {
    if (externalSignal.aborted) controller.abort()
    else externalSignal.addEventListener('abort', abortFromCaller, { once: true })
  }
  const timeout = window.setTimeout(() => controller.abort(), options.timeout || 60000)
  const headers = { Accept: 'application/json', ...(options.headers || {}) }
  if (state.authToken) headers.Authorization = `Bearer ${state.authToken}`
  if (options.body && typeof options.body === 'string' && !(options.body instanceof FormData)) headers['Content-Type'] = 'application/json'

  try {
    const response = await fetch(path, { ...options, headers, signal: controller.signal })
    const contentType = response.headers.get('content-type') || ''
    const payload = contentType.includes('application/json') ? await response.json() : await response.text()
    if (!response.ok) {
      const detail = typeof payload === 'object' ? payload.detail || payload.message : payload
      const detailMessage = typeof detail === 'object' ? detail.message : detail
      const stage = typeof detail === 'object' && detail.stage ? `（${detail.stage}）` : ''
      throw new Error(`${detailMessage || `请求失败（${response.status}）`}${stage}`)
    }
    if (path.startsWith('/api/') && !state.backendOnline) {
      setBackendStatus(true)
    }
    return payload
  } catch (error) {
    if (error.name === 'AbortError') {
      const abortedByCaller = Boolean(externalSignal?.aborted)
      const requestError = new Error(abortedByCaller ? '请求已取消' : '请求超时，请稍后重试')
      requestError.name = abortedByCaller ? 'RequestCancelledError' : 'RequestTimeoutError'
      throw requestError
    }
    throw error
  } finally {
    window.clearTimeout(timeout)
    externalSignal?.removeEventListener('abort', abortFromCaller)
  }
}

async function streamAgentRequest(payload, onStage) {
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), 180000)
  try {
    const response = await fetch('/api/agent/stream', {
      method: 'POST',
      headers: {
        Accept: 'text/event-stream',
        'Content-Type': 'application/json',
        ...(state.authToken ? { Authorization: `Bearer ${state.authToken}` } : {})
      },
      body: JSON.stringify(payload),
      signal: controller.signal
    })
    if (!response.ok || !response.body) {
      const body = await response.json().catch(() => ({}))
      throw new Error(body?.detail?.message || body?.detail || `请求失败（${response.status}）`)
    }
    if (!state.backendOnline) setBackendStatus(true)
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let result = null
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const blocks = buffer.split('\n\n')
      buffer = blocks.pop() || ''
      blocks.forEach((block) => {
        const line = block.split('\n').find((item) => item.startsWith('data:'))
        if (!line) return
        const event = JSON.parse(line.slice(5).trim())
        if (event.event === 'stage') onStage?.(event)
        else if (event.event === 'result') result = event.data
        else if (event.event === 'error') throw new Error(event.message || '流式分析失败')
      })
    }
    if (!result) throw new Error('分析流未返回最终结果')
    if (result.status === 'error') throw new Error(result.message || '智能分析失败')
    return result
  } catch (error) {
    if (error.name === 'AbortError') throw new Error('分析超时，请稍后重试')
    throw error
  } finally {
    window.clearTimeout(timeout)
  }
}

function setBackendStatus(online) {
  state.backendOnline = online
  state.backendChecked = true
  backendStatus.className = `backend-status ${online ? 'is-online' : 'is-offline'}`
  backendStatus.querySelector('.status-text').textContent = online ? '后端已连接' : '后端未连接'
  backendStatus.title = online ? 'FastAPI 服务运行正常' : '当前使用前端样例数据，启动后端后可自动连接'
}

async function probeBackend() {
  const candidates = [
    ['/api/health/live', { timeout: 3500 }],
    ['/__backend_health', { timeout: 3500 }],
  ]
  let lastError = null
  for (const [path, options] of candidates) {
    try {
      await apiRequest(path, options)
      return { online: true, status: 200, target: 'fastapi' }
    } catch (error) {
      lastError = error
    }
  }
  throw lastError || new Error('后端健康检查失败')
}

async function checkBackend({ refreshView = false } = {}) {
  const previousOnline = state.backendOnline
  let online = previousOnline
  try {
    const result = await probeBackend()
    online = Boolean(result.online)
    state.backendHealthFailures = 0
  } catch {
    state.backendHealthFailures += 1
    online = state.backendHealthFailures >= 2 ? false : state.backendOnline
  }

  setBackendStatus(online)
  const changed = previousOnline !== online
  if (refreshView || changed) {
    if (['dashboard', 'reports'].includes(state.view) && state.backendOnline) await loadDashboardContext()
    else if (managementConfig[state.view] && state.backendOnline) {
      if (state.view === 'enterprises') await loadEnterpriseManagement()
      else await loadRecords(state.view)
      if (state.view === 'metrics') {
        await loadKnowledgeStatus()
        await loadKnowledgeDocuments()
      }
      if (state.view === 'datasources') {
        await loadEnterprises()
        await loadLatestDataSourceImportJob()
      }
    }
    else if (state.view === 'chat' && state.backendOnline) await loadChatConfiguration()
    else if (state.view === 'history' && state.backendOnline) await loadConversations({ rerender: true })
    else renderCurrentView()
  }
}

function previewBanner(message = '后端尚未启动，当前页面展示前端样例数据。启动 FastAPI 后刷新即可切换到真实数据。') {
  return `<div class="preview-banner"><strong>预览模式</strong><span>${escapeHtml(message)}</span></div>`
}

function pageHeading(title, description, actions = '', className = '') {
  return `
    <div class="page-heading ${escapeHtml(className)}">
      <div>
        <h1>${escapeHtml(title)}</h1>
        <p>${escapeHtml(description).replace(/\n/g, '<br>')}</p>
      </div>
      ${actions ? `<div class="heading-actions">${actions}</div>` : ''}
    </div>
  `
}

async function activateView(view, updateHash = true) {
  if (!state.authToken || !state.currentUser) {
    renderLogin()
    return
  }
  if (!viewTitles[view]) view = 'dashboard'
  if (view === 'users' && state.currentUser?.role !== 'admin') {
    view = 'dashboard'
    toast('仅管理员可以访问用户管理', 'warning')
  }
  if (state.view === 'chat' && view !== 'chat' && state.voiceListening) {
    stopVoiceInput({ abort: true, silent: true })
  }
  state.view = view
  pageTitle.textContent = viewTitles[view]
  document.querySelectorAll('.nav-item').forEach((item) => {
    item.classList.toggle('active', item.dataset.view === view)
  })
  closeSidebar()
  if (updateHash) history.replaceState(null, '', `#${view}`)
  if (!state.backendOnline) await checkBackend({ refreshView: false })
  renderCurrentView()

  if (['dashboard', 'reports'].includes(view) && state.backendOnline) loadDashboardContext()
  if (view === 'reports' && state.backendOnline) loadReportDrafts({ rerender: true })
  if (view === 'enterprises' && state.backendOnline) loadEnterpriseManagement()
  else if (managementConfig[view] && state.backendOnline) loadRecords(view)
  if (view === 'datasources' && state.backendOnline) {
    loadEnterprises()
    loadLatestDataSourceImportJob()
  }
  if (view === 'metrics' && state.backendOnline) {
    loadKnowledgeStatus()
    loadKnowledgeDocuments()
  }
  if (view === 'chat' && state.backendOnline) loadChatConfiguration()
  if (view === 'history' && state.backendOnline) loadConversations({ rerender: true })
  viewRoot.focus({ preventScroll: true })
}

function renderCurrentView() {
  disposeCharts()
  if (state.view === 'dashboard') renderDashboard()
  else if (state.view === 'chat') renderChat()
  else if (state.view === 'history') renderHistory()
  else if (state.view === 'chartdetail') renderChartDetail()
  else if (state.view === 'reports') renderReports()
  else if (state.view === 'reporteditor') renderReportEditor()
  else if (managementConfig[state.view]) renderManagement(state.view)
}

function dashboardChartOptions(dashboard = state.dashboard) {
  const primary = dashboard.primaryMetric || { name: '销售额', unit: '¥' }
  const valueFormatter = (value) => primary.unit === '¥' ? formatCurrency(value) : `${formatNumber(value)}${primary.unit || ''}`
  return {
    trend: {
      animationDuration: 500,
      color: ['#3157d5'],
      tooltip: { trigger: 'axis', valueFormatter },
      grid: { left: 12, right: 14, top: 30, bottom: 8, containLabel: true },
      xAxis: {
        type: 'category',
        boundaryGap: false,
        data: dashboard.trendData?.x || [],
        axisLine: { lineStyle: { color: '#dfe4ec' } },
        axisTick: { show: false },
        axisLabel: { color: '#7c899d', fontSize: 10 }
      },
      yAxis: {
        type: 'value',
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: '#7c899d', fontSize: 10, formatter: valueFormatter },
        splitLine: { lineStyle: { color: '#edf0f4' } }
      },
      series: [{
        type: 'line',
        smooth: 0.35,
        symbol: 'circle',
        symbolSize: 7,
        data: dashboard.trendData?.y || [],
        lineStyle: { width: 3 },
        areaStyle: { color: 'rgba(49, 87, 213, 0.08)' }
      }]
    },
    share: {
      color: ['#3157d5', '#0f9f9a', '#e0a53b', '#8491a6'],
      tooltip: { trigger: 'item', formatter: (params) => `${params.name}<br/>${valueFormatter(params.value)}` },
      legend: { bottom: 0, icon: 'circle', itemWidth: 7, itemHeight: 7, textStyle: { color: '#68758a', fontSize: 10 } },
      series: [{
        type: 'pie',
        radius: ['52%', '72%'],
        center: ['50%', '43%'],
        avoidLabelOverlap: true,
        itemStyle: { borderColor: '#fff', borderWidth: 3 },
        label: { show: false },
        emphasis: { label: { show: true, fontSize: 12, fontWeight: 'bold' } },
        data: dashboard.pieData || []
      }]
    }
  }
}

function selectDashboardDataSource() {
  const sources = state.dashboardDataSources || []
  if (!sources.some((source) => Number(source.id) === Number(state.selectedDataSourceId))) {
    state.selectedDataSourceId = sources.length ? Number(sources[0].id) : null
  }
  if (state.selectedDataSourceId) {
    window.localStorage.setItem('atlas-dashboard-data-source-id', String(state.selectedDataSourceId))
  }
  syncWorkspaceEnterprise()
  return state.selectedDataSourceId
}

function selectedDataSource() {
  return (state.dashboardDataSources || []).find(
    (source) => Number(source.id) === Number(state.selectedDataSourceId)
  ) || null
}

function selectedEnterprise() {
  const source = selectedDataSource()
  if (!source) return null
  return (state.enterprises || []).find(
    (enterprise) => Number(enterprise.id) === Number(source.enterprise_id)
  ) || null
}

function selectedEnterpriseName() {
  return selectedEnterprise()?.name || '未配置企业'
}

function dataSourceDisplayNumber(sourceId) {
  const index = (state.records.datasources || []).findIndex(
    (source) => Number(source.id) === Number(sourceId)
  )
  return index >= 0 ? index + 1 : '—'
}

function enterpriseDisplayNumber(enterpriseId) {
  const index = (state.enterprises || []).findIndex(
    (enterprise) => Number(enterprise.id) === Number(enterpriseId)
  )
  return index >= 0 ? index + 1 : '—'
}

function syncWorkspaceEnterprise() {
  const label = document.querySelector('#workspace-enterprise-name')
  if (label) label.textContent = selectedEnterpriseName()
}

async function switchGlobalDataSource(sourceId, {
  reloadAnalytics = false,
  resetConversation = false,
  feedback = false
} = {}) {
  const nextId = Number(sourceId)
  const source = (state.dashboardDataSources || []).find((item) => Number(item.id) === nextId)
  if (!source) {
    if (feedback) toast('所选数据源不存在或已被删除', 'error')
    return null
  }

  const changed = Number(state.selectedDataSourceId) !== nextId
  state.selectedDataSourceId = nextId
  state.reportPreview = null
  state.dashboardDimensionValue = null
  window.localStorage.setItem('atlas-dashboard-data-source-id', String(nextId))
  syncWorkspaceEnterprise()

  if (resetConversation && changed) startNewConversation({ navigate: false })
  if (state.view === 'enterprises') renderManagement('enterprises')
  if (reloadAnalytics && ['dashboard', 'reports'].includes(state.view)) {
    await loadDashboard(true, true)
  }
  if (feedback && changed) {
    toast(`全局数据源已切换为 ${source.name}`, 'success')
  }
  return source
}

function dashboardDataSourceSelectHtml() {
  selectDashboardDataSource()
  const options = (state.dashboardDataSources || []).map((source) => `
    <option value="${escapeHtml(source.id)}" ${Number(source.id) === Number(state.selectedDataSourceId) ? 'selected' : ''}>
      ${escapeHtml(source.name)} · ${escapeHtml(source.database)}
    </option>`).join('')
  return `<label class="dashboard-source-picker"><span>数据源</span><select class="select" id="dashboard-data-source" aria-label="驾驶舱数据源" ${options ? '' : 'disabled'}>${options || '<option>暂无数据源</option>'}</select></label>`
}

function chatDataSourceSelectHtml() {
  selectDashboardDataSource()
  const options = (state.dashboardDataSources || []).map((source) => `
    <option value="${escapeHtml(source.id)}" ${Number(source.id) === Number(state.selectedDataSourceId) ? 'selected' : ''}>
      ${escapeHtml(source.name)} · ${escapeHtml(source.database)}
    </option>`).join('')
  return `<label class="chat-source-picker"><span>数据源</span><select class="select" id="chat-data-source" aria-label="智能问数数据源" ${options && !state.chatLoading ? '' : 'disabled'}>${options || '<option>暂无数据源</option>'}</select></label>`
}

function dashboardPeriodSelectHtml() {
  const options = [
    ['year', '本年度'],
    ['six_months', '最近 6 个月'],
    ['quarter', '本季度'],
    ['all', '全部时间']
  ]
  return `<label class="dashboard-period-picker"><span>统计周期</span><select class="select" id="period-select" aria-label="统计周期">${options.map(([value, label]) => `<option value="${value}" ${state.dashboardPeriod === value ? 'selected' : ''}>${label}</option>`).join('')}</select></label>`
}

function dashboardErrorBanner() {
  if (!state.dashboardIsDemo) return ''
  if (!state.backendChecked || state.dashboardLoading) {
    return '<div class="preview-banner"><strong>正在加载</strong><span>正在读取当前数据源并生成经营洞察…</span></div>'
  }
  return `<div class="preview-banner error" role="alert"><strong>后台错误</strong><span>后台错误，当前为样例数据，请及时修复</span></div>`
}

function deltaHtml(value, suffix = '%') {
  const number = Number(value)
  if (!Number.isFinite(number)) return '<span class="delta neutral">— 暂无对比</span><span>较上期</span>'
  const direction = number > 0 ? '↑' : (number < 0 ? '↓' : '→')
  const className = number < 0 ? 'delta down' : (number > 0 ? 'delta' : 'delta neutral')
  return `<span class="${className}">${direction} ${formatNumber(Math.abs(number))}${suffix}</span><span>较上期</span>`
}

function dashboardInsightsHtml(insights = {}) {
  if (insights.status === 'pending') {
    return '<div class="insight-api-notice"><span class="spinner dark"></span><strong>正在根据当前数据源生成经营洞察…</strong></div>'
  }
  if (insights.status === 'unconfigured') {
    return `<div class="insight-api-notice"><strong>前往智能问数模块配置API</strong><button class="button small" type="button" data-navigate="chat">前往配置</button></div>`
  }
  if (insights.status === 'error') {
    return `<div class="insight-api-notice error"><strong>经营洞察生成失败</strong><p>${escapeHtml(insights.message || '请检查 API 配置后重试')}</p></div>`
  }
  const items = Array.isArray(insights.items) ? insights.items : []
  if (!items.length) return '<div class="empty-state compact">当前数据源没有可生成的经营洞察。</div>'
  return items.map((item, index) => `
    <div class="insight-item"><span class="insight-index">${String(index + 1).padStart(2, '0')}</span><div><strong>${escapeHtml(item.title)}</strong><p>${escapeHtml(item.content)}</p></div></div>
  `).join('')
}

function normalizedDashboardKpis(data) {
  // Current dashboard responses always carry `kpis`, including an empty array.
  // Only responses from the legacy fixed-card API need the compatibility fallback.
  if (Array.isArray(data.kpis)) return data.kpis
  return [
    { name: '累计销售额', value: data.totalSales, unit: '¥', delta: data.deltas?.totalSales },
    { name: '订单总量', value: data.orderCount, unit: '单', delta: data.deltas?.orderCount },
    { name: '活跃客户', value: data.customerCount, unit: '人', delta: data.deltas?.customerCount },
    { name: '订单完成率', value: data.completionRate, unit: '%', delta: data.deltas?.completionRate }
  ]
}

function metricValueHtml(metric) {
  if (metric.unit === '¥' || metric.unit === '元') return formatCurrency(metric.value)
  if (metric.unit === '%') return `${formatNumber(metric.value)}%`
  return `${formatNumber(metric.value)}${metric.unit ? ` ${escapeHtml(metric.unit)}` : ''}`
}

function dashboardKpisHtml(data) {
  return normalizedDashboardKpis(data).slice(0, 4).map((metric) => `
    <article class="kpi-card">
      <div class="kpi-topline"><span class="kpi-label">${escapeHtml(metric.name)}</span><span class="kpi-symbol">${escapeHtml(metric.unit || '◇')}</span></div>
      <strong class="kpi-value">${metricValueHtml(metric)}</strong>
      <div class="kpi-foot">${deltaHtml(metric.delta, metric.unit === '%' ? ' 个百分点' : '%')}</div>
    </article>`).join('')
}

function bindDashboardSourceMenu() {
  document.querySelector('#dashboard-data-source')?.addEventListener('change', async (event) => {
    await switchGlobalDataSource(event.target.value, { reloadAnalytics: true })
  })
  document.querySelector('#period-select')?.addEventListener('change', async (event) => {
    state.reportPreview = null
    state.dashboardDimensionValue = null
    state.dashboardPeriod = event.target.value
    window.localStorage.setItem('atlas-dashboard-period', state.dashboardPeriod)
    await loadDashboard(true, true)
  })
}

function renderDashboard() {
  const data = state.dashboard
  const primaryMetricName = data.primaryMetric?.name || '销售额'
  const dimensionName = data.dimension?.field || '默认维度'
  viewRoot.innerHTML = `
    ${pageHeading(
      '经营驾驶舱',
      '把关键指标、趋势变化和 AI 洞察放在同一个决策视图中。',
      `${dashboardDataSourceSelectHtml()}
       ${dashboardPeriodSelectHtml()}
       <button class="button" id="refresh-dashboard" type="button">↻ 刷新数据</button>
       <button class="button primary" type="button" data-navigate="chat">✦ 开始问数</button>`
    )}
    ${dashboardErrorBanner()}
    ${state.dashboardDimensionValue ? `<div class="preview-banner"><strong>联动筛选</strong><span>${escapeHtml(dimensionName)} = ${escapeHtml(state.dashboardDimensionValue)}</span><button class="button small" id="clear-dashboard-filter" type="button">清除筛选</button></div>` : ''}

    <section class="dashboard-kpis" aria-label="关键经营指标">
      ${dashboardKpisHtml(data)}
    </section>

    <section class="dashboard-grid">
      <div>
        <article class="panel">
          <header class="panel-header">
            <div><h2>${escapeHtml(primaryMetricName)}趋势</h2><p>按月观察指标变化和经营节奏</p></div>
            <div class="inline-actions"><span class="data-source-note">${state.dashboardIsDemo ? '样例数据' : '实时查询'}</span><button class="button small" type="button" data-dashboard-chart-detail="trend">查看详情</button></div>
          </header>
          <div class="panel-body"><div class="chart" id="trend-chart" role="img" aria-label="月度销售额趋势图"></div></div>
        </article>
      </div>

      <div class="dashboard-side">
        <article class="panel">
          <header class="panel-header"><div><h2>${escapeHtml(primaryMetricName)}按${escapeHtml(dimensionName)}分布</h2><p>点击图形可筛选全看板</p></div><button class="button small" type="button" data-dashboard-chart-detail="share">查看详情</button></header>
          <div class="panel-body"><div class="chart compact" id="share-chart" role="img" aria-label="厂商订单分布图"></div></div>
        </article>
        <article class="panel">
          <header class="panel-header"><div><h2>AI 经营洞察</h2><p>基于当前指标自动生成</p></div></header>
          <div class="panel-body insight-list">
            ${dashboardInsightsHtml(data.insights)}
          </div>
        </article>
      </div>
    </section>
  `

  const options = dashboardChartOptions()
  createChart(document.querySelector('#trend-chart'), options.trend)
  const shareChart = createChart(document.querySelector('#share-chart'), options.share)
  shareChart?.on('click', async (params) => {
    state.dashboardDimensionValue = state.dashboardDimensionValue === params.name ? null : params.name
    await loadDashboard(true, true)
  })
  bindDashboardSourceMenu()
  document.querySelector('#clear-dashboard-filter')?.addEventListener('click', async () => {
    state.dashboardDimensionValue = null
    await loadDashboard(true, true)
  })
  document.querySelectorAll('[data-dashboard-chart-detail]').forEach((button) => {
    button.addEventListener('click', () => openDashboardChartDetail(button.dataset.dashboardChartDetail))
  })

  document.querySelector('#refresh-dashboard')?.addEventListener('click', async () => {
    if (!state.backendOnline) {
      await checkBackend({ refreshView: true })
      if (!state.backendOnline) toast('后端尚未启动，继续展示样例数据', 'warning')
      return
    }
    await loadDashboardContext(true, true)
  })
  bindNavigateButtons()
}

async function loadDashboardSources() {
  const records = await apiRequest('/api/admin/data_sources/', { timeout: 12000 })
  state.dashboardDataSources = Array.isArray(records) ? records : []
  state.records.datasources = structuredClone(state.dashboardDataSources)
  state.recordsFromApi.datasources = true
  state.loaded.datasources = true
  selectDashboardDataSource()
  syncWorkspaceEnterprise()
  if (!state.selectedDataSourceId) throw new Error('数据源管理中尚未配置数据源')
}

async function loadDashboardContext(showFeedback = false, force = false) {
  // An older insight request must not block reloading KPI configuration.
  if (state.dashboardLoading && !state.dashboardConfigurationStale) return
  state.dashboardLoading = true
  try {
    await Promise.all([loadDashboardSources(), loadEnterprises()])
    syncWorkspaceEnterprise()
    const cacheKey = dashboardCacheKey()
    const cached = force ? null : readDashboardCache(cacheKey)
    if (cached) {
      state.dashboard = structuredClone(cached)
      state.dashboardIsDemo = false
      state.dashboardError = ''
      state.dashboardConfigurationStale = false
      state.dashboardLoading = false
      if (['dashboard', 'reports'].includes(state.view)) renderCurrentView()
      return
    }
    await loadDashboard(showFeedback, force)
  } catch (error) {
    state.dashboard = structuredClone(demoDashboard)
    state.dashboardIsDemo = true
    state.dashboardError = error.message || '后台错误'
    state.dashboardLoading = false
    if (['dashboard', 'reports'].includes(state.view)) renderCurrentView()
    if (showFeedback) toast(state.dashboardError, 'error', 5200)
  } finally {
    state.dashboardLoading = false
  }
}

async function loadDashboard(showFeedback = false, force = false) {
  if (!state.selectedDataSourceId) return loadDashboardContext(showFeedback, force)
  const requestId = ++state.dashboardRequestId
  state.dashboardLoading = true
  const requestedSourceId = Number(state.selectedDataSourceId)
  const requestedPeriod = state.dashboardPeriod
  const requestedDimension = state.dashboardDimensionValue
  const cacheKey = dashboardCacheKey({
    sourceId: requestedSourceId,
    period: requestedPeriod,
    dimension: requestedDimension
  })
  if (force) clearDashboardCache(cacheKey)
  else {
    const cached = readDashboardCache(cacheKey)
    if (cached) {
      state.dashboard = structuredClone(cached)
      state.dashboardIsDemo = false
      state.dashboardError = ''
      state.dashboardLoading = false
      if (['dashboard', 'reports'].includes(state.view)) renderCurrentView()
      return
    }
  }
  try {
    const baseParams = new URLSearchParams({
      data_source_id: String(requestedSourceId),
      include_insights: 'false',
      period: requestedPeriod
    })
    if (requestedDimension) baseParams.set('dimension_value', requestedDimension)
    const data = await apiRequest(`/api/dashboard/?${baseParams}`, { timeout: 20000 })
    if (requestId !== state.dashboardRequestId || requestedSourceId !== Number(state.selectedDataSourceId) || requestedPeriod !== state.dashboardPeriod || requestedDimension !== state.dashboardDimensionValue) return
      state.dashboard = {
      kpis: data.kpis || [],
      primaryMetric: data.primaryMetric || null,
      dimension: data.dimension || null,
      totalSales: data.totalSales ?? 0,
      orderCount: data.orderCount ?? 0,
      customerCount: data.customerCount ?? 0,
      completionRate: data.completionRate ?? 0,
      deltas: data.deltas || {},
      trendData: data.trendData || { x: [], y: [] },
      pieData: data.pieData || [],
      insights: data.insights || { status: 'pending', message: '正在生成经营洞察', items: [] }
    }
    state.dashboardIsDemo = false
    state.dashboardError = ''
    state.dashboardConfigurationStale = false
    state.dashboardLoading = false
    if (['dashboard', 'reports'].includes(state.view)) renderCurrentView()
    if (showFeedback) toast('当前数据源的看板数据已更新', 'success')

    state.dashboardInsightsLoading = true
    const insightParams = new URLSearchParams({
      data_source_id: String(requestedSourceId),
      user_id: String(state.currentUserId),
      include_insights: 'true',
      period: requestedPeriod
    })
    if (requestedDimension) insightParams.set('dimension_value', requestedDimension)
    try {
      const insightData = await apiRequest(`/api/dashboard/?${insightParams}`, { timeout: 120000 })
      if (requestId !== state.dashboardRequestId || requestedSourceId !== Number(state.selectedDataSourceId) || requestedPeriod !== state.dashboardPeriod || requestedDimension !== state.dashboardDimensionValue) return
      state.dashboard.insights = insightData.insights || { status: 'error', message: '经营洞察没有返回内容', items: [] }
      writeDashboardCache(cacheKey, state.dashboard)
    } catch (error) {
      if (requestId !== state.dashboardRequestId || requestedSourceId !== Number(state.selectedDataSourceId) || requestedPeriod !== state.dashboardPeriod || requestedDimension !== state.dashboardDimensionValue) return
      state.dashboard.insights = { status: 'error', message: error.message || '经营洞察生成失败', items: [] }
    } finally {
      if (requestId === state.dashboardRequestId) state.dashboardInsightsLoading = false
      if (requestId === state.dashboardRequestId && requestedSourceId === Number(state.selectedDataSourceId) && requestedPeriod === state.dashboardPeriod && requestedDimension === state.dashboardDimensionValue && ['dashboard', 'reports'].includes(state.view)) renderCurrentView()
    }
  } catch (error) {
    if (requestId !== state.dashboardRequestId) return
    state.dashboard = structuredClone(demoDashboard)
    state.dashboardIsDemo = true
    state.dashboardError = error.message || '后台错误'
    state.dashboardLoading = false
    if (['dashboard', 'reports'].includes(state.view)) renderCurrentView()
    if (showFeedback) toast(error.message || '仪表盘数据读取失败', 'error')
  } finally {
    if (requestId === state.dashboardRequestId) state.dashboardLoading = false
  }
}

function messageTable(data) {
  const columns = Array.isArray(data?.columns) ? data.columns : []
  const rows = Array.isArray(data?.rows) ? data.rows.slice(0, 8) : []
  if (!columns.length) return ''
  return `
    <div class="result-table-wrap">
      <table class="result-table">
        <thead><tr>${columns.map((column) => `<th>${escapeHtml(column)}</th>`).join('')}</tr></thead>
        <tbody>${rows.map((row) => `<tr>${row.map((cell) => `<td>${escapeHtml(cell)}</td>`).join('')}</tr>`).join('')}</tbody>
      </table>
      ${data.rows.length > rows.length ? `<span class="message-meta">仅展示前 ${rows.length} 行，共 ${data.rows.length} 行</span>` : ''}
    </div>
  `
}

function messageHtml(message) {
  const loading = message.loading ? '<div class="loading-line" aria-label="正在分析"></div>' : ''
  const text = message.text ? `<div class="message-answer">${escapeHtml(message.text)}</div>` : ''
  const plan = message.plan ? `
    <details class="analysis-details">
      <summary>查看查询计划与 SQL</summary>
      <div class="plan-grid">
        <span><b>意图</b>${escapeHtml(message.plan.intent || '业务数据分析')}</span>
        <span><b>请求类型</b>${escapeHtml(message.plan.request_type || 'sql')}</span>
        <span><b>分析类型</b>${escapeHtml(message.plan.analysis_type || 'summary')}</span>
        <span><b>结果行数</b>${escapeHtml(message.data?.row_count ?? message.data?.rows?.length ?? 0)}</span>
        ${message.plan.matched_metrics?.length ? `<span><b>命中指标</b>${escapeHtml(message.plan.matched_metrics.map((metric) => metric.name).join('、'))}</span>` : ''}
        ${message.plan.metric_validation ? `<span><b>口径校验</b>${escapeHtml({ passed: '已通过', reference_only: '参考口径', not_matched: '未命中指标' }[message.plan.metric_validation.status] || message.plan.metric_validation.status)}</span>` : ''}
      </div>
      ${message.sql ? `<pre class="sql-block">${escapeHtml(message.sql)}</pre>` : ''}
    </details>` : (message.sql ? `<pre class="sql-block">${escapeHtml(message.sql)}</pre>` : '')
  const hasTable = Boolean(message.data?.columns?.length)
  const hasChart = Boolean(message.chartOption || message.chartData)
  const table = hasTable ? `
    <div class="artifact-heading">
      <strong>查询结果</strong>
      <button class="artifact-download" type="button" data-export-table="${escapeHtml(message.id)}">↓ 导出 XLSX</button>
    </div>
    ${messageTable(message.data)}` : ''
  const chart = hasChart ? `
    <div class="artifact-heading">
      <strong>可视化图表</strong>
      <div class="inline-actions">
        <button class="artifact-download" type="button" data-chart-detail="${escapeHtml(message.id)}">查看详情</button>
        <button class="artifact-download" type="button" data-export-chart="${escapeHtml(message.id)}">↓ 下载 PNG</button>
      </div>
    </div>
    <div class="message-chart" id="message-chart-${escapeHtml(message.id)}"></div>` : ''
  const reportAction = message.reportSection
    ? `<button class="artifact-download" type="button" data-add-report-section="${escapeHtml(message.id)}">添加到报告</button>`
    : ''
  return `
    <div class="message ${message.role}">
      <div class="message-avatar">${message.role === 'user' ? '我' : 'AI'}</div>
      <div class="message-bubble">
        ${loading}${text}${plan}${table}${chart}${reportAction}
        ${message.meta ? `<span class="message-meta">${escapeHtml(message.meta)}</span>` : ''}
      </div>
    </div>
  `
}

function chatChartOption(data) {
  const columns = data?.columns || []
  const rows = data?.rows || []
  if (columns.length < 2 || !rows.length) return null
  return {
    color: ['#3157d5', '#0f9f9a', '#e0a53b'],
    tooltip: { trigger: 'axis' },
    legend: { top: 10, textStyle: { fontSize: 10, color: '#68758a' } },
    grid: { left: 10, right: 12, top: 42, bottom: 8, containLabel: true },
    xAxis: {
      type: 'category',
      data: rows.map((row) => row[0]),
      axisTick: { show: false },
      axisLine: { lineStyle: { color: '#dfe4ec' } },
      axisLabel: { color: '#7c899d', fontSize: 10 }
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#7c899d', fontSize: 10 },
      splitLine: { lineStyle: { color: '#edf0f4' } }
    },
    series: columns.slice(1, 4).map((column, index) => ({
      name: column,
      type: rows.length > 8 ? 'line' : 'bar',
      smooth: true,
      barMaxWidth: 34,
      data: rows.map((row) => row[index + 1])
    }))
  }
}

function openDashboardChartDetail(kind) {
  const metricName = state.dashboard.primaryMetric?.name || '销售额'
  const dimensionName = state.dashboard.dimension?.field || '维度'
  if (kind === 'share') {
    state.chartDetail = {
      title: `${metricName}按${dimensionName}分布`,
      sourceView: 'dashboard',
      data: {
        columns: [dimensionName, metricName],
        rows: (state.dashboard.pieData || []).map((item) => [item.name, item.value])
      },
      preferredType: 'pie'
    }
  } else {
    state.chartDetail = {
      title: `${metricName}趋势`,
      sourceView: 'dashboard',
      data: {
        columns: ['月份', metricName],
        rows: (state.dashboard.trendData?.x || []).map((label, index) => [label, state.dashboard.trendData?.y?.[index] ?? null])
      },
      preferredType: 'line'
    }
  }
  state.chartDetailType = 'auto'
  state.chartDetailRowIndexes = state.chartDetail.data.rows.map((_, index) => index)
  state.chartDetailLimit = 'all'
  activateView('chartdetail')
}

function openChartDetail(message) {
  if (!message?.data?.columns?.length) {
    toast('当前图表没有可查看的数据', 'warning')
    return
  }
  const originalType = message.chartOption?.series?.[0]?.type
  state.chartDetail = {
    title: message.plan?.chart_title || message.plan?.intent || '智能问数图表',
    sourceView: 'chat',
    messageId: message.id,
    data: structuredClone(message.data),
    preferredType: ['line', 'bar', 'pie'].includes(originalType) ? originalType : null,
    sql: message.sql || ''
  }
  state.chartDetailType = 'auto'
  state.chartDetailRowIndexes = state.chartDetail.data.rows.map((_, index) => index)
  state.chartDetailLimit = 'all'
  activateView('chartdetail')
}

function chartDetailData() {
  const source = state.chartDetail?.data || { columns: [], rows: [] }
  const sourceRows = Array.isArray(source.rows) ? source.rows : []
  const selectedIndexes = new Set(Array.isArray(state.chartDetailRowIndexes)
    ? state.chartDetailRowIndexes.filter((index) => Number.isInteger(index) && index >= 0 && index < sourceRows.length)
    : sourceRows.map((_, index) => index))
  let rows = sourceRows.filter((_, index) => selectedIndexes.has(index))
  const limit = state.chartDetailLimit === 'all' ? null : Number(state.chartDetailLimit)
  if (limit) rows = rows.slice(0, limit)
  return { columns: [...(source.columns || [])], rows: structuredClone(rows), row_count: rows.length }
}

function chartDetailDimensionPickerHtml() {
  const source = state.chartDetail?.data || { columns: [], rows: [] }
  const dimensionColumn = String(source.columns?.[0] || '横轴')
  const isDateDimension = /(^ym$|date|time|month|year|日期|时间|月份|年月)/i.test(dimensionColumn)
  const filterLabel = isDateDimension ? '日期筛选' : `${dimensionColumn}筛选`
  const itemLabel = isDateDimension ? '个日期' : '项'
  const rows = Array.isArray(source.rows) ? source.rows : []
  const selected = new Set(state.chartDetailRowIndexes)
  return `<div class="chart-detail-control">
    <span>${escapeHtml(filterLabel)}</span>
    <div class="column-multiselect" id="chart-detail-dimension">
      <button class="column-multiselect-trigger" id="chart-detail-dimension-trigger" type="button" aria-haspopup="listbox" aria-expanded="false">
        <span data-dimension-selection-summary>已选择 ${selected.size} / ${rows.length} ${itemLabel}</span><span aria-hidden="true">⌄</span>
      </button>
      <div class="column-multiselect-menu" id="chart-detail-dimension-menu" role="listbox" aria-multiselectable="true" data-item-label="${escapeHtml(itemLabel)}" hidden>
        ${rows.map((row, index) => `<button class="column-multiselect-option${selected.has(index) ? ' selected' : ''}" type="button" role="option" aria-selected="${selected.has(index)}" data-row-index="${index}">
          <span>${escapeHtml(row?.[0] ?? `第 ${index + 1} 项`)}</span><span class="column-multiselect-check" aria-hidden="true">${selected.has(index) ? '✅' : ''}</span>
        </button>`).join('')}
      </div>
    </div>
  </div>`
}

function chartDetailOption(data) {
  const columns = data.columns || []
  const rows = data.rows || []
  if (columns.length < 2 || !rows.length) return null
  let type = state.chartDetailType === 'auto'
    ? (state.chartDetail?.preferredType || (rows.length > 8 ? 'line' : 'bar'))
    : state.chartDetailType
  if (type === 'pie') {
    return {
      color: ['#3157d5', '#0f9f9a', '#e0a53b', '#8491a6', '#8b5cf6', '#ef6c57'],
      tooltip: { trigger: 'item' },
      legend: { type: 'scroll', bottom: 0 },
      series: [{
        name: columns[1],
        type: 'pie',
        radius: ['38%', '68%'],
        center: ['50%', '45%'],
        data: rows.map((row) => ({ name: row[0], value: Number(row[1]) || 0 })),
        itemStyle: { borderColor: '#fff', borderWidth: 2 }
      }]
    }
  }
  return {
    color: ['#3157d5', '#0f9f9a', '#e0a53b'],
    tooltip: { trigger: 'axis' },
    legend: { top: 8 },
    grid: { left: 18, right: 22, top: 52, bottom: 18, containLabel: true },
    xAxis: { type: 'category', data: rows.map((row) => row[0]), axisLabel: { interval: 0, rotate: rows.length > 12 ? 30 : 0 } },
    yAxis: { type: 'value', splitLine: { lineStyle: { color: '#edf0f4' } } },
    series: columns.slice(1, 5).map((column, index) => ({
      name: column,
      type,
      smooth: type === 'line',
      barMaxWidth: 42,
      data: rows.map((row) => row[index + 1])
    }))
  }
}

function renderFullResultTable(data) {
  if (!data.columns?.length) return '<div class="empty-state compact">没有可展示的数据。</div>'
  return `<div class="result-table-wrap chart-detail-table"><table class="result-table">
    <thead><tr>${data.columns.map((column) => `<th>${escapeHtml(column)}</th>`).join('')}</tr></thead>
    <tbody>${data.rows.map((row) => `<tr>${data.columns.map((_, index) => `<td>${escapeHtml(row[index])}</td>`).join('')}</tr>`).join('')}</tbody>
  </table></div>`
}

function renderChartDetail() {
  const detail = state.chartDetail
  if (!detail) {
    viewRoot.innerHTML = `${pageHeading('图表详情', '尚未选择要查看的图表。', '<button class="button" type="button" data-navigate="chat">返回智能问数</button>')}<div class="empty-state">请从驾驶舱或智能问数图表进入详情。</div>`
    bindNavigateButtons()
    return
  }
  const data = chartDetailData()
  const backLabel = detail.sourceView === 'dashboard' ? '返回驾驶舱' : '返回智能问数'
  viewRoot.innerHTML = `
    ${pageHeading(detail.title, `当前展示 ${data.rows.length} 行数据，可筛选并切换可视化方式。`, `<button class="button" id="chart-detail-back" type="button">← ${backLabel}</button><button class="button" id="chart-detail-xlsx" type="button">↓ 导出 XLSX</button><button class="button primary" id="chart-detail-png" type="button">↓ 下载 PNG</button>`)}
    <section class="chart-detail-controls panel">
      <label><span>图表类型</span><select class="select" id="chart-detail-type"><option value="auto">自动推荐</option><option value="line">折线图</option><option value="bar">柱状图</option><option value="pie">饼图</option></select></label>
      ${chartDetailDimensionPickerHtml()}
      <label><span>显示范围</span><select class="select" id="chart-detail-limit"><option value="all">全部数据</option><option value="10">前 10 条</option><option value="20">前 20 条</option><option value="50">前 50 条</option></select></label>
    </section>
    <section class="panel chart-detail-panel">
      <header class="panel-header"><div><h2>${escapeHtml(detail.title)}</h2><p>${data.rows.length} 行 · ${data.columns.length} 列</p></div></header>
      <div class="panel-body"><div class="chart-detail-canvas" id="chart-detail-canvas"></div></div>
    </section>
    <section class="panel chart-detail-panel">
      <header class="panel-header"><div><h2>明细数据</h2><p>导出文件包含当前筛选后的完整结果</p></div></header>
      <div class="panel-body">${renderFullResultTable(data)}</div>
    </section>
    ${detail.sql ? `<details class="analysis-details chart-detail-sql"><summary>查看原始 SQL</summary><pre class="sql-block">${escapeHtml(detail.sql)}</pre></details>` : ''}
  `
  const typeSelect = document.querySelector('#chart-detail-type')
  const limitSelect = document.querySelector('#chart-detail-limit')
  typeSelect.value = state.chartDetailType
  limitSelect.value = state.chartDetailLimit
  const option = chartDetailOption(data)
  if (option) createChart(document.querySelector('#chart-detail-canvas'), option)
  else document.querySelector('#chart-detail-canvas').innerHTML = '<div class="empty-state compact">筛选后没有可绘制的数据。</div>'

  typeSelect.addEventListener('change', (event) => { state.chartDetailType = event.target.value; renderChartDetail() })
  limitSelect.addEventListener('change', (event) => { state.chartDetailLimit = event.target.value; renderChartDetail() })
  const dimensionPicker = document.querySelector('#chart-detail-dimension')
  const dimensionTrigger = document.querySelector('#chart-detail-dimension-trigger')
  const dimensionMenu = document.querySelector('#chart-detail-dimension-menu')
  const dimensionOptions = [...dimensionMenu.querySelectorAll('[data-row-index]')]
  const dimensionSummary = dimensionTrigger.querySelector('[data-dimension-selection-summary]')
  const dimensionItemLabel = dimensionMenu.dataset.itemLabel || '项'
  let draftRowIndexes = new Set(state.chartDetailRowIndexes)
  let dimensionMenuOpen = false

  const syncDraftSelection = () => {
    dimensionOptions.forEach((optionButton) => {
      const index = Number(optionButton.dataset.rowIndex)
      const isSelected = draftRowIndexes.has(index)
      optionButton.classList.toggle('selected', isSelected)
      optionButton.setAttribute('aria-selected', String(isSelected))
      optionButton.querySelector('.column-multiselect-check').textContent = isSelected ? '✅' : ''
    })
    dimensionSummary.textContent = `已选择 ${draftRowIndexes.size} / ${dimensionOptions.length} ${dimensionItemLabel}`
  }
  const closeDimensionMenu = (applySelection = true) => {
    if (!dimensionMenuOpen) return
    dimensionMenuOpen = false
    dimensionMenu.hidden = true
    dimensionTrigger.setAttribute('aria-expanded', 'false')
    document.removeEventListener('pointerdown', handleOutsideDimensionMenu, true)
    document.removeEventListener('keydown', handleDimensionMenuKeydown, true)
    if (!applySelection) return
    const nextIndexes = [...draftRowIndexes].sort((left, right) => left - right)
    const previousIndexes = [...state.chartDetailRowIndexes].sort((left, right) => left - right)
    if (nextIndexes.join(',') !== previousIndexes.join(',')) {
      state.chartDetailRowIndexes = nextIndexes
      renderChartDetail()
    }
  }
  function handleOutsideDimensionMenu(event) {
    if (!dimensionPicker.contains(event.target)) closeDimensionMenu(true)
  }
  function handleDimensionMenuKeydown(event) {
    if (event.key === 'Escape') {
      event.preventDefault()
      closeDimensionMenu(true)
      dimensionTrigger.focus()
    }
  }
  dimensionTrigger.addEventListener('click', () => {
    if (dimensionMenuOpen) {
      closeDimensionMenu(true)
      return
    }
    draftRowIndexes = new Set(state.chartDetailRowIndexes)
    syncDraftSelection()
    dimensionMenuOpen = true
    dimensionMenu.hidden = false
    dimensionTrigger.setAttribute('aria-expanded', 'true')
    document.addEventListener('pointerdown', handleOutsideDimensionMenu, true)
    document.addEventListener('keydown', handleDimensionMenuKeydown, true)
  })
  dimensionOptions.forEach((optionButton) => {
    optionButton.addEventListener('click', () => {
      const index = Number(optionButton.dataset.rowIndex)
      if (draftRowIndexes.has(index)) draftRowIndexes.delete(index)
      else draftRowIndexes.add(index)
      syncDraftSelection()
    })
  })
  document.querySelector('#chart-detail-back').addEventListener('click', () => activateView(detail.sourceView))
  document.querySelector('#chart-detail-png').addEventListener('click', () => exportChartElementAsPng(document.querySelector('#chart-detail-canvas'), detail.title))
  document.querySelector('#chart-detail-xlsx').addEventListener('click', async (event) => {
    event.currentTarget.disabled = true
    try { await exportTableAsXlsx({ data, plan: { chart_title: detail.title } }) }
    catch (error) { toast(`XLSX 导出失败：${error.message}`, 'error', 5200) }
    finally { event.currentTarget.disabled = false }
  })
}

function apiConfigurationHtml() {
  const configured = Boolean(state.llmConfigStatus?.configured)
  return `
    <section class="api-config-card" aria-label="DeepSeek API 配置">
      <div class="api-config-title">
        <div><h3>DeepSeek API</h3><p>按用户隔离，密钥只提交到后端且不会回显。</p></div>
        <span class="api-config-status ${configured ? 'configured' : 'missing'}">
          ${configured ? '已配置API' : '请配置API'}
        </span>
      </div>
      <p class="api-config-user">当前账号：${escapeHtml(state.currentUser?.username || '')}</p>
      <form class="api-config-form" id="api-config-form">
        <input class="field" id="api-key-input" name="api_key" type="password" autocomplete="new-password"
          placeholder="请输入 DeepSeek API Key" aria-label="DeepSeek API Key" />
        <button class="api-config-submit ${configured ? 'modify' : ''}" type="submit" ${state.llmConfigLoading ? 'disabled' : ''}>
          ${state.llmConfigLoading ? '保存中…' : (configured ? '修改' : '配置')}
        </button>
      </form>
    </section>`
}

async function loadLlmConfigStatus({ rerender = true } = {}) {
  if (!state.backendOnline) {
    state.llmConfigStatus = null
    return
  }
  try {
    state.llmConfigStatus = await apiRequest(
      `/api/llm-config/status?user_id=${encodeURIComponent(state.currentUserId)}`,
      { timeout: 12000 }
    )
  } catch (error) {
    state.llmConfigStatus = null
    if (rerender) toast(error.message || '读取 API 配置状态失败', 'error')
  }
  if (rerender && state.view === 'chat') renderChat()
}

async function loadChatConfiguration() {
  try {
    await loadDashboardSources()
  } catch (error) {
    toast(error.message || '读取智能问数数据源失败', 'error')
  }
  await loadLlmConfigStatus({ rerender: true })
}

async function saveLlmConfiguration(event) {
  event.preventDefault()
  if (state.llmConfigLoading) return
  const input = document.querySelector('#api-key-input')
  const apiKey = input?.value.trim() || ''
  if (!apiKey) {
    toast('请输入 DeepSeek API Key', 'warning')
    input?.focus()
    return
  }
  state.llmConfigLoading = true
  const wasConfigured = Boolean(state.llmConfigStatus?.configured)
  try {
    state.llmConfigStatus = await apiRequest('/api/llm-config/', {
      method: 'PUT',
      body: JSON.stringify({ user_id: state.currentUserId, api_key: apiKey }),
      timeout: 20000
    })
    if (!state.backendOnline) setBackendStatus(true)
    clearDashboardCache()
    if (input) input.value = ''
    toast(wasConfigured ? 'API Key 已更新，后端配置已刷新' : 'API Key 已配置，后端配置已刷新', 'success')
  } catch (error) {
    toast(error.message || 'API 配置保存失败', 'error', 5200)
  } finally {
    state.llmConfigLoading = false
    if (state.view === 'chat') renderChat()
  }
}

function formatConversationTime(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  }).format(date)
}

async function loadConversations({ rerender = false } = {}) {
  if (!state.backendOnline || state.historyLoading) return
  state.historyLoading = true
  try {
    state.conversations = await apiRequest(`/api/conversations/?user_id=${state.currentUserId}`, { timeout: 15000 })
    state.conversationsLoaded = true
  } catch (error) {
    state.conversations = []
    state.conversationsLoaded = false
    if (rerender) toast(error.message || '历史记录读取失败', 'error')
  } finally {
    state.historyLoading = false
    if (rerender && state.view === 'history') renderHistory()
  }
}

async function ensureConversation(question) {
  if (state.currentConversationId || !state.backendOnline) return state.currentConversationId
  const record = await apiRequest('/api/conversations/', {
    method: 'POST',
    body: JSON.stringify({
      user_id: state.currentUserId,
      title: question.slice(0, 60),
      data_source_id: state.selectedDataSourceId || null
    }),
    timeout: 15000
  })
  state.currentConversationId = record.id
  state.conversationsLoaded = false
  return record.id
}

async function persistConversationMessage(role, content, payload = {}) {
  if (!state.backendOnline || !state.currentConversationId) return
  await apiRequest(`/api/conversations/${state.currentConversationId}/messages`, {
    method: 'POST',
    body: JSON.stringify({ user_id: state.currentUserId, role, content, payload }),
    timeout: 20000
  })
  state.conversationsLoaded = false
}

function startNewConversation({ navigate = true } = {}) {
  state.currentConversationId = null
  state.messages = initialChatMessages()
  if (navigate) activateView('chat')
  else if (state.view === 'chat') renderChat()
}

async function openConversation(conversationId) {
  try {
    const detail = await apiRequest(`/api/conversations/${conversationId}?user_id=${state.currentUserId}`, { timeout: 15000 })
    state.currentConversationId = detail.id
    if (detail.data_source_id && state.dashboardDataSources.some((source) => Number(source.id) === Number(detail.data_source_id))) {
      await switchGlobalDataSource(detail.data_source_id)
    }
    state.messages = detail.messages.map((message) => {
      const payload = message.payload || {}
      return {
        id: `history-message-${message.id}`,
        role: message.role,
        text: message.content,
        plan: payload.plan,
        sql: payload.sql,
        data: payload.data,
        chartOption: payload.chart_config || payload.chartOption,
        reportSection: payload.report_section || null,
        meta: formatConversationTime(message.created_at)
      }
    })
    if (!state.messages.length) state.messages = initialChatMessages()
    activateView('chat')
  } catch (error) {
    toast(error.message || '会话读取失败', 'error')
  }
}

async function renameConversation(conversationId) {
  const current = state.conversations.find((item) => Number(item.id) === Number(conversationId))
  const title = window.prompt('请输入新的会话名称', current?.title || '')?.trim()
  if (!title) return
  try {
    await apiRequest(`/api/conversations/${conversationId}`, {
      method: 'PUT',
      body: JSON.stringify({ user_id: state.currentUserId, title }),
      timeout: 15000
    })
    await loadConversations({ rerender: true })
    toast('会话已重命名', 'success')
  } catch (error) {
    toast(error.message || '会话重命名失败', 'error')
  }
}

async function deleteConversation(conversationId) {
  if (!window.confirm('确定删除这条问数会话及其全部消息吗？')) return
  try {
    await apiRequest(`/api/conversations/${conversationId}?user_id=${state.currentUserId}`, {
      method: 'DELETE',
      timeout: 15000
    })
    if (Number(state.currentConversationId) === Number(conversationId)) startNewConversation({ navigate: false })
    await loadConversations({ rerender: true })
    toast('会话已删除', 'success')
  } catch (error) {
    toast(error.message || '会话删除失败', 'error')
  }
}

function renderHistory() {
  const items = state.conversations || []
  viewRoot.innerHTML = `
    ${pageHeading(
      '问数历史',
      '按用户保存每次提问、SQL、数据表和图表，可随时继续分析。',
      '<button class="button primary" id="new-history-conversation" type="button">＋ 新建问数</button>'
    )}
    ${!state.backendOnline ? '<div class="preview-banner error"><strong>后台错误</strong><span>历史记录需要后端服务才能读取。</span></div>' : ''}
    <section class="history-panel">
      ${state.historyLoading ? '<div class="empty-state">正在读取历史记录…</div>' : items.length ? `
        <div class="history-list">
          ${items.map((item) => `
            <article class="history-item">
              <button class="history-main" type="button" data-open-conversation="${escapeHtml(item.id)}">
                <strong>${escapeHtml(item.title)}</strong>
                <span>${escapeHtml(item.message_count)} 条消息 · ${escapeHtml(formatConversationTime(item.updated_at))}</span>
              </button>
              <div class="history-actions">
                <button class="button small" type="button" data-open-conversation="${escapeHtml(item.id)}">继续对话</button>
                <button class="button small" type="button" data-rename-conversation="${escapeHtml(item.id)}">重命名</button>
                <button class="button small danger-text" type="button" data-delete-conversation="${escapeHtml(item.id)}">删除</button>
              </div>
            </article>`).join('')}
        </div>` : '<div class="empty-state"><strong>暂无问数历史</strong><span>完成第一次智能问数后，会话会自动保存在这里。</span></div>'}
    </section>
  `
  document.querySelector('#new-history-conversation')?.addEventListener('click', () => startNewConversation())
  document.querySelectorAll('[data-open-conversation]').forEach((button) => {
    button.addEventListener('click', () => openConversation(Number(button.dataset.openConversation)))
  })
  document.querySelectorAll('[data-rename-conversation]').forEach((button) => {
    button.addEventListener('click', () => renameConversation(Number(button.dataset.renameConversation)))
  })
  document.querySelectorAll('[data-delete-conversation]').forEach((button) => {
    button.addEventListener('click', () => deleteConversation(Number(button.dataset.deleteConversation)))
  })
}

function renderChat() {
  disposeCharts()
  const selectedSource = state.dashboardDataSources.find((source) => Number(source.id) === Number(state.selectedDataSourceId))
  viewRoot.innerHTML = `
    <div class="chat-layout">
      <section class="chat-panel" aria-label="智能问数对话">
        <header class="chat-toolbar">
          <div><h2>数据分析会话</h2><span class="data-source-note">${state.backendOnline ? '已连接业务数据' : '前端预览模式'}</span></div>
          <div class="inline-actions">
            <button class="button small" id="new-conversation" type="button">＋ 新建会话</button>
            <button class="button small" type="button" data-navigate="history">◷ 历史记录</button>
          </div>
        </header>
        <div class="chat-context-bar">
          ${chatDataSourceSelectHtml()}
          <span>当前查询：${escapeHtml(selectedSource?.database || '未选择数据源')} · 切换后自动新建会话</span>
        </div>
        <div class="messages" id="messages">${state.messages.map(messageHtml).join('')}</div>
        <div class="chat-composer">
          <div class="composer-box">
            <textarea id="question-input" rows="1" placeholder="输入经营问题，例如：最近 6 个月销售额趋势如何？" aria-label="输入问题"></textarea>
            <div class="inline-actions">
              <button class="button ${state.voiceListening ? 'danger' : 'ghost'} small" id="voice-button" type="button" aria-label="${state.voiceListening ? '停止语音输入' : '开始语音输入'}">
                ${state.voiceListening ? '■ 停止录音' : '◉ 语音'}
              </button>
              <button class="button primary" id="send-question" type="button" ${state.chatLoading ? 'disabled' : ''}>
                ${state.chatLoading ? '<span class="spinner"></span>分析中' : '发送 ↗'}
              </button>
            </div>
          </div>
          <div class="composer-help"><span>自动生成查询计划、执行 SQL，并调用图表、异常、归因和报告工具</span><span>Enter 发送 · Shift + Enter 换行</span></div>
        </div>
      </section>

      <aside class="prompt-panel">
        ${apiConfigurationHtml()}
        <h3>推荐问题</h3>
        <p>从一个清晰的问题开始，平台会结合指标口径完成分析。</p>
        <button class="prompt-chip" type="button" data-prompt="最近 6 个月销售额趋势如何？">最近 6 个月销售额趋势如何？<span>趋势分析</span></button>
        <button class="prompt-chip" type="button" data-prompt="各客户订单量占比是多少？">各客户订单量占比是多少？<span>结构分析</span></button>
        <button class="prompt-chip" type="button" data-prompt="本月销售额是否存在异常？">本月销售额是否存在异常？<span>异常检测</span></button>
        <button class="prompt-chip" type="button" data-prompt="为什么订单完成率下降？">为什么订单完成率下降？<span>归因分析</span></button>
      </aside>
    </div>
  `

  state.messages.forEach((message) => {
    if (!message.chartOption && !message.chartData) return
    const option = message.chartOption || chatChartOption(message.chartData)
    if (option) createChart(document.querySelector(`#message-chart-${CSS.escape(message.id)}`), option)
  })

  document.querySelectorAll('[data-export-chart]').forEach((button) => {
    button.addEventListener('click', () => {
      const message = state.messages.find((item) => item.id === button.dataset.exportChart)
      if (message) exportChartAsPng(message)
    })
  })
  document.querySelectorAll('[data-chart-detail]').forEach((button) => {
    button.addEventListener('click', () => {
      const message = state.messages.find((item) => item.id === button.dataset.chartDetail)
      if (message) openChartDetail(message)
    })
  })
  document.querySelectorAll('[data-export-table]').forEach((button) => {
    button.addEventListener('click', async () => {
      const message = state.messages.find((item) => item.id === button.dataset.exportTable)
      if (!message) return
      button.disabled = true
      try {
        await exportTableAsXlsx(message)
      } catch (error) {
        toast(`XLSX 导出失败：${error.message}`, 'error', 5200)
      } finally {
        button.disabled = false
      }
    })
  })
  document.querySelectorAll('[data-add-report-section]').forEach((button) => {
    button.addEventListener('click', () => {
      const message = state.messages.find((item) => item.id === button.dataset.addReportSection)
      if (!message?.reportSection) return
      const content = defaultReportContent()
      content.findings = [message.reportSection, ...(content.findings || [])]
      state.currentReport = {
        id: null,
        title: `${message.plan?.chart_title || message.plan?.intent || '智能问数'}分析报告`,
        data_source_id: state.selectedDataSourceId,
        period: state.dashboardPeriod,
        content,
        versions: []
      }
      activateView('reporteditor')
    })
  })

  const messageArea = document.querySelector('#messages')
  messageArea.scrollTop = messageArea.scrollHeight
  const input = document.querySelector('#question-input')

  document.querySelectorAll('[data-prompt]').forEach((button) => {
    button.addEventListener('click', () => {
      const prompt = button.dataset.prompt
      document.querySelector('#question-input').value = prompt
      document.querySelector('#question-input').focus()
    })
  })

  document.querySelector('#send-question')?.addEventListener('click', () => sendQuestion())
  document.querySelector('#new-conversation')?.addEventListener('click', () => startNewConversation({ navigate: false }))
  document.querySelector('#chat-data-source')?.addEventListener('change', (event) => {
    switchGlobalDataSource(event.target.value, { resetConversation: true }).then((source) => {
      if (source) toast(`已切换到 ${source.name}，并新建问数会话`, 'success')
    })
  })
  input?.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      sendQuestion()
    }
  })
  document.querySelector('#voice-button')?.addEventListener('click', startVoiceInput)
  document.querySelector('#api-config-form')?.addEventListener('submit', saveLlmConfiguration)
  bindNavigateButtons()
}

function applyRoleVisibility() {
  const isAdmin = state.currentUser?.role === 'admin'
  document.querySelectorAll('[data-admin-only]').forEach((element) => {
    element.toggleAttribute('hidden', !isAdmin)
  })
  if (logoutButton) logoutButton.hidden = !state.currentUser
  if (userAvatar) {
    const username = state.currentUser?.username || '未登录'
    userAvatar.textContent = username.slice(0, 2).toUpperCase()
    userAvatar.setAttribute('aria-label', `当前用户：${username}`)
  }
}

function renderLogin(message = '') {
  disposeCharts()
  pageTitle.textContent = '登录'
  applyRoleVisibility()
  viewRoot.innerHTML = `<section class="login-shell">
    <div class="login-card panel">
      <div class="brand-mark login-brand" aria-hidden="true">A</div>
      <h1>登录 Atlas BI</h1>
      <p>使用平台账号进入企业经营分析空间。</p>
      ${message ? `<div class="inline-error">${escapeHtml(message)}</div>` : ''}
      <form id="login-form">
        <label><span>用户名</span><input class="field" id="login-username" autocomplete="username" required autofocus /></label>
        <label><span>密码</span><input class="field" id="login-password" type="password" autocomplete="current-password" required /></label>
        <button class="button primary" type="submit">登录</button>
      </form>
      <div class="auth-switch" id="registration-entry" hidden>
        <span>首次部署且没有账号？</span>
        <button class="auth-link" id="show-register" type="button">注册首个管理员</button>
      </div>
    </div>
  </section>`
  document.querySelector('#login-form').addEventListener('submit', login)
  document.querySelector('#show-register').addEventListener('click', () => renderRegister())
  loadRegistrationAvailability()
}

async function loadRegistrationAvailability() {
  const entry = document.querySelector('#registration-entry')
  if (!entry) return
  try {
    const result = await apiRequest('/api/auth/registration-status', { timeout: 5000 })
    if (document.body.contains(entry)) entry.hidden = !result.available
  } catch {
    if (document.body.contains(entry)) entry.hidden = true
  }
}

function renderRegister(message = '') {
  disposeCharts()
  pageTitle.textContent = '首次注册'
  applyRoleVisibility()
  viewRoot.innerHTML = `<section class="login-shell">
    <div class="login-card panel">
      <div class="brand-mark login-brand" aria-hidden="true">A</div>
      <h1>创建首个管理员</h1>
      <p>仅空系统可以注册。创建成功后，其他账号由管理员统一维护。</p>
      ${message ? `<div class="inline-error">${escapeHtml(message)}</div>` : ''}
      <form id="register-form">
        <label><span>管理员用户名</span><input class="field" id="register-username" autocomplete="username" maxlength="50" required autofocus /></label>
        <label><span>密码</span><input class="field" id="register-password" type="password" autocomplete="new-password" required /></label>
        <label><span>确认密码</span><input class="field" id="register-password-confirm" type="password" autocomplete="new-password" required /></label>
        <button class="button primary" type="submit">注册并登录</button>
      </form>
      <div class="auth-switch">
        <span>已经有账号？</span>
        <button class="auth-link" id="back-to-login" type="button">返回登录</button>
      </div>
    </div>
  </section>`
  document.querySelector('#register-form').addEventListener('submit', registerFirstAdmin)
  document.querySelector('#back-to-login').addEventListener('click', () => renderLogin())
}

async function completeAuthentication(result) {
  state.authToken = result.access_token
  state.currentUser = result.user
  state.currentUserId = Number(result.user.id)
  window.localStorage.setItem('atlas-auth-token', state.authToken)
  window.localStorage.setItem('atlas-auth-user', JSON.stringify(state.currentUser))
  window.localStorage.setItem('atlas-current-user-id', String(state.currentUserId))
  applyRoleVisibility()
  await checkBackend()
  if (state.backendOnline) await loadEnterprises()
  activateView('dashboard')
}

async function registerFirstAdmin(event) {
  event.preventDefault()
  const form = event.currentTarget
  const button = form.querySelector('button[type="submit"]')
  const username = document.querySelector('#register-username').value.trim()
  const password = document.querySelector('#register-password').value
  const confirmation = document.querySelector('#register-password-confirm').value
  if (password !== confirmation) {
    renderRegister('两次输入的密码不一致')
    return
  }
  button.disabled = true
  button.textContent = '正在创建…'
  try {
    const result = await apiRequest('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
      timeout: 15000
    })
    await completeAuthentication(result)
    toast('管理员账号创建成功', 'success')
  } catch (error) {
    renderRegister(error.message || '注册失败')
  } finally {
    button.disabled = false
    button.textContent = '注册并登录'
  }
}

async function login(event) {
  event.preventDefault()
  const button = event.currentTarget.querySelector('button[type="submit"]')
  button.disabled = true
  try {
    const result = await apiRequest('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({
        username: document.querySelector('#login-username').value.trim(),
        password: document.querySelector('#login-password').value
      }),
      timeout: 15000
    })
    await completeAuthentication(result)
  } catch (error) {
    renderLogin(error.message || '登录失败')
  } finally {
    button.disabled = false
  }
}

async function logout() {
  if (state.voiceListening) stopVoiceInput({ abort: true, silent: true })
  await cancelDataSourceImport({ silent: true, requireConfirmation: false, cancelLatest: true })
  state.authToken = ''
  state.currentUser = null
  state.currentUserId = null
  window.localStorage.removeItem('atlas-auth-token')
  window.localStorage.removeItem('atlas-auth-user')
  renderLogin()
}

async function bootstrapAuthenticatedApp() {
  if (!state.authToken) {
    renderLogin()
    return
  }
  try {
    state.currentUser = await apiRequest('/api/auth/me', { timeout: 10000 })
    state.currentUserId = Number(state.currentUser.id)
    window.localStorage.setItem('atlas-auth-user', JSON.stringify(state.currentUser))
    applyRoleVisibility()
    const initialView = location.hash.slice(1)
    activateView(viewTitles[initialView] ? initialView : 'dashboard', false)
    await checkBackend()
    if (state.backendOnline) await loadEnterprises()
  } catch (error) {
    state.authToken = ''
    state.currentUser = null
    window.localStorage.removeItem('atlas-auth-token')
    window.localStorage.removeItem('atlas-auth-user')
    renderLogin(error.message)
  }
}

function demoQueryResult(question) {
  if (question.includes('客户') || question.includes('占比')) {
    return {
      text: '前端预览：华东区域当前贡献最高，华东与华南合计占比约 63%。启动后端后将使用真实数据库结果。',
      sql: 'SELECT region, SUM(amount) AS sales\nFROM orders\nWHERE status = \'paid\'\nGROUP BY region\nORDER BY sales DESC;',
      data: { columns: ['region', 'sales'], rows: [['华东区域', 1031148], ['华南区域', 773361], ['华北区域', 601503], ['其他区域', 458288]] }
    }
  }
  return {
    text: '前端预览：最近两个月销售额持续增长，8 月达到当前周期峰值。启动后端后将使用真实数据库结果。',
    sql: "SELECT DATE_FORMAT(create_time, '%Y-%m') AS month, SUM(amount) AS sales\nFROM orders\nWHERE status = 'paid'\nGROUP BY month\nORDER BY month;",
    data: { columns: ['month', 'sales'], rows: demoDashboard.trendData.x.map((month, index) => [month, demoDashboard.trendData.y[index]]) }
  }
}

async function sendQuestion() {
  if (state.chatLoading) return
  if (state.voiceListening) {
    stopVoiceInput({ sendAfterStop: true })
    return
  }
  const input = document.querySelector('#question-input')
  if (state.backendOnline && !state.llmConfigStatus?.configured) {
    toast('请配置API', 'error')
    document.querySelector('#api-key-input')?.focus()
    return
  }
  if (state.backendOnline && !state.selectedDataSourceId) {
    toast('请先选择智能问数数据源', 'warning')
    document.querySelector('#chat-data-source')?.focus()
    return
  }
  const question = input?.value.trim()
  if (!question) {
    toast('请先输入一个数据问题', 'warning')
    return
  }

  state.messages.push({ id: createClientId(), role: 'user', text: question, meta: currentTime() })
  const loadingId = createClientId()
  state.messages.push({ id: loadingId, role: 'assistant', loading: true, meta: '正在理解指标并查询数据' })
  state.chatLoading = true
  renderChat()

  try {
    if (state.backendOnline) {
      try {
        await ensureConversation(question)
        await persistConversationMessage('user', question)
      } catch (historyError) {
        toast(`本次问数可继续，但历史记录保存失败：${historyError.message}`, 'warning', 5200)
      }
    }
    let responseMessage
    if (!state.backendOnline) {
      await new Promise((resolve) => window.setTimeout(resolve, 650))
      const preview = demoQueryResult(question)
      responseMessage = {
        id: loadingId,
        role: 'assistant',
        text: preview.text,
        plan: {
          intent: '前端预览分析',
          request_type: 'sql',
          analysis_type: question.includes('趋势') ? 'trend' : 'share'
        },
        sql: preview.sql,
        data: preview.data,
        chartData: preview.data,
        meta: '前端样例 · 后端未连接'
      }
    } else {
      const result = await streamAgentRequest({
        question,
        user_id: state.currentUserId,
        data_source_id: state.selectedDataSourceId,
        conversation_id: state.currentConversationId
      }, (event) => {
        state.messages = state.messages.map((message) => message.id === loadingId
          ? { ...message, meta: event.message || '正在分析' }
          : message)
        const meta = document.querySelector(`[data-message-id="${CSS.escape(loadingId)}"] .message-meta`)
        if (meta) meta.textContent = event.message || '正在分析'
      })
      responseMessage = {
        id: loadingId,
        role: 'assistant',
        text: result.answer || result.message || '分析已完成，但没有返回文字结论。',
        plan: result.plan,
        sql: result.sql,
        data: result.data,
        chartOption: result.chart_config,
        reportSection: result.report_section,
        meta: `智能分析 · ${currentTime()}`
      }
    }
    state.messages = state.messages.map((message) => message.id === loadingId ? responseMessage : message)
    if (state.backendOnline && state.currentConversationId) {
      try {
        await persistConversationMessage('assistant', responseMessage.text, {
          plan: responseMessage.plan,
          sql: responseMessage.sql,
          data: responseMessage.data,
          chart_config: responseMessage.chartOption || responseMessage.chartData || null,
          report_section: responseMessage.reportSection || null
        })
      } catch (historyError) {
        toast(`分析已完成，但回答未写入历史：${historyError.message}`, 'warning', 5200)
      }
    }
  } catch (error) {
    const errorMessage = {
      id: loadingId,
      role: 'assistant',
      text: `本次分析没有完成：${error.message}`,
      meta: '请求失败 · 可检查数据源或后端日志'
    }
    state.messages = state.messages.map((message) => message.id === loadingId ? errorMessage : message)
    if (state.backendOnline && state.currentConversationId) {
      try {
        await persistConversationMessage('assistant', errorMessage.text, { error: true })
      } catch {
        // The visible query error is more important than a secondary history error.
      }
    }
    toast(error.message || '问数请求失败', 'error', 5200)
  } finally {
    state.chatLoading = false
    renderChat()
  }
}

function setVoiceControls(listening, stopping = false) {
  const button = document.querySelector('#voice-button')
  if (!button) return
  button.disabled = stopping
  button.classList.toggle('danger', listening)
  button.classList.toggle('ghost', !listening)
  button.setAttribute('aria-label', listening ? '停止语音输入' : '开始语音输入')
  button.textContent = stopping ? '… 正在停止' : (listening ? '■ 停止录音' : '◉ 语音')
}

function stopVoiceInput({ sendAfterStop = false, abort = false, silent = false } = {}) {
  if (!state.voiceRecognition) return
  state.voiceSendAfterStop = sendAfterStop
  state.voiceSilentEnd = silent
  setVoiceControls(true, true)
  try {
    if (abort) state.voiceRecognition.abort()
    else state.voiceRecognition.stop()
  } catch {
    state.voiceRecognition = null
    state.voiceListening = false
    state.voiceSendAfterStop = false
    state.voiceSilentEnd = false
    setVoiceControls(false)
  }
}

function startVoiceInput() {
  if (state.voiceListening) {
    stopVoiceInput()
    return
  }
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition
  if (!Recognition) {
    toast('当前浏览器不支持语音识别，请使用 Chrome 或 Edge', 'warning')
    return
  }
  const recognition = new Recognition()
  const input = document.querySelector('#question-input')
  const existingText = input?.value || ''
  recognition.lang = 'zh-CN'
  recognition.continuous = true
  recognition.interimResults = true
  let finalTranscript = ''
  state.voiceRecognition = recognition
  state.voiceListening = true
  state.voiceSendAfterStop = false
  state.voiceSilentEnd = false
  setVoiceControls(true)
  recognition.onstart = () => {
    setVoiceControls(true)
    toast('正在聆听，再次点击“停止录音”即可结束')
  }
  recognition.onresult = (event) => {
    let interimTranscript = ''
    for (let index = event.resultIndex; index < event.results.length; index += 1) {
      const transcript = event.results[index][0].transcript
      if (event.results[index].isFinal) finalTranscript += transcript
      else interimTranscript += transcript
    }
    const currentInput = document.querySelector('#question-input')
    if (currentInput) currentInput.value = `${existingText}${finalTranscript}${interimTranscript}`
  }
  recognition.onerror = (event) => {
    if (event.error !== 'aborted') toast(`语音识别失败：${event.error || '请重试'}`, 'error')
  }
  recognition.onend = () => {
    const shouldSend = state.voiceSendAfterStop
    const silent = state.voiceSilentEnd
    const hasQuestion = Boolean(document.querySelector('#question-input')?.value.trim())
    state.voiceRecognition = null
    state.voiceListening = false
    state.voiceSendAfterStop = false
    state.voiceSilentEnd = false
    setVoiceControls(false)
    if (shouldSend && hasQuestion) sendQuestion()
    else if (!silent) toast(hasQuestion ? '语音输入已停止，可编辑后发送' : '语音输入已停止', 'success')
  }
  try {
    recognition.start()
  } catch (error) {
    state.voiceRecognition = null
    state.voiceListening = false
    setVoiceControls(false)
    toast(`无法启动语音输入：${error.message}`, 'error')
  }
}

function recordSearchText(record) {
  return Object.values(record).join(' ').toLowerCase()
}

function metricDashboardToggle(record) {
  const enabled = record.dashboard_enabled !== false
  const updating = state.metricDashboardUpdatingIds.includes(Number(record.id))
  const label = `${enabled ? '已用于看板' : '未用于看板'}${updating ? ' · 保存中' : ''}`
  const nextLabel = enabled ? '未用于看板' : '已用于看板'
  return `<button class="tag ${enabled ? 'success' : 'neutral'} metric-dashboard-toggle${updating ? ' is-updating' : ''}" type="button" data-toggle-metric-dashboard="${escapeHtml(record.id)}" aria-pressed="${enabled}" title="点击切换为${nextLabel}" ${updating ? 'disabled' : ''}>${label}</button>`
}

function renderMetricRow(record, source) {
  const dataSource = state.records.datasources.find(
    (item) => Number(item.id) === Number(record.data_source_id)
  )
  const topic = record.topic === '通用' ? '未分类' : (record.topic || '未分类')
  return `
    <tr data-search="${escapeHtml(recordSearchText(record))}">
      <td class="metric-name-cell"><span class="cell-title">${escapeHtml(record.name)}</span><span class="cell-subtitle">指标 ID ${escapeHtml(record.id)}${record.aliases ? ` · ${escapeHtml(record.aliases)}` : ''}</span></td>
      <td class="metric-topic-cell"><span class="tag">${escapeHtml(topic)}</span></td>
      <td class="metric-description-cell">${record.description ? escapeHtml(record.description) : '<span class="muted-value">未填写口径说明</span>'}</td>
      <td class="metric-sql-cell"><div class="metric-sql-scroll" tabindex="0"><code>${escapeHtml(record.sql_expr || '—')}</code></div></td>
      <td class="metric-config-cell">
        <div class="metric-source"><strong>${escapeHtml(dataSource?.name || `数据源 ${record.data_source_id}`)}</strong><span>ID ${escapeHtml(record.data_source_id)}</span></div>
      </td>
      <td class="metric-actions-cell">
        ${metricDashboardToggle(record)}
        ${rowActions('metrics', record.id, source)}
      </td>
    </tr>`
}

function metricDefinitionKey(record) {
  return record.definition_id ? `metric:${record.definition_id}` : `metric-name:${record.name}`
}

function metricDefinitionGroups() {
  const groups = new Map()
  state.records.metrics.forEach((record) => {
    const key = metricDefinitionKey(record)
    if (!groups.has(key)) {
      groups.set(key, {
        key,
        id: record.definition_id || null,
        name: record.name,
        description: record.description,
        topic: record.topic === '通用' ? '未分类' : (record.topic || '未分类'),
        aliases: record.aliases,
        unit: record.unit,
        bindings: []
      })
    }
    groups.get(key).bindings.push(record)
  })
  return [...groups.values()]
}

function metricBindingCard(record, source, mode) {
  const dataSource = state.records.datasources.find((item) => Number(item.id) === Number(record.data_source_id))
  const enterprise = state.enterprises.find((item) => Number(item.id) === Number(dataSource?.enterprise_id))
  const title = mode === 'metric' ? (dataSource?.name || `数据源 ${record.data_source_id}`) : record.name
  const subtitle = mode === 'metric'
    ? `${enterprise?.name || '未知企业'} · 数据源序号 ${dataSourceDisplayNumber(record.data_source_id)}`
    : `${record.topic === '通用' ? '未分类' : (record.topic || '未分类')}${record.unit ? ` · ${record.unit}` : ''}`
  return `<article class="metric-binding-card" data-search="${escapeHtml(recordSearchText(record))}">
    <div class="metric-binding-identity"><strong>${escapeHtml(title)}</strong><span>${escapeHtml(subtitle)}</span></div>
    <div class="metric-binding-sql"><span>SQL</span><code>${escapeHtml(record.sql_expr || '—')}</code></div>
    <div class="metric-binding-status">${metricDashboardToggle(record)}</div>
    <div class="metric-binding-actions">${rowActions('metrics', record.id, source)}</div>
  </article>`
}

function metricGroupShell({ key, title, subtitle, meta, bindings, source, mode, defaults }) {
  const expanded = state.expandedMetricGroupKeys.includes(key)
  const search = `${title} ${subtitle} ${bindings.map(recordSearchText).join(' ')}`.toLowerCase()
  return `<article class="metric-catalog-group ${expanded ? 'expanded' : ''}" data-search="${escapeHtml(search)}">
    <header class="metric-catalog-header">
      <button class="metric-catalog-toggle" type="button" data-toggle-metric-group="${escapeHtml(key)}" aria-expanded="${expanded}">
        <span class="metric-catalog-chevron">${expanded ? '▾' : '▸'}</span>
        <span class="metric-catalog-title"><strong>${escapeHtml(title)}</strong><small>${escapeHtml(subtitle)}</small></span>
        <span class="metric-catalog-meta">${meta}</span>
      </button>
      <button class="button small" type="button" data-add-metric-binding='${escapeHtml(JSON.stringify(defaults))}'>＋ 新增绑定</button>
    </header>
    ${expanded ? `<div class="metric-catalog-bindings">${bindings.length
      ? bindings.map((record) => metricBindingCard(record, source, mode)).join('')
      : '<div class="empty-state compact"><strong>还没有指标绑定</strong><span>点击“新增绑定”为该数据源配置指标。</span></div>'}</div>` : ''}
  </article>`
}

function metricCatalogView(source) {
  if (state.metricCatalogMode === 'metric') {
    const groups = metricDefinitionGroups()
    if (!groups.length) return '<div class="empty-state"><strong>还没有指标</strong><span>点击右上角“新建指标”创建第一条逻辑指标及数据源绑定。</span></div>'
    return `<div class="metric-catalog-list">${groups.map((group) => metricGroupShell({
      key: group.key,
      title: group.name,
      subtitle: group.description || '未填写业务口径',
      meta: `<span class="tag">${escapeHtml(group.topic)}</span><span>${group.bindings.length} 个数据源</span>`,
      bindings: group.bindings,
      source,
      mode: 'metric',
      defaults: {
        name: group.name,
        description: group.description || '',
        topic: group.topic,
        aliases: group.aliases || '',
        unit: group.unit || ''
      }
    })).join('')}</div>`
  }

  const dataSources = state.records.datasources
  if (!dataSources.length) return '<div class="empty-state"><strong>还没有数据源</strong><span>请先在数据源管理中接入业务数据库。</span></div>'
  return `<div class="metric-catalog-list">${dataSources.map((dataSource) => {
    const bindings = state.records.metrics.filter((record) => Number(record.data_source_id) === Number(dataSource.id))
    const enterprise = state.enterprises.find((item) => Number(item.id) === Number(dataSource.enterprise_id))
    return metricGroupShell({
      key: `source:${dataSource.id}`,
      title: dataSource.name,
      subtitle: `${enterprise?.name || '未知企业'} · ${dataSource.database}`,
      meta: `<span>${bindings.length} 个指标</span>`,
      bindings,
      source,
      mode: 'datasource',
      defaults: { data_source_id: dataSource.id }
    })
  }).join('')}</div>`
}

function renderDataSourceRow(record, source) {
  const host = `${record.host || '—'}:${record.port || '—'}`
  const enterprise = state.enterprises.find((item) => Number(item.id) === Number(record.enterprise_id))
  return `
    <tr data-search="${escapeHtml(recordSearchText(record))}">
      <td><span class="cell-title">${escapeHtml(record.name)}</span><span class="cell-subtitle">序号 ${escapeHtml(dataSourceDisplayNumber(record.id))}</span></td>
      <td><span class="tag success">${escapeHtml((record.db_type || 'mysql').toUpperCase())}</span></td>
      <td>${escapeHtml(host)}</td>
      <td>${escapeHtml(record.database || '—')}</td>
      <td><span class="cell-title">${escapeHtml(enterprise?.name || '未知企业')}</span></td>
      <td>${source ? '<span class="tag success">已接入</span>' : '<span class="tag warning">样例</span>'}</td>
      <td>${rowActions('datasources', record.id, source)}</td>
    </tr>`
}

function roleLabel(role) {
  return { admin: '管理员', analyst: '分析师', user: '普通用户' }[role] || role || '普通用户'
}

function renderUserRow(record, source) {
  return `
    <tr data-search="${escapeHtml(recordSearchText(record))}">
      <td><span class="cell-title">${escapeHtml(record.username)}</span><span class="cell-subtitle">ID ${escapeHtml(record.id)}</span></td>
      <td><span class="tag ${record.role === 'admin' ? '' : 'neutral'}">${escapeHtml(roleLabel(record.role))}</span></td>
      <td><span class="tag success">正常</span></td>
      <td>${source ? '来自业务数据库' : '前端样例账户'}</td>
      <td>${rowActions('users', record.id, source)}</td>
    </tr>`
}

function renderEnterpriseRow(record, source) {
  const dataSources = state.records.datasources.filter(
    (item) => Number(item.enterprise_id) === Number(record.id)
  )
  const expanded = state.expandedEnterpriseIds.includes(Number(record.id))
  const active = dataSources.some((item) => Number(item.id) === Number(state.selectedDataSourceId))
  const search = `${recordSearchText(record)} ${dataSources.map(recordSearchText).join(' ')}`
  const children = dataSources.length
    ? `<div class="enterprise-source-grid">${dataSources.map((item) => `
        <button class="enterprise-source-card ${Number(item.id) === Number(state.selectedDataSourceId) ? 'active' : ''}" type="button" data-select-global-source="${escapeHtml(item.id)}" aria-pressed="${Number(item.id) === Number(state.selectedDataSourceId)}">
          <div><strong>${escapeHtml(item.name)}</strong><span>${escapeHtml((item.db_type || 'mysql').toUpperCase())} · ${escapeHtml(item.host)}:${escapeHtml(item.port)}</span></div>
          <div><span>${escapeHtml(item.database)}</span><small>数据源序号 ${escapeHtml(dataSourceDisplayNumber(item.id))}</small></div>
        </button>`).join('')}</div>`
    : '<div class="empty-state compact"><strong>暂无下属数据源</strong><span>请在数据源管理中将数据源关联到该企业。</span></div>'
  return `<tr data-search="${escapeHtml(search)}">
    <td><button class="enterprise-toggle" type="button" data-toggle-enterprise="${escapeHtml(record.id)}" aria-expanded="${expanded}"><span>${expanded ? '▾' : '▸'}</span><span><strong>${escapeHtml(record.name)}</strong><small>企业序号 ${escapeHtml(enterpriseDisplayNumber(record.id))}</small></span></button></td>
    <td><span class="tag ${dataSources.length ? 'success' : 'neutral'}">${dataSources.length} 个数据源</span>${active ? '<span class="tag">当前空间</span>' : ''}</td>
    <td>${rowActions('enterprises', record.id, source)}</td>
  </tr>${expanded ? `<tr class="enterprise-detail-row" data-search="${escapeHtml(search)}"><td colspan="3">${children}</td></tr>` : ''}`
}

function departmentChildren(record, records = state.records.departments) {
  return records.filter((item) => Number(item.parent_id) === Number(record.id))
}

function renderDepartmentRow(record, source, depth = 0, visited = new Set()) {
  if (visited.has(Number(record.id))) return ''
  const nextVisited = new Set(visited).add(Number(record.id))
  const enterprise = state.enterprises.find((item) => Number(item.id) === Number(record.enterprise_id))
  const children = departmentChildren(record).filter(
    (item) => Number(item.enterprise_id) === Number(record.enterprise_id)
  )
  const expanded = state.expandedDepartmentIds.includes(Number(record.id))
  const toggle = children.length
    ? `<button class="department-tree-toggle" type="button" data-toggle-department="${escapeHtml(record.id)}" aria-label="${expanded ? '收起' : '展开'}${escapeHtml(record.name)}" aria-expanded="${expanded}">${expanded ? '▾' : '▸'}</button>`
    : '<span class="department-tree-spacer" aria-hidden="true"></span>'
  const row = `<tr data-search="${escapeHtml(`${recordSearchText(record)} ${enterprise?.name || ''}`)}">
    <td><div class="department-tree-cell" style="--department-depth:${Math.max(0, depth)}">${toggle}<button class="department-open-button" type="button" data-open-department="${escapeHtml(record.id)}"><span class="cell-title">${escapeHtml(record.name)}</span><span class="cell-subtitle">部门序号 ${escapeHtml(record.id)}</span></button></div></td>
    <td><span class="cell-title">${escapeHtml(enterprise?.name || '未知企业')}</span></td>
    <td>${rowActions('departments', record.id, source)}</td>
  </tr>`
  if (!expanded || !children.length) return row
  return row + children.map((child) => renderDepartmentRow(child, source, depth + 1, nextVisited)).join('')
}

function renderDepartmentTree(source) {
  const records = state.records.departments
  const byId = new Map(records.map((item) => [Number(item.id), item]))
  const roots = records.filter((item) => {
    const parent = item.parent_id ? byId.get(Number(item.parent_id)) : null
    return !parent || Number(parent.enterprise_id) !== Number(item.enterprise_id)
  })
  return roots.map((record) => renderDepartmentRow(record, source)).join('')
}

function rowActions(entity, id, source, deletable = true) {
  return `<div class="inline-actions">
    <button class="button small" type="button" data-edit-entity="${entity}" data-id="${escapeHtml(id)}">编辑</button>
    ${deletable ? `<button class="button small danger" type="button" data-delete-entity="${entity}" data-id="${escapeHtml(id)}">删除</button>` : ''}
    ${source ? '' : '<span class="cell-subtitle">预览</span>'}
  </div>`
}

function managementTable(entity) {
  const records = state.records[entity]
  const source = state.recordsFromApi[entity]
  if (!records.length) {
    return `<div class="empty-state"><div class="empty-symbol">◇</div><strong>还没有数据</strong><span>点击右上角按钮创建第一条记录。</span></div>`
  }
  if (entity === 'metrics') {
    return metricCatalogView(source)
  }
  if (entity === 'datasources') {
    return `<div class="table-scroll"><table class="data-table"><thead><tr><th>数据源</th><th>类型</th><th>连接地址</th><th>数据库</th><th>所属企业</th><th>状态</th><th>操作</th></tr></thead><tbody>${records.map((record) => renderDataSourceRow(record, source)).join('')}</tbody></table></div>`
  }
  if (entity === 'enterprises') {
    const unique = Array.from(new Map(records.map((record) => [Number(record.id), record])).values())
    return `<div class="table-scroll"><table class="data-table enterprise-table"><thead><tr><th>企业</th><th>下属数据源</th><th>操作</th></tr></thead><tbody>${unique.map((record) => renderEnterpriseRow(record, source)).join('')}</tbody></table></div>`
  }
  if (entity === 'departments') {
    return `<div class="table-scroll"><table class="data-table department-tree-table"><thead><tr><th>部门</th><th>所属企业</th><th>操作</th></tr></thead><tbody>${renderDepartmentTree(source)}</tbody></table></div>`
  }
  return `<div class="table-scroll"><table class="data-table"><thead><tr><th>用户</th><th>角色</th><th>状态</th><th>来源</th><th>操作</th></tr></thead><tbody>${records.map((record) => renderUserRow(record, source)).join('')}</tbody></table></div>`
}

function knowledgeCategoryLabel(category) {
  return { table: '表说明', field: '字段含义', rule: '分析规则', question: '常见问题' }[category] || category
}

function knowledgeSourceGroups() {
  const sources = state.records.datasources.map((source) => {
    const enterprise = state.enterprises.find((item) => Number(item.id) === Number(source.enterprise_id))
    return {
      key: `source:${source.id}`,
      source,
      title: source.name,
      subtitle: `${enterprise?.name || '未知企业'} · ${source.database || '未配置数据库'}`,
      documents: state.knowledgeDocuments.filter(
        (document) => Number(document.data_source_id) === Number(source.id)
      )
    }
  })
  const unbound = state.knowledgeDocuments.filter((document) => !document.data_source_id)
  if (unbound.length) {
    sources.push({
      key: 'source:unbound',
      source: null,
      title: '未绑定数据源',
      subtitle: '历史通用知识，请编辑后绑定到具体数据源',
      documents: unbound
    })
  }
  return sources
}

const knowledgeCategories = ['table', 'field', 'rule', 'question']

function knowledgeCategoryGroup(group, category) {
  const documents = group.documents.filter((document) => document.category === category)
  const key = `${group.key}:category:${category}`
  const expanded = state.expandedKnowledgeCategoryKeys.includes(key)
  const hasDocuments = documents.length > 0
  const toggle = hasDocuments
    ? `<button class="knowledge-category-toggle" type="button" data-toggle-knowledge-category="${escapeHtml(key)}" aria-expanded="${expanded}" aria-label="${expanded ? '收起' : '展开'}${escapeHtml(knowledgeCategoryLabel(category))}">${expanded ? '▾' : '▸'}</button>`
    : '<span class="knowledge-category-toggle-spacer" aria-hidden="true"></span>'
  const rows = documents.map((document) => `
    <tr data-search="${escapeHtml(`${document.title} ${document.content}`.toLowerCase())}">
      <td><span class="cell-title">${escapeHtml(document.title)}</span><span class="cell-subtitle">ID ${escapeHtml(document.id)}</span></td>
      <td>${escapeHtml(document.content)}</td>
      <td><div class="inline-actions">
        <button class="button small" type="button" data-edit-knowledge="${escapeHtml(document.id)}">编辑</button>
        <button class="button small danger" type="button" data-delete-knowledge="${escapeHtml(document.id)}">删除</button>
      </div></td>
    </tr>`).join('')
  return `<section class="knowledge-category-group">
    <div class="knowledge-category-header">
      <div>${toggle}<strong>${escapeHtml(knowledgeCategoryLabel(category))}</strong></div>
      <span>${documents.length} 条</span>
    </div>
    ${expanded ? `<div class="knowledge-category-detail"><div class="table-scroll"><table class="data-table knowledge-category-table"><thead><tr><th>标题</th><th>内容</th><th>操作</th></tr></thead><tbody>${rows}</tbody></table></div></div>` : ''}
  </section>`
}

function knowledgeSourceGroup(group) {
  const expanded = state.expandedKnowledgeSourceIds.includes(group.key)
  const hasDocuments = group.documents.length > 0
  const toggle = hasDocuments
    ? `<button class="knowledge-source-toggle" type="button" data-toggle-knowledge-source="${escapeHtml(group.key)}" aria-expanded="${expanded}" aria-label="${expanded ? '收起' : '展开'}${escapeHtml(group.title)}">${expanded ? '▾' : '▸'}</button>`
    : '<span class="knowledge-source-toggle-spacer" aria-hidden="true"></span>'
  return `<article class="knowledge-source-group" data-search="${escapeHtml(`${group.title} ${group.subtitle} ${group.documents.map((item) => `${item.title} ${item.content}`).join(' ')}`.toLowerCase())}">
    <div class="knowledge-source-header">
      <div class="knowledge-source-identity">${toggle}<div><strong>${escapeHtml(group.title)}</strong><small>${escapeHtml(group.subtitle)}</small></div></div>
      <div class="knowledge-source-meta"><strong>${group.documents.length} 条知识</strong></div>
    </div>
    ${expanded ? `<div class="knowledge-source-detail"><div class="knowledge-category-groups">${knowledgeCategories.map((category) => knowledgeCategoryGroup(group, category)).join('')}</div></div>` : ''}
  </article>`
}

function knowledgeDocumentsPanel() {
  const groups = knowledgeSourceGroups()
  const documents = state.knowledgeDocuments
  return `
    <section class="table-panel knowledge-documents-panel">
      <div class="table-toolbar">
        <div><strong>数据字典与分析规则</strong><span class="cell-subtitle">按数据源分类；展开后查看进入 RAG 的表说明、字段含义与分析规则</span></div>
        <span class="data-source-note">${groups.length} 个数据源分组 · ${documents.length} 条知识</span>
      </div>
      ${groups.length ? `<div class="knowledge-source-groups">${groups.map(knowledgeSourceGroup).join('')}</div>` : '<div class="empty-state compact"><strong>还没有数据源知识分组</strong><span>接入数据源后可自动生成数据字典与分析规则。</span></div>'}
    </section>`
}

function dataSourceImportIsRunning(job = state.dataSourceImportJob) {
  return Boolean(job && ['queued', 'processing'].includes(job.status))
}

function dataSourceImportSeenKey(job) {
  return `atlas-data-source-import-seen:${state.currentUserId || 'unknown'}:${job?.id || 'unknown'}`
}

function dataSourceImportStatusHtml() {
  const job = state.dataSourceImportJob
  if (!job) return ''
  const failed = job.status === 'failed'
  const completed = job.status === 'completed'
  const label = failed
    ? `接入失败：${job.error_message || job.message}`
    : completed
      ? '数据源接入成功'
      : job.message || '数据源处理中'
  return `<button class="data-source-import-chip ${failed ? 'failed' : completed ? 'completed' : 'processing'}" type="button" id="data-source-import-status" title="点击查看处理详情">
    ${dataSourceImportIsRunning(job) ? '<span class="spinner dark" aria-hidden="true"></span>' : `<span aria-hidden="true">${failed ? '!' : '✓'}</span>`}
    <span>${escapeHtml(label)}</span>
  </button>`
}

function closeDataSourceImportModal() {
  state.dataSourceImportModalOpen = false
  state.dataSourceImportDismissed = dataSourceImportIsRunning()
  closeModal()
  if (state.view === 'datasources') renderManagement('datasources')
}

function bindDataSourceImportModalClose() {
  document.querySelector('#close-modal')?.addEventListener('click', closeDataSourceImportModal)
  document.querySelector('#cancel-modal')?.addEventListener('click', closeDataSourceImportModal)
  modalLayer.onclick = (event) => {
    if (event.target === modalLayer) closeDataSourceImportModal()
  }
}

function openDataSourceImportModal() {
  if (state.dataSourceImportJob) {
    renderDataSourceImportProgressModal()
    return
  }
  state.dataSourceImportModalOpen = true
  state.dataSourceImportDismissed = false
  modalLayer.className = 'modal-layer open'
  modalLayer.setAttribute('aria-hidden', 'false')
  modalLayer.innerHTML = `
    <section class="modal data-source-import-modal" role="dialog" aria-modal="true" aria-labelledby="data-source-import-title">
      <header class="modal-header">
        <div><h2 id="data-source-import-title">上传 SQL 接入数据源</h2><p>文件名使用“企业名-数据源名.sql”，平台会自动创建或匹配企业。</p></div>
        <button class="icon-button" type="button" id="close-modal" aria-label="关闭">×</button>
      </header>
      <form id="data-source-import-form">
        <div class="modal-body">
          <div class="form-grid">
            <div class="form-group full"><label for="import-sql-file">SQL 初始化文件 *</label><label class="sql-upload-dropzone" id="sql-upload-dropzone" for="import-sql-file"><span class="sql-upload-symbol">↑</span><span class="sql-upload-copy"><strong>选择 .sql 文件</strong><small>文件名格式：企业名-数据源名.sql；UTF-8 编码，最大 5 MB</small></span></label><input class="visually-hidden" id="import-sql-file" name="sql_file" type="file" accept=".sql,text/sql,application/sql" required /></div>
          </div>
          <div class="import-safety-note">为保护现有业务数据，平台不会覆盖已存在的数据库，也不会执行文件中的账号授权、删除数据库或任意管理命令。</div>
        </div>
        <footer class="modal-footer"><button class="button" type="button" id="cancel-modal">取消</button><button class="button primary" type="submit">开始上传并接入</button></footer>
      </form>
    </section>`
  bindDataSourceImportModalClose()
  document.querySelector('#import-sql-file')?.addEventListener('change', (event) => {
    renderSelectedSqlFile(event.target.files?.[0])
  })
  document.querySelector('#data-source-import-form')?.addEventListener('submit', startDataSourceImport)
}

function formatUploadFileSize(bytes) {
  if (!Number.isFinite(bytes) || bytes < 1024) return `${bytes || 0} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
}

function parseDataSourceImportFileName(fileName) {
  const safeName = String(fileName || '').split(/[\\/]/).pop().trim()
  if (!safeName.toLowerCase().endsWith('.sql')) return null
  const stem = safeName.slice(0, -4).trim()
  const separator = stem.indexOf('-')
  if (separator <= 0 || separator >= stem.length - 1) return null
  const enterpriseName = stem.slice(0, separator).trim()
  const dataSourceName = stem.slice(separator + 1).trim()
  return enterpriseName && dataSourceName ? { enterpriseName, dataSourceName } : null
}

function renderSelectedSqlFile(file) {
  const dropzone = document.querySelector('#sql-upload-dropzone')
  if (!dropzone || !file) return
  const parsed = parseDataSourceImportFileName(file.name)
  if (!parsed) {
    dropzone.classList.remove('selected')
    dropzone.classList.add('invalid')
    dropzone.innerHTML = `
      <span class="sql-upload-symbol">!</span>
      <span class="sql-upload-copy"><strong>文件名格式不正确</strong><small>请改为“企业名-数据源名.sql”，例如：星辰智造有限公司-运营数据.sql</small></span>
      <span class="sql-upload-change">重新选择</span>`
    return
  }
  dropzone.classList.remove('invalid')
  dropzone.classList.add('selected')
  dropzone.innerHTML = `
    <span class="sql-upload-symbol">✓</span>
    <span class="sql-upload-copy"><strong>${escapeHtml(file.name)}</strong><small>企业：${escapeHtml(parsed.enterpriseName)} · 数据源：${escapeHtml(parsed.dataSourceName)} · ${escapeHtml(formatUploadFileSize(file.size))}</small></span>
    <span class="sql-upload-change">更换文件</span>`
}

function importStepClass(stepIndex, stage, status) {
  let stageIndex = { uploaded: 0, building: 1, metrics: 2, completed: 3 }[stage] ?? 0
  if (stage === 'failed') {
    const progress = Number(state.dataSourceImportJob?.progress) || 10
    stageIndex = progress >= 70 ? 2 : progress >= 25 ? 1 : 0
  }
  if (status === 'completed' || stepIndex < stageIndex) return 'completed'
  if (status === 'failed' && stepIndex === Math.min(stageIndex, 2)) return 'failed'
  if (stepIndex === stageIndex) return 'active'
  return 'pending'
}

function renderDataSourceImportProgressModal() {
  const job = state.dataSourceImportJob
  if (!job) {
    openDataSourceImportModal()
    return
  }
  state.dataSourceImportModalOpen = true
  state.dataSourceImportDismissed = false
  const steps = [
    ['SQL 文件上传', '校验文件格式、目标数据库和允许执行的语句'],
    ['数据源建设', '创建数据库和表，并配置后端托管的只读访问'],
    ['指标与知识生成', '使用当前账号的 DeepSeek API 生成指标、数据字典和分析规则']
  ]
  const success = job.status === 'completed'
  const failed = job.status === 'failed'
  modalLayer.className = 'modal-layer open'
  modalLayer.setAttribute('aria-hidden', 'false')
  modalLayer.innerHTML = `
    <section class="modal data-source-progress-modal" role="dialog" aria-modal="true" aria-labelledby="data-source-progress-title">
      <header class="modal-header">
        <div><h2 id="data-source-progress-title">${success ? '数据源接入成功' : failed ? '数据源接入未完成' : '正在接入数据源'}</h2><p>${job.enterprise_name ? `${escapeHtml(job.enterprise_name)} · ` : ''}${escapeHtml(job.data_source_name || '新数据源')}${job.database_name ? ` · ${escapeHtml(job.database_name)}` : ''}</p></div>
        <button class="icon-button" type="button" id="close-modal" aria-label="关闭">×</button>
      </header>
      <div class="modal-body">
        <div class="data-source-import-result ${success ? 'success' : failed ? 'failed' : ''}">
          ${success ? '<span class="import-result-icon">✓</span><strong>数据源接入成功</strong><p>数据库、只读连接、指标、数据字典和分析规则已经准备完成。</p>' : failed ? `<span class="import-result-icon">!</span><strong>处理失败</strong><p>${escapeHtml(job.error_message || job.message || '请检查后端日志')}</p>` : `<span class="spinner dark import-main-spinner" aria-hidden="true"></span><strong>${escapeHtml(job.message || '正在处理')}</strong><p>可以关闭弹窗，后台任务不会中断。</p>`}
        </div>
        <div class="data-source-import-steps">
          ${steps.map(([title, description], index) => {
            const className = importStepClass(index, job.stage, job.status)
            return `<div class="data-source-import-step ${className}"><span class="import-step-icon">${className === 'completed' ? '✓' : className === 'failed' ? '!' : className === 'active' ? '<i class="spinner dark"></i>' : index + 1}</span><div><strong>${title}</strong><small>${description}</small></div></div>`
          }).join('')}
        </div>
        <div class="import-progress-track"><span style="width:${Math.max(4, Math.min(100, Number(job.progress) || 0))}%"></span></div>
        ${success ? `<p class="import-completion-detail">已自动创建 ${escapeHtml(job.metrics_created || 0)} 项指标和 ${escapeHtml(job.knowledge_documents_created || 0)} 条数据字典 / 分析规则，窗口即将关闭。</p>` : ''}
      </div>
      <footer class="modal-footer">${failed ? '<button class="button primary" type="button" id="retry-data-source-import">重新上传</button>' : ''}${dataSourceImportIsRunning(job) ? '<button class="button danger" type="button" id="cancel-data-source-import">取消接入</button>' : ''}<button class="button" type="button" id="cancel-modal">${failed ? '关闭' : success ? '关闭' : '转到后台处理'}</button></footer>
    </section>`
  bindDataSourceImportModalClose()
  document.querySelector('#retry-data-source-import')?.addEventListener('click', () => {
    state.dataSourceImportJob = null
    openDataSourceImportModal()
  })
  document.querySelector('#cancel-data-source-import')?.addEventListener('click', () => cancelDataSourceImport())
}

async function cancelDataSourceImport({ silent = false, requireConfirmation = true, cancelLatest = false } = {}) {
  let job = state.dataSourceImportJob
  if ((!job || !dataSourceImportIsRunning(job)) && cancelLatest && state.backendOnline && state.authToken) {
    try {
      const latest = await apiRequest('/api/admin/data_sources/import-jobs/latest', { timeout: 10000 })
      if (dataSourceImportIsRunning(latest)) job = latest
    } catch {
      // No unfinished job exists, or the backend is already unavailable.
    }
  }
  if (!job || !dataSourceImportIsRunning(job)) return true
  if (requireConfirmation && !window.confirm('确定取消本次数据源接入吗？已创建的未完成数据库、数据源和指标将被回退。')) return false
  const button = document.querySelector('#cancel-data-source-import')
  if (button) {
    button.disabled = true
    button.textContent = '正在取消…'
  }
  if (!job.id) state.dataSourceImportUploadController?.abort()
  try {
    if (job.id && state.backendOnline) {
      await apiRequest(`/api/admin/data_sources/import-jobs/${job.id}/cancel`, {
        method: 'POST',
        timeout: 30000
      })
    }
  } catch (error) {
    if (!silent) {
      toast(error.message || '取消接入失败', 'error', 5000)
      if (button) {
        button.disabled = false
        button.textContent = '取消接入'
      }
      return false
    }
  }
  if (state.dataSourceImportPollingTimer) window.clearTimeout(state.dataSourceImportPollingTimer)
  state.dataSourceImportPollingTimer = null
  state.dataSourceImportUploadController = null
  state.dataSourceImportJob = null
  state.dataSourceImportModalOpen = false
  state.dataSourceImportDismissed = false
  closeModal()
  if (state.view === 'datasources') renderManagement('datasources')
  if (!silent) toast('数据源接入已取消，未完成内容正在回退', 'success')
  return true
}

async function startDataSourceImport(event) {
  event.preventDefault()
  const form = event.currentTarget
  const file = form.querySelector('#import-sql-file')?.files?.[0]
  if (!file) {
    toast('请选择 SQL 文件', 'warning')
    return
  }
  const parsedFileName = parseDataSourceImportFileName(file.name)
  if (!parsedFileName) {
    toast('SQL 文件名必须为“企业名-数据源名.sql”', 'warning', 5200)
    return
  }
  const dataSourceName = parsedFileName.dataSourceName
  state.dataSourceImportJob = {
    id: null,
    data_source_name: dataSourceName,
    enterprise_name: parsedFileName.enterpriseName,
    database_name: null,
    status: 'processing',
    stage: 'uploaded',
    progress: 5,
    message: 'SQL 文件上传中',
    metrics_created: 0,
    knowledge_documents_created: 0
  }
  renderDataSourceImportProgressModal()
  const uploadController = new AbortController()
  state.dataSourceImportUploadController = uploadController
  try {
    const importParams = new URLSearchParams({
      file_name: file.name
    })
    const job = await apiRequest(`/api/admin/data_sources/import?${importParams}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/sql' },
      body: file,
      timeout: 30000,
      signal: uploadController.signal
    })
    state.dataSourceImportUploadController = null
    state.dataSourceImportJob = { ...job, enterprise_name: parsedFileName.enterpriseName }
    if (job.status === 'cancelled') {
      if (state.dataSourceImportPollingTimer) window.clearTimeout(state.dataSourceImportPollingTimer)
      state.dataSourceImportPollingTimer = null
      state.dataSourceImportJob = null
      state.dataSourceImportModalOpen = false
      closeModal()
      if (state.view === 'datasources') renderManagement('datasources')
      return
    }
    if (state.dataSourceImportModalOpen) renderDataSourceImportProgressModal()
    scheduleDataSourceImportPoll()
    if (state.view === 'datasources') renderManagement('datasources')
  } catch (error) {
    state.dataSourceImportUploadController = null
    if (error.name === 'RequestCancelledError') return
    state.dataSourceImportJob = {
      ...state.dataSourceImportJob,
      status: 'failed',
      stage: 'failed',
      progress: 100,
      message: '文件上传失败',
      error_message: error.message || '上传失败'
    }
    renderDataSourceImportProgressModal()
  }
}

function scheduleDataSourceImportPoll(delay = 1300) {
  if (state.dataSourceImportPollingTimer) window.clearTimeout(state.dataSourceImportPollingTimer)
  if (!dataSourceImportIsRunning() || !state.dataSourceImportJob?.id) return
  state.dataSourceImportPollingTimer = window.setTimeout(pollDataSourceImportJob, delay)
}

async function pollDataSourceImportJob() {
  const jobId = state.dataSourceImportJob?.id
  if (!jobId) return
  try {
    const previousEnterpriseName = state.dataSourceImportJob?.enterprise_name
    const responseJob = await apiRequest(`/api/admin/data_sources/import-jobs/${jobId}`, { timeout: 12000 })
    const job = { ...responseJob, enterprise_name: previousEnterpriseName }
    state.dataSourceImportJob = job
    if (job.status === 'cancelled') {
      state.dataSourceImportJob = null
      state.dataSourceImportModalOpen = false
      state.dataSourceImportDismissed = false
      closeModal()
      if (state.view === 'datasources') renderManagement('datasources')
      return
    }
    if (state.dataSourceImportModalOpen) renderDataSourceImportProgressModal()
    if (state.view === 'datasources') renderManagement('datasources')
    if (job.status === 'completed') {
      window.localStorage.setItem(dataSourceImportSeenKey(job), '1')
      clearDashboardCache()
      await activateImportedDataSource(job)
      state.dataSourceImportJob = job
      renderDataSourceImportProgressModal()
      window.setTimeout(() => {
        if (state.dataSourceImportJob?.id !== job.id || state.dataSourceImportJob?.status !== 'completed') return
        state.dataSourceImportJob = null
        state.dataSourceImportModalOpen = false
        closeModal()
        if (state.view === 'datasources') renderManagement('datasources')
        toast(`数据源接入成功，已生成 ${job.metrics_created || 0} 项指标和 ${job.knowledge_documents_created || 0} 条知识`, 'success', 5200)
      }, 2200)
      return
    }
    if (job.status === 'failed') {
      return
    }
    scheduleDataSourceImportPoll()
  } catch (error) {
    if (state.view === 'datasources') toast(error.message || '无法读取数据源处理状态', 'error')
    scheduleDataSourceImportPoll(3000)
  }
}

async function activateImportedDataSource(job) {
  await Promise.all([loadRecords('datasources'), loadRecords('metrics'), loadEnterprises()])
  state.dashboardDataSources = structuredClone(state.records.datasources)
  if (job?.data_source_id) {
    await switchGlobalDataSource(job.data_source_id, {
      reloadAnalytics: ['dashboard', 'reports'].includes(state.view),
      resetConversation: true
    })
  } else {
    selectDashboardDataSource()
    syncWorkspaceEnterprise()
  }
}

async function loadLatestDataSourceImportJob() {
  if (!state.currentUserId) return
  try {
    const job = await apiRequest('/api/admin/data_sources/import-jobs/latest', { timeout: 10000 })
    if (job.status === 'cancelled') {
      state.dataSourceImportJob = null
      if (state.dataSourceImportPollingTimer) window.clearTimeout(state.dataSourceImportPollingTimer)
      state.dataSourceImportPollingTimer = null
      if (state.view === 'datasources') renderManagement('datasources')
      return
    }
    if (job.status === 'completed' && window.localStorage.getItem(dataSourceImportSeenKey(job)) === '1') return
    state.dataSourceImportJob = job
    if (dataSourceImportIsRunning(job)) scheduleDataSourceImportPoll(300)
    else if (job.status === 'completed') {
      await activateImportedDataSource(job)
      window.localStorage.setItem(dataSourceImportSeenKey(job), '1')
      renderDataSourceImportProgressModal()
      window.setTimeout(() => {
        if (state.dataSourceImportJob?.id !== job.id) return
        state.dataSourceImportJob = null
        state.dataSourceImportModalOpen = false
        closeModal()
        if (state.view === 'datasources') renderManagement('datasources')
      }, 2200)
    }
    if (state.view === 'datasources') renderManagement('datasources')
  } catch {
    // A 404 simply means this user has never imported a SQL data source.
  }
}

function departmentProgress(value) {
  const progress = Math.min(100, Math.max(0, Number(value) || 0))
  return `<div class="department-progress" aria-label="进度 ${progress}%"><div><span style="width:${progress}%"></span></div><strong>${progress}%</strong></div>`
}

function renderDepartmentEmployeeView(workspace) {
  const employees = workspace.employees || []
  const tasks = workspace.tasks || []
  if (!employees.length) {
    return '<div class="empty-state compact"><strong>当前部门还没有员工</strong><span>员工只会显示在其直接所属部门，不包含下级部门。</span></div>'
  }
  return `<div class="department-employee-list">${employees.map((employee) => {
    const task = tasks.find((item) => Number(item.id) === Number(employee.task_id))
    return `<article class="department-employee-row">
      <div class="department-person"><span>${escapeHtml(employee.name.slice(0, 1) || '员')}</span><div><strong>${escapeHtml(employee.name)}</strong><small>${escapeHtml(employee.title || '未设置岗位')}</small></div></div>
      <div class="department-employee-task"><small>负责任务</small><strong>${escapeHtml(task?.name || '暂未分配任务')}</strong></div>
      <div class="department-employee-progress">${task ? departmentProgress(task.progress) : '<span class="cell-subtitle">暂无进度</span>'}</div>
      <div class="inline-actions"><button class="button small" type="button" data-edit-department-employee="${escapeHtml(employee.id)}">编辑</button><button class="button small danger" type="button" data-delete-department-employee="${escapeHtml(employee.id)}">删除</button></div>
    </article>`
  }).join('')}</div>`
}

function renderDepartmentTaskView(workspace) {
  const tasks = workspace.tasks || []
  const employees = workspace.employees || []
  if (!tasks.length) {
    return '<div class="empty-state compact"><strong>当前部门还没有任务</strong><span>创建任务后，可以将当前部门员工分配给该任务。</span></div>'
  }
  return `<div class="department-task-board">${tasks.map((task) => {
    const participants = employees.filter((employee) => Number(employee.task_id) === Number(task.id))
    return `<article class="department-task-card">
      <header><div><strong>${escapeHtml(task.name)}</strong><p>${escapeHtml(task.description || '暂无任务说明')}</p></div><div class="inline-actions"><button class="button small" type="button" data-edit-department-task="${escapeHtml(task.id)}">编辑</button><button class="button small danger" type="button" data-delete-department-task="${escapeHtml(task.id)}">删除</button></div></header>
      ${departmentProgress(task.progress)}
      <div class="department-task-people"><small>参与员工 · ${participants.length} 人</small>${participants.length ? `<div>${participants.map((employee) => `<span>${escapeHtml(employee.name)}</span>`).join('')}</div>` : '<p>暂无员工负责此任务</p>'}</div>
    </article>`
  }).join('')}</div>`
}

function renderDepartmentWorkspace() {
  const department = state.departmentWorkspace?.department || state.records.departments.find(
    (item) => Number(item.id) === Number(state.currentDepartmentId)
  )
  if (!department) {
    state.currentDepartmentId = null
    renderManagement('departments')
    return
  }
  const enterprise = state.enterprises.find((item) => Number(item.id) === Number(department.enterprise_id))
  const workspace = state.departmentWorkspace || { department, employees: [], tasks: [] }
  const activeMode = state.departmentWorkspaceMode
  const actionLabel = activeMode === 'employees' ? '新增员工' : '新增任务'
  viewRoot.innerHTML = `
    ${pageHeading(
      department.name,
      `${enterprise?.name || '未知企业'} · 仅展示当前部门直属员工与任务，不包含任何下级部门`,
      `<button class="button" type="button" id="back-to-departments">← 返回部门树</button><button class="button" type="button" id="reload-department-workspace">↻ 刷新</button><button class="button primary" type="button" id="create-department-workspace-item">＋ ${actionLabel}</button>`
    )}
    <section class="department-workspace panel">
      <div class="department-workspace-toolbar">
        <div class="department-view-segmented" role="tablist" aria-label="部门详情视图">
          <button type="button" role="tab" data-department-mode="employees" aria-selected="${activeMode === 'employees'}" class="${activeMode === 'employees' ? 'active' : ''}">按员工 <span>${workspace.employees?.length || 0}</span></button>
          <button type="button" role="tab" data-department-mode="tasks" aria-selected="${activeMode === 'tasks'}" class="${activeMode === 'tasks' ? 'active' : ''}">按任务 <span>${workspace.tasks?.length || 0}</span></button>
        </div>
        <span class="data-source-note">数据范围：${escapeHtml(department.name)}本级</span>
      </div>
      <div class="department-workspace-content">${state.departmentWorkspaceLoading
        ? '<div class="empty-state compact"><span class="spinner dark" aria-hidden="true"></span><strong>正在读取部门数据…</strong></div>'
        : activeMode === 'employees' ? renderDepartmentEmployeeView(workspace) : renderDepartmentTaskView(workspace)}</div>
    </section>`
  document.querySelector('#back-to-departments').addEventListener('click', () => {
    state.currentDepartmentId = null
    state.departmentWorkspace = null
    renderManagement('departments')
  })
  document.querySelector('#reload-department-workspace').addEventListener('click', () => loadDepartmentWorkspace(true))
  document.querySelector('#create-department-workspace-item').addEventListener('click', () => {
    if (activeMode === 'employees') openDepartmentEmployeeModal()
    else openDepartmentTaskModal()
  })
  document.querySelectorAll('[data-department-mode]').forEach((button) => {
    button.addEventListener('click', () => {
      state.departmentWorkspaceMode = button.dataset.departmentMode
      renderDepartmentWorkspace()
    })
  })
  document.querySelectorAll('[data-edit-department-employee]').forEach((button) => {
    button.addEventListener('click', () => openDepartmentEmployeeModal(
      workspace.employees.find((item) => Number(item.id) === Number(button.dataset.editDepartmentEmployee))
    ))
  })
  document.querySelectorAll('[data-delete-department-employee]').forEach((button) => {
    button.addEventListener('click', () => deleteDepartmentWorkspaceItem('employees', Number(button.dataset.deleteDepartmentEmployee)))
  })
  document.querySelectorAll('[data-edit-department-task]').forEach((button) => {
    button.addEventListener('click', () => openDepartmentTaskModal(
      workspace.tasks.find((item) => Number(item.id) === Number(button.dataset.editDepartmentTask))
    ))
  })
  document.querySelectorAll('[data-delete-department-task]').forEach((button) => {
    button.addEventListener('click', () => deleteDepartmentWorkspaceItem('tasks', Number(button.dataset.deleteDepartmentTask)))
  })
}

async function openDepartmentWorkspace(departmentId) {
  state.currentDepartmentId = Number(departmentId)
  state.departmentWorkspace = null
  state.departmentWorkspaceLoading = true
  renderDepartmentWorkspace()
  await loadDepartmentWorkspace()
}

async function loadDepartmentWorkspace(showFeedback = false) {
  if (!state.currentDepartmentId) return
  if (!state.backendOnline) {
    state.departmentWorkspaceLoading = false
    renderDepartmentWorkspace()
    toast('后端不可用，无法读取部门员工与任务', 'error')
    return
  }
  state.departmentWorkspaceLoading = true
  renderDepartmentWorkspace()
  try {
    state.departmentWorkspace = await apiRequest(
      `/api/admin/departments/${state.currentDepartmentId}/workspace`,
      { timeout: 15000 }
    )
    if (showFeedback) toast('部门数据已刷新', 'success')
  } catch (error) {
    toast(error.message || '部门详情读取失败', 'error', 5000)
  } finally {
    state.departmentWorkspaceLoading = false
    if (state.view === 'departments' && state.currentDepartmentId) renderDepartmentWorkspace()
  }
}

function openDepartmentTaskModal(record = null) {
  modalLayer.className = 'modal-layer open'
  modalLayer.setAttribute('aria-hidden', 'false')
  modalLayer.innerHTML = `
    <section class="modal" role="dialog" aria-modal="true" aria-labelledby="department-task-modal-title">
      <header class="modal-header"><div><h2 id="department-task-modal-title">${record ? '编辑任务' : '新增任务'}</h2><p>任务仅属于当前部门，可由多名当前部门员工共同负责。</p></div><button class="icon-button" type="button" id="close-modal" aria-label="关闭">×</button></header>
      <form id="department-task-form"><div class="modal-body"><div class="form-grid">
        <div class="form-group full"><label for="department-task-name">任务名称 *</label><input class="field" id="department-task-name" name="name" value="${escapeHtml(record?.name || '')}" maxlength="120" required /></div>
        <div class="form-group full"><label for="department-task-description">任务说明</label><textarea class="textarea" id="department-task-description" name="description">${escapeHtml(record?.description || '')}</textarea></div>
        <div class="form-group full"><label for="department-task-progress">任务进度 *</label><div class="department-progress-editor"><input class="field" id="department-task-progress" name="progress" type="range" min="0" max="100" value="${escapeHtml(record?.progress ?? 0)}" /><output id="department-task-progress-output">${escapeHtml(record?.progress ?? 0)}%</output></div></div>
      </div></div><footer class="modal-footer"><button class="button" type="button" id="cancel-modal">取消</button><button class="button primary" type="submit">保存任务</button></footer></form>
    </section>`
  document.querySelector('#close-modal').addEventListener('click', closeModal)
  document.querySelector('#cancel-modal').addEventListener('click', closeModal)
  document.querySelector('#department-task-progress').addEventListener('input', (event) => {
    document.querySelector('#department-task-progress-output').textContent = `${event.target.value}%`
  })
  document.querySelector('#department-task-form').addEventListener('submit', (event) => saveDepartmentTask(event, record))
  modalLayer.onclick = (event) => { if (event.target === modalLayer) closeModal() }
  document.querySelector('#department-task-name').focus()
}

async function saveDepartmentTask(event, record) {
  event.preventDefault()
  const data = new FormData(event.currentTarget)
  const payload = { name: String(data.get('name') || '').trim(), description: String(data.get('description') || '').trim() || null, progress: Number(data.get('progress') || 0) }
  try {
    await apiRequest(`/api/admin/departments/${state.currentDepartmentId}/tasks${record ? `/${record.id}` : ''}`, {
      method: record ? 'PUT' : 'POST', body: JSON.stringify(payload), timeout: 15000
    })
    closeModal()
    await loadDepartmentWorkspace()
    toast(record ? '任务已更新' : '任务已创建', 'success')
  } catch (error) { toast(error.message || '任务保存失败', 'error', 5000) }
}

function openDepartmentEmployeeModal(record = null) {
  const tasks = state.departmentWorkspace?.tasks || []
  modalLayer.className = 'modal-layer open'
  modalLayer.setAttribute('aria-hidden', 'false')
  modalLayer.innerHTML = `
    <section class="modal" role="dialog" aria-modal="true" aria-labelledby="department-employee-modal-title">
      <header class="modal-header"><div><h2 id="department-employee-modal-title">${record ? '编辑员工' : '新增员工'}</h2><p>每名员工只能负责一项当前部门任务。</p></div><button class="icon-button" type="button" id="close-modal" aria-label="关闭">×</button></header>
      <form id="department-employee-form"><div class="modal-body"><div class="form-grid">
        <div class="form-group"><label for="department-employee-name">员工姓名 *</label><input class="field" id="department-employee-name" name="name" value="${escapeHtml(record?.name || '')}" maxlength="100" required /></div>
        <div class="form-group"><label for="department-employee-title">岗位</label><input class="field" id="department-employee-title" name="title" value="${escapeHtml(record?.title || '')}" maxlength="100" /></div>
        <div class="form-group full"><label for="department-employee-task">负责任务</label><select class="select" id="department-employee-task" name="task_id"><option value="">暂不分配</option>${tasks.map((task) => `<option value="${escapeHtml(task.id)}" ${Number(task.id) === Number(record?.task_id) ? 'selected' : ''}>${escapeHtml(task.name)} · ${escapeHtml(task.progress)}%</option>`).join('')}</select></div>
      </div></div><footer class="modal-footer"><button class="button" type="button" id="cancel-modal">取消</button><button class="button primary" type="submit">保存员工</button></footer></form>
    </section>`
  document.querySelector('#close-modal').addEventListener('click', closeModal)
  document.querySelector('#cancel-modal').addEventListener('click', closeModal)
  document.querySelector('#department-employee-form').addEventListener('submit', (event) => saveDepartmentEmployee(event, record))
  modalLayer.onclick = (event) => { if (event.target === modalLayer) closeModal() }
  document.querySelector('#department-employee-name').focus()
}

async function saveDepartmentEmployee(event, record) {
  event.preventDefault()
  const data = new FormData(event.currentTarget)
  const taskId = Number(data.get('task_id'))
  const payload = { name: String(data.get('name') || '').trim(), title: String(data.get('title') || '').trim() || null, task_id: taskId > 0 ? taskId : null }
  try {
    await apiRequest(`/api/admin/departments/${state.currentDepartmentId}/employees${record ? `/${record.id}` : ''}`, {
      method: record ? 'PUT' : 'POST', body: JSON.stringify(payload), timeout: 15000
    })
    closeModal()
    await loadDepartmentWorkspace()
    toast(record ? '员工信息已更新' : '员工已添加', 'success')
  } catch (error) { toast(error.message || '员工保存失败', 'error', 5000) }
}

async function deleteDepartmentWorkspaceItem(kind, id) {
  const collection = kind === 'tasks' ? state.departmentWorkspace?.tasks : state.departmentWorkspace?.employees
  const record = collection?.find((item) => Number(item.id) === Number(id))
  const label = kind === 'tasks' ? '任务' : '员工'
  if (!record || !window.confirm(`确定删除${label}“${record.name}”吗？`)) return
  try {
    await apiRequest(`/api/admin/departments/${state.currentDepartmentId}/${kind}/${id}`, { method: 'DELETE', timeout: 15000 })
    await loadDepartmentWorkspace()
    toast(`${label}已删除`, 'success')
  } catch (error) { toast(error.message || `${label}删除失败`, 'error', 5000) }
}

function renderManagement(entity) {
  if (entity === 'departments' && state.currentDepartmentId) {
    renderDepartmentWorkspace()
    return
  }
  const config = managementConfig[entity]
  const isPreview = !state.recordsFromApi[entity]
  const knowledgeAction = entity === 'metrics'
    ? `<button class="button" type="button" id="create-knowledge-document">＋ 新增字典 / 规则</button><button class="button" type="button" id="rebuild-knowledge" ${state.rebuildingKnowledge ? 'disabled' : ''}>${state.rebuildingKnowledge ? '正在重建…' : '重建知识库'}</button>`
    : ''
  const metricCatalogToggle = entity === 'metrics'
    ? `<div class="metric-catalog-segmented" role="group" aria-label="指标知识库分组方式">
        <button type="button" data-metric-catalog-mode="datasource" class="${state.metricCatalogMode === 'datasource' ? 'active' : ''}">按数据源</button>
        <button type="button" data-metric-catalog-mode="metric" class="${state.metricCatalogMode === 'metric' ? 'active' : ''}">按指标</button>
      </div>`
    : ''
  const knowledgeNote = entity === 'metrics' && state.knowledgeStatus
    ? `<span class="data-source-note">索引 ${escapeHtml(state.knowledgeStatus.indexed_count)} / 来源 ${escapeHtml(state.knowledgeStatus.source_count ?? state.knowledgeStatus.metric_count)}（指标 ${escapeHtml(state.knowledgeStatus.metric_count)} · 字典 ${escapeHtml(state.knowledgeStatus.document_count ?? 0)} · 表结构 ${escapeHtml(state.knowledgeStatus.schema_count ?? 0)}）· ${state.knowledgeStatus.synchronized ? '已同步' : '待重建'}</span>`
    : ''
  const importStatus = entity === 'datasources' ? dataSourceImportStatusHtml() : ''
  viewRoot.innerHTML = `
    ${pageHeading(
      config.title,
      config.description,
      `${metricCatalogToggle}${knowledgeAction}<button class="button" type="button" id="reload-records">↻ 重新载入</button><button class="button primary" type="button" id="create-record">＋ ${escapeHtml(config.buttonLabel)}</button>${importStatus}`,
      entity === 'metrics' ? 'metric-management-heading' : ''
    )}
    ${isPreview ? previewBanner(state.backendOnline ? '后端已连接，但该模块数据读取失败；当前展示样例记录。' : undefined) : ''}
    <section class="table-panel">
      <div class="table-toolbar">
        <div class="search-box"><input class="field" id="record-search" type="search" placeholder="${escapeHtml(config.searchPlaceholder)}" /></div>
        <span class="data-source-note">${entity === 'metrics' ? (state.metricCatalogMode === 'metric' ? `共 ${metricDefinitionGroups().length} 个指标` : `共 ${state.records.datasources.length} 个数据源`) : `共 ${state.records[entity].length} 条记录`}</span>${knowledgeNote}
      </div>
      <div id="management-table">${managementTable(entity)}</div>
    </section>
    ${entity === 'metrics' ? knowledgeDocumentsPanel() : ''}
  `

  document.querySelector('#record-search')?.addEventListener('input', (event) => {
    const query = event.target.value.trim().toLowerCase()
    document.querySelectorAll('#management-table [data-search]').forEach((item) => {
      if (item.classList.contains('metric-binding-card')) return
      item.hidden = Boolean(query) && !(item.dataset.search || '').includes(query)
    })
  })
  document.querySelector('#create-record')?.addEventListener('click', () => {
    // Departments must belong to an existing enterprise. SQL-file onboarding
    // is different: the backend derives and creates the enterprise from the
    // "企业名-数据源名.sql" filename, so an empty catalog must not block it.
    if (entity === 'departments' && !state.enterprises.length) {
      toast('请先在企业管理中创建企业', 'warning')
      return
    }
    if (entity === 'datasources') openDataSourceImportModal()
    else openRecordModal(entity)
  })
  document.querySelector('#data-source-import-status')?.addEventListener('click', () => {
    if (state.dataSourceImportJob) renderDataSourceImportProgressModal()
  })
  document.querySelector('#create-knowledge-document')?.addEventListener('click', () => openKnowledgeDocumentModal())
  document.querySelector('#rebuild-knowledge')?.addEventListener('click', rebuildKnowledgeBase)
  document.querySelector('#reload-records')?.addEventListener('click', async () => {
    await checkBackend()
    if (entity === 'enterprises') await loadEnterpriseManagement(true)
    else await loadRecords(entity, true)
    if (entity === 'metrics') await loadKnowledgeStatus()
    if (entity === 'datasources') await loadEnterprises()
  })
  document.querySelectorAll('[data-edit-entity]').forEach((button) => {
    button.addEventListener('click', () => {
      const id = String(button.dataset.id)
      const record = state.records[entity].find((item) => String(item.id) === id)
      openRecordModal(entity, record)
    })
  })
  document.querySelectorAll('[data-delete-entity]').forEach((button) => {
    button.addEventListener('click', () => {
      const record = state.records[entity].find((item) => String(item.id) === String(button.dataset.id))
      if (entity === 'datasources') openDataSourceDeleteDialog(record)
      else deleteRecord(entity, button.dataset.id)
    })
  })
  document.querySelectorAll('[data-toggle-enterprise]').forEach((button) => {
    button.addEventListener('click', () => {
      const id = Number(button.dataset.toggleEnterprise)
      state.expandedEnterpriseIds = state.expandedEnterpriseIds.includes(id)
        ? state.expandedEnterpriseIds.filter((item) => item !== id)
        : [...state.expandedEnterpriseIds, id]
      renderManagement('enterprises')
    })
  })
  document.querySelectorAll('[data-toggle-department]').forEach((button) => {
    button.addEventListener('click', () => {
      const id = Number(button.dataset.toggleDepartment)
      state.expandedDepartmentIds = state.expandedDepartmentIds.includes(id)
        ? state.expandedDepartmentIds.filter((item) => item !== id)
        : [...state.expandedDepartmentIds, id]
      renderManagement('departments')
    })
  })
  document.querySelectorAll('[data-open-department]').forEach((button) => {
    button.addEventListener('click', () => openDepartmentWorkspace(Number(button.dataset.openDepartment)))
  })
  document.querySelectorAll('[data-metric-catalog-mode]').forEach((button) => {
    button.addEventListener('click', () => {
      state.metricCatalogMode = button.dataset.metricCatalogMode
      state.expandedMetricGroupKeys = []
      window.localStorage.setItem('atlas-metric-catalog-mode', state.metricCatalogMode)
      renderManagement('metrics')
    })
  })
  document.querySelectorAll('[data-toggle-metric-group]').forEach((button) => {
    button.addEventListener('click', () => {
      const key = button.dataset.toggleMetricGroup
      state.expandedMetricGroupKeys = state.expandedMetricGroupKeys.includes(key)
        ? state.expandedMetricGroupKeys.filter((item) => item !== key)
        : [...state.expandedMetricGroupKeys, key]
      renderManagement('metrics')
    })
  })
  document.querySelectorAll('[data-toggle-knowledge-source]').forEach((button) => {
    button.addEventListener('click', () => {
      const key = button.dataset.toggleKnowledgeSource
      state.expandedKnowledgeSourceIds = state.expandedKnowledgeSourceIds.includes(key)
        ? state.expandedKnowledgeSourceIds.filter((item) => item !== key)
        : [...state.expandedKnowledgeSourceIds, key]
      renderManagement('metrics')
    })
  })
  document.querySelectorAll('[data-toggle-knowledge-category]').forEach((button) => {
    button.addEventListener('click', () => {
      const key = button.dataset.toggleKnowledgeCategory
      state.expandedKnowledgeCategoryKeys = state.expandedKnowledgeCategoryKeys.includes(key)
        ? state.expandedKnowledgeCategoryKeys.filter((item) => item !== key)
        : [...state.expandedKnowledgeCategoryKeys, key]
      renderManagement('metrics')
    })
  })
  document.querySelectorAll('[data-add-metric-binding]').forEach((button) => {
    button.addEventListener('click', () => {
      const defaults = JSON.parse(button.dataset.addMetricBinding || '{}')
      if (!defaults.name && !metricDefinitionGroups().length) {
        openRecordModal('metrics', null, { ...defaults, createDefinition: true })
        return
      }
      openRecordModal('metrics', null, defaults)
    })
  })
  document.querySelectorAll('[data-toggle-metric-dashboard]').forEach((button) => {
    button.addEventListener('click', () => toggleMetricDashboard(button.dataset.toggleMetricDashboard))
  })
  document.querySelectorAll('[data-select-global-source]').forEach((button) => {
    button.addEventListener('click', () => {
      switchGlobalDataSource(button.dataset.selectGlobalSource, { feedback: true })
    })
  })
  document.querySelectorAll('[data-edit-knowledge]').forEach((button) => {
    button.addEventListener('click', () => {
      const document = state.knowledgeDocuments.find((item) => String(item.id) === String(button.dataset.editKnowledge))
      if (document) openKnowledgeDocumentModal(document)
    })
  })
  document.querySelectorAll('[data-delete-knowledge]').forEach((button) => {
    button.addEventListener('click', () => deleteKnowledgeDocument(button.dataset.deleteKnowledge))
  })
}

async function toggleMetricDashboard(metricId) {
  const numericId = Number(metricId)
  const record = state.records.metrics.find((item) => Number(item.id) === numericId)
  if (!record || state.metricDashboardUpdatingIds.includes(numericId)) return

  const previousEnabled = record.dashboard_enabled !== false
  const nextEnabled = !previousEnabled
  state.metricDashboardUpdatingIds = [...state.metricDashboardUpdatingIds, numericId]
  state.records.metrics = state.records.metrics.map((item) => Number(item.id) === numericId
    ? { ...item, dashboard_enabled: nextEnabled }
    : item)
  renderManagement('metrics')

  try {
    if (state.recordsFromApi.metrics) {
      const saved = await apiRequest(`/api/admin/metrics/${numericId}/dashboard-enabled`, {
        method: 'PATCH',
        body: JSON.stringify({ dashboard_enabled: nextEnabled }),
        timeout: 15000
      })
      state.records.metrics = state.records.metrics.map((item) => Number(item.id) === numericId ? saved : item)
      invalidateDashboardConfiguration()
      toast(nextEnabled ? '该指标已用于看板' : '该指标已从看板移除', 'success')
      if (['dashboard', 'reports'].includes(state.view)) await loadDashboardContext(false, true)
    } else {
      invalidateDashboardConfiguration()
      toast('预览状态已更新，启动后端后可保存真实配置', 'warning')
    }
  } catch (error) {
    state.records.metrics = state.records.metrics.map((item) => Number(item.id) === numericId
      ? { ...item, dashboard_enabled: previousEnabled }
      : item)
    toast(error.message || '看板状态更新失败，已恢复原状态', 'error', 5000)
  } finally {
    state.metricDashboardUpdatingIds = state.metricDashboardUpdatingIds.filter((id) => id !== numericId)
    if (state.view === 'metrics') renderManagement('metrics')
  }
}

async function loadKnowledgeStatus() {
  try {
    state.knowledgeStatus = await apiRequest('/api/admin/knowledge/status', { timeout: 12000 })
    if (state.view === 'metrics') renderManagement('metrics')
  } catch (error) {
    state.knowledgeStatus = null
  }
}

async function loadKnowledgeDocuments() {
  if (!state.backendOnline) return
  try {
    const [documents, dataSources] = await Promise.all([
      apiRequest('/api/admin/knowledge/documents/', { timeout: 12000 }),
      apiRequest('/api/admin/data_sources/', { timeout: 12000 })
    ])
    state.knowledgeDocuments = Array.isArray(documents) ? documents : []
    state.knowledgeDocumentsLoaded = true
    if (Array.isArray(dataSources)) state.records.datasources = dataSources
    if (state.view === 'metrics') renderManagement('metrics')
  } catch (error) {
    state.knowledgeDocumentsLoaded = false
    if (state.view === 'metrics') toast(error.message || '数据字典读取失败', 'error')
  }
}

async function rebuildKnowledgeBase() {
  if (!state.backendOnline || state.rebuildingKnowledge) return
  state.rebuildingKnowledge = true
  if (state.view === 'metrics') renderManagement('metrics')
  try {
    const result = await apiRequest('/api/admin/knowledge/rebuild', {
      method: 'POST',
      timeout: 120000
    })
    clearDashboardCache()
    state.knowledgeStatus = result
    toast(`知识库已重建，共同步 ${result.indexed_count ?? 0} 条知识来源`, 'success')
  } catch (error) {
    toast(error.message || '知识库重建失败', 'error', 6000)
  } finally {
    state.rebuildingKnowledge = false
    if (state.view === 'metrics') renderManagement('metrics')
  }
}

function openKnowledgeDocumentModal(record = null) {
  const dataSourceOptions = [
    '<option value="">通用</option>',
    ...state.records.datasources.map((source) => `<option value="${escapeHtml(source.id)}" ${String(source.id) === String(record?.data_source_id) ? 'selected' : ''}>${escapeHtml(source.name)}（ID ${escapeHtml(source.id)}）</option>`)
  ].join('')
  const categories = [
    ['table', '表结构说明'],
    ['field', '字段含义'],
    ['rule', '分析规则'],
    ['question', '常见分析问题']
  ]
  modalLayer.className = 'modal-layer open'
  modalLayer.setAttribute('aria-hidden', 'false')
  modalLayer.innerHTML = `
    <section class="modal" role="dialog" aria-modal="true" aria-labelledby="knowledge-modal-title">
      <header class="modal-header">
        <div><h2 id="knowledge-modal-title">${record ? '编辑' : '新增'}知识条目</h2><p>保存后会自动重建 RAG 索引。</p></div>
        <button class="icon-button" type="button" id="close-modal" aria-label="关闭">×</button>
      </header>
      <form id="knowledge-document-form">
        <div class="modal-body"><div class="form-grid">
          <div class="form-group"><label for="knowledge-category">知识类型 *</label><select class="select" id="knowledge-category" required>${categories.map(([value, label]) => `<option value="${value}" ${value === record?.category ? 'selected' : ''}>${label}</option>`).join('')}</select></div>
          <div class="form-group"><label for="knowledge-data-source">数据源</label><select class="select" id="knowledge-data-source">${dataSourceOptions}</select></div>
          <div class="form-group full"><label for="knowledge-title">标题 *</label><input class="field" id="knowledge-title" required maxlength="200" value="${escapeHtml(record?.title || '')}" placeholder="例如：orders.status 字段含义" /></div>
          <div class="form-group full"><label for="knowledge-content">知识内容 *</label><textarea class="textarea" id="knowledge-content" required placeholder="写明业务含义、取值范围、分析规则或问题与标准分析方法">${escapeHtml(record?.content || '')}</textarea></div>
        </div></div>
        <footer class="modal-footer"><button class="button" type="button" id="cancel-modal">取消</button><button class="button primary" type="submit">保存并同步</button></footer>
      </form>
    </section>`
  document.querySelector('#close-modal').addEventListener('click', closeModal)
  document.querySelector('#cancel-modal').addEventListener('click', closeModal)
  document.querySelector('#knowledge-document-form').addEventListener('submit', (event) => saveKnowledgeDocument(event, record))
  modalLayer.onclick = (event) => {
    if (event.target === modalLayer) closeModal()
  }
  document.querySelector('#knowledge-title')?.focus()
}

async function saveKnowledgeDocument(event, existing = null) {
  event.preventDefault()
  const sourceValue = document.querySelector('#knowledge-data-source').value
  const payload = {
    category: document.querySelector('#knowledge-category').value,
    title: document.querySelector('#knowledge-title').value.trim(),
    content: document.querySelector('#knowledge-content').value.trim(),
    data_source_id: sourceValue ? Number(sourceValue) : null
  }
  try {
    const saved = await apiRequest(
      existing ? `/api/admin/knowledge/documents/${existing.id}` : '/api/admin/knowledge/documents/',
      {
        method: existing ? 'PUT' : 'POST',
        body: JSON.stringify(payload),
        timeout: 120000
      }
    )
    if (existing) state.knowledgeDocuments = state.knowledgeDocuments.map((item) => item.id === existing.id ? saved : item)
    else state.knowledgeDocuments.push(saved)
    clearDashboardCache()
    closeModal()
    await loadKnowledgeStatus()
    toast('知识条目已保存并同步到 RAG', 'success')
  } catch (error) {
    toast(error.message || '知识条目保存失败', 'error', 6000)
  }
}

async function deleteKnowledgeDocument(id) {
  const item = state.knowledgeDocuments.find((document) => String(document.id) === String(id))
  if (!item || !window.confirm(`确定删除知识条目“${item.title}”吗？`)) return
  try {
    await apiRequest(`/api/admin/knowledge/documents/${id}`, { method: 'DELETE', timeout: 120000 })
    state.knowledgeDocuments = state.knowledgeDocuments.filter((document) => String(document.id) !== String(id))
    clearDashboardCache()
    await loadKnowledgeStatus()
    toast('知识条目已删除，RAG 索引已同步', 'success')
  } catch (error) {
    toast(error.message || '知识条目删除失败', 'error', 6000)
  }
}

async function loadEnterprises() {
  try {
    const result = await apiRequest('/api/admin/enterprises/', { timeout: 12000 })
    state.enterprises = Array.isArray(result) ? result : []
    state.records.enterprises = structuredClone(state.enterprises)
    state.recordsFromApi.enterprises = true
    state.loaded.enterprises = true
    syncWorkspaceEnterprise()
  } catch {
    state.enterprises = []
    syncWorkspaceEnterprise()
  }
}

async function loadEnterpriseManagement(showFeedback = false) {
  try {
    const [enterprises, dataSources] = await Promise.all([
      apiRequest('/api/admin/enterprises/', { timeout: 12000 }),
      apiRequest('/api/admin/data_sources/', { timeout: 12000 })
    ])
    state.enterprises = Array.isArray(enterprises) ? enterprises : []
    state.records.enterprises = structuredClone(state.enterprises)
    state.records.datasources = Array.isArray(dataSources) ? dataSources : []
    state.dashboardDataSources = structuredClone(state.records.datasources)
    state.recordsFromApi.enterprises = true
    state.recordsFromApi.datasources = true
    state.loaded.enterprises = true
    state.loaded.datasources = true
    selectDashboardDataSource()
    syncWorkspaceEnterprise()
    if (state.view === 'enterprises') renderManagement('enterprises')
    if (showFeedback) toast('企业及下属数据源已重新载入', 'success')
  } catch (error) {
    state.recordsFromApi.enterprises = false
    if (!state.loaded.enterprises) state.records.enterprises = structuredClone(demoRecords.enterprises)
    if (!state.loaded.datasources) state.records.datasources = structuredClone(demoRecords.datasources)
    state.loaded.enterprises = true
    state.loaded.datasources = true
    if (state.view === 'enterprises') renderManagement('enterprises')
    if (showFeedback) toast(error.message || '企业数据读取失败', 'error')
  }
}

async function loadRecords(entity, showFeedback = false) {
  if (!managementConfig[entity]) return
  try {
    const records = await apiRequest(managementConfig[entity].endpoint, { timeout: 12000 })
    state.records[entity] = Array.isArray(records) ? records : []
    state.recordsFromApi[entity] = true
    state.loaded[entity] = true
    if (state.view === entity) renderManagement(entity)
    if (showFeedback) toast('数据已重新载入', 'success')
  } catch (error) {
    state.recordsFromApi[entity] = false
    if (!state.loaded[entity]) state.records[entity] = structuredClone(demoRecords[entity])
    state.loaded[entity] = true
    if (state.view === entity) renderManagement(entity)
    if (showFeedback) toast(error.message || '数据读取失败', 'error')
  }
}

function fieldsForEntity(entity) {
  return managementConfig[entity].fields
}

function departmentDescendantIds(departmentId) {
  const descendants = new Set()
  const visit = (id) => {
    departmentChildren({ id }).forEach((child) => {
      if (descendants.has(Number(child.id))) return
      descendants.add(Number(child.id))
      visit(child.id)
    })
  }
  if (departmentId) visit(departmentId)
  return descendants
}

function departmentParentOptions(enterpriseId, selectedId = null, currentId = null) {
  const enterpriseDepartments = state.records.departments.filter(
    (item) => Number(item.enterprise_id) === Number(enterpriseId) && Number(item.id) !== Number(currentId)
  )
  const blocked = departmentDescendantIds(currentId)
  const available = enterpriseDepartments.filter((item) => !blocked.has(Number(item.id)))
  const availableIds = new Set(available.map((item) => Number(item.id)))
  const roots = available.filter((item) => !item.parent_id || !availableIds.has(Number(item.parent_id)))
  const rows = []
  const walk = (record, depth = 0, visited = new Set()) => {
    if (visited.has(Number(record.id))) return
    const nextVisited = new Set(visited).add(Number(record.id))
    rows.push({ record, depth })
    available.filter((item) => Number(item.parent_id) === Number(record.id)).forEach((child) => walk(child, depth + 1, nextVisited))
  }
  roots.forEach((root) => walk(root))
  return `<option value="">作为一级部门</option>${rows.map(({ record, depth }) => `<option value="${escapeHtml(record.id)}" ${Number(record.id) === Number(selectedId) ? 'selected' : ''}>${'　'.repeat(depth)}${depth ? '└ ' : ''}${escapeHtml(record.name)}</option>`).join('')}`
}

function fieldHtml(field, value, editing = false) {
  const id = `form-${field.name}`
  const resolved = value ?? field.default ?? ''
  const required = field.required && !(editing && field.type === 'password')
  const attrs = `${required ? 'required' : ''} ${field.min !== undefined ? `min="${field.min}"` : ''} ${field.max !== undefined ? `max="${field.max}"` : ''}`
  const placeholder = editing && field.type === 'password' ? '留空表示保持原密码' : (field.placeholder || '')
  let control
  if (field.type === 'textarea') {
    control = `<textarea class="textarea" id="${id}" name="${field.name}" placeholder="${escapeHtml(placeholder)}" ${attrs}>${escapeHtml(resolved)}</textarea>`
  } else if (field.type === 'select' || field.type === 'boolean') {
    control = `<select class="select" id="${id}" name="${field.name}" ${attrs}>${field.options.map(([optionValue, label]) => `<option value="${escapeHtml(optionValue)}" ${String(optionValue) === String(resolved) ? 'selected' : ''}>${escapeHtml(label)}</option>`).join('')}</select>`
  } else if (field.type === 'topic-select') {
    const selectedTopic = resolved === '通用' ? '未分类' : resolved
    const commonTopics = ['未分类', '销售经营', '订单分析', '客户分析', '履约效率', '财务分析', '库存供应', '市场营销', '产品分析', '组织效能']
    const existingTopics = state.records.metrics.map((metric) => metric.topic === '通用' ? '未分类' : metric.topic).filter(Boolean)
    const topicOptions = [...new Set([...commonTopics, ...existingTopics, selectedTopic].filter(Boolean))]
    control = `<select class="select" id="${id}" name="${field.name}" ${attrs}>${topicOptions.map((topic) => `<option value="${escapeHtml(topic)}" ${String(topic) === String(selectedTopic) ? 'selected' : ''}>${escapeHtml(topic)}</option>`).join('')}</select>`
  } else if (field.type === 'metric-definition-select') {
    const definitionOptions = metricDefinitionGroups().map((definition) => `<option value="${escapeHtml(definition.name)}">${escapeHtml(definition.name)} · ${escapeHtml(definition.topic)}</option>`).join('')
    control = `<select class="select" id="${id}" name="${field.name}" ${attrs}>${definitionOptions || '<option value="">请先创建逻辑指标</option>'}</select>`
  } else if (field.type === 'readonly') {
    control = `<input class="field" id="${id}" name="${field.name}" type="text" value="${escapeHtml(resolved)}" readonly ${attrs} />`
  } else if (field.type === 'data-source-select') {
    const dataSourceOptions = state.records.datasources.map((source, index) => {
      const enterprise = state.enterprises.find((item) => Number(item.id) === Number(source.enterprise_id))
      return `<option value="${escapeHtml(source.id)}" ${String(source.id) === String(resolved || state.records.datasources[0]?.id) ? 'selected' : ''}>序号 ${index + 1} · ${escapeHtml(source.name)} · ${escapeHtml(enterprise?.name || '未知企业')}</option>`
    }).join('')
    control = `<select class="select" id="${id}" name="${field.name}" ${attrs}>${dataSourceOptions || '<option value="">请先接入数据源</option>'}</select>`
  } else if (field.type === 'enterprise-select') {
    const enterpriseOptions = state.enterprises.map((enterprise) => `
      <option value="${escapeHtml(enterprise.id)}" ${String(enterprise.id) === String(resolved || state.enterprises[0]?.id) ? 'selected' : ''}>
        ${escapeHtml(enterprise.name)}
      </option>`).join('')
    control = `<select class="select" id="${id}" name="${field.name}" ${attrs}>${enterpriseOptions || '<option value="">请先创建企业</option>'}</select>`
  } else if (field.type === 'department-parent-select') {
    control = `<select class="select" id="${id}" name="${field.name}" ${attrs}>${departmentParentOptions(field.enterpriseId, resolved, field.currentId)}</select>`
  } else {
    control = `<input class="field" id="${id}" name="${field.name}" type="${field.type}" value="${escapeHtml(resolved)}" placeholder="${escapeHtml(placeholder)}" ${attrs} />`
  }
  return `<div class="form-group ${field.full ? 'full' : ''}"><label for="${id}">${escapeHtml(field.label)}${required ? ' *' : ''}</label>${control}</div>`
}

function openRecordModal(entity, record = null, defaults = null) {
  const config = managementConfig[entity]
  let fields = fieldsForEntity(entity).map((field) => ({ ...field }))
  if (entity === 'departments') {
    const enterpriseId = record?.enterprise_id ?? defaults?.enterprise_id ?? state.enterprises[0]?.id
    fields = fields.map((field) => field.type === 'department-parent-select'
      ? { ...field, enterpriseId, currentId: record?.id }
      : field)
  }
  const addingMetricBinding = entity === 'metrics' && !record && defaults && !defaults.createDefinition
  if (addingMetricBinding) {
    const bindingFieldNames = new Set(['name', 'data_source_id', 'sql_expr', 'base_table', 'time_field', 'dimension_field', 'dashboard_enabled'])
    fields = fields.filter((field) => bindingFieldNames.has(field.name))
    fields = fields.map((field) => field.name === 'name'
      ? { ...field, label: '逻辑指标', type: defaults.name ? 'readonly' : 'metric-definition-select' }
      : field)
  }
  modalLayer.className = 'modal-layer open'
  modalLayer.setAttribute('aria-hidden', 'false')
  modalLayer.innerHTML = `
    <section class="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title">
      <header class="modal-header">
        <div><h2 id="modal-title">${addingMetricBinding ? '新增指标绑定' : `${record ? '编辑' : '新建'}${escapeHtml(config.title.replace('管理', '').replace('知识库', ''))}`}</h2><p>${state.recordsFromApi[entity] ? '保存后会写入现有后端接口。' : '当前为预览模式，操作只保留在本次页面会话中。'}</p></div>
        <button class="icon-button" type="button" id="close-modal" aria-label="关闭">×</button>
      </header>
      <form id="record-form">
        <div class="modal-body"><div class="form-grid">${fields.map((field) => fieldHtml(field, field.type === 'password' ? '' : (record?.[field.name] ?? defaults?.[field.name]), Boolean(record))).join('')}</div></div>
        <footer class="modal-footer"><button class="button" type="button" id="cancel-modal">取消</button><button class="button primary" type="submit">保存记录</button></footer>
      </form>
    </section>
  `
  const close = () => closeModal()
  document.querySelector('#close-modal').addEventListener('click', close)
  document.querySelector('#cancel-modal').addEventListener('click', close)
  document.querySelector('#record-form').addEventListener('submit', (event) => saveRecord(event, entity, record, fields))
  if (entity === 'departments') {
    document.querySelector('#form-enterprise_id')?.addEventListener('change', (event) => {
      const parentSelect = document.querySelector('#form-parent_id')
      if (parentSelect) parentSelect.innerHTML = departmentParentOptions(Number(event.target.value), null, record?.id)
    })
  }
  modalLayer.onclick = (event) => {
    if (event.target === modalLayer) close()
  }
  document.querySelector('#record-form input, #record-form textarea, #record-form select')?.focus()
}

function closeModal() {
  modalLayer.className = 'modal-layer'
  modalLayer.setAttribute('aria-hidden', 'true')
  modalLayer.innerHTML = ''
  modalLayer.onclick = null
}

function formPayload(form, fields, existing) {
  const data = new FormData(form)
  return Object.fromEntries(fields.map((field) => {
    let value = data.get(field.name)
    if ((field.name === 'password') && !value && existing?.password) value = existing.password
    if (field.type === 'number' || field.type === 'enterprise-select' || field.type === 'data-source-select' || field.type === 'department-parent-select') value = field.nullable && value === '' ? null : Number(value)
    if (field.type === 'boolean') value = value === 'true'
    return [field.name, value]
  }))
}

async function saveRecord(event, entity, existing, fields = fieldsForEntity(entity)) {
  event.preventDefault()
  const config = managementConfig[entity]
  const payload = formPayload(event.currentTarget, fields, existing)
  const sourceIsApi = state.recordsFromApi[entity]

  try {
    if (sourceIsApi) {
      const url = existing ? `${config.endpoint}${existing.id}` : config.endpoint
      const saved = await apiRequest(url, {
        method: existing ? 'PUT' : 'POST',
        body: JSON.stringify(payload),
        timeout: 20000
      })
      if (existing) {
        state.records[entity] = state.records[entity].map((record) => String(record.id) === String(existing.id) ? saved : record)
      } else {
        state.records[entity].push(saved)
      }
      if (['metrics', 'datasources'].includes(entity)) clearDashboardCache()
      if (entity === 'metrics') {
        toast('指标已保存并同步到知识库', 'success')
      } else if (entity === 'datasources' && saved.provisioning_status === 'granted') {
        toast(saved.provisioning_message || '数据源已保存并自动授予只读权限', 'success', 5200)
      } else if (entity === 'datasources' && saved.provisioning_status === 'verified') {
        toast('数据源已保存，连接和只读权限验证通过', 'success', 4200)
      } else {
        toast('记录已保存到后端', 'success')
      }
      if (entity === 'enterprises') {
        state.enterprises = structuredClone(state.records.enterprises)
        syncWorkspaceEnterprise()
      }
      if (entity === 'datasources') {
        state.dashboardDataSources = structuredClone(state.records.datasources)
        selectDashboardDataSource()
        syncWorkspaceEnterprise()
      }
    } else {
      if (existing) {
        state.records[entity] = state.records[entity].map((record) => String(record.id) === String(existing.id) ? { ...record, ...payload } : record)
      } else {
        const nextId = Math.max(0, ...state.records[entity].map((record) => Number(record.id) || 0)) + 1
        state.records[entity].push({ id: nextId, ...payload })
      }
      if (['metrics', 'datasources'].includes(entity)) clearDashboardCache()
      toast('预览记录已更新，启动后端后可保存真实数据', 'warning')
    }
    closeModal()
    renderManagement(entity)
    if (sourceIsApi && entity === 'metrics') {
      await Promise.all([loadRecords('metrics'), loadKnowledgeStatus()])
    }
  } catch (error) {
    toast(error.message || '保存失败', 'error', 5000)
  }
}

async function deleteRecord(entity, id) {
  const record = state.records[entity].find((item) => String(item.id) === String(id))
  if (!record) return
  if (!window.confirm(`确定删除“${record.name || record.username || id}”吗？`)) return

  try {
    if (state.recordsFromApi[entity]) {
      await apiRequest(`${managementConfig[entity].endpoint}${id}`, { method: 'DELETE', timeout: 15000 })
      toast(entity === 'metrics' ? '指标已删除，知识库已同步' : '记录已从后端删除', 'success')
      if (entity === 'metrics') await loadKnowledgeStatus()
    } else {
      toast('已从当前预览中移除，不影响后端数据', 'warning')
    }
    state.records[entity] = state.records[entity].filter((item) => String(item.id) !== String(id))
    if (entity === 'enterprises') state.enterprises = structuredClone(state.records.enterprises)
    if (entity === 'datasources') {
      state.dashboardDataSources = structuredClone(state.records.datasources)
      selectDashboardDataSource()
    }
    syncWorkspaceEnterprise()
    if (['metrics', 'datasources'].includes(entity)) clearDashboardCache()
    renderManagement(entity)
  } catch (error) {
    toast(error.message || '删除失败', 'error', 5000)
  }
}

function openDataSourceDeleteDialog(record) {
  if (!record) return
  modalLayer.className = 'modal-layer open'
  modalLayer.setAttribute('aria-hidden', 'false')
  modalLayer.innerHTML = `
    <section class="modal compact-modal" role="dialog" aria-modal="true" aria-labelledby="data-source-delete-title">
      <header class="modal-header">
        <div><h2 id="data-source-delete-title">删除数据源</h2><p>${escapeHtml(record.name)} · ${escapeHtml(record.database)}</p></div>
        <button class="icon-button" type="button" id="close-modal" aria-label="关闭">×</button>
      </header>
      <div class="modal-body data-source-delete-copy">
        <p>请选择删除方式：</p>
        <p><strong>仅取消接入</strong>：平台停止使用该数据源并从菜单中隐藏，保留业务数据库和相关指标。</p>
        <p><strong>删除完整数据源</strong>：继续进入不可恢复操作的二次确认。</p>
      </div>
      <footer class="modal-footer">
        <button class="button" type="button" id="cancel-modal">取消</button>
        <button class="button warning" type="button" id="disconnect-data-source">仅取消接入</button>
        <button class="button danger" type="button" id="delete-full-data-source">删除完整数据源</button>
      </footer>
    </section>`
  document.querySelector('#close-modal').addEventListener('click', closeModal)
  document.querySelector('#cancel-modal').addEventListener('click', closeModal)
  document.querySelector('#disconnect-data-source').addEventListener('click', () => performDataSourceDeletion(record, 'disconnect'))
  document.querySelector('#delete-full-data-source').addEventListener('click', () => openFullDataSourceDeleteWarning(record))
  modalLayer.onclick = (event) => {
    if (event.target === modalLayer) closeModal()
  }
}

function openFullDataSourceDeleteWarning(record) {
  modalLayer.innerHTML = `
    <section class="modal compact-modal" role="alertdialog" aria-modal="true" aria-labelledby="full-delete-warning-title">
      <header class="modal-header">
        <div><h2 id="full-delete-warning-title">将删除相关指标</h2><p>这是不可恢复的危险操作</p></div>
        <button class="icon-button" type="button" id="close-modal" aria-label="关闭">×</button>
      </header>
      <div class="modal-body data-source-delete-copy">
        <div class="deletion-warning">将永久删除数据库“${escapeHtml(record.database)}”、该数据源的指标绑定和专属字典内容。</div>
        <p>历史问数和报告记录会保留，但会解除与该数据源的关联。请确认已经完成必要的数据备份。</p>
      </div>
      <footer class="modal-footer">
        <button class="button" type="button" id="cancel-modal">取消</button>
        <button class="button danger-solid" type="button" id="confirm-full-data-source-delete">确认</button>
      </footer>
    </section>`
  document.querySelector('#close-modal').addEventListener('click', closeModal)
  document.querySelector('#cancel-modal').addEventListener('click', closeModal)
  document.querySelector('#confirm-full-data-source-delete').addEventListener('click', () => performDataSourceDeletion(record, 'full'))
  modalLayer.onclick = (event) => {
    if (event.target === modalLayer) closeModal()
  }
}

async function performDataSourceDeletion(record, mode) {
  const actionButton = document.querySelector(mode === 'full' ? '#confirm-full-data-source-delete' : '#disconnect-data-source')
  if (actionButton) {
    actionButton.disabled = true
    actionButton.textContent = mode === 'full' ? '正在删除…' : '正在取消…'
  }
  try {
    if (state.recordsFromApi.datasources) {
      const result = await apiRequest(
        `${managementConfig.datasources.endpoint}${record.id}?mode=${mode}`,
        { method: 'DELETE', timeout: mode === 'full' ? 120000 : 30000 }
      )
      if (result.knowledge_warning) toast(result.knowledge_warning, 'warning', 7000)
      toast(mode === 'full' ? '完整数据源及相关指标已删除' : '已取消接入，业务数据库和指标均已保留', 'success')
    } else {
      toast('已从当前预览中移除，不影响后端数据', 'warning')
    }
    state.records.datasources = state.records.datasources.filter((item) => String(item.id) !== String(record.id))
    state.records.metrics = state.records.metrics.filter((item) => String(item.data_source_id) !== String(record.id))
    state.dashboardDataSources = structuredClone(state.records.datasources)
    selectDashboardDataSource()
    syncWorkspaceEnterprise()
    clearDashboardCache()
    closeModal()
    renderManagement('datasources')
  } catch (error) {
    toast(error.message || '数据源操作失败', 'error', 7000)
    if (actionButton) {
      actionButton.disabled = false
      actionButton.textContent = mode === 'full' ? '确认' : '仅取消接入'
    }
  }
}

function defaultReportContent() {
  const insights = state.dashboard.insights?.items || []
  const kpis = normalizedDashboardKpis(state.dashboard)
  const metricSummary = kpis.map((item) => `${item.name}${String(metricValueHtml(item)).replace(/<[^>]+>/g, '')}`).join('，')
  return {
    executive_summary: `本报告基于当前数据源与指标知识库生成：${metricSummary}。`,
    trend_narrative: dashboardTrendNarrative(state.dashboard),
    findings: insights.map((item) => item.content).filter(Boolean),
    recommendations: insights.map((item) => item.recommendation).filter(Boolean),
    conclusion: '请结合业务背景复核数据口径，并持续跟踪关键指标变化。',
    snapshot: {
      kpis: structuredClone(kpis),
      primaryMetric: structuredClone(state.dashboard.primaryMetric || null),
      dimension: structuredClone(state.dashboard.dimension || null),
      totalSales: state.dashboard.totalSales,
      orderCount: state.dashboard.orderCount,
      customerCount: state.dashboard.customerCount,
      completionRate: state.dashboard.completionRate,
      trendData: structuredClone(state.dashboard.trendData || { x: [], y: [] })
    }
  }
}

async function loadReportDrafts({ rerender = false, force = false } = {}) {
  if (!state.backendOnline || state.reportDraftsLoading || (state.reportDraftsLoaded && !force)) return
  state.reportDraftsLoading = true
  if (rerender && state.view === 'reports') renderReports()
  try {
    const result = await apiRequest(`/api/reports/?user_id=${state.currentUserId}`, { timeout: 15000 })
    state.reportDrafts = Array.isArray(result) ? result : []
    state.reportDraftsLoaded = true
  } catch (error) {
    toast(error.message || '报告草稿读取失败', 'error')
  } finally {
    state.reportDraftsLoading = false
    if (rerender && state.view === 'reports') renderReports()
  }
}

function newReportEditor() {
  const now = new Intl.DateTimeFormat('zh-CN', { year: 'numeric', month: 'long' }).format(new Date())
  state.currentReport = {
    id: null,
    title: `${now}经营分析报告`,
    data_source_id: state.selectedDataSourceId,
    period: state.dashboardPeriod,
    content: defaultReportContent(),
    versions: []
  }
  activateView('reporteditor')
}

async function openReportEditor(reportId) {
  if (!state.backendOnline) {
    toast('后端不可用，无法读取已保存报告', 'warning')
    return
  }
  try {
    state.currentReport = await apiRequest(`/api/reports/${reportId}?user_id=${state.currentUserId}`, { timeout: 15000 })
    activateView('reporteditor')
  } catch (error) {
    toast(error.message || '报告读取失败', 'error')
  }
}

async function openReportPreview(reportId) {
  if (!state.backendOnline) {
    toast('后端不可用，无法读取已保存报告', 'warning')
    return
  }
  try {
    state.reportPreview = await apiRequest(`/api/reports/${reportId}?user_id=${state.currentUserId}`, { timeout: 15000 })
    if (state.view === 'reports') renderReports()
    else activateView('reports')
  } catch (error) {
    toast(error.message || '报告预览读取失败', 'error')
  }
}

async function deleteReport(reportId) {
  const draft = state.reportDrafts.find((item) => Number(item.id) === Number(reportId))
  if (!draft || !window.confirm(`确定删除报告“${draft.title}”及其全部版本吗？`)) return
  try {
    await apiRequest(`/api/reports/${reportId}?user_id=${state.currentUserId}`, { method: 'DELETE', timeout: 15000 })
    if (Number(state.reportPreview?.id) === Number(reportId)) state.reportPreview = null
    state.reportDraftsLoaded = false
    await loadReportDrafts({ rerender: true, force: true })
    toast('报告及版本历史已删除', 'success')
  } catch (error) {
    toast(error.message || '报告删除失败', 'error')
  }
}

function reportEditorContentFromForm() {
  const lines = (selector) => document.querySelector(selector).value.split('\n').map((value) => value.trim()).filter(Boolean)
  return {
    executive_summary: document.querySelector('#report-executive-summary').value.trim(),
    trend_narrative: document.querySelector('#report-trend-narrative').value.trim(),
    findings: lines('#report-findings'),
    recommendations: lines('#report-recommendations'),
    conclusion: document.querySelector('#report-conclusion').value.trim(),
    snapshot: structuredClone(state.currentReport?.content?.snapshot || defaultReportContent().snapshot)
  }
}

async function saveReportEditor(event) {
  event.preventDefault()
  if (state.reportSaving) return
  if (!state.backendOnline) {
    toast('后端不可用，无法保存报告', 'error')
    return
  }
  const title = document.querySelector('#report-editor-title').value.trim()
  if (!title) {
    toast('请填写报告标题', 'warning')
    return
  }
  state.reportSaving = true
  const payload = {
    user_id: state.currentUserId,
    title,
    data_source_id: state.currentReport?.data_source_id || state.selectedDataSourceId,
    period: state.currentReport?.period || state.dashboardPeriod,
    content: reportEditorContentFromForm()
  }
  try {
    const path = state.currentReport?.id ? `/api/reports/${state.currentReport.id}` : '/api/reports/'
    state.currentReport = await apiRequest(path, {
      method: state.currentReport?.id ? 'PUT' : 'POST',
      body: JSON.stringify(payload),
      timeout: 20000
    })
    state.reportDraftsLoaded = false
    toast(`报告已保存为版本 V${state.currentReport.version_count}`, 'success')
    renderReportEditor()
  } catch (error) {
    toast(error.message || '报告保存失败', 'error')
  } finally {
    state.reportSaving = false
  }
}

function restoreReportVersion(versionNumber) {
  const version = state.currentReport?.versions?.find((item) => Number(item.version_number) === Number(versionNumber))
  if (!version) return
  state.currentReport.content = structuredClone(version.content)
  renderReportEditor()
  toast(`已载入 V${version.version_number}，点击保存后将生成新版本`, 'warning', 4800)
}

function renderReportEditor() {
  const report = state.currentReport
  if (!report) {
    viewRoot.innerHTML = `${pageHeading('报表编辑', '尚未选择报告。', '<button class="button" type="button" data-navigate="reports">返回分析报告</button>')}<div class="empty-state">请新建或打开一份报告。</div>`
    bindNavigateButtons()
    return
  }
  const content = report.content || defaultReportContent()
  const versions = report.versions || []
  viewRoot.innerHTML = `
    ${pageHeading('报表编辑', '编辑章节内容并保存；每次保存都会自动创建不可变版本。', '<button class="button" type="button" data-navigate="reports">← 返回报告</button><button class="button primary" type="submit" form="report-editor-form">保存新版本</button>')}
    ${!state.backendOnline ? '<div class="preview-banner error"><strong>后台错误</strong><span>当前可以编辑，但后端恢复前无法保存。</span></div>' : ''}
    <div class="report-editor-layout">
      <form class="report-editor-form panel" id="report-editor-form">
        <label class="report-editor-field"><span>报告标题</span><input class="field" id="report-editor-title" value="${escapeHtml(report.title)}" maxlength="200" required /></label>
        <label class="report-editor-field"><span>执行摘要</span><textarea class="field" id="report-executive-summary" rows="4">${escapeHtml(content.executive_summary || '')}</textarea></label>
        <label class="report-editor-field"><span>经营趋势</span><textarea class="field" id="report-trend-narrative" rows="4">${escapeHtml(content.trend_narrative || '')}</textarea></label>
        <label class="report-editor-field"><span>核心发现</span><small>每行一条，保存后按列表展示</small><textarea class="field" id="report-findings" rows="7">${escapeHtml((content.findings || []).join('\n'))}</textarea></label>
        <label class="report-editor-field"><span>行动建议</span><small>每行一条，保存后按列表展示</small><textarea class="field" id="report-recommendations" rows="7">${escapeHtml((content.recommendations || []).join('\n'))}</textarea></label>
        <label class="report-editor-field"><span>结论</span><textarea class="field" id="report-conclusion" rows="4">${escapeHtml(content.conclusion || '')}</textarea></label>
      </form>
      <aside class="report-version-panel panel">
        <h2>版本历史</h2>
        <p>载入旧版本不会覆盖当前版本，保存时会生成一个新版本。</p>
        ${versions.length ? `<div class="report-version-list">${versions.map((version) => `
          <button type="button" data-restore-report-version="${version.version_number}"><strong>V${version.version_number}</strong><span>${escapeHtml(formatConversationTime(version.created_at))}</span></button>
        `).join('')}</div>` : '<div class="empty-state compact">首次保存后会出现 V1。</div>'}
        <dl class="report-editor-meta"><div><dt>数据源</dt><dd>${escapeHtml(report.data_source_id || state.selectedDataSourceId || '未选择')}</dd></div><div><dt>统计周期</dt><dd>${escapeHtml(report.period || state.dashboardPeriod)}</dd></div></dl>
      </aside>
    </div>
  `
  document.querySelector('#report-editor-form').addEventListener('submit', saveReportEditor)
  document.querySelectorAll('[data-restore-report-version]').forEach((button) => {
    button.addEventListener('click', () => restoreReportVersion(Number(button.dataset.restoreReportVersion)))
  })
  bindNavigateButtons()
}

function dashboardTrendNarrative(data) {
  const periods = data.trendData?.x || []
  const values = data.trendData?.y || []
  const metric = data.primaryMetric || { name: '主指标', unit: '' }
  const valueText = (value) => metric.unit === '¥' ? formatCurrency(value) : `${formatNumber(value)}${metric.unit || ''}`
  if (!periods.length) return `当前数据源没有可展示的${metric.name}月度趋势。`
  if (values.length < 2) return `${periods[0]}${metric.name}为${valueText(values[0])}，暂缺上一期数据进行比较。`
  const current = Number(values.at(-1) || 0)
  const previous = Number(values.at(-2) || 0)
  const delta = previous ? ((current - previous) / Math.abs(previous)) * 100 : null
  const change = delta === null ? '无法计算环比' : `较上一期${delta >= 0 ? '增长' : '下降'}${formatNumber(Math.abs(delta))}%`
  return `${periods.at(-1)}${metric.name}为${valueText(current)}，${change}。以上结论来自当前选择的数据源。`
}

function reportInsightsHtml(insights = {}, field = 'content') {
  if (insights.status === 'unconfigured') {
    return `<div class="insight-api-notice"><strong>前往智能问数模块配置API</strong><button class="button small" type="button" data-navigate="chat">前往配置</button></div>`
  }
  if (insights.status === 'error') {
    return `<p class="inline-error">${escapeHtml(insights.message || '经营洞察生成失败')}</p>`
  }
  const values = (insights.items || []).map((item) => item[field]).filter(Boolean)
  if (!values.length) return '<p>当前数据源暂时没有可展示的分析内容。</p>'
  return `<ol>${values.map((value) => `<li>${escapeHtml(value)}</li>`).join('')}</ol>`
}

function reportValueListHtml(values) {
  const items = Array.isArray(values) ? values.filter(Boolean) : []
  return items.length
    ? `<ol>${items.map((value) => `<li>${escapeHtml(value)}</li>`).join('')}</ol>`
    : '<p>当前报告没有填写此部分内容。</p>'
}

function renderReports() {
  const preview = state.reportPreview
  const previewContent = preview?.content || null
  const data = previewContent?.snapshot || state.dashboard
  const period = new Intl.DateTimeFormat('zh-CN', { year: 'numeric', month: 'long' }).format(new Date())
  const title = preview?.title || `${period}经营分析报告`
  const reportKpis = normalizedDashboardKpis(data).slice(0, 4)
  const reportActions = preview
    ? `<button class="button" id="close-report-preview" type="button">← 返回实时报告</button><button class="button" id="edit-preview-report" type="button">✎ 编辑此报告</button>`
    : `<button class="button" type="button" data-navigate="chat">✦ 补充 AI 分析</button><button class="button" id="edit-report" type="button">✎ 编辑报告</button>`
  viewRoot.innerHTML = `
    ${pageHeading(
      '经营分析报告',
      '把关键指标、趋势和行动建议整理成可打印的管理报告。',
      `${dashboardDataSourceSelectHtml()}${dashboardPeriodSelectHtml()}${reportActions}<button class="button primary" id="print-report" type="button">⇩ 导出 / 打印</button>`
    )}
    ${dashboardErrorBanner()}
    ${preview ? `<div class="preview-banner"><strong>已保存版本 V${escapeHtml(preview.version_count)}</strong><span>正在预览保存于 ${escapeHtml(formatConversationTime(preview.updated_at))} 的指标快照和编辑内容。</span></div>` : ''}
    <article class="report-sheet">
      <header class="report-cover">
        <span class="report-kicker">ATLAS BI · MANAGEMENT REPORT</span>
        <h1>${escapeHtml(title)}</h1>
        <p>${escapeHtml(selectedEnterpriseName())} · 经营分析中心 · 生成于 ${escapeHtml(new Date().toLocaleDateString('zh-CN'))}</p>
      </header>
      <div class="report-content">
        <section class="report-summary">
          ${reportKpis.map((metric) => `<div class="report-number"><span>${escapeHtml(metric.name)}</span><strong>${metricValueHtml(metric)}</strong></div>`).join('')}
        </section>
        ${previewContent?.executive_summary ? `<section class="report-section"><h2>执行摘要</h2><p>${escapeHtml(previewContent.executive_summary)}</p></section>` : ''}
        <section class="report-section">
          <h2>01 · 经营趋势</h2>
          <p>${escapeHtml(previewContent?.trend_narrative || dashboardTrendNarrative(data))}</p>
          <div class="report-chart" id="report-trend-chart"></div>
        </section>
        <section class="report-section">
          <h2>02 · 核心发现</h2>
          ${previewContent ? reportValueListHtml(previewContent.findings) : reportInsightsHtml(state.dashboard.insights, 'content')}
        </section>
        <section class="report-section">
          <h2>03 · 行动建议</h2>
          ${previewContent ? reportValueListHtml(previewContent.recommendations) : reportInsightsHtml(state.dashboard.insights, 'recommendation')}
        </section>
        ${previewContent?.conclusion ? `<section class="report-section"><h2>04 · 结论</h2><p>${escapeHtml(previewContent.conclusion)}</p></section>` : ''}
      </div>
    </article>
    <section class="saved-reports panel">
      <header class="panel-header"><div><h2>已保存报告</h2><p>当前用户的草稿和版本历史</p></div><button class="button small" id="new-saved-report" type="button">＋ 新建报告</button></header>
      <div class="panel-body">
        ${state.reportDraftsLoading ? '<div class="empty-state compact">正在读取报告…</div>' : state.reportDrafts.length ? `<div class="saved-report-list">${state.reportDrafts.map((draft) => `
          <article><button class="saved-report-main" type="button" data-preview-report="${draft.id}"><strong>${escapeHtml(draft.title)}</strong><span>V${escapeHtml(draft.version_count)} · ${escapeHtml(formatConversationTime(draft.updated_at))}</span></button><div class="inline-actions"><button class="button small" type="button" data-preview-report="${draft.id}">预览</button><button class="button small" type="button" data-open-report="${draft.id}">编辑</button><button class="button small danger-text" type="button" data-delete-report="${draft.id}">删除</button></div></article>
        `).join('')}</div>` : '<div class="empty-state compact">尚未保存报告，点击“编辑报告”创建第一份。</div>'}
      </div>
    </section>
  `

  const option = dashboardChartOptions(data).trend
  createChart(document.querySelector('#report-trend-chart'), option)
  bindDashboardSourceMenu()
  document.querySelector('#print-report').addEventListener('click', () => window.print())
  document.querySelector('#edit-report')?.addEventListener('click', newReportEditor)
  document.querySelector('#close-report-preview')?.addEventListener('click', () => { state.reportPreview = null; renderReports() })
  document.querySelector('#edit-preview-report')?.addEventListener('click', () => openReportEditor(preview.id))
  document.querySelector('#new-saved-report').addEventListener('click', newReportEditor)
  document.querySelectorAll('[data-open-report]').forEach((button) => button.addEventListener('click', () => openReportEditor(Number(button.dataset.openReport))))
  document.querySelectorAll('[data-preview-report]').forEach((button) => button.addEventListener('click', () => openReportPreview(Number(button.dataset.previewReport))))
  document.querySelectorAll('[data-delete-report]').forEach((button) => button.addEventListener('click', () => deleteReport(Number(button.dataset.deleteReport))))
  bindNavigateButtons()
}

function bindNavigateButtons() {
  document.querySelectorAll('[data-navigate]').forEach((button) => {
    button.addEventListener('click', () => activateView(button.dataset.navigate))
  })
}

function openSidebar() {
  sidebar.classList.add('open')
  sidebarBackdrop.classList.add('open')
}

function closeSidebar() {
  sidebar.classList.remove('open')
  sidebarBackdrop.classList.remove('open')
}

document.querySelectorAll('.nav-item').forEach((item) => {
  item.addEventListener('click', () => activateView(item.dataset.view))
})
document.querySelector('#mobile-menu').addEventListener('click', openSidebar)
sidebarBackdrop.addEventListener('click', closeSidebar)
backendStatus.addEventListener('click', () => checkBackend({ refreshView: true }))
logoutButton?.addEventListener('click', logout)

document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') {
    closeModal()
    closeSidebar()
  }
})

window.addEventListener('hashchange', () => {
  const requested = location.hash.slice(1)
  if (viewTitles[requested] && requested !== state.view) activateView(requested, false)
})

bootstrapAuthenticatedApp()
window.setInterval(() => { if (state.authToken) checkBackend() }, 30000)
