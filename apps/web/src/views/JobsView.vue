<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { Layers3, ListTodo, RefreshCw } from 'lucide-vue-next'
import { api, errorMessage } from '../api'
import PageHeader from '../components/PageHeader.vue'
import StatusBadge from '../components/StatusBadge.vue'

const activeTab = ref<'jobs' | 'batches'>('jobs')
const jobs = ref<any[]>([])
const batches = ref<any[]>([])
const selectedBatch = ref<any | null>(null)
const error = ref('')
let timer: any

async function load() {
  error.value = ''
  try {
    const [jobResponse, batchResponse] = await Promise.all([
      api.get('/retrieval-jobs'),
      api.get('/retrieval-batches'),
    ])
    jobs.value = jobResponse.data
    batches.value = batchResponse.data
    if (selectedBatch.value) {
      selectedBatch.value = (await api.get(`/retrieval-batches/${selectedBatch.value.id}`)).data
    }
  } catch (e) { error.value = errorMessage(e) }
}
async function openBatch(item: any) {
  activeTab.value = 'batches'
  try { selectedBatch.value = (await api.get(`/retrieval-batches/${item.id}`)).data }
  catch (e) { error.value = errorMessage(e) }
}
function formatDate(value: string) { return new Date(value).toLocaleString('pt-BR') }
function sourceAttempt(item: any) { return item.attempts?.[item.attempts.length - 1]?.installation || '—' }

onMounted(() => {
  load()
  timer = setInterval(load, 5000)
  window.addEventListener('tenant-changed', load)
})
onUnmounted(() => {
  clearInterval(timer)
  window.removeEventListener('tenant-changed', load)
})
</script>

<template>
  <PageHeader title="Jobs e lotes" subtitle="Acompanhe consultas individuais, processamento em lote, tentativas, fontes e resultados">
    <button class="btn" @click="load"><RefreshCw :size="16" />Atualizar</button>
  </PageHeader>
  <div v-if="error" class="alert danger integrations-alert">{{ error }}</div>

  <div class="query-mode-tabs compact-tabs">
    <button :class="{ active: activeTab === 'jobs' }" @click="activeTab='jobs'"><ListTodo :size="17" />Jobs individuais <span>{{ jobs.length }}</span></button>
    <button :class="{ active: activeTab === 'batches' }" @click="activeTab='batches'"><Layers3 :size="17" />Lotes <span>{{ batches.length }}</span></button>
  </div>

  <section v-if="activeTab === 'jobs'" class="panel table-wrap">
    <table>
      <thead><tr><th>Chave / operação</th><th>Tipo</th><th>Ambiente</th><th>Fonte</th><th>Situação</th><th>Progresso</th><th>Iniciado</th></tr></thead>
      <tbody>
        <tr v-for="item in jobs" :key="item.id">
          <td><strong class="table-primary">{{ item.access_key || item.operation }}</strong><small>{{ item.operation }}<template v-if="item.batch_id"> · lote {{ item.batch_id.slice(0,8) }}</template></small></td>
          <td><span class="doc-type">{{ item.document_type.toUpperCase() }}</span></td>
          <td>{{ item.environment === 'production' ? 'Produção' : 'Homologação' }}</td>
          <td>{{ sourceAttempt(item) }}</td>
          <td><StatusBadge :status="item.status" /><small v-if="item.error_message" class="batch-error">{{ item.error_message }}</small></td>
          <td><div class="progress"><i :style="{width:`${item.progress}%`}"></i></div><small>{{ item.progress }}%</small></td>
          <td>{{ formatDate(item.created_at) }}</td>
        </tr>
        <tr v-if="!jobs.length"><td colspan="7" class="loading-cell">Nenhum job neste tenant.</td></tr>
      </tbody>
    </table>
  </section>

  <div v-else class="jobs-batch-layout">
    <section class="panel table-wrap">
      <table>
        <thead><tr><th>Lote</th><th>Tipo</th><th>Status</th><th>Processados</th><th>Resultados</th><th>Iniciado</th></tr></thead>
        <tbody>
          <tr v-for="item in batches" :key="item.id" class="clickable-row" @click="openBatch(item)">
            <td><strong class="table-primary">{{ item.id.slice(0,8) }}</strong><small>{{ item.environment === 'production' ? 'Produção' : 'Homologação' }}</small></td>
            <td><span class="doc-type">{{ item.document_type.toUpperCase() }}</span></td>
            <td><StatusBadge :status="item.status" /></td>
            <td>{{ item.completed_count }} / {{ item.total_count }}</td>
            <td>{{ item.found_count }} localizados · {{ item.failed_count }} falhas</td>
            <td>{{ formatDate(item.created_at) }}</td>
          </tr>
          <tr v-if="!batches.length"><td colspan="6" class="loading-cell">Nenhum lote criado.</td></tr>
        </tbody>
      </table>
    </section>

    <section v-if="selectedBatch" class="panel batch-detail-panel">
      <div class="panel-title"><div><h3>Lote {{ selectedBatch.id.slice(0,8) }}</h3><p>{{ selectedBatch.total_count }} item(ns)</p></div><StatusBadge :status="selectedBatch.status" /></div>
      <div class="batch-metrics mini">
        <div><span>Localizados</span><strong>{{ selectedBatch.found_count }}</strong></div>
        <div><span>Não encontrados</span><strong>{{ selectedBatch.not_found_count }}</strong></div>
        <div><span>Falhas</span><strong>{{ selectedBatch.failed_count }}</strong></div>
      </div>
      <div class="batch-detail-list">
        <div v-for="item in selectedBatch.jobs || []" :key="item.id">
          <div><strong>{{ item.access_key }}</strong><small>{{ sourceAttempt(item) }}</small></div>
          <StatusBadge :status="item.status" />
        </div>
      </div>
    </section>
  </div>
</template>
