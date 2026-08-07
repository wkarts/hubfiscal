import { defineStore } from 'pinia'
import { api } from '../api'

interface User { id: string; name: string; email: string; is_platform_admin: boolean }
interface Tenant {
  id: string
  name: string
  slug: string
  type: string
  status: string
  settings: Record<string, any>
}
interface TenantContext {
  tenant_id: string | null
  role: string | null
  permissions: string[]
  enabled_resources: string[]
  entity_scope: string[]
  profile_id: string | null
  profile_name: string | null
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null as User | null,
    tenants: [] as Tenant[],
    tenantId: localStorage.getItem('hf_tenant_id') || '',
    context: null as TenantContext | null,
    ready: false,
  }),
  getters: {
    authenticated: () => Boolean(localStorage.getItem('hf_access_token')),
    selectedTenant(state): Tenant | undefined { return state.tenants.find((tenant) => tenant.id === state.tenantId) },
    enabledResources(state): string[] {
      if (!state.tenantId && state.user?.is_platform_admin) return []
      return state.context?.enabled_resources || state.selectedTenant?.settings?.enabled_resources || []
    },
    hasResource(): (resource: string) => boolean {
      return (resource: string) => {
        if (!this.tenantId && this.user?.is_platform_admin) return true
        return this.enabledResources.includes(resource)
      }
    },
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
      this.tenantId = ''
      this.context = null
      location.href = '/login'
    },
    async loadContext() {
      if (!this.tenantId) {
        this.context = null
        return
      }
      try {
        this.context = (await api.get('/auth/context')).data
      } catch {
        this.context = null
      }
    },
    async load() {
      if (!this.authenticated) { this.ready = true; return }
      const { data } = await api.get('/auth/me')
      this.user = data
      try { this.tenants = (await api.get('/auth/tenants')).data } catch { this.tenants = [] }
      if (this.tenantId && !this.tenants.some((tenant) => tenant.id === this.tenantId)) {
        this.tenantId = ''
        localStorage.removeItem('hf_tenant_id')
      }
      if (!this.tenantId && this.tenants.length && !this.user?.is_platform_admin) {
        this.tenantId = this.tenants[0].id
        localStorage.setItem('hf_tenant_id', this.tenantId)
      }
      await this.loadContext()
      this.ready = true
    },
    async selectTenant(id: string) {
      this.tenantId = id
      if (id) localStorage.setItem('hf_tenant_id', id)
      else localStorage.removeItem('hf_tenant_id')
      await this.loadContext()
      window.dispatchEvent(new Event('tenant-changed'))
    },
  },
})
