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
const items = [
  { to: '/', label: 'Visão geral', icon: LayoutDashboard },
  { to: '/tenants', label: 'Clientes', icon: Building2, platform: true },
  { to: '/users', label: 'Usuários', icon: Users },
  { to: '/companies', label: 'Empresas e CNPJs', icon: Landmark },
  { to: '/certificates', label: 'Certificados', icon: ShieldCheck },
  { to: '/plugins', label: 'Plugins', icon: PlugZap },
  { to: '/policies', label: 'Políticas', icon: GitBranch },
  { to: '/documents', label: 'Documentos', icon: Files },
  { to: '/nfse', label: 'NFS-e', icon: ReceiptText },
  { to: '/query', label: 'Consultar chave', icon: Search },
  { to: '/jobs', label: 'Jobs e lotes', icon: ListTodo },
  { to: '/api-clients', label: 'API e credenciais', icon: KeyRound },
  { to: '/webhooks', label: 'Webhooks', icon: Webhook },
  { to: '/audit', label: 'Auditoria', icon: ScrollText },
  { to: '/settings', label: 'Configurações', icon: Settings },
]
const visibleItems = computed(() => items.filter((i) => !i.platform || auth.user?.is_platform_admin))
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
      </div>
    </aside>
    <div class="content-shell">
      <header class="topbar">
        <button class="icon-button" @click="collapsed=!collapsed; mobile=!mobile"><Menu :size="20" /></button>
        <div class="tenant-switcher" v-if="auth.tenants.length">
          <span>Cliente</span>
          <select :value="auth.tenantId" @change="auth.selectTenant(($event.target as HTMLSelectElement).value)">
            <option value="">Administração da plataforma</option>
            <option v-for="tenant in auth.tenants" :key="tenant.id" :value="tenant.id">{{ tenant.name }}</option>
          </select>
          <ChevronDown :size="16" />
        </div>
        <div class="topbar-spacer"></div>
        <button class="icon-button notification"><Bell :size="20" /><i></i></button>
        <div class="profile"><div class="avatar">{{ auth.user?.name?.slice(0,1) || 'H' }}</div><div><strong>{{ auth.user?.name || 'Carregando' }}</strong><small>{{ auth.user?.is_platform_admin ? 'Administrador da plataforma' : 'Usuário fiscal' }}</small></div></div>
      </header>
      <main class="main-content"><slot /></main>
    </div>
  </div>
</template>
