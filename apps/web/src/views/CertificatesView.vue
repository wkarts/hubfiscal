<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { api, errorMessage } from '../api'
import PageHeader from '../components/PageHeader.vue'
import Modal from '../components/Modal.vue'
import DataTable from '../components/DataTable.vue'
import StatusBadge from '../components/StatusBadge.vue'
import { Plus, ShieldCheck } from 'lucide-vue-next'

const rows = ref<any[]>([])
const entities = ref<any[]>([])
const open = ref(false)
const error = ref('')
const name = ref('')
const password = ref('')
const entityId = ref('')
const file = ref<File | null>(null)
const cols = [
  { key: 'name', label: 'Certificado' },
  { key: 'company_label', label: 'CNPJ / Empresa' },
  { key: 'certificate_type', label: 'Tipo' },
  { key: 'serial_number', label: 'Número de série' },
  { key: 'valid_until', label: 'Validade' },
  { key: 'status', label: 'Situação' },
]

function decorate(items: any[]) {
  const byId = new Map(entities.value.map((entity) => [entity.id, entity]))
  return items.map((item) => {
    const entity = item.legal_entity_id ? byId.get(item.legal_entity_id) : undefined
    return {
      ...item,
      company_label: entity ? `${entity.trade_name || entity.legal_name} · ${entity.document}` : 'Uso geral do tenant',
    }
  })
}
async function load() {
  try {
    const [certificateResponse, entityResponse] = await Promise.all([
      api.get('/certificates'),
      api.get('/legal-entities/options'),
    ])
    entities.value = entityResponse.data.filter((entity: any) => entity.enabled_resources?.includes('certificates'))
    rows.value = decorate(certificateResponse.data)
  } catch (exception) {
    error.value = errorMessage(exception)
  }
}
async function save() {
  if (!file.value) return
  const fd = new FormData()
  fd.append('name', name.value)
  fd.append('password', password.value)
  if (entityId.value) fd.append('legal_entity_id', entityId.value)
  fd.append('file', file.value)
  try {
    await api.post('/certificates', fd)
    open.value = false
    name.value = ''
    password.value = ''
    entityId.value = ''
    file.value = null
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
  <PageHeader title="Certificados digitais" subtitle="Cofre criptografado para múltiplos certificados A1 vinculados aos CNPJs do tenant">
    <button class="btn primary" @click="open=true"><Plus :size="16" />Cadastrar certificado</button>
  </PageHeader>
  <div class="info-banner"><ShieldCheck /><div><strong>Proteção de ponta a ponta</strong><span>Arquivos PFX/P12 e senhas são criptografados antes do armazenamento.</span></div></div>
  <div v-if="error" class="alert danger">{{ error }}</div>
  <section class="panel">
    <DataTable :columns="cols" :rows="rows">
      <template #cell-valid_until="{ value }">{{ value ? new Date(value).toLocaleDateString('pt-BR') : '—' }}</template>
      <template #cell-status="{ value }"><StatusBadge :status="value" /></template>
    </DataTable>
  </section>
  <Modal :open="open" title="Novo certificado A1" @close="open=false">
    <form class="form-grid" @submit.prevent="save">
      <label>Nome<input v-model="name" required /></label>
      <label>Empresa / CNPJ
        <select v-model="entityId">
          <option value="">Uso geral do tenant</option>
          <option v-for="entity in entities" :key="entity.id" :value="entity.id">{{ entity.trade_name || entity.legal_name }} · {{ entity.document }}</option>
        </select>
      </label>
      <label>Senha do PFX<input v-model="password" type="password" required /></label>
      <label>Arquivo<input type="file" accept=".pfx,.p12" required @change="file=($event.target as HTMLInputElement).files?.[0]||null" /></label>
      <div v-if="error" class="alert danger span-2">{{ error }}</div>
      <div class="form-actions span-2"><button class="btn primary">Criptografar e salvar</button></div>
    </form>
  </Modal>
</template>
