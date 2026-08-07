<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { Camera, KeyRound, Save, Trash2, UserRound } from 'lucide-vue-next'
import { api, errorMessage } from '../api'
import PageHeader from '../components/PageHeader.vue'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const loading = ref(false)
const error = ref('')
const success = ref('')
const profile = reactive({ name: '', email: '' })
const password = reactive({ current_password: '', new_password: '', confirm_password: '' })

async function load() {
  error.value = ''
  try {
    const { data } = await api.get('/profile')
    profile.name = data.name
    profile.email = data.email
    await auth.loadAvatar()
  } catch (e) { error.value = errorMessage(e) }
}
async function saveProfile() {
  loading.value = true
  error.value = ''
  success.value = ''
  try {
    await api.patch('/profile', { name: profile.name, email: profile.email })
    success.value = 'Dados da conta atualizados.'
    await auth.load()
  } catch (e) { error.value = errorMessage(e) }
  finally { loading.value = false }
}
async function changePassword() {
  error.value = ''
  success.value = ''
  if (password.new_password !== password.confirm_password) {
    error.value = 'A confirmação da nova senha não confere.'
    return
  }
  loading.value = true
  try {
    await api.post('/profile/password', {
      current_password: password.current_password,
      new_password: password.new_password,
    })
    password.current_password = ''
    password.new_password = ''
    password.confirm_password = ''
    success.value = 'Senha alterada com sucesso.'
  } catch (e) { error.value = errorMessage(e) }
  finally { loading.value = false }
}
async function uploadAvatar(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  error.value = ''
  success.value = ''
  const data = new FormData()
  data.append('file', file)
  try {
    await api.post('/profile/avatar', data)
    success.value = 'Foto atualizada.'
    if (auth.user) auth.user.has_avatar = true
    await auth.loadAvatar()
  } catch (e) { error.value = errorMessage(e) }
  ;(event.target as HTMLInputElement).value = ''
}
async function removeAvatar() {
  error.value = ''
  try {
    await api.delete('/profile/avatar')
    if (auth.user) auth.user.has_avatar = false
    auth.clearAvatar()
    success.value = 'Foto removida.'
  } catch (e) { error.value = errorMessage(e) }
}

onMounted(load)
</script>

<template>
  <PageHeader title="Minha conta" subtitle="Gerencie seus dados pessoais, foto de perfil e credenciais de acesso" />
  <div v-if="error" class="alert danger integrations-alert">{{ error }}</div>
  <div v-if="success" class="alert success integrations-alert">{{ success }}</div>

  <div class="profile-page-grid">
    <section class="panel profile-identity-card">
      <div class="profile-photo-large">
        <img v-if="auth.avatarUrl" :src="auth.avatarUrl" alt="Foto do usuário" />
        <UserRound v-else :size="52" />
      </div>
      <h2>{{ auth.user?.name }}</h2>
      <p>{{ auth.user?.email }}</p>
      <span class="profile-role-pill">{{ auth.context?.profile_name || (auth.user?.is_platform_admin ? 'Administrador da plataforma' : 'Usuário') }}</span>
      <div class="profile-photo-actions">
        <label class="btn primary"><Camera :size="16" />Alterar foto<input type="file" accept="image/jpeg,image/png,image/webp" @change="uploadAvatar" /></label>
        <button v-if="auth.user?.has_avatar" class="btn" @click="removeAvatar"><Trash2 :size="16" />Remover</button>
      </div>
      <small>JPEG, PNG ou WebP · máximo 2 MB. A imagem é armazenada criptografada.</small>
    </section>

    <div class="profile-settings-stack">
      <section class="panel profile-section">
        <div class="profile-section-title"><UserRound :size="20" /><div><h3>Dados pessoais</h3><p>Esses dados identificam você na plataforma e nas trilhas de auditoria.</p></div></div>
        <form class="form-grid" @submit.prevent="saveProfile">
          <label>Nome<input v-model="profile.name" required minlength="3" /></label>
          <label>E-mail<input v-model="profile.email" type="email" required /></label>
          <div class="form-actions span-2"><button class="btn primary" :disabled="loading"><Save :size="16" />Salvar dados</button></div>
        </form>
      </section>

      <section class="panel profile-section">
        <div class="profile-section-title"><KeyRound :size="20" /><div><h3>Alterar senha</h3><p>A senha atual é sempre exigida antes da troca.</p></div></div>
        <form class="form-grid" @submit.prevent="changePassword">
          <label class="span-2">Senha atual<input v-model="password.current_password" type="password" required autocomplete="current-password" /></label>
          <label>Nova senha<input v-model="password.new_password" type="password" required minlength="8" autocomplete="new-password" /></label>
          <label>Confirmar nova senha<input v-model="password.confirm_password" type="password" required minlength="8" autocomplete="new-password" /></label>
          <div class="form-actions span-2"><button class="btn primary" :disabled="loading"><KeyRound :size="16" />Alterar senha</button></div>
        </form>
      </section>
    </div>
  </div>
</template>
