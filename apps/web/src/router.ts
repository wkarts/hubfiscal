import { createRouter, createWebHistory } from 'vue-router'
import LoginView from './views/LoginView.vue'
import BootstrapView from './views/BootstrapView.vue'
import DashboardView from './views/DashboardView.vue'
import TenantsView from './views/TenantsView.vue'
import UsersView from './views/UsersView.vue'
import LegalEntitiesView from './views/LegalEntitiesView.vue'
import CertificatesView from './views/CertificatesView.vue'
import PluginsView from './views/PluginsView.vue'
import PoliciesView from './views/PoliciesView.vue'
import DocumentsView from './views/DocumentsView.vue'
import NfseView from './views/NfseView.vue'
import QueryView from './views/QueryView.vue'
import JobsView from './views/JobsView.vue'
import ApiClientsView from './views/ApiClientsView.vue'
import WebhooksView from './views/WebhooksView.vue'
import AuditView from './views/AuditView.vue'
import SettingsView from './views/SettingsView.vue'
import ProfileView from './views/ProfileView.vue'

const routes = [
  { path: '/login', component: LoginView, meta: { public: true } },
  { path: '/bootstrap', component: BootstrapView, meta: { public: true } },
  { path: '/', component: DashboardView },
  { path: '/tenants', component: TenantsView },
  { path: '/users', component: UsersView },
  { path: '/companies', component: LegalEntitiesView },
  { path: '/certificates', component: CertificatesView },
  { path: '/plugins', component: PluginsView },
  { path: '/policies', component: PoliciesView },
  { path: '/documents', component: DocumentsView },
  { path: '/nfse', component: NfseView },
  { path: '/query', component: QueryView },
  { path: '/jobs', component: JobsView },
  { path: '/api-clients', component: ApiClientsView },
  { path: '/webhooks', component: WebhooksView },
  { path: '/audit', component: AuditView },
  { path: '/settings', component: SettingsView },
  { path: '/profile', component: ProfileView },
]

const router = createRouter({ history: createWebHistory(), routes })
router.beforeEach((to) => {
  if (!to.meta.public && !localStorage.getItem('hf_access_token')) return '/login'
  if (to.path === '/login' && localStorage.getItem('hf_access_token')) return '/'
})
export default router
