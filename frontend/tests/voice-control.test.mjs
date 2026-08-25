import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const chatSource = readFileSync(new URL('../src/views/Chat.vue', import.meta.url), 'utf8')

test('Vue voice input exposes an explicit stop action', () => {
  assert.match(chatSource, /isListening \? '停止录音' : '语音'/)
  assert.match(chatSource, /voiceRecognition\.stop\(\)/)
  assert.match(chatSource, /recognition\.continuous = true/)
  assert.match(chatSource, /语音输入已停止，可编辑后发送/)
  assert.match(chatSource, /stopVoice\(true\)/)
})
