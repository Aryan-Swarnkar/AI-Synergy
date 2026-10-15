// Overridable: $env:VITE_API_BASE="http://127.0.0.1:8001/api" (else :8000)
const BASE =
  (import.meta as unknown as { env?: Record<string, string> }).env?.VITE_API_BASE ??
  'http://127.0.0.1:8000/api'

export function authHeaders(): Record<string, string> {
  const t = localStorage.getItem('ks_token')
  return t ? { Authorization: `Bearer ${t}` } : {}
}

async function req(path: string, init?: RequestInit): Promise<unknown> {
  const r = await fetch(BASE + path, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...authHeaders(), ...(init?.headers ?? {}) },
  })
  const body = await r.json().catch(() => ({}))
  if (!r.ok) {
    const e = body as { error_code?: string; message?: string }
    throw new Error(`${e.error_code ?? r.status}: ${e.message ?? 'request failed'}`)
  }
  return body
}

export const api = {
  get: (p: string) => req(p),
  post: (p: string, b?: unknown) => req(p, { method: 'POST', body: b === undefined ? undefined : JSON.stringify(b) }),
  login: async (role: string, user_id: string) => {
    const r = (await req('/auth/demo-login', { method: 'POST', body: JSON.stringify({ role, user_id }) })) as { token: string }
    localStorage.setItem('ks_token', r.token)
    localStorage.setItem('ks_role', role)
    return r
  },
}
