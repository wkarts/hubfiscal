<script setup lang="ts">
defineProps<{ open: boolean; title: string; wide?: boolean }>()
defineEmits(['close'])
</script>
<template>
  <Teleport to="body"><div v-if="open" class="modal-backdrop" @click.self="$emit('close')"><div class="modal" :class="{ wide }"><div class="modal-header"><h3>{{ title }}</h3><button class="icon-button" @click="$emit('close')">×</button></div><div class="modal-body"><slot /></div></div></div></Teleport>
</template>
