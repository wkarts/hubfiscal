<script setup lang="ts">
import { onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from './stores/auth'
import AppLayout from './components/AppLayout.vue'

const route = useRoute()
const auth = useAuthStore()
onMounted(() => auth.load())
</script>

<template>
  <RouterView v-if="route.meta.public" />
  <AppLayout v-else><RouterView /></AppLayout>
</template>
