export function readDraft<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key)
    return raw ? JSON.parse(raw) as T : fallback
  } catch {
    return fallback
  }
}

export function writeDraft(key: string, value: unknown) {
  localStorage.setItem(key, JSON.stringify(value))
}

export function removeDraft(key: string) {
  localStorage.removeItem(key)
}
