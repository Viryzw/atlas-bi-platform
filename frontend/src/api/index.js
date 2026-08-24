import axios from 'axios'

const api = axios.create({
  baseURL: '/api',  // 使用 vite 代理，实际请求会转发到 http://127.0.0.1:8000
  headers: { 'Content-Type': 'application/json' }
})

// ========== 智能问数 ==========
// 产品入口只有分析 Agent；它会在后端依次调用 SQL Agent 和数据分析工具。
export const queryAgent = (question, userId) => api.post('/agent/', { question, user_id: userId })
// 仅为开发调试保留，不应在产品界面中作为并列模式展示。
export const querySQL = (question) => api.post('/query/', { question })

// ========== 指标管理 ==========
export const getMetrics = () => api.get('/admin/metrics/')
export const createMetric = (data) => api.post('/admin/metrics/', data)
export const updateMetric = (id, data) => api.put(`/admin/metrics/${id}`, data)
export const deleteMetric = (id) => api.delete(`/admin/metrics/${id}`)
export const getKnowledgeStatus = () => api.get('/admin/knowledge/status')
export const rebuildKnowledge = () => api.post('/admin/knowledge/rebuild')
export const getKnowledgeDocuments = () => api.get('/admin/knowledge/documents/')
export const createKnowledgeDocument = (data) => api.post('/admin/knowledge/documents/', data)
export const updateKnowledgeDocument = (id, data) => api.put(`/admin/knowledge/documents/${id}`, data)
export const deleteKnowledgeDocument = (id) => api.delete(`/admin/knowledge/documents/${id}`)

// ========== 用户 DeepSeek 配置 ==========
export const getLlmConfigStatus = (userId) => api.get('/llm-config/status', { params: { user_id: userId } })
export const saveLlmConfig = (userId, apiKey) => api.put('/llm-config/', { user_id: userId, api_key: apiKey })

// ========== 企业管理 ==========
export const getEnterprises = () => api.get('/admin/enterprises/')

// ========== 数据源管理 ==========
export const getDataSources = () => api.get('/admin/data_sources/')
export const createDataSource = (data) => api.post('/admin/data_sources/', data)
export const updateDataSource = (id, data) => api.put(`/admin/data_sources/${id}`, data)
export const deleteDataSource = (id) => api.delete(`/admin/data_sources/${id}`)

// ========== 用户管理 ==========
export const getUsers = () => api.get('/admin/users/')
export const createUser = (data) => api.post('/admin/users/', data)
export const updateUser = (id, data) => api.put(`/admin/users/${id}`, data)
export const deleteUser = (id) => api.delete(`/admin/users/${id}`)

// ========== 仪表盘聚合数据 ==========
export const getDashboard = (dataSourceId, userId, includeInsights = true) => api.get('/dashboard/', {
  params: { data_source_id: dataSourceId, user_id: userId, include_insights: includeInsights }
})
