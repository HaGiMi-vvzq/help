import api from './client'

export function getSettings() {
  return api.get<{ has_api_key: boolean; api_key_masked: string; base_url: string; pro_model: string; flash_model: string }>('/settings')
}

export function updateSettings(data: { deepseek_api_key: string }) {
  return api.put<{ ok: boolean; message: string }>('/settings', data)
}

export function testApiKey(data: { deepseek_api_key: string }) {
  return api.post<{ ok: boolean; message: string; connection_path?: 'default' | 'local_proxy' }>('/settings/test-api-key', data)
}
