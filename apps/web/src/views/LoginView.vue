<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Boxes } from 'lucide-vue-next'
import { api, errorMessage } from '../api'
import { useAuthStore } from '../stores/auth'
const router=useRouter(), auth=useAuthStore(); const email=ref(''), password=ref(''), error=ref(''), loading=ref(false)
onMounted(async()=>{ try { const {data}=await api.get('/bootstrap/status'); if(data.required) router.replace('/bootstrap') } catch{} })
async function submit(){ loading.value=true; error.value=''; try{await auth.login(email.value,password.value); router.push('/')}catch(e){error.value=errorMessage(e)}finally{loading.value=false} }
</script>
<template><div class="auth-page"><div class="auth-visual"><div class="auth-brand"><Boxes :size="42"/><div><strong>HUB FISCAL</strong><span>Plataforma inteligente de documentos fiscais</span></div></div><h1>Controle fiscal multicanal, seguro e escalável.</h1><p>Centralize NF-e, NFC-e, CT-e, MDF-e e NFS-e com conectores plugáveis, filas e cofre de documentos.</p><div class="feature-list"><span>✓ SaaS multiempresa</span><span>✓ Plugins sem fonte fixa</span><span>✓ Docker e CloudPanel</span></div></div><form class="auth-card" @submit.prevent="submit"><h2>Entrar na plataforma</h2><p>Utilize suas credenciais administrativas.</p><label>E-mail<input v-model="email" type="email" required placeholder="admin@empresa.com.br" /></label><label>Senha<input v-model="password" type="password" required placeholder="••••••••••" /></label><div v-if="error" class="alert danger">{{ error }}</div><button class="btn primary full" :disabled="loading">{{ loading ? 'Entrando...' : 'Entrar' }}</button></form></div></template>
