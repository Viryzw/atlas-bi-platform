import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const appSource = readFileSync(new URL('../public/assets/app.js', import.meta.url), 'utf8')

test('an empty enterprise catalog does not block SQL-file onboarding', () => {
  assert.match(appSource, /entity === 'departments' && !state\.enterprises\.length/)
  assert.doesNotMatch(
    appSource,
    /\['datasources', 'departments'\]\.includes\(entity\) && !state\.enterprises\.length/
  )
  assert.match(appSource, /file_name: file\.name/)
  assert.match(appSource, /企业名-数据源名\.sql/)
})
