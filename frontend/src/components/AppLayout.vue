<script setup lang="ts">
import { logout } from '../services/api'
import { useAuthStore } from '../stores/auth'

const authStore = useAuthStore()
</script>

<template>
  <div>
    <nav class="app-nav">
      <span class="brand">Purina Tracker</span>
      <router-link to="/">Inventory</router-link>
      <router-link v-if="authStore.isAdmin" to="/invoice">Invoice</router-link>
      <span class="spacer"></span>
      <button class="logout-btn" @click="logout">Logout</button>
    </nav>
    <main class="page-content">
      <slot />
    </main>
  </div>
</template>
