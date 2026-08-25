import ExcelJS from 'exceljs'

export function safeFileName(value, fallback) {
  const normalized = String(value || fallback)
    .replace(/[\\/:*?"<>|]/g, '-')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 80)
  return normalized || fallback
}

export function downloadUrl(url, filename) {
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

export async function buildXlsxBuffer(data) {
  const columns = Array.isArray(data?.columns) ? data.columns : []
  const rows = Array.isArray(data?.rows) ? data.rows : []
  if (!columns.length) throw new Error('当前消息没有可导出的表格')

  const workbook = new ExcelJS.Workbook()
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
    column.width = Math.min(40, Math.max(12, ...values.map((value) => String(value ?? '').length + 2)))
    const populated = rows.map((row) => row?.[columnIndex]).filter((value) => value !== null && value !== undefined)
    if (populated.length && populated.every((value) => typeof value === 'number')) {
      column.numFmt = populated.some((value) => !Number.isInteger(value)) ? '#,##0.00' : '#,##0'
    } else if (column.values.slice(2).some((value) => value instanceof Date)) {
      column.numFmt = 'yyyy-mm-dd hh:mm:ss'
    }
  })

  const buffer = await workbook.xlsx.writeBuffer()
  return { buffer, rowCount: rows.length }
}

export async function exportRowsToXlsx(data, title = '智能问数结果') {
  const { buffer, rowCount } = await buildXlsxBuffer(data)
  downloadBlob(
    new Blob([buffer], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' }),
    `${safeFileName(title, '智能问数结果')}.xlsx`
  )
  return rowCount
}
