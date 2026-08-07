<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import {
  LayoutDashboard, Building2, Users, Landmark, ShieldCheck, PlugZap, GitBranch,
  Files, ReceiptText, Search, ListTodo, KeyRound, Webhook, ScrollText, Settings, Menu, Bell,
  ChevronDown, LogOut, BookOpen, Boxes
} from 'lucide-vue-next'

const auth = useAuthStore()
const route = useRoute()
const collapsed = ref(false)
const mobile = ref(false)
const appVersion = __APP_VERSION__
const buildSha = __BUILD_SHA__.slice(0, 8)
const buildDate = __BUILD_DATE__
const items = [
  { to: '/', label: 'Visão geral', icon: LayoutDashboard, resource: 'dashboard' },
  { to: '/tenants', label: 'Tenants / Clientes', icon: Building2, platform: true },
  { to: '/users', label: 'Usuários e perfis', icon: Users, resource: 'users' },
  { to: '/companies', label: 'Empresas e CNPJs', icon: Landmark, resource: 'companies' },
  { to: '/certificates', label: 'Certificados', icon: ShieldCheck, resource: 'certificates' },
  { to: '/plugins', label: 'Plugins', icon: PlugZap, resource: 'plugins' },
  { to: '/policies', label: 'Políticas', icon: GitBranch, resource: 'policies' },
  { to: '/documents', label: 'Documentos', icon: Files, resource: 'documents' },
  { to: '/nfse', label: 'NFS-e', icon: ReceiptText, resource: 'nfse' },
  { to: '/query', label: 'Consultar chave', icon: Search, resource: 'query' },
  { to: '/jobs', label: 'Jobs e lotes', icon: ListTodo, resource: 'jobs' },
  { to: '/api-clients', label: 'API e credenciais', icon: KeyRound, resource: 'api_clients' },
  { to: '/webhooks', label: 'Webhooks', icon: Webhook, resource: 'webhooks' },
  { to: '/audit', label: 'Auditoria', icon: ScrollText, resource: 'audit' },
  { to: '/settings', label: 'Configurações', icon: Settings, resource: 'integrations' },
]
const visibleItems = computed(() => items.filter((item) => {
  if (item.platform) return Boolean(auth.user?.is_platform_admin)
  if (!item.resource) return true
  if (!auth.tenantId && auth.user?.is_platform_admin) return true
  return auth.enabledResources.includes(item.resource)
}))
const profileLabel = computed(() => {
  if (auth.user?.is_platform_admin && !auth.tenantId) return 'Administrador da plataforma'
  return auth.context?.profile_name || auth.context?.role || 'Usuário fiscal'
})
</script>

<template>
  <div class="app-shell" :class="{ collapsed }">
    <aside class="sidebar" :class="{ mobileOpen: mobile }">
      <div class="brand">
        <div class="brand-mark"><Boxes :size="23" /></div>
        <div v-if="!collapsed"><strong>HUB FISCAL</strong><small>Plataforma inteligente</small></div>
      </div>
      <nav class="nav-list">
        <RouterLink v-for="item in visibleItems" :key="item.to" :to="item.to" class="nav-item" :class="{ active: route.path === item.to }" @click="mobile=false">
          <component :is="item.icon" :size="19" /><span v-if="!collapsed">{{ item.label }}</span>
        </RouterLink>
      </nav>
      <div class="sidebar-footer">
        <a href="/docs" target="_blank" class="nav-item"><BookOpen :size="19" /><span v-if="!collapsed">Documentação API</span></a>
        <button class="nav-item" @click="auth.logout"><LogOut :size="19" /><span v-if="!collapsed">Sair</span></button>
        <div v-if="!collapsed" class="version-info" :title="`Build ${buildSha} em ${buildDate}`">
          <strong>Versão {{ appVersion }}</strong>
          <small>build {{ buildSha }}</small>
        </div>
      </div>
    </aside>
    <div class="content-shell">
      <header class="topbar">
        <button class="icon-button" @click="collapsed=!collapsed; mobile=!mobile"><Menu :size="20" /></button>
        <div class="tenant-switcher" v-if="auth.tenants.length">
          <span>Tenant</span>
          <select :value="auth.tenantId" @change="auth.selectTenant(($event.target as HTMLSelectElement).value)">
            <option v-if="auth.user?.is_platform_admin" value="">Administração da plataforma</option>
            <option v-for="tenant in auth.tenants" :key="tenant.id" :value="tenant.id">{{ tenant.name }}</option>
          </select>
          <ChevronDown :size="16" />
        </div>
        <div class="topbar-spacer"></div>
        <button class="icon-button notification"><Bell :size="20" /><i></i></button>
        <div class="profile"><div class="avatar">{{ auth.user?.name?.slice(0,1) || 'H' }}</div><div><strong>{{ auth.user?.name || 'Carregando' }}</strong><small>{{ profileLabel }}</small></div></div>
      </header>
      <main class="main-content"><slot /></main>
    </div>
  </div>
</template>

<style scoped>
.version-info {
  margin: 8px 10px 2px;
  padding: 10px 12px;
  border-radius: 9px;
  background: rgba(255, 255, 255, 0.06);
  color: #dce9fb;
}
.version-info strong,
.version-info small {
  display: block;
}
.version-info strong {
  font-size: 11px;
}
.version-info small {
  margin-top: 3px;
  color: #8ca4c6;
  font-size: 9px;
}
</style>
