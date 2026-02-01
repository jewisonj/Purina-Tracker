<script setup lang="ts">
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { login } from '../services/api'
import InputText from 'primevue/inputtext'
import Button from 'primevue/button'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const pin = ref('')
const error = ref('')
const loading = ref(false)

async function handleLogin() {
  if (!pin.value) return
  loading.value = true
  error.value = ''

  try {
    const role = await login(pin.value)
    authStore.setAuthenticated(true, role)
    const redirect = (route.query.redirect as string) || '/'
    router.push(redirect)
  } catch (e: any) {
    error.value = 'Invalid PIN. Please try again.'
    pin.value = ''
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-header">
        <h1>Purina Tracker</h1>
        <p>Enter your PIN to continue</p>
      </div>

      <form @submit.prevent="handleLogin" class="login-form">
        <div class="field">
          <InputText
            v-model="pin"
            type="password"
            placeholder="Enter PIN"
            :class="{ 'p-invalid': error }"
            autofocus
            style="width: 100%; font-size: 18px; text-align: center; letter-spacing: 8px;"
          />
        </div>

        <div v-if="error" class="error-msg">{{ error }}</div>

        <Button
          type="submit"
          label="Login"
          :loading="loading"
          :disabled="!pin"
          style="width: 100%"
          severity="danger"
        />
      </form>

      <p class="viewer-hint">To see available inventory use pin <strong>1234</strong></p>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--surface-alt);
}

.login-card {
  background: var(--surface-card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 40px;
  width: 100%;
  max-width: 380px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
}

.login-header {
  text-align: center;
  margin-bottom: 32px;
}

.login-header h1 {
  color: var(--primary-light);
  font-size: 24px;
  margin-bottom: 8px;
}

.login-header p {
  color: var(--text-secondary);
  font-size: 14px;
}

.login-form .field {
  margin-bottom: 16px;
}

.error-msg {
  color: var(--danger);
  font-size: 13px;
  text-align: center;
  margin-bottom: 12px;
}

.viewer-hint {
  margin-top: 24px;
  text-align: center;
  color: var(--text-secondary);
  font-size: 14px;
  line-height: 1.4;
  padding: 10px;
  border: 1px dashed var(--border);
  border-radius: 8px;
  background: var(--surface-alt);
}

.viewer-hint strong {
  color: var(--text);
  letter-spacing: 2px;
}
</style>
