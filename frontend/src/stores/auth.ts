import { defineStore } from 'pinia'
import { ref } from 'vue'
import { verifyAuth, isLoggedIn } from '../services/api'

export const useAuthStore = defineStore('auth', () => {
  const authenticated = ref(false)
  const initialized = ref(false)

  async function initialize() {
    if (initialized.value) return

    if (isLoggedIn()) {
      authenticated.value = await verifyAuth()
    }
    initialized.value = true
  }

  function setAuthenticated(value: boolean) {
    authenticated.value = value
    initialized.value = true
  }

  return {
    authenticated,
    initialized,
    isAuthenticated: authenticated,
    initialize,
    setAuthenticated,
  }
})
