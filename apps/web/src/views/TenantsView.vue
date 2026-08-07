<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { Plus, Search } from 'lucide-vue-next'
import { api, errorMessage } from '../api'
import DataTable from '../components/DataTable.vue'
import Modal from '../components/Modal.vue'
import PageHeader from '../components/PageHeader.vue'
import StatusBadge from '../components/StatusBadge.vue'

interface ResourceItem { key: string; label: string }
interface Preset { key: string; name: string; description: string; resources: string[] }

const rows = ref<any[]>([])
const presets = ref<Preset[]>([])
const resources = ref<ResourceItem[]>([])
const open = ref(false)
const error = ref('')
const lookupLoading = ref(false)
const form = reactive({
  name: '',
  slug: '',
  type: 'customer',
  document: '',
  resource_preset: 'complete',
  enabled_resources: [] as string[],
  owner_name: '',
  owner_email: '',
  owner_password: '',
})
const cols = [
  { key: 'name', label: 'Tenant / Cliente' },
  { key: 'primary_document', label: 'CNPJ principal' },
  { key: 'resource_preset', label: 'Recursos' },
  { key: 'type', label: 'Tipo' },
  { key: 'status', label: 'Situação' },
  { key: 'created_at', label: 'Criado em' },
]
const selectedPreset = computed(() => presets.value.find((preset) => preset.key === form.resource_preset))

function slugify(value: string) {
  return value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
}
function flattened(item: any) {
  return {
    ...item,
    primary_document: item.settings?.primary_document || '—',
    resource_preset: item.settings?.resource_preset === 'custom'
      ? `${item.settings?.enabled_resources?.length || 0} personalizados`
      : (presets.value.find((preset) => preset.key === item.settings?.resource_preset)?.name || item.settings?.resource_preset || 'Completo'),
  }
}
function applyPreset() {
  const preset = selectedPreset.value
  if (preset) form.enabled_resources = [...preset.resources]
}
function toggleResource(key: string) {
  form.resource_preset = 'custom'
  form.enabled_resources = form.enabled_resources.includes(key)
    ? form.enabled_resources.filter((item) => item !== key)
    : [...form.enabled_resources, key]
}
function resetForm() {
  Object.assign(form, {
    name: '', slug: '', type: 'customer', document: '', resource_preset: 'complete',
    enabled_resources: presets.value.find((preset) => preset.key === 'complete')?.resources || resources.value.map((item) => item.key),
    owner_name: '', owner_email: '', owner_password: '',
  })
  error.value = ''
}
async function load() {
  const [tenantResponse, presetResponse, resourceResponse] = await Promise.all([
    api.get('/tenants'),
    api.get('/tenants/resource-presets'),
    api.get('/access-profiles/resources'),
  ])
  presets.value = presetResponse.data
  resources.value = resourceResponse.data
  rows.value = tenantResponse.data.map(flattened)
  if (!form.enabled_resources.length) applyPreset()
}
async function lookupCnpj() {
  if (!form.document) return
  lookupLoading.value = true
  error.value = ''
  try {
    const { data } = await api.get(`/company-lookup/${encodeURIComponent(form.document)}`)
    form.document = data.formatted_document
    if (!form.name) form.name = data.trade_name || data.legal_name
    if (!form.slug && form.name) form.slug = slugify(form.name)
  } catch (exception) {
    error.value = errorMessage(exception)
  } finally {
    lookupLoading.value = false
  }
}
async function save() {
  error.value = ''
  try {
    const payload = { ...form, lookup_company: true }
    await api.post('/tenants', payload)
    open.value = false
    resetForm()
    await load()
  } catch (exception) {
    error.value = errorMessage(exception)
  }
}
function showCreate() {
  resetForm()
  open.value = true
}

onMounted(load)
</script>

<template>
  <PageHeader title="Tenants e clientes da plataforma" subtitle="Cada tenant possui usuários, perfis e vários CNPJs com recursos fiscais independentes">
    <button class="btn primary" @click="showCreate"><Plus :size="16" />Novo tenant</button>
  </PageHeader>

  <section class="panel">
    <DataTable :columns="cols" :rows="rows">
      <template #cell-status="{ value }"><StatusBadge :status="value" /></template>
      <template #cell-created_at="{ value }">{{ new Date(value).toLocaleDateString('pt-BR') }}</template>
    </DataTable>
  </section>

  <Modal :open="open" title="Cadastrar tenant / cliente" @close="open=false">
    <form class="form-grid" @submit.prevent="save">
      <label class="span-2">CNPJ principal
        <div class="inline-field">
          <input v-model="form.document" placeholder="00.000.000/0000-00 ou CNPJ alfanumérico" />
          <button type="button" class="btn" :disabled="lookupLoading || !form.document" @click="lookupCnpj">
            <Search :size="15" />{{ lookupLoading ? 'Consultando...' : 'Consultar' }}
          </button>
        </div>
      </label>
      <label>Nome do tenant<input v-model="form.name" required @blur="!form.slug && (form.slug=slugify(form.name))" /></label>
      <label>Identificador / slug<input v-model="form.slug" required /></label>
      <label>Tipo<select v-model="form.type"><option value="customer">Cliente</option><option value="partner">Parceiro / contabilidade</option></select></label>
      <label>Preset de recursos
        <select v-model="form.resource_preset" @change="applyPreset">
          <option v-for="preset in presets" :key="preset.key" :value="preset.key">{{ preset.name }}</option>
          <option value="custom">Personalizado</option>
        </select>
      </label>
      <div class="span-2 resource-section">
        <div class="resource-heading"><strong>Recursos habilitados</strong><small>{{ selectedPreset?.description || 'Seleção personalizada' }}</small></div>
        <div class="resource-grid">
          <label v-for="resource in resources" :key="resource.key" class="check-card">
            <input type="checkbox" :checked="form.enabled_resources.includes(resource.key)" @change="toggleResource(resource.key)" />
            <span>{{ resource.label }}</span>
          </label>
        </div>
      </div>
      <div class="form-separator">Administrador inicial do tenant</div>
      <label>Nome<input v-model="form.owner_name" /></label>
      <label>E-mail<input v-model="form.owner_email" type="email" /></label>
      <label class="span-2">Senha inicial<input v-model="form.owner_password" type="password" minlength="10" /></label>
      <div v-if="error" class="alert danger span-2">{{ error }}</div>
      <div class="form-actions span-2">
        <button type="button" class="btn" @click="open=false">Cancelar</button>
        <button class="btn primary">Criar tenant</button>
      </div>
    </form>
  </Modal>
</template>
