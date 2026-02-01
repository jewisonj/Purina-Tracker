<script setup lang="ts">
import { logout } from '../services/api'
</script>

<template>
  <div>
    <nav class="app-nav">
      <span class="brand">Purina Tracker</span>
      <router-link to="/">Inventory</router-link>
      <router-link to="/prices">Prices</router-link>
      <router-link to="/log">Log</router-link>
      <span class="spacer"></span>
      <button class="logout-btn" @click="logout">Logout</button>
    </nav>
    <main class="page-content">
      <slot />
    </main>
  </div>
</template>
