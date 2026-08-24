<template>
  <el-card shadow="hover">
    <template #header>
      <span>{{ title }}</span>
    </template>
    <div :ref="el => chartRef = el" style="height: 300px"></div>
  </el-card>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  title: String,
  option: Object  // ECharts 配置
})

const chartRef = ref(null)
let chartInstance = null

const renderChart = () => {
  if (!chartRef.value) return
  if (!chartInstance) {
    chartInstance = echarts.init(chartRef.value)
  }
  chartInstance.setOption(props.option)
}

onMounted(() => {
  renderChart()
  window.addEventListener('resize', () => chartInstance?.resize())
})

watch(() => props.option, () => renderChart(), { deep: true })
</script>