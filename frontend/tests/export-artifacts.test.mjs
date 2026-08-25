import assert from 'node:assert/strict'
import test from 'node:test'
import ExcelJS from 'exceljs'

import { buildXlsxBuffer, safeFileName } from '../src/utils/exportArtifacts.js'

test('XLSX export preserves complete rows and spreadsheet types', async () => {
  const { buffer, rowCount } = await buildXlsxBuffer({
    columns: ['厂商', '销售额', '统计时间'],
    rows: [
      ['厂商 A', 1200.5, '2026-08-15 10:30:00'],
      ['厂商 B', 800, '2026-08-15']
    ]
  })

  const workbook = new ExcelJS.Workbook()
  await workbook.xlsx.load(buffer)
  const worksheet = workbook.getWorksheet('查询结果')

  assert.equal(rowCount, 2)
  assert.equal(worksheet.rowCount, 3)
  assert.equal(worksheet.getCell('A2').value, '厂商 A')
  assert.equal(worksheet.getCell('B2').value, 1200.5)
  assert.ok(worksheet.getCell('C2').value instanceof Date)
  assert.equal(worksheet.views[0].state, 'frozen')
  assert.equal(worksheet.views[0].ySplit, 1)
  assert.deepEqual(worksheet.autoFilter, 'A1:C1')
  assert.equal(worksheet.getCell('A1').fill.fgColor.argb, 'FF3157D5')
})

test('download filenames remove characters rejected by operating systems', () => {
  assert.equal(safeFileName('各厂商/销售额:*?', '结果'), '各厂商-销售额---')
})
