<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useToast } from 'primevue/usetoast'
import { importPriceList, getPriceListArchive } from '../services/api'
import { useInventoryStore } from '../stores/inventory'
import AppLayout from '../components/AppLayout.vue'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import InputText from 'primevue/inputtext'
import Button from 'primevue/button'
import FileUpload from 'primevue/fileupload'

const store = useInventoryStore()
const toast = useToast()

const headers = ref<string[]>([])
const rows = ref<string[][]>([])
const loading = ref(false)
const uploading = ref(false)
const globalFilter = ref('')

async function loadArchive() {
  loading.value = true
  try {
    const data = await getPriceListArchive()
    headers.value = data.headers
    rows.value = data.rows
  } catch (e: any) {
    toast.add({ severity: 'error', summary: 'Error', detail: e.message, life: 4000 })
  } finally {
    loading.value = false
  }
}

onMounted(loadArchive)

const filteredRows = ref<string[][]>([])

import { computed } from 'vue'
const displayRows = computed(() => {
  const q = globalFilter.value.toLowerCase().trim()
  if (!q) return rows.value
  return rows.value.filter(row =>
    row.some(cell => cell.toLowerCase().includes(q))
  )
})

async function handleUpload(event: any) {
  const file = event.files?.[0]
  if (!file) return
  uploading.value = true
  try {
    const result = await importPriceList(file)
    toast.add({
      severity: 'success',
      summary: 'CSV Imported',
      detail: result.message,
      life: 5000,
    })
    await loadArchive()
    await store.fetchProducts()
  } catch (e: any) {
    toast.add({ severity: 'error', summary: 'Import Failed', detail: e.message, life: 5000 })
  } finally {
    uploading.value = false
  }
}
</script>

<template>
  <AppLayout>
    <div class="prices-page">
      <div class="page-header">
        <h1>Dealer Price List</h1>
      </div>

      <div class="toolbar">
        <InputText
          v-model="globalFilter"
          placeholder="Search..."
          style="width: 260px; max-width: 100%;"
        />
        <FileUpload
          mode="basic"
          accept=".csv"
          :auto="true"
          chooseLabel="Upload New CSV"
          chooseIcon="pi pi-upload"
          :customUpload="true"
          @uploader="handleUpload"
          :disabled="uploading"
        />
      </div>

      <p class="hint">
        This is the full Purina dealer price list. Upload a new CSV to refresh costs.
      </p>

      <DataTable
        :value="displayRows"
        :loading="loading"
        stripedRows
        scrollable
        scrollHeight="calc(100vh - 280px)"
        size="small"
        tableStyle="min-width: 800px"
      >
        <Column
          v-for="(header, idx) in headers"
          :key="idx"
          :field="String(idx)"
          :header="header"
          style="min-width: 120px"
        >
          <template #body="{ data }">{{ data[idx] }}</template>
        </Column>
      </DataTable>
    </div>
  </AppLayout>
</template>

<style scoped>
.prices-page {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.page-header h1 {
  margin: 0;
  font-size: 20px;
  color: var(--text);
}

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.hint {
  color: var(--text-secondary);
  font-size: 13px;
  margin: 0;
}
</style>
