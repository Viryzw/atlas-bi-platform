import assert from 'node:assert/strict'
import test from 'node:test'

import { createClientId } from '../public/assets/client-id.js'

test('client IDs use native randomUUID when available', () => {
  const expected = '123e4567-e89b-42d3-a456-426614174000'
  assert.equal(createClientId({ randomUUID: () => expected }), expected)
})

test('client IDs fall back to an RFC 4122 UUID when randomUUID is unavailable', () => {
  const cryptoApi = {
    getRandomValues(bytes) {
      bytes.forEach((_, index) => { bytes[index] = index })
      return bytes
    }
  }
  const id = createClientId(cryptoApi)

  assert.match(id, /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/)
})

test('client IDs still work without Web Crypto', () => {
  assert.match(createClientId(null), /^client-[a-z0-9]+-[a-z0-9]+$/)
})
