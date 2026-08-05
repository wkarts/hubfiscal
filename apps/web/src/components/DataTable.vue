<script setup lang="ts">
interface Column { key: string; label: string; class?: string }
defineProps<{ columns: Column[]; rows: any[]; loading?: boolean; rowKey?: string }>()
</script>
<template>
  <div class="table-wrap"><table><thead><tr><th v-for="col in columns" :key="col.key">{{ col.label }}</th><th v-if="$slots.actions"></th></tr></thead><tbody>
    <tr v-if="loading"><td :colspan="columns.length+1" class="loading-cell">Carregando...</td></tr>
    <tr v-for="(row,index) in rows" :key="row[rowKey || 'id'] || index"><td v-for="col in columns" :key="col.key" :class="col.class"><slot :name="`cell-${col.key}`" :row="row" :value="row[col.key]">{{ row[col.key] ?? '—' }}</slot></td><td v-if="$slots.actions" class="actions-cell"><slot name="actions" :row="row" /></td></tr>
  </tbody></table></div>
</template>
