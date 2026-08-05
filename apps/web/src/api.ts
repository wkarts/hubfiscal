import axios from 'axios'

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 60000,
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('hf_access_token')
  const tenantId = localStorage.getItem('hf_tenant_id')
  if (token) config.headers.Authorization = `Bearer ${token}`
  if (tenantId) config.headers['X-Tenant-ID'] = tenantId
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('hf_access_token')
      localStorage.removeItem('hf_refresh_token')
      if (!location.pathname.includes('/login')) location.href = '/login'
    }
    return Promise.reject(error)
  },
)

export function errorMessage(error: any): string {
  return error?.response?.data?.detail || error?.message || 'Falha inesperada'
}
