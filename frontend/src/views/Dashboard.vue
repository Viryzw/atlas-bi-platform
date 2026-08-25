<template>
  <div>
    <div class="dashboard-toolbar">
      <strong>经营驾驶舱</strong>
      <el-select v-model="selectedDataSourceId" placeholder="选择数据源" @change="handleSourceChange">
        <el-option
          v-for="source in dataSources"
          :key="source.id"
          :label="`${source.name} · ${source.database}`"
          :value="source.id"
        />
      </el-select>
    </div>

    <div v-if="backendError" class="backend-error">后台错误，当前为样例数据，请及时修复</div>

    <el-row :gutter="20">
      <el-col :span="6" v-for="item in kpiList" :key="item.title">
        <el-card shadow="hover">
          <div class="kpi-content">
            <div>
              <div class="kpi-title">{{ item.title }}</div>
              <div class="kpi-value">{{ item.value }}</div>
              <div class="kpi-delta">{{ item.delta }}</div>
            </div>
            <div :style="{ background: item.color }" class="kpi-icon">
              <el-icon :size="24" color="white"><component :is="item.icon" /></el-icon>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="dashboard-row">
      <el-col :span="16">
        <el-card shadow="hover">
          <template #header><span>月度销售额趋势</span></template>
          <div ref="trendChart" class="chart"></div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover">
          <template #header><span>厂商订单分布</span></template>
          <div ref="pieChart" class="chart"></div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="hover" class="insight-card">
      <template #header><span>AI 经营洞察</span></template>
      <div v-if="dashboard.insights?.status === 'unconfigured'" class="api-notice">
        <strong>前往智能问数模块配置API</strong>
        <router-link to="/chat">前往配置</router-link>
      </div>
      <div v-else-if="dashboard.insights?.status === 'pending'" class="api-notice">
        <strong>正在根据当前数据源生成经营洞察…</strong>
      </div>
      <div v-else-if="dashboard.insights?.status === 'error'" class="backend-error">
        {{ dashboard.insights.message }}
      </div>
      <div v-else class="insight-list">
        <div v-for="item in dashboard.insights?.items || []" :key="item.title" class="insight-item">
          <strong>{{ item.title }}</strong>
          <p>{{ item.content }}</p>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { getDashboard, getDataSources } from '../api'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { Wallet, ShoppingCart, User, TrendCharts } from '@element-plus/icons-vue'

const sampleDashboard = {
  totalSales: 2864300,
  orderCount: 12846,
  customerCount: 2189,
  completionRate: 92.4,
  deltas: { totalSales: 12.6, orderCount: 8.2, customerCount: 5.4, completionRate: -1.3 },
  trendData: { x: ['5月', '6月', '7月', '8月'], y: [2890000, 3010000, 3380000, 3660000] },
  pieData: [{ name: '样例厂商A', value: 36 }, { name: '样例厂商B', value: 27 }],
  insights: { status: 'sample', items: [{ title: '样例洞察', content: '恢复后端后将根据真实数据源生成。' }] }
}

const dashboard = ref(structuredClone(sampleDashboard))
const dataSources = ref([])
const selectedDataSourceId = ref(Number(window.localStorage.getItem('atlas-dashboard-data-source-id')) || null)
const currentUserId = Number(window.localStorage.getItem('atlas-current-user-id')) || 1
const backendError = ref(false)
const trendChart = ref(null)
const pieChart = ref(null)
let trendInstance = null
let pieInstance = null

const formatValue = (value) => new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 2 }).format(Number(value || 0))
const deltaText = (value, suffix = '%') => {
  const number = Number(value)
  if (!Number.isFinite(number)) return '暂无上期数据'
  return `${number > 0 ? '↑' : number < 0 ? '↓' : '→'} ${formatValue(Math.abs(number))}${suffix} 较上期`
}

const kpiList = ref([])
const updateKpis = () => {
  const data = dashboard.value
  kpiList.value = [
    { title: '总销售额', value: `¥${formatValue(data.totalSales)}`, delta: deltaText(data.deltas?.totalSales), icon: Wallet, color: '#409EFF' },
    { title: '订单总数', value: formatValue(data.orderCount), delta: deltaText(data.deltas?.orderCount), icon: ShoppingCart, color: '#67C23A' },
    { title: '客户数', value: formatValue(data.customerCount), delta: deltaText(data.deltas?.customerCount), icon: User, color: '#E6A23C' },
    { title: '完成率', value: `${formatValue(data.completionRate)}%`, delta: deltaText(data.deltas?.completionRate, ' 个百分点'), icon: TrendCharts, color: '#F56C6C' }
  ]
}

const renderCharts = async () => {
  await nextTick()
  if (trendChart.value) {
    trendInstance ||= echarts.init(trendChart.value)
    trendInstance.setOption({
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: dashboard.value.trendData?.x || [] },
      yAxis: { type: 'value' },
      series: [{ data: dashboard.value.trendData?.y || [], type: 'line', smooth: true }]
    }, true)
  }
  if (pieChart.value) {
    pieInstance ||= echarts.init(pieChart.value)
    pieInstance.setOption({
      tooltip: { trigger: 'item' },
      series: [{ type: 'pie', radius: '55%', data: dashboard.value.pieData || [] }]
    }, true)
  }
}

const useSampleData = async () => {
  dashboard.value = structuredClone(sampleDashboard)
  backendError.value = true
  updateKpis()
  await renderCharts()
}

const loadSelectedDashboard = async () => {
  if (!selectedDataSourceId.value) return useSampleData()
  const sourceId = Number(selectedDataSourceId.value)
  try {
    const { data } = await getDashboard(sourceId, currentUserId, false)
    if (sourceId !== Number(selectedDataSourceId.value)) return
    dashboard.value = data
    backendError.value = false
    updateKpis()
    await renderCharts()
    try {
      const insightResponse = await getDashboard(sourceId, currentUserId, true)
      if (sourceId !== Number(selectedDataSourceId.value)) return
      dashboard.value.insights = insightResponse.data.insights
    } catch (error) {
      dashboard.value.insights = { status: 'error', message: error.message || '经营洞察生成失败', items: [] }
    }
  } catch {
    await useSampleData()
    ElMessage.error('加载当前数据源失败')
  }
}

const handleSourceChange = async () => {
  window.localStorage.setItem('atlas-dashboard-data-source-id', String(selectedDataSourceId.value))
  await loadSelectedDashboard()
}

onMounted(async () => {
  try {
    const { data } = await getDataSources()
    dataSources.value = data
    if (!data.some(source => Number(source.id) === Number(selectedDataSourceId.value))) {
      selectedDataSourceId.value = data.length ? Number(data[0].id) : null
    }
    if (selectedDataSourceId.value) {
      window.localStorage.setItem('atlas-dashboard-data-source-id', String(selectedDataSourceId.value))
    }
    await loadSelectedDashboard()
  } catch {
    await useSampleData()
  }
})

onBeforeUnmount(() => {
  trendInstance?.dispose()
  pieInstance?.dispose()
})
</script>

<style scoped>
.dashboard-toolbar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 18px; }
.dashboard-toolbar .el-select { width: 280px; }
.backend-error { margin-bottom: 18px; padding: 12px 14px; border: 1px solid #f2b8b8; border-radius: 8px; background: #fff5f5; color: #c62828; }
.kpi-content { display: flex; justify-content: space-between; }
.kpi-title { color: #909399; font-size: 14px; }
.kpi-value { margin-top: 10px; font-size: 28px; font-weight: bold; }
.kpi-delta { margin-top: 7px; color: #909399; font-size: 12px; }
.kpi-icon { width: 48px; height: 48px; display: flex; align-items: center; justify-content: center; border-radius: 50%; }
.dashboard-row { margin-top: 20px; }
.chart { height: 350px; }
.insight-card { margin-top: 20px; }
.insight-list { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
.insight-item p { margin-bottom: 0; color: #606266; line-height: 1.65; }
.api-notice { display: flex; align-items: center; gap: 16px; color: #b26a00; }
</style>
