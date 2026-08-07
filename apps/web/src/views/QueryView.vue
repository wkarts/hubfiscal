<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import {
  Boxes, CheckCircle2, Database, FileSearch, Layers3, ListPlus, RefreshCw,
  Route, Search, ServerCog, ShieldCheck,
} from 'lucide-vue-next'
import { api, errorMessage } from '../api'
import PageHeader from '../components/PageHeader.vue'
import StatusBadge from '../components/StatusBadge.vue'

const mode = ref<'single' | 'batch' | 'dfe'>('single')
const entities = ref<any[]>([])
const sources = ref<any[]>([])
const cursors = ref<any[]>([])
const job = ref<any | null>(null)
const batch = ref<any | null>(null)
const error = ref('')
const success = ref('')
const loading = ref(false)
const timer = ref<any>(null)

const common = reactive({
  legal_entity_id: '',
  document_type: 'nfe',
  environment: 'production',
  plugin_installation_id: '',
})
const single = reactive({ access_key: '' })
const batchForm = reactive({ access_keys_text: '' })
const dfe = reactive({
  plugin_installation_id: '',
  operation: 'distNSU',
  nsu: '',
  access_key: '',
})

const sourceOptions = computed(() => sources.value.filter((source) => {
  const documentTypes = source.capabilities?.document_types || []
  const supportsType = documentTypes.length === 0 || documentTypes.includes(common.document_type)
  const supportsEntity = !source.legal_entity_id || !common.legal_entity_id || source.legal_entity_id === common.legal_entity_id
  return supportsType && supportsEntity
}))
const dfeSources = computed(() => sources.value.filter((source) =>
  source.plugin_key === 'nfe-distribution' && (!source.legal_entity_id || !common.legal_entity_id || source.legal_entity_id === common.legal_entity_id),
))
const selectedCursor = computed(() => cursors.value.find((cursor) =>
  cursor.legal_entity_id === common.legal_entity_id &&
  cursor.plugin_installation_id === dfe.plugin_installation_id &&
  cursor.environment === common.environment,
))
const batchKeys = computed(() => {
  const seen = new Set<string>()
  return batchForm.access_keys_text
    .split(/[\n,;]+/)
    .map((value) => value.replace(/\s+/g, '').trim())
    .filter((value) => value && !seen.has(value) && seen.add(value))
})

function stopPolling() {
  if (timer.value) clearInterval(timer.value)
  timer.value = null
}
async function loadBase() {
  error.value = ''
  try {
    const [entityResponse, sourceResponse, cursorResponse] = await Promise.all([
      api.get('/legal-entities/options'),
      api.get('/query/sources'),
      api.get('/dfe/cursors'),
    ])
    entities.value = entityResponse.data
    sources.value = sourceResponse.data
    cursors.value = cursorResponse.data
    if (common.legal_entity_id && !entities.value.some((item) => item.id === common.legal_entity_id)) common.legal_entity_id = ''
  } catch (e) { error.value = errorMessage(e) }
}
function resetResult() {
  stopPolling()
  job.value = null
  batch.value = null
  error.value = ''
  success.value = ''
}
function selectMode(value: 'single' | 'batch' | 'dfe') {
  mode.value = value
  resetResult()
  if (value === 'dfe') {
    common.document_type = 'nfe'
    if (!dfe.plugin_installation_id && dfeSources.value.length) dfe.plugin_installation_id = dfeSources.value[0].id
  }
}
function sourceName(id: string | null) {
  if (!id) return 'Roteamento automático'
  return sources.value.find((item) => item.id === id)?.name || id
}
function entityName(id: string | null) {
  if (!id) return 'Não especificado'
  const item = entities.value.find((entry) => entry.id === id)
  return item ? `${item.legal_name} · ${item.document}` : id
}

async function pollJob(id: string) {
  stopPolling()
  const refresh = async () => {
    try {
      job.value = (await api.get(`/retrieval-jobs/${id}`)).data
      if (['completed', 'partial', 'not_found', 'failed', 'human_action_required'].includes(job.value.status)) {
        stopPolling()
        loading.value = false
        await loadBase()
      }
    } catch (e) {
      stopPolling()
      loading.value = false
      error.value = errorMessage(e)
    }
  }
  await refresh()
  if (loading.value) timer.value = setInterval(refresh, 1500)
}
async function submitSingle() {
  loading.value = true
  error.value = ''
  success.value = ''
  try {
    const { data } = await api.post('/retrieval-jobs', {
      legal_entity_id: common.legal_entity_id || null,
      plugin_installation_id: common.plugin_installation_id || null,
      document_type: common.document_type,
      access_key: single.access_key.replace(/\s+/g, ''),
      environment: common.environment,
      operation: 'retrieve_by_key',
      mode: common.plugin_installation_id ? 'specific_source' : 'automatic_with_assisted_fallback',
      parameters: {},
    })
    job.value = data
    await pollJob(data.id)
  } catch (e) {
    loading.value = false
    error.value = errorMessage(e)
  }
}
async function submitBatch() {
  if (!batchKeys.value.length) return
  loading.value = true
  error.value = ''
  success.value = ''
  try {
    const { data } = await api.post('/retrieval-batches', {
      legal_entity_id: common.legal_entity_id || null,
      plugin_installation_id: common.plugin_installation_id || null,
      document_type: common.document_type,
      environment: common.environment,
      mode: common.plugin_installation_id ? 'specific_source' : 'automatic_with_assisted_fallback',
      access_keys: batchKeys.value,
    })
    batch.value = data
    await pollBatch(data.id)
  } catch (e) {
    loading.value = false
    error.value = errorMessage(e)
  }
}
async function pollBatch(id: string) {
  stopPolling()
  const refresh = async () => {
    try {
      batch.value = (await api.get(`/retrieval-batches/${id}`)).data
      if (['completed', 'partial', 'failed'].includes(batch.value.status) || batch.value.completed_count >= batch.value.total_count) {
        stopPolling()
        loading.value = false
      }
    } catch (e) {
      stopPolling()
      loading.value = false
      error.value = errorMessage(e)
    }
  }
  await refresh()
  if (loading.value) timer.value = setInterval(refresh, 1800)
}
async function submitDfe() {
  loading.value = true
  error.value = ''
  success.value = ''
  try {
    const payload: any = {
      legal_entity_id: common.legal_entity_id,
      plugin_installation_id: dfe.plugin_installation_id,
      environment: common.environment,
      operation: dfe.operation,
    }
    if (dfe.operation === 'consNSU') payload.nsu = dfe.nsu
    if (dfe.operation === 'consChNFe') payload.access_key = dfe.access_key.replace(/\s+/g, '')
    const { data } = await api.post('/dfe/distribution', payload)
    job.value = data
    await pollJob(data.id)
  } catch (e) {
    loading.value = false
    error.value = errorMessage(e)
  }
}
function loadTxtFile(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  const reader = new FileReader()
  reader.onload = () => { batchForm.access_keys_text = String(reader.result || '') }
  reader.readAsText(file)
}
function formatDate(value: string | null) {
  return value ? new Date(value).toLocaleString('pt-BR') : '—'
}

onMounted(() => {
  loadBase()
  window.addEventListener('tenant-changed', () => { resetResult(); loadBase() })
})
onUnmounted(() => stopPolling())
</script>

<template>
  <PageHeader title="Central de consultas fiscais" subtitle="Consulte por chave, processe lotes e sincronize a Distribuição DF-e com fontes e ambientes parametrizados">
    <button class="btn" @click="loadBase"><RefreshCw :size="16" />Atualizar fontes</button>
  </PageHeader>

  <div class="query-mode-tabs">
    <button :class="{ active: mode === 'single' }" @click="selectMode('single')"><Search :size="17" />Chave única</button>
    <button :class="{ active: mode === 'batch' }" @click="selectMode('batch')"><Layers3 :size="17" />Lote de chaves</button>
    <button :class="{ active: mode === 'dfe' }" @click="selectMode('dfe')"><ServerCog :size="17" />Distribuição DF-e</button>
  </div>

  <div v-if="error" class="alert danger integrations-alert">{{ error }}</div>
  <div v-if="success" class="alert success integrations-alert">{{ success }}</div>

  <section class="panel query-console">
    <div class="query-context-grid">
      <label>Empresa / CNPJ
        <select v-model="common.legal_entity_id" required>
          <option value="">{{ mode === 'dfe' ? 'Selecione o CNPJ' : 'Não especificada' }}</option>
          <option v-for="entity in entities" :key="entity.id" :value="entity.id">{{ entity.legal_name }} · {{ entity.document }}</option>
        </select>
      </label>
      <label v-if="mode !== 'dfe'">Tipo de documento
        <select v-model="common.document_type">
          <option value="nfe">NF-e</option><option value="nfce">NFC-e</option><option value="cte">CT-e</option><option value="mdfe">MDF-e</option><option value="nfse">NFS-e</option>
        </select>
      </label>
      <label>Ambiente
        <select v-model="common.environment">
          <option value="production">Produção</option>
          <option value="homologation">Homologação</option>
        </select>
      </label>
      <label v-if="mode !== 'dfe'">Fonte / conector
        <select v-model="common.plugin_installation_id">
          <option value="">Roteamento automático</option>
          <option v-for="source in sourceOptions" :key="source.id" :value="source.id">{{ source.name }} · {{ source.definition_name }}</option>
        </select>
      </label>
    </div>

    <form v-if="mode === 'single'" class="query-operation" @submit.prevent="submitSingle">
      <div class="query-operation-icon"><FileSearch /></div>
      <div class="query-operation-copy"><h2>Consulta por chave</h2><p>Verifica o repositório e percorre as fontes configuradas, ou usa diretamente a fonte selecionada.</p></div>
      <label class="query-key-field">Chave / identificador
        <input v-model="single.access_key" required placeholder="NF-e/CT-e/MDF-e: informe a chave de acesso; NFS-e: identificador do provedor" />
      </label>
      <button class="btn primary query-submit" :disabled="loading"><Search :size="17" />{{ loading ? 'Consultando...' : 'Consultar documento' }}</button>
    </form>

    <form v-else-if="mode === 'batch'" class="query-operation batch-operation" @submit.prevent="submitBatch">
      <div class="query-operation-icon"><ListPlus /></div>
      <div class="query-operation-copy"><h2>Buscador de chaves em lote</h2><p>Até 500 identificadores por lote. Duplicidades são removidas antes do processamento.</p></div>
      <label class="batch-textarea">Chaves / identificadores
        <textarea v-model="batchForm.access_keys_text" rows="11" placeholder="Uma chave por linha&#10;2926...&#10;3526..."></textarea>
      </label>
      <div class="batch-toolbar">
        <label class="file-button">Importar .TXT<input type="file" accept=".txt,text/plain" @change="loadTxtFile" /></label>
        <span>{{ batchKeys.length }} chave(s) únicas</span>
        <button class="btn primary" :disabled="loading || !batchKeys.length"><Layers3 :size="17" />{{ loading ? 'Processando...' : 'Criar lote' }}</button>
      </div>
    </form>

    <form v-else class="query-operation dfe-operation" @submit.prevent="submitDfe">
      <div class="query-operation-icon"><ServerCog /></div>
      <div class="query-operation-copy"><h2>Ambiente Nacional — Distribuição DF-e</h2><p>Execute distribuição sequencial por NSU ou consultas pontuais usando o certificado A1 configurado no aplicativo.</p></div>
      <div class="dfe-form-grid">
        <label>Conector Distribuição DF-e
          <select v-model="dfe.plugin_installation_id" required>
            <option value="">Selecione</option>
            <option v-for="source in dfeSources" :key="source.id" :value="source.id">{{ source.name }}</option>
          </select>
        </label>
        <label>Operação
          <select v-model="dfe.operation">
            <option value="distNSU">distNSU · distribuição sequencial</option>
            <option value="consNSU">consNSU · consultar um NSU</option>
            <option value="consChNFe">consChNFe · consultar uma chave</option>
          </select>
        </label>
        <label v-if="dfe.operation === 'consNSU'">NSU<input v-model="dfe.nsu" inputmode="numeric" maxlength="15" placeholder="000000000000123" required /></label>
        <label v-if="dfe.operation === 'consChNFe'" class="span-2">Chave NF-e<input v-model="dfe.access_key" maxlength="44" placeholder="44 dígitos" required /></label>
      </div>
      <div v-if="selectedCursor" class="dfe-cursor-card">
        <div><span>Último NSU</span><strong>{{ selectedCursor.last_nsu }}</strong></div>
        <div><span>Máximo NSU</span><strong>{{ selectedCursor.max_nsu || '—' }}</strong></div>
        <div><span>Último cStat</span><strong>{{ selectedCursor.last_cstat || '—' }}</strong></div>
        <div><span>Próxima consulta</span><strong>{{ selectedCursor.blocked_until ? formatDate(selectedCursor.blocked_until) : 'Disponível' }}</strong></div>
      </div>
      <div class="dfe-note"><ShieldCheck :size="16" /><span>O cursor de `distNSU` é persistido por CNPJ, ambiente e conector para preservar a sequência operacional.</span></div>
      <button class="btn primary query-submit" :disabled="loading || !common.legal_entity_id || !dfe.plugin_installation_id"><ServerCog :size="17" />{{ loading ? 'Consultando Ambiente Nacional...' : 'Executar DF-e' }}</button>
    </form>
  </section>

  <section v-if="job" class="panel result-panel query-result">
    <div class="panel-title">
      <div><h3>Operação {{ job.id }}</h3><p>{{ job.operation }} · {{ job.environment }} · {{ sourceName(job.plugin_installation_id) }}</p></div>
      <StatusBadge :status="job.status" />
    </div>
    <div class="query-summary-line">
      <span><Database :size="15" />{{ entityName(job.legal_entity_id) }}</span>
      <span v-if="job.access_key"><Search :size="15" />{{ job.access_key }}</span>
      <span><Boxes :size="15" />{{ (job.result_document_ids || []).length }} documento(s)</span>
    </div>
    <div class="progress large"><i :style="{ width: `${job.progress}%` }"></i></div>
    <div v-if="job.attempts?.length" class="attempt-grid">
      <article v-for="attempt in job.attempts" :key="attempt.at">
        <strong>{{ attempt.installation }}</strong><StatusBadge :status="attempt.status" /><small>{{ attempt.message || 'Processado' }}</small>
      </article>
    </div>
    <div v-if="job.error_message" class="alert danger">{{ job.error_message }}</div>
    <div v-if="job.human_action" class="alert warning">Ação humana necessária: {{ job.human_action.instructions }}</div>
    <RouterLink v-if="job.result_document_ids?.length || job.result_document_id" class="btn primary" to="/documents"><CheckCircle2 :size="16" />Abrir documentos localizados</RouterLink>
  </section>

  <section v-if="batch" class="panel batch-result">
    <div class="panel-title">
      <div><h3>Lote {{ batch.id }}</h3><p>{{ batch.document_type?.toUpperCase() }} · {{ batch.environment }} · {{ sourceName(batch.plugin_installation_id) }}</p></div>
      <StatusBadge :status="batch.status" />
    </div>
    <div class="batch-metrics">
      <div><span>Total</span><strong>{{ batch.total_count }}</strong></div>
      <div><span>Concluídos</span><strong>{{ batch.completed_count }}</strong></div>
      <div><span>Localizados</span><strong>{{ batch.found_count }}</strong></div>
      <div><span>Não encontrados</span><strong>{{ batch.not_found_count }}</strong></div>
      <div><span>Falhas</span><strong>{{ batch.failed_count }}</strong></div>
    </div>
    <div class="table-wrap">
      <table><thead><tr><th>Chave</th><th>Status</th><th>Progresso</th><th>Fonte</th><th>Resultado</th></tr></thead>
        <tbody><tr v-for="item in batch.jobs || []" :key="item.id">
          <td><code>{{ item.access_key }}</code></td><td><StatusBadge :status="item.status" /></td>
          <td>{{ item.progress }}%</td><td>{{ sourceName(item.plugin_installation_id) }}</td>
          <td>{{ item.result_document_ids?.length || 0 }} doc(s)<small v-if="item.error_message" class="batch-error">{{ item.error_message }}</small></td>
        </tr></tbody>
      </table>
    </div>
  </section>
</template>
