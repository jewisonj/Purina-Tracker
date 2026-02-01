import type { Product, LogEntry, InventoryAdjustment } from '../types'

const API_BASE = '/api'

function getToken(): string | null {
  return localStorage.getItem('auth_token')
}

function authHeaders(): HeadersInit {
  const token = getToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
      ...options.headers,
    },
  })

  if (res.status === 401) {
    localStorage.removeItem('auth_token')
    window.location.href = '/login'
    throw new Error('Unauthorized')
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `Request failed: ${res.status}`)
  }

  return res.json()
}

// Auth
export async function login(pin: string): Promise<string> {
  const data = await request<{ token: string; role: string }>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ pin }),
  })
  localStorage.setItem('auth_token', data.token)
  localStorage.setItem('auth_role', data.role)
  return data.role
}

export async function verifyAuth(): Promise<string | null> {
  try {
    const data = await request<{ status: string; user: string }>('/auth/verify')
    localStorage.setItem('auth_role', data.user)
    return data.user
  } catch {
    return null
  }
}

export function logout() {
  localStorage.removeItem('auth_token')
  localStorage.removeItem('auth_role')
  window.location.href = '/login'
}

export function isLoggedIn(): boolean {
  return !!getToken()
}

export function getRole(): string {
  return localStorage.getItem('auth_role') || ''
}

// Products
export async function getProducts(): Promise<Product[]> {
  return request<Product[]>('/products')
}

export async function updateMarkup(materialNo: string, markupPct: number): Promise<Product> {
  return request<Product>(`/products/${encodeURIComponent(materialNo)}/markup`, {
    method: 'PUT',
    body: JSON.stringify({ markup_pct: markupPct }),
  })
}

export async function updateReorder(materialNo: string, reorderPoint: number): Promise<Product> {
  return request<Product>(`/products/${encodeURIComponent(materialNo)}/reorder`, {
    method: 'PUT',
    body: JSON.stringify({ reorder_point: reorderPoint }),
  })
}

// Inventory
export async function adjustInventory(adj: InventoryAdjustment): Promise<Product> {
  return request<Product>('/inventory/adjust', {
    method: 'POST',
    body: JSON.stringify(adj),
  })
}

export async function bulkAdjust(adjustments: InventoryAdjustment[]): Promise<Product[]> {
  return request<Product[]>('/inventory/bulk-adjust', {
    method: 'POST',
    body: JSON.stringify({ adjustments }),
  })
}

export async function getLog(limit = 100): Promise<LogEntry[]> {
  return request<LogEntry[]>(`/inventory/log?limit=${limit}`)
}

export async function getLowStock(): Promise<Product[]> {
  return request<Product[]>('/inventory/low-stock')
}

// Price list archive
export async function getPriceListArchive(): Promise<{ headers: string[]; rows: string[][] }> {
  return request<{ headers: string[]; rows: string[][] }>('/pricelist/archive')
}

// Price list import
export async function importPriceList(file: File): Promise<{ updated: number; new_products: string[]; message: string }> {
  const token = getToken()
  const formData = new FormData()
  formData.append('file', file)

  const res = await fetch(`${API_BASE}/pricelist/import`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: formData,
  })

  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `Upload failed: ${res.status}`)
  }

  return res.json()
}
