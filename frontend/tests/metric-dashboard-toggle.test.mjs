import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const appSource = readFileSync(new URL('../public/assets/app.js', import.meta.url), 'utf8')

test('metric dashboard badges are interactive and persist through the dedicated endpoint', () => {
  assert.match(appSource, /data-toggle-metric-dashboard=/)
  assert.match(appSource, /\/api\/admin\/metrics\/\$\{numericId\}\/dashboard-enabled/)
  assert.match(appSource, /method: 'PATCH'/)
  assert.match(appSource, /invalidateDashboardConfiguration\(\)/)
  assert.match(appSource, /dashboard_enabled: previousEnabled/)
})

test('current KPI arrays never fall back to legacy fixed dashboard cards', () => {
  assert.match(appSource, /if \(Array\.isArray\(data\.kpis\)\) return data\.kpis/)
  assert.match(appSource, /dashboardConfigurationStale/)
})
