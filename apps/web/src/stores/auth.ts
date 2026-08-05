import { defineStore } from 'pinia'
import { api } from '../api'

interface User { id: string; name: string; email: string; is_platform_admin: boolean }
interface Tenant { id: string; name: string; slug: string; type: string; status: string }

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null as User | null,
    tenants: [] as Tenant[],
    tenantId: localStorage.getItem('hf_tenant_id') || '',
    ready: false,
  }),
  getters: {
    authenticated: () => Boolean(localStorage.getItem('hf_access_token')),
    selectedTenant(state): Tenant | undefined { return state.tenants.find((t) => t.id === state.tenantId) },
  },
  actions: {
    async login(email: string, password: string) {
      const { data } = await api.post('/auth/login', { email, password })
      localStorage.setItem('hf_access_token', data.access_token)
      localStorage.setItem('hf_refresh_token', data.refresh_token)
      await this.load()
    },
    logout() {
      localStorage.removeItem('hf_access_token')
      localStorage.removeItem('hf_refresh_token')
      localStorage.removeItem('hf_tenant_id')
      this.user = null
      this.tenants = []
      location.href = '/login'
    },
    async load() {
      if (!this.authenticated) { this.ready = true; return }
      const { data } = await api.get('/auth/me')
      this.user = data
      try { this.tenants = (await api.get('/auth/tenants')).data } catch { this.tenants = [] }
      if (!this.tenantId && this.tenants.length) this.selectTenant(this.tenants[0].id)
      this.ready = true
    },
    selectTenant(id: string) {
      this.tenantId = id
      localStorage.setItem('hf_tenant_id', id)
      window.dispatchEvent(new Event('tenant-changed'))
    },
  },
})
