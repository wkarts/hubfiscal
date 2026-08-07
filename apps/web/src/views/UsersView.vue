<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { Pencil, Plus, ShieldCheck } from 'lucide-vue-next'
import { api, errorMessage } from '../api'
import { useAuthStore } from '../stores/auth'
import DataTable from '../components/DataTable.vue'
import Modal from '../components/Modal.vue'
import PageHeader from '../components/PageHeader.vue'
import StatusBadge from '../components/StatusBadge.vue'

interface ResourceItem { key: string; label: string }

const auth = useAuthStore()
const rows = ref<any[]>([])
const profiles = ref<any[]>([])
const entities = ref<any[]>([])
const resources = ref<ResourceItem[]>([])
const userOpen = ref(false)
const profileOpen = ref(false)
const error = ref('')
const editingUser = ref<any | null>(null)
const editingProfile = ref<any | null>(null)
const form = reactive({ name: '', email: '', password: '', profile_id: '', entity_scope: [] as string[] })
const profileForm = reactive({ name: '', key: '', description: '', enabled_resources: [] as string[], can_manage: false })
const cols = [
  { key: 'name', label: 'Nome' },
  { key: 'email', label: 'E-mail' },
  { key: 'profile_name', label: 'Perfil' },
  { key: 'scope_label', label: 'Escopo CNPJ' },
  { key: 'resource_count', label: 'Recursos' },
  { key: 'status', label: 'Situação' },
]
const profileCols = [
  { key: 'name', label: 'Perfil' },
  { key: 'description', label: 'Descrição' },
  { key: 'permissions_label', label: 'Permissões' },
  { key: 'resource_count', label: 'Recursos' },
  { key: 'system_label', label: 'Origem' },
]
const tenantSelected = computed(() => Boolean(auth.tenantId))
const canUsers = computed(() => !auth.tenantId ? Boolean(auth.user?.is_platform_admin) : auth.enabledResources.includes('users'))
const canProfiles = computed(() => Boolean(auth.tenantId) && auth.enabledResources.includes('profiles'))

function mapUsers(items: any[]) {
  return items.map((item) => ({
    ...item,
    profile_name: item.profile_name || item.role,
    scope_label: item.entity_scope?.length ? `${item.entity_scope.length} CNPJ(s)` : 'Todos os CNPJs',
    resource_count: `${item.enabled_resources?.length || 0}`,
  }))
}
function mapProfiles(items: any[]) {
  return items.map((item) => ({
    ...item,
    permissions_label: item.permissions?.includes('*') ? 'Controle total' : (item.permissions || []).join(', '),
    resource_count: `${item.enabled_resources?.length || 0} habilitados`,
    system_label: item.system ? 'Padrão' : 'Personalizado',
  }))
}
async function load() {
  error.value = ''
  rows.value = []
  profiles.value = []
  entities.value = []
  try {
    const resourceResponse = await api.get('/access-profiles/resources')
    resources.value = resourceResponse.data
    if (!auth.tenantId) {
      if (canUsers.value) rows.value = mapUsers((await api.get('/users')).data)
      return
    }

    const requests: Promise<any>[] = []
    const keys: string[] = []
    if (canUsers.value) {
      keys.push('users', 'entities')
      requests.push(api.get('/users'), api.get('/legal-entities/options'))
    }
    if (canUsers.value || canProfiles.value) {
      keys.push('profiles')
      requests.push(api.get('/access-profiles'))
    }
    const responses = await Promise.all(requests)
    responses.forEach((response, index) => {
      const key = keys[index]
      if (key === 'users') rows.value = mapUsers(response.data)
      if (key === 'entities') entities.value = response.data
      if (key === 'profiles') profiles.value = mapProfiles(response.data)
    })
  } catch (exception) {
    error.value = errorMessage(exception)
  }
}
function toggleScope(id: string) {
  form.entity_scope = form.entity_scope.includes(id)
    ? form.entity_scope.filter((item) => item !== id)
    : [...form.entity_scope, id]
}
function toggleProfileResource(key: string) {
  profileForm.enabled_resources = profileForm.enabled_resources.includes(key)
    ? profileForm.enabled_resources.filter((item) => item !== key)
    : [...profileForm.enabled_resources, key]
}
function showUserCreate() {
  if (!tenantSelected.value || !canUsers.value) return
  editingUser.value = null
  Object.assign(form, { name: '', email: '', password: '', profile_id: profiles.value[0]?.id || '', entity_scope: [] })
  error.value = ''
  userOpen.value = true
}
function editUser(row: any) {
  editingUser.value = row
  Object.assign(form, { name: row.name, email: row.email, password: '', profile_id: row.profile_id || '', entity_scope: [...(row.entity_scope || [])] })
  error.value = ''
  userOpen.value = true
}
async function saveUser() {
  try {
    if (editingUser.value) {
      await api.patch(`/users/${editingUser.value.id}/membership`, { profile_id: form.profile_id, entity_scope: form.entity_scope })
    } else {
      await api.post('/users', { ...form, role: profiles.value.find((profile) => profile.id === form.profile_id)?.key || 'tenant_admin' })
    }
    userOpen.value = false
    await load()
  } catch (exception) {
    error.value = errorMessage(exception)
  }
}
function showProfileCreate() {
  if (!tenantSelected.value || !canProfiles.value) return
  editingProfile.value = null
  Object.assign(profileForm, { name: '', key: '', description: '', enabled_resources: [...auth.enabledResources], can_manage: false })
  error.value = ''
  profileOpen.value = true
}
function editProfile(row: any) {
  editingProfile.value = row
  Object.assign(profileForm, {
    name: row.name,
    key: row.key,
    description: row.description || '',
    enabled_resources: [...(row.enabled_resources || [])],
    can_manage: row.permissions?.includes('manage') || row.permissions?.includes('*'),
  })
  error.value = ''
  profileOpen.value = true
}
async function saveProfile() {
  try {
    if (editingProfile.value) {
      const payload: any = {
        name: profileForm.name,
        description: profileForm.description,
        enabled_resources: profileForm.enabled_resources,
      }
      if (!editingProfile.value.system) payload.permissions = profileForm.can_manage ? ['read', 'write', 'manage'] : ['read', 'write']
      await api.patch(`/access-profiles/${editingProfile.value.id}`, payload)
    } else {
      await api.post('/access-profiles', {
        name: profileForm.name,
        key: profileForm.key,
        description: profileForm.description,
        permissions: profileForm.can_manage ? ['read', 'write', 'manage'] : ['read', 'write'],
        enabled_resources: profileForm.enabled_resources,
        entity_scope_mode: 'all',
      })
    }
    profileOpen.value = false
    await auth.loadContext()
    await load()
  } catch (exception) {
    error.value = errorMessage(exception)
  }
}

onMounted(() => {
  load()
  window.addEventListener('tenant-changed', load)
})
onUnmounted(() => window.removeEventListener('tenant-changed', load))
</script>

<template>
  <PageHeader title="Usuários, perfis e permissões" subtitle="Associe cada usuário a um perfil e, opcionalmente, limite o acesso a CNPJs específicos">
    <div class="page-actions" v-if="tenantSelected">
      <button v-if="canProfiles" class="btn" @click="showProfileCreate"><ShieldCheck :size="16" />Novo perfil</button>
      <button v-if="canUsers" class="btn primary" @click="showUserCreate"><Plus :size="16" />Novo usuário</button>
    </div>
  </PageHeader>

  <div v-if="!tenantSelected" class="info-banner">
    <ShieldCheck :size="20" /><div><strong>Selecione um tenant</strong><span>Perfis, usuários e escopos são configurados dentro de cada tenant.</span></div>
  </div>
  <div v-if="tenantSelected && !canUsers && !canProfiles" class="info-banner">
    <ShieldCheck :size="20" /><div><strong>Recursos de acesso desabilitados</strong><span>Este perfil não possui os módulos Usuários ou Perfis.</span></div>
  </div>
  <div v-if="error" class="alert danger">{{ error }}</div>

  <section v-if="canUsers" class="panel">
    <div class="panel-title"><div><h3>Usuários</h3><p>Acesso administrativo e fiscal do tenant selecionado.</p></div></div>
    <DataTable :columns="cols" :rows="rows">
      <template #cell-status="{ value }"><StatusBadge :status="value" /></template>
      <template #actions="{ row }"><button v-if="tenantSelected" class="btn small" @click="editUser(row)"><Pencil :size="14" />Acesso</button></template>
    </DataTable>
  </section>

  <section v-if="canProfiles" class="panel section-gap">
    <div class="panel-title"><div><h3>Perfis do tenant</h3><p>Os recursos marcados definem o que aparece e pode ser acessado pelo perfil.</p></div></div>
    <DataTable :columns="profileCols" :rows="profiles">
      <template #actions="{ row }"><button class="btn small" @click="editProfile(row)"><Pencil :size="14" />Configurar</button></template>
    </DataTable>
  </section>

  <Modal :open="userOpen" :title="editingUser ? 'Alterar acesso do usuário' : 'Novo usuário'" @close="userOpen=false">
    <form class="form-grid" @submit.prevent="saveUser">
      <template v-if="!editingUser">
        <label>Nome<input v-model="form.name" required /></label>
        <label>E-mail<input v-model="form.email" type="email" required /></label>
        <label class="span-2">Senha inicial<input v-model="form.password" type="password" minlength="10" required /></label>
      </template>
      <label class="span-2">Perfil
        <select v-model="form.profile_id" required>
          <option v-for="profile in profiles" :key="profile.id" :value="profile.id">{{ profile.name }}</option>
        </select>
      </label>
      <div class="span-2 resource-section">
        <div class="resource-heading"><strong>Escopo de CNPJs</strong><small>Nenhum marcado significa acesso a todos os CNPJs permitidos pelo perfil.</small></div>
        <div class="resource-grid">
          <label v-for="entity in entities" :key="entity.id" class="check-card">
            <input type="checkbox" :checked="form.entity_scope.includes(entity.id)" @change="toggleScope(entity.id)" />
            <span>{{ entity.trade_name || entity.legal_name }}<small>{{ entity.document }}</small></span>
          </label>
        </div>
      </div>
      <div v-if="error" class="alert danger span-2">{{ error }}</div>
      <div class="form-actions span-2"><button type="button" class="btn" @click="userOpen=false">Cancelar</button><button class="btn primary">Salvar acesso</button></div>
    </form>
  </Modal>

  <Modal :open="profileOpen" :title="editingProfile ? `Configurar perfil — ${editingProfile.name}` : 'Novo perfil'" @close="profileOpen=false">
    <form class="form-grid" @submit.prevent="saveProfile">
      <label>Nome<input v-model="profileForm.name" required /></label>
      <label>Chave<input v-model="profileForm.key" :disabled="Boolean(editingProfile)" required pattern="[a-z0-9_-]+" /></label>
      <label class="span-2">Descrição<input v-model="profileForm.description" /></label>
      <label v-if="!editingProfile?.system" class="check-line span-2"><input v-model="profileForm.can_manage" type="checkbox" />Pode administrar usuários e perfis</label>
      <div class="span-2 resource-section">
        <div class="resource-heading"><strong>Recursos do perfil</strong><small>Selecione somente os módulos que esse perfil deve utilizar.</small></div>
        <div class="resource-grid">
          <label v-for="resource in resources" :key="resource.key" class="check-card">
            <input type="checkbox" :checked="profileForm.enabled_resources.includes(resource.key)" @change="toggleProfileResource(resource.key)" />
            <span>{{ resource.label }}</span>
          </label>
        </div>
      </div>
      <div v-if="error" class="alert danger span-2">{{ error }}</div>
      <div class="form-actions span-2"><button type="button" class="btn" @click="profileOpen=false">Cancelar</button><button class="btn primary">Salvar perfil</button></div>
    </form>
  </Modal>
</template>
