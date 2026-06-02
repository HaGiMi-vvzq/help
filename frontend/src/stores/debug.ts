import { defineStore } from 'pinia'
import { ref } from 'vue'

interface DebugEvent {
  id: number
  time: string
  type: 'success' | 'error' | 'info' | 'api'
  message: string
}

export const useDebugStore = defineStore('debug', () => {
  const events = ref<DebugEvent[]>([])
  const visible = ref(true)
  let nextId = 0

  function log(type: DebugEvent['type'], message: string) {
    events.value.push({
      id: nextId++,
      time: new Date().toLocaleTimeString(),
      type,
      message,
    })
    if (events.value.length > 50) events.value.shift()
  }

  function success(msg: string) { log('success', msg) }
  function error(msg: string) { log('error', msg) }
  function info(msg: string) { log('info', msg) }
  function api(msg: string) { log('api', msg) }

  function clear() { events.value = [] }
  function toggle() { visible.value = !visible.value }

  return { events, visible, log, success, error, info, api, clear, toggle }
})
