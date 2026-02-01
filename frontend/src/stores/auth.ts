import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { verifyAuth, isLoggedIn, getRole } from '../services/api'

export const useAuthStore = defineStore('auth', () => {
  const authenticated = ref(false)
  const initialized = ref(false)
  const role = ref('')

  async function initialize() {
    if (initialized.value) return

    if (isLoggedIn()) {
      const verifiedRole = await verifyAuth()
      if (verifiedRole) {
        authenticated.value = true
        role.value = verifiedRole
      }
    }
    initialized.value = true
  }

  function setAuthenticated(value: boolean, userRole: string = '') {
    authenticated.value = value
    role.value = userRole
    initialized.value = true
  }

  const isAdmin = computed(() => role.value === 'admin')

  return {
    authenticated,
    initialized,
    role,
    isAuthenticated: authenticated,
    isAdmin,
    initialize,
    setAuthenticated,
  }
})
