import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as echarts from 'echarts'
import App from './App.vue'
import router from './router'

const app = createApp(App)
app.use(ElementPlus)
app.use(router)
// 全局挂载 echarts（方便组件使用）
app.config.globalProperties.$echarts = echarts
app.mount('#app')