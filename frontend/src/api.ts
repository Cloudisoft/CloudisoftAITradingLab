const BASE = import.meta.env.VITE_API_URL ?? ''

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const token = sessionStorage.getItem('clab_token')
  const res = await fetch(BASE + path, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init?.headers,
    },
  })
  if (!res.ok) {
    const text = await res.text()
    let msg = text
    try {
      const d = JSON.parse(text).detail
      msg = Array.isArray(d) ? d.map((e: { field?: string; message?: string; msg?: string }) => `${e.field ?? ''}: ${e.message ?? e.msg}`).join('; ') : String(d)
    } catch { /* keep raw text */ }
    throw new Error(`${res.status} ${msg}`)
  }
  return res.json() as Promise<T>
}

export async function login(email: string, password: string) {
  const body = new URLSearchParams({ username: email, password })
  const res = await fetch(BASE + '/api/auth/token', { method: 'POST', body })
  if (!res.ok) throw new Error('Login failed')
  const { access_token } = await res.json()
  sessionStorage.setItem('clab_token', access_token) // session only; never localStorage
}
