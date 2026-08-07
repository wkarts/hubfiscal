<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import {
  Activity, CheckCircle2, ChevronRight, CirclePower, KeyRound, PackagePlus,
  PlugZap, RefreshCw, Settings2, ShieldCheck, Trash2, XCircle,
} from 'lucide-vue-next'
import { api, errorMessage } from '../api'
import Modal from '../components/Modal.vue'
import PageHeader from '../components/PageHeader.vue'
import StatusBadge from '../components/StatusBadge.vue'

const tabs = [
  { key: 'catalog', label: 'Aplicativos disponíveis' },
  { key: 'installed', label: 'Instalados' },
  { key: 'authorized', label: 'Credenciais e autorizações' },
]
const activeTab = ref('catalog')
const catalog = ref<any[]>([])
const installations = ref<any[]>([])
const entities = ref<any[]>([])
const certificates = ref<any[]>([])
const loading = ref(false)
const error = ref('')
const success = ref('')
const modalOpen = ref(false)
const modalMode = ref<'install' | 'edit'>('install')
const selectedDefinition = ref<any | null>(null)
const selectedInstallation = ref<any | null>(null)
const form = reactive({
  name: '',
  legal_entity_id: '',
  priority: 100,
  enabled: true,
  config: {} as Record<string, any>,
  secrets: {} as Record<string, string>,
})

const installedByKey = computed(() => {
  const map = new Map<string, any[]>()
  for (const item of installations.value) {
    const list = map.get(item.plugin_key) || []
    list.push(item)
    map.set(item.plugin_key, list)
  }
  return map
})
const authorizedItems = computed(() => installations.value.filter((item) =>
  item.configured_secret_keys?.length || item.definition?.capabilities?.requires_certificate,
))

function schemaOf(definition: any) {
  return definition?.config_schema || definition?.definition?.config_schema || {}
}
function configFields(definition: any) { return schemaOf(definition).config_fields || [] }
function secretFields(definition: any) { return schemaOf(definition).secret_fields || [] }
function categoryLabel(item: any) {
  const category = schemaOf(item).category
  return ({ official: 'Oficial', provider: 'Provedor', native: 'Nativo', municipal: 'Municipal', automation: 'Automação', assisted: 'Assistido', development: 'Desenvolvimento' } as any)[category] || 'Integração'
}
function maturityLabel(item: any) {
  const maturity = schemaOf(item).maturity
  return ({ native: 'Nativo', configurable: 'Configurável', assisted: 'Assistido', demo: 'Demonstração' } as any)[maturity] || 'Disponível'
}
function defaultFor(field: any) {
  if (field.default !== undefined) return field.default
  if (field.type === 'boolean') return false
  return ''
}
function resetForm() {
  form.name = ''
  form.legal_entity_id = ''
  form.priority = 100
  form.enabled = true
  form.config = {}
  form.secrets = {}
}
function prepareDefinition(definition: any, installation?: any) {
  resetForm()
  selectedDefinition.value = definition
  selectedInstallation.value = installation || null
  for (const field of configFields(definition)) {
    form.config[field.key] = installation?.config?.[field.key] ?? defaultFor(field)
  }
  for (const field of secretFields(definition)) form.secrets[field.key] = ''
  if (installation) {
    form.name = installation.name
    form.legal_entity_id = installation.legal_entity_id || ''
    form.priority = installation.priority
    form.enabled = installation.enabled
    modalMode.value = 'edit'
  } else {
    form.name = definition.name
    modalMode.value = 'install'
  }
  error.value = ''
  success.value = ''
  modalOpen.value = true
}
function openInstall(definition: any) { prepareDefinition(definition) }
function openEdit(installation: any) { prepareDefinition(installation.definition, installation) }

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [catalogResponse, installationsResponse, entitiesResponse, certificatesResponse] = await Promise.all([
      api.get('/plugins/catalog'),
      api.get('/plugins/installations'),
      api.get('/legal-entities/options'),
      api.get('/certificates'),
    ])
    catalog.value = catalogResponse.data
    installations.value = installationsResponse.data
    entities.value = entitiesResponse.data
    certificates.value = certificatesResponse.data
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loading.value = false
  }
}

function normalizedConfig() {
  const config: Record<string, any> = {}
  for (const field of configFields(selectedDefinition.value)) {
    const value = form.config[field.key]
    if (field.type === 'number' && value !== '' && value !== null && value !== undefined) config[field.key] = Number(value)
    else if (field.type === 'boolean') config[field.key] = Boolean(value)
    else if (value !== '' && value !== null && value !== undefined) config[field.key] = value
  }
  return config
}
function normalizedSecrets() {
  return Object.fromEntries(Object.entries(form.secrets).filter(([, value]) => String(value || '').trim() !== ''))
}

async function save() {
  if (!selectedDefinition.value) return
  error.value = ''
  try {
    if (modalMode.value === 'install') {
      await api.post('/plugins/installations', {
        plugin_key: selectedDefinition.value.key,
        name: form.name,
        legal_entity_id: form.legal_entity_id || null,
        priority: form.priority,
        enabled: form.enabled,
        config: normalizedConfig(),
        secrets: normalizedSecrets(),
      })
      success.value = 'Aplicativo instalado e pronto para configuração.'
    } else if (selectedInstallation.value) {
      await api.patch(`/plugins/installations/${selectedInstallation.value.id}`, {
        name: form.name,
        legal_entity_id: form.legal_entity_id || null,
        priority: form.priority,
        enabled: form.enabled,
        config: normalizedConfig(),
        secrets: normalizedSecrets(),
      })
      success.value = 'Configuração atualizada.'
    }
    modalOpen.value = false
    await load()
    activeTab.value = 'installed'
  } catch (e) {
    error.value = errorMessage(e)
  }
}
async function health(item: any) {
  error.value = ''
  try {
    const { data } = await api.post(`/plugins/installations/${item.id}/healthcheck`)
    success.value = data.message || (data.healthy ? 'Conexão aprovada.' : 'Conector respondeu com falha.')
    await load()
  } catch (e) { error.value = errorMessage(e) }
}
async function toggle(item: any) {
  error.value = ''
  try {
    await api.patch(`/plugins/installations/${item.id}`, { enabled: !item.enabled })
    await load()
  } catch (e) { error.value = errorMessage(e) }
}
async function remove(item: any) {
  if (!confirm(`Remover a instalação “${item.name}”?`)) return
  error.value = ''
  try {
    await api.delete(`/plugins/installations/${item.id}`)
    await load()
  } catch (e) { error.value = errorMessage(e) }
}
function certificateOptions(field: any) {
  if (field.type !== 'certificate') return []
  return certificates.value.filter((cert) => !form.legal_entity_id || !cert.legal_entity_id || cert.legal_entity_id === form.legal_entity_id)
}

onMounted(() => {
  load()
  window.addEventListener('tenant-changed', load)
})
onUnmounted(() => window.removeEventListener('tenant-changed', load))
</script>

<template>
  <PageHeader title="Aplicativos e conectores" subtitle="Instale, autorize e configure fontes fiscais sem editar JSON ou alterar o núcleo da plataforma">
    <button class="btn" :disabled="loading" @click="load"><RefreshCw :size="16" />Atualizar</button>
  </PageHeader>

  <div v-if="error" class="alert danger integrations-alert">{{ error }}</div>
  <div v-if="success" class="alert success integrations-alert">{{ success }}</div>

  <section class="panel applications-shell">
    <div class="applications-tabs">
      <button v-for="tab in tabs" :key="tab.key" :class="{ active: activeTab === tab.key }" @click="activeTab = tab.key">
        {{ tab.label }}
        <span v-if="tab.key === 'installed'">{{ installations.length }}</span>
        <span v-if="tab.key === 'authorized'">{{ authorizedItems.length }}</span>
      </button>
    </div>

    <div v-if="activeTab === 'catalog'" class="applications-list">
      <article v-for="app in catalog" :key="app.key" class="application-row">
        <div class="application-logo"><PlugZap :size="27" /></div>
        <div class="application-info">
          <div class="application-title-line">
            <h3>{{ app.name }}</h3>
            <span class="integration-chip">{{ categoryLabel(app) }}</span>
            <span class="integration-chip subtle">{{ maturityLabel(app) }}</span>
          </div>
          <p>{{ app.description || 'Integração fiscal disponível para o Hub Fiscal.' }}</p>
          <div class="application-capabilities">
            <span v-for="type in app.capabilities?.document_types || []" :key="type">{{ type.toUpperCase() }}</span>
            <span v-if="app.capabilities?.supports_batch">Lotes</span>
            <span v-if="app.capabilities?.supports_discovery">Descoberta</span>
            <span v-if="app.capabilities?.requires_certificate">Certificado A1</span>
          </div>
        </div>
        <div class="application-actions">
          <small v-if="app.installed_count">{{ app.installed_count }} instalação(ões)</small>
          <button class="btn primary" @click="openInstall(app)"><PackagePlus :size="16" />Instalar</button>
        </div>
      </article>
      <div v-if="!catalog.length && !loading" class="empty-applications">Nenhum aplicativo disponível.</div>
    </div>

    <div v-else-if="activeTab === 'installed'" class="applications-list">
      <article v-for="item in installations" :key="item.id" class="application-row">
        <div class="application-logo installed"><Settings2 :size="26" /></div>
        <div class="application-info">
          <div class="application-title-line">
            <h3>{{ item.name }}</h3>
            <StatusBadge :status="item.enabled ? item.health_status : 'disabled'" />
          </div>
          <p>{{ item.definition?.description }}</p>
          <div class="application-capabilities">
            <span>{{ item.definition?.name || item.plugin_key }}</span>
            <span>Prioridade {{ item.priority }}</span>
            <span v-if="item.legal_entity_id">Escopo por CNPJ</span>
            <span v-else>Todo o tenant</span>
          </div>
        </div>
        <div class="application-actions stacked">
          <button class="btn" @click="openEdit(item)"><Settings2 :size="15" />Configurar</button>
          <button class="btn" @click="health(item)"><Activity :size="15" />Testar</button>
          <button class="btn" @click="toggle(item)"><CirclePower :size="15" />{{ item.enabled ? 'Desativar' : 'Ativar' }}</button>
          <button class="icon-danger" title="Remover" @click="remove(item)"><Trash2 :size="16" /></button>
        </div>
      </article>
      <div v-if="!installations.length" class="empty-applications">
        <PlugZap :size="30" /><strong>Nenhum conector instalado</strong><span>Abra “Aplicativos disponíveis” e instale uma fonte fiscal.</span>
      </div>
    </div>

    <div v-else class="applications-list">
      <article v-for="item in authorizedItems" :key="item.id" class="application-row">
        <div class="application-logo authorized"><KeyRound :size="26" /></div>
        <div class="application-info">
          <div class="application-title-line"><h3>{{ item.name }}</h3><ShieldCheck :size="18" class="authorized-check" /></div>
          <p>{{ item.definition?.description }}</p>
          <div class="authorization-list">
            <span v-for="key in item.configured_secret_keys" :key="key"><CheckCircle2 :size="13" />{{ key }}</span>
            <span v-if="item.definition?.capabilities?.requires_certificate"><CheckCircle2 :size="13" />Certificado digital</span>
          </div>
        </div>
        <div class="application-actions">
          <span class="authorization-state" :class="{ active: item.authorized }">
            <CheckCircle2 v-if="item.authorized" :size="15" /><XCircle v-else :size="15" />{{ item.authorized ? 'Autorizado' : 'Pendente' }}
          </span>
          <button class="btn" @click="openEdit(item)">Revisar <ChevronRight :size="15" /></button>
        </div>
      </article>
      <div v-if="!authorizedItems.length" class="empty-applications">Nenhuma credencial externa configurada neste tenant.</div>
    </div>
  </section>

  <Modal :open="modalOpen" :title="modalMode === 'install' ? `Instalar ${selectedDefinition?.name || ''}` : `Configurar ${selectedInstallation?.name || ''}`" wide @close="modalOpen=false">
    <form class="integration-form" @submit.prevent="save">
      <div class="integration-form-intro">
        <div class="application-logo"><PlugZap :size="24" /></div>
        <div><strong>{{ selectedDefinition?.name }}</strong><p>{{ selectedDefinition?.description }}</p></div>
      </div>

      <div class="form-grid">
        <label>Nome da instalação<input v-model="form.name" required /></label>
        <label>Prioridade<input v-model.number="form.priority" type="number" min="1" max="9999" /></label>
        <label class="span-2">CNPJ / escopo
          <select v-model="form.legal_entity_id">
            <option value="">Todo o tenant</option>
            <option v-for="entity in entities" :key="entity.id" :value="entity.id">{{ entity.legal_name }} · {{ entity.document }}</option>
          </select>
        </label>

        <template v-for="field in configFields(selectedDefinition)" :key="field.key">
          <label :class="{ 'span-2': field.type === 'url' }">
            {{ field.label }}<small v-if="field.help" class="field-help">{{ field.help }}</small>
            <select v-if="field.type === 'select'" v-model="form.config[field.key]" :required="field.required">
              <option value="">Selecione</option>
              <option v-for="option in field.options || []" :key="option.value" :value="option.value">{{ option.label }}</option>
            </select>
            <select v-else-if="field.type === 'certificate'" v-model="form.config[field.key]" :required="field.required">
              <option value="">Selecione um certificado A1</option>
              <option v-for="cert in certificateOptions(field)" :key="cert.id" :value="cert.id">{{ cert.name }} · {{ cert.subject_document || 'sem documento' }}</option>
            </select>
            <span v-else-if="field.type === 'boolean'" class="switch-field"><input v-model="form.config[field.key]" type="checkbox" /> Ativo</span>
            <input v-else v-model="form.config[field.key]" :type="field.type === 'number' ? 'number' : field.type === 'url' ? 'url' : 'text'" :placeholder="field.placeholder" :required="field.required" :min="field.min" :max="field.max" />
          </label>
        </template>

        <div v-if="secretFields(selectedDefinition).length" class="form-separator">Credenciais protegidas</div>
        <label v-for="field in secretFields(selectedDefinition)" :key="field.key" class="span-2">
          {{ field.label }}
          <small class="field-help" v-if="modalMode === 'edit'">Deixe em branco para manter o valor já armazenado.</small>
          <input v-model="form.secrets[field.key]" type="password" :required="field.required && modalMode === 'install'" autocomplete="new-password" />
        </label>
        <label class="span-2 switch-line"><input v-model="form.enabled" type="checkbox" /> Ativar esta instalação imediatamente</label>
      </div>

      <div v-if="error" class="alert danger">{{ error }}</div>
      <div class="form-actions">
        <button type="button" class="btn" @click="modalOpen=false">Cancelar</button>
        <button class="btn primary">{{ modalMode === 'install' ? 'Instalar aplicativo' : 'Salvar configuração' }}</button>
      </div>
    </form>
  </Modal>
</template>
