<template>
  <div>
    <el-card>
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span>指标管理</span>
          <div>
            <el-button :loading="rebuilding" @click="handleRebuild">重建知识库</el-button>
            <el-button type="primary" @click="openForm(null)">新增指标</el-button>
          </div>
        </div>
      </template>
      <el-table :data="list" border stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="名称" />
        <el-table-column prop="topic" label="主题领域" />
        <el-table-column prop="description" label="口径说明" show-overflow-tooltip />
        <el-table-column label="操作" width="200">
          <template #default="{ row }">
            <el-button size="small" @click="openForm(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card style="margin-top: 18px">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <div>
            <span>数据字典与分析规则</span>
            <small style="display: block; color: #909399; margin-top: 4px">与指标、实时数据库表结构一起进入 RAG</small>
          </div>
          <el-button @click="openKnowledgeForm(null)">新增字典 / 规则</el-button>
        </div>
      </template>
      <el-table :data="knowledgeDocuments" border stripe>
        <el-table-column label="类型" width="130">
          <template #default="{ row }">{{ categoryLabel(row.category) }}</template>
        </el-table-column>
        <el-table-column prop="title" label="标题" width="220" />
        <el-table-column prop="content" label="内容" show-overflow-tooltip />
        <el-table-column prop="data_source_id" label="数据源" width="100">
          <template #default="{ row }">{{ row.data_source_id || '通用' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="200">
          <template #default="{ row }">
            <el-button size="small" @click="openKnowledgeForm(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="handleKnowledgeDelete(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新增/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="formTitle" width="600px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="主题领域">
          <el-input v-model="form.topic" />
        </el-form-item>
        <el-form-item label="口径说明">
          <el-input v-model="form.description" type="textarea" />
        </el-form-item>
        <el-form-item label="SQL表达式">
          <el-input v-model="form.sql_expr" type="textarea" rows="3" />
        </el-form-item>
        <el-form-item label="数据源ID" required>
          <el-input-number v-model="form.data_source_id" :min="1" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="knowledgeDialogVisible" :title="knowledgeEditId ? '编辑知识条目' : '新增知识条目'" width="620px">
      <el-form :model="knowledgeForm" label-width="110px">
        <el-form-item label="知识类型" required>
          <el-select v-model="knowledgeForm.category">
            <el-option label="表结构说明" value="table" />
            <el-option label="字段含义" value="field" />
            <el-option label="分析规则" value="rule" />
            <el-option label="常见分析问题" value="question" />
          </el-select>
        </el-form-item>
        <el-form-item label="标题" required><el-input v-model="knowledgeForm.title" /></el-form-item>
        <el-form-item label="知识内容" required><el-input v-model="knowledgeForm.content" type="textarea" :rows="5" /></el-form-item>
        <el-form-item label="数据源 ID"><el-input-number v-model="knowledgeForm.data_source_id" :min="1" clearable /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="knowledgeDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitKnowledgeForm">保存并同步</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import {
  createKnowledgeDocument,
  createMetric,
  deleteKnowledgeDocument,
  deleteMetric,
  getKnowledgeDocuments,
  getMetrics,
  rebuildKnowledge,
  updateKnowledgeDocument,
  updateMetric
} from '../../api'
import { ElMessage, ElMessageBox } from 'element-plus'

const list = ref([])
const dialogVisible = ref(false)
const formTitle = ref('新增指标')
const form = ref({ name: '', topic: '', description: '', sql_expr: '', data_source_id: 1 })
const editId = ref(null)
const rebuilding = ref(false)
const knowledgeDocuments = ref([])
const knowledgeDialogVisible = ref(false)
const knowledgeEditId = ref(null)
const knowledgeForm = ref({ category: 'field', title: '', content: '', data_source_id: null })

const errorMessage = (error, fallback) => {
  const detail = error?.response?.data?.detail
  return (typeof detail === 'object' ? detail?.message : detail) || fallback
}

const loadData = async () => {
  const [metricResponse, knowledgeResponse] = await Promise.all([getMetrics(), getKnowledgeDocuments()])
  list.value = metricResponse.data
  knowledgeDocuments.value = knowledgeResponse.data
}

const categoryLabel = (category) => ({ table: '表说明', field: '字段含义', rule: '分析规则', question: '常见问题' }[category] || category)

const openKnowledgeForm = (row) => {
  knowledgeEditId.value = row?.id || null
  knowledgeForm.value = row
    ? { category: row.category, title: row.title, content: row.content, data_source_id: row.data_source_id }
    : { category: 'field', title: '', content: '', data_source_id: null }
  knowledgeDialogVisible.value = true
}

const submitKnowledgeForm = async () => {
  try {
    if (knowledgeEditId.value) await updateKnowledgeDocument(knowledgeEditId.value, knowledgeForm.value)
    else await createKnowledgeDocument(knowledgeForm.value)
    knowledgeDialogVisible.value = false
    await loadData()
    ElMessage.success('知识条目已保存并同步到 RAG')
  } catch (e) {
    ElMessage.error(errorMessage(e, '知识条目保存失败'))
  }
}

const handleKnowledgeDelete = (id) => {
  ElMessageBox.confirm('确认删除该知识条目吗？', '提示', { type: 'warning' })
    .then(async () => {
      await deleteKnowledgeDocument(id)
      await loadData()
      ElMessage.success('知识条目已删除，RAG 已同步')
    })
    .catch(() => {})
}

const openForm = (row) => {
  if (row) {
    formTitle.value = '编辑指标'
    form.value = { ...row }
    editId.value = row.id
  } else {
    formTitle.value = '新增指标'
    form.value = { name: '', topic: '', description: '', sql_expr: '', data_source_id: 1 }
    editId.value = null
  }
  dialogVisible.value = true
}

const submitForm = async () => {
  try {
    if (editId.value) {
      await updateMetric(editId.value, form.value)
      ElMessage.success('更新成功，知识库已同步')
    } else {
      await createMetric(form.value)
      ElMessage.success('创建成功，知识库已同步')
    }
    dialogVisible.value = false
    loadData()
  } catch (e) {
    ElMessage.error(errorMessage(e, '操作失败'))
  }
}

const handleDelete = (id) => {
  ElMessageBox.confirm('确认删除该指标吗？', '提示', { type: 'warning' })
    .then(async () => {
      await deleteMetric(id)
      ElMessage.success('删除成功，知识库已同步')
      loadData()
    })
    .catch(() => {})
}

const handleRebuild = async () => {
  rebuilding.value = true
  try {
    const { data } = await rebuildKnowledge()
    ElMessage.success(`知识库重建完成，共 ${data.indexed_count} 条知识来源`)
  } catch (e) {
    ElMessage.error(errorMessage(e, '知识库重建失败'))
  } finally {
    rebuilding.value = false
  }
}

onMounted(loadData)
</script>
