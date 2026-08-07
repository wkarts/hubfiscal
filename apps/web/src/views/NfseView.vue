<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { ReceiptText, PlugZap, Landmark } from 'lucide-vue-next'
import { api } from '../api'
import { useAuthStore } from '../stores/auth'
import PageHeader from '../components/PageHeader.vue'
import DataTable from '../components/DataTable.vue'
import StatusBadge from '../components/StatusBadge.vue'

const auth = useAuthStore()
const rows = ref<any[]>([])
const plugins = ref<any[]>([])
const cols = [
  { key: 'access_key', label: 'Identificador' },
  { key: 'issuer_document', label: 'Prestador' },
  { key: 'recipient_document', label: 'Tomador' },
  { key: 'total_amount', label: 'Valor' },
  { key: 'status', label: 'Situação' },
  { key: 'created_at', label: 'Recebido' },
]

async function load() {
  rows.value = (await api.get('/documents', { params: { document_type: 'nfse' } })).data
  if (auth.enabledResources.includes('plugins')) {
    plugins.value = (await api.get('/plugins/installations')).data.filter((plugin: any) => ['nfse-national', 'webiss'].includes(plugin.plugin_key))
  } else {
    plugins.value = []
  }
}
onMounted(() => {
  load()
  window.addEventListener('tenant-changed', load)
})
onUnmounted(() => window.removeEventListener('tenant-changed', load))
</script>

<template>
  <PageHeader title="NFS-e" subtitle="Ambiente Nacional, WebISS e provedores municipais por plugins e roteamento por município" />
  <div class="metric-grid">
    <div class="metric-card blue"><div><span>NFS-e armazenadas</span><strong>{{ rows.length }}</strong><small>Cofre municipal</small></div><ReceiptText /></div>
    <div class="metric-card violet"><div><span>Conectores NFS-e</span><strong>{{ plugins.length }}</strong><small>Nacional e municipais</small></div><PlugZap /></div>
    <div class="metric-card green"><div><span>Roteamento</span><strong>IBGE</strong><small>Município + inscrição</small></div><Landmark /></div>
  </div>
  <section class="panel">
    <div class="panel-title"><div><h3>Documentos de serviço</h3><p>NFS-e obtidas, importadas ou recebidas por integrações</p></div></div>
    <DataTable :columns="cols" :rows="rows">
      <template #cell-total_amount="{ value }">{{ value ? Number(value).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' }) : '—' }}</template>
      <template #cell-status="{ value }"><StatusBadge :status="value" /></template>
      <template #cell-created_at="{ value }">{{ new Date(value).toLocaleString('pt-BR') }}</template>
    </DataTable>
  </section>
  <section v-if="auth.enabledResources.includes('plugins')" class="panel" style="margin-top:18px">
    <div class="panel-title"><div><h3>Conectores municipais</h3><p>Instale e configure NFS-e Nacional, WebISS ou outro provedor pelo catálogo.</p></div><RouterLink class="btn" to="/plugins">Gerenciar plugins</RouterLink></div>
  </section>
</template>
