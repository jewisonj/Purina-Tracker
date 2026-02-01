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
    await login(pin.value)
    authStore.setAuthenticated(true)
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
    </div>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f0f2f5;
}

.login-card {
  background: white;
  border-radius: 12px;
  padding: 40px;
  width: 100%;
  max-width: 380px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.login-header {
  text-align: center;
  margin-bottom: 32px;
}

.login-header h1 {
  color: #c41230;
  font-size: 24px;
  margin-bottom: 8px;
}

.login-header p {
  color: #6c757d;
  font-size: 14px;
}

.login-form .field {
  margin-bottom: 16px;
}

.error-msg {
  color: #dc3545;
  font-size: 13px;
  text-align: center;
  margin-bottom: 12px;
}
</style>
