<script setup lang="ts">
const props = defineProps<{ status: string }>()
const positive = ['active','healthy','completed','authorized','found']
const warning = ['queued','running','unknown','human_action_required','summary']
</script>
<template><span class="badge" :class="positive.includes(status) ? 'success' : warning.includes(status) ? 'warning' : 'danger'">{{ status.replaceAll('_',' ') }}</span></template>
