<template>
  <div>
    <el-card>
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span>数据源管理</span>
          <el-button type="primary" @click="openForm(null)">新增数据源</el-button>
        </div>
      </template>
      <el-table :data="list" border stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="名称" />
        <el-table-column prop="db_type" label="类型" />
        <el-table-column prop="host" label="主机" />
        <el-table-column prop="port" label="端口" />
        <el-table-column prop="database" label="数据库" />
        <el-table-column label="操作" width="200">
          <template #default="{ row }">
            <el-button size="small" @click="openForm(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row.id)">删除</el-button>
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
        <el-form-item label="数据库类型">
          <el-input v-model="form.db_type" placeholder="如 mysql" />
        </el-form-item>
        <el-form-item label="主机" required>
          <el-input v-model="form.host" placeholder="localhost" />
        </el-form-item>
        <el-form-item label="端口" required>
          <el-input-number v-model="form.port" :min="1" :max="65535" />
        </el-form-item>
        <el-form-item label="数据库名" required>
          <el-input v-model="form.database" />
        </el-form-item>
        <el-form-item label="用户名" required>
          <el-input v-model="form.username" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" show-password :placeholder="editId ? '留空表示保持原密码' : '请输入数据库密码（可为空）'" />
        </el-form-item>
        <el-form-item label="所属企业" required>
          <el-select v-model="form.enterprise_id" placeholder="请选择企业" style="width: 100%">
            <el-option v-for="enterprise in enterprises" :key="enterprise.id" :label="`${enterprise.name}（ID ${enterprise.id}）`" :value="enterprise.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getDataSources, createDataSource, updateDataSource, deleteDataSource, getEnterprises } from '../../api'
import { ElMessage, ElMessageBox } from 'element-plus'

const list = ref([])
const dialogVisible = ref(false)
const formTitle = ref('新增数据源')
const form = ref({ name: '', db_type: 'mysql', host: 'localhost', port: 3306, database: '', username: '', password: '', enterprise_id: 1 })
const editId = ref(null)
const enterprises = ref([])

const errorMessage = (error, fallback) => {
  const detail = error?.response?.data?.detail
  return (typeof detail === 'object' ? detail?.message : detail) || fallback
}

const loadData = async () => {
  const [dataSourceResponse, enterpriseResponse] = await Promise.all([getDataSources(), getEnterprises()])
  list.value = dataSourceResponse.data
  enterprises.value = enterpriseResponse.data
}

const openForm = (row) => {
  if (row) {
    formTitle.value = '编辑数据源'
    form.value = { ...row, password: '' }
    editId.value = row.id
  } else {
    formTitle.value = '新增数据源'
    form.value = { name: '', db_type: 'mysql', host: 'localhost', port: 3306, database: '', username: '', password: '', enterprise_id: enterprises.value[0]?.id ?? null }
    editId.value = null
  }
  dialogVisible.value = true
}

const submitForm = async () => {
  try {
    if (!form.value.enterprise_id) {
      ElMessage.error('请先创建或选择一个企业')
      return
    }
    if (editId.value) {
      await updateDataSource(editId.value, form.value)
      ElMessage.success('更新成功')
    } else {
      await createDataSource(form.value)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    loadData()
  } catch (e) {
    ElMessage.error(errorMessage(e, '操作失败'))
  }
}

const handleDelete = (id) => {
  ElMessageBox.confirm('确认删除该数据源吗？', '提示', { type: 'warning' })
    .then(async () => {
      await deleteDataSource(id)
      ElMessage.success('删除成功')
      loadData()
    })
    .catch(() => {})
}

onMounted(loadData)
</script>
