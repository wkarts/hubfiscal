<script setup lang="ts">
import { onMounted, onUnmounted, reactive, ref } from 'vue'
import { Plus, Search, SlidersHorizontal } from 'lucide-vue-next'
import { api, errorMessage } from '../api'
import DataTable from '../components/DataTable.vue'
import Modal from '../components/Modal.vue'
import PageHeader from '../components/PageHeader.vue'
import StatusBadge from '../components/StatusBadge.vue'

interface ResourceItem { key: string; label: string }

const rows = ref<any[]>([])
const resources = ref<ResourceItem[]>([])
const open = ref(false)
const resourceOpen = ref(false)
const error = ref('')
const lookupLoading = ref(false)
const editing = ref<any | null>(null)
const form = reactive({
  document: '',
  legal_name: '',
  trade_name: '',
  state_registration: '',
  city_ibge_code: '',
  municipal_registrations: [] as any[],
  relationship_type: 'client',
  enabled_resources: [] as string[],
})
const resourceSelection = ref<string[]>([])
const cols = [
  { key: 'legal_name', label: 'Razão social' },
  { key: 'trade_name', label: 'Fantasia' },
  { key: 'document_display', label: 'CNPJ/CPF' },
  { key: 'relationship_label', label: 'Vínculo' },
  { key: 'resource_count', label: 'Recursos' },
  { key: 'status', label: 'Situação' },
]

function displayDocument(value: string) {
  if (!value || value.length !== 14) return value
  return `${value.slice(0, 2)}.${value.slice(2, 5)}.${value.slice(5, 8)}/${value.slice(8, 12)}-${value.slice(12)}`
}
function normalizeRows(items: any[]) {
  return items.map((item) => ({
    ...item,
    document_display: displayDocument(item.document),
    relationship_label: item.is_primary ? 'Tenant principal' : item.relationship_type === 'client' ? 'Cliente atendido' : item.relationship_type,
    resource_count: `${item.enabled_resources?.length || 0} habilitados`,
  }))
}
function resetForm() {
  Object.assign(form, {
    document: '', legal_name: '', trade_name: '', state_registration: '', city_ibge_code: '',
    municipal_registrations: [], relationship_type: 'client', enabled_resources: resources.value.map((item) => item.key),
  })
  error.value = ''
}
function toggleFormResource(key: string) {
  form.enabled_resources = form.enabled_resources.includes(key)
    ? form.enabled_resources.filter((item) => item !== key)
    : [...form.enabled_resources, key]
}
function toggleEditResource(key: string) {
  resourceSelection.value = resourceSelection.value.includes(key)
    ? resourceSelection.value.filter((item) => item !== key)
    : [...resourceSelection.value, key]
}
async function load() {
  const [companiesResponse, resourcesResponse] = await Promise.all([
    api.get('/legal-entities'),
    api.get('/access-profiles/resources'),
  ])
  resources.value = resourcesResponse.data
  rows.value = normalizeRows(companiesResponse.data)
  if (!form.enabled_resources.length) form.enabled_resources = resources.value.map((item) => item.key)
}
async function lookupCnpj() {
  if (!form.document) return
  lookupLoading.value = true
  error.value = ''
  try {
    const { data } = await api.get(`/company-lookup/${encodeURIComponent(form.document)}`)
    form.document = data.formatted_document
    form.legal_name = data.legal_name || form.legal_name
    form.trade_name = data.trade_name || form.trade_name
    form.state_registration = data.state_registration || form.state_registration
    form.city_ibge_code = data.city_ibge_code || form.city_ibge_code
  } catch (exception) {
    error.value = `${errorMessage(exception)}. Você ainda pode preencher os dados manualmente.`
  } finally {
    lookupLoading.value = false
  }
}
async function save() {
  error.value = ''
  try {
    await api.post('/legal-entities', { ...form, lookup_company: true })
    open.value = false
    resetForm()
    await load()
  } catch (exception) {
    error.value = errorMessage(exception)
  }
}
function editResources(row: any) {
  editing.value = row
  resourceSelection.value = [...(row.enabled_resources || [])]
  error.value = ''
  resourceOpen.value = true
}
async function saveResources() {
  if (!editing.value) return
  try {
    await api.patch(`/legal-entities/${editing.value.id}/resources`, { enabled_resources: resourceSelection.value })
    resourceOpen.value = false
    await load()
  } catch (exception) {
    error.value = errorMessage(exception)
  }
}
function showCreate() {
  resetForm()
  open.value = true
}

onMounted(() => {
  load()
  window.addEventListener('tenant-changed', load)
})
onUnmounted(() => window.removeEventListener('tenant-changed', load))
</script>

<template>
  <PageHeader title="Empresas e CNPJs" subtitle="CNPJs atendidos pelo tenant, cada um com certificados, documentos e recursos próprios">
    <button class="btn primary" @click="showCreate"><Plus :size="16" />Nova empresa</button>
  </PageHeader>

  <section class="panel">
    <DataTable :columns="cols" :rows="rows">
      <template #cell-status="{ value }"><StatusBadge :status="value" /></template>
      <template #actions="{ row }"><button class="btn small" @click="editResources(row)"><SlidersHorizontal :size="14" />Recursos</button></template>
    </DataTable>
  </section>

  <Modal :open="open" title="Cadastrar empresa / CNPJ" @close="open=false">
    <form class="form-grid" @submit.prevent="save">
      <label class="span-2">CNPJ/CPF
        <div class="inline-field">
          <input v-model="form.document" required placeholder="00.000.000/0000-00 ou CNPJ alfanumérico" />
          <button type="button" class="btn" :disabled="lookupLoading || !form.document" @click="lookupCnpj">
            <Search :size="15" />{{ lookupLoading ? 'Consultando...' : 'Consultar CNPJ' }}
          </button>
        </div>
      </label>
      <label>Razão social<input v-model="form.legal_name" placeholder="Preenchida pela consulta ou manualmente" /></label>
      <label>Nome fantasia<input v-model="form.trade_name" /></label>
      <label>Inscrição estadual<input v-model="form.state_registration" /></label>
      <label>Código IBGE<input v-model="form.city_ibge_code" /></label>
      <label>Tipo de vínculo
        <select v-model="form.relationship_type">
          <option value="client">Cliente atendido</option>
          <option value="branch">Filial / estabelecimento</option>
          <option value="managed">Empresa gerenciada</option>
        </select>
      </label>
      <div class="span-2 resource-section">
        <div class="resource-heading"><strong>Recursos desta empresa</strong><small>Todos começam habilitados; desmarque o que não se aplica.</small></div>
        <div class="resource-grid">
          <label v-for="resource in resources" :key="resource.key" class="check-card">
            <input type="checkbox" :checked="form.enabled_resources.includes(resource.key)" @change="toggleFormResource(resource.key)" />
            <span>{{ resource.label }}</span>
          </label>
        </div>
      </div>
      <div v-if="error" class="alert danger span-2">{{ error }}</div>
      <div class="form-actions span-2"><button type="button" class="btn" @click="open=false">Cancelar</button><button class="btn primary">Salvar empresa</button></div>
    </form>
  </Modal>

  <Modal :open="resourceOpen" :title="`Recursos — ${editing?.legal_name || ''}`" @close="resourceOpen=false">
    <div class="resource-section">
      <p class="muted-text">Ative somente os módulos que este CNPJ utilizará dentro do tenant.</p>
      <div class="resource-grid">
        <label v-for="resource in resources" :key="resource.key" class="check-card">
          <input type="checkbox" :checked="resourceSelection.includes(resource.key)" @change="toggleEditResource(resource.key)" />
          <span>{{ resource.label }}</span>
        </label>
      </div>
      <div v-if="error" class="alert danger">{{ error }}</div>
      <div class="form-actions"><button class="btn" @click="resourceOpen=false">Cancelar</button><button class="btn primary" @click="saveResources">Salvar recursos</button></div>
    </div>
  </Modal>
</template>
