<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useInventoryStore } from '../stores/inventory'
import AppLayout from '../components/AppLayout.vue'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import InputText from 'primevue/inputtext'
import Tag from 'primevue/tag'

const store = useInventoryStore()
const globalFilter = ref('')

const filteredLog = computed(() => {
  const q = globalFilter.value.toLowerCase().trim()
  if (!q) return store.logEntries
  return store.logEntries.filter(
    e =>
      e.product_name.toLowerCase().includes(q) ||
      e.change_type.toLowerCase().includes(q) ||
      e.material_no.toLowerCase().includes(q)
  )
})

onMounted(() => {
  store.fetchLog(200)
})

function tagSeverity(changeType: string): string {
  switch (changeType) {
    case 'sale': return 'danger'
    case 'restock': return 'success'
    default: return 'info'
  }
}
</script>

<template>
  <AppLayout>
    <h1 class="page-title">Inventory Log</h1>

    <div style="margin-bottom: 16px;">
      <InputText
        v-model="globalFilter"
        placeholder="Search log..."
        style="width: 300px; max-width: 100%;"
      />
    </div>

    <DataTable
      :value="filteredLog"
      :loading="store.loading"
      stripedRows
      scrollable
      scrollHeight="calc(100vh - 240px)"
      size="small"
      tableStyle="min-width: 800px"
    >
      <Column field="timestamp" header="Time" style="width: 160px" />
      <Column field="product_name" header="Product" style="min-width: 200px">
        <template #body="{ data }">
          <strong>{{ data.product_name }}</strong>
        </template>
      </Column>
      <Column field="change_type" header="Type" style="width: 100px">
        <template #body="{ data }">
          <Tag :value="data.change_type" :severity="tagSeverity(data.change_type)" />
        </template>
      </Column>
      <Column field="qty_changed" header="Change" style="width: 80px">
        <template #body="{ data }">
          <span :style="{ color: data.qty_changed > 0 ? '#28a745' : '#dc3545', fontWeight: 700 }">
            {{ data.qty_changed > 0 ? '+' : '' }}{{ data.qty_changed }}
          </span>
        </template>
      </Column>
      <Column header="Qty" style="width: 120px">
        <template #body="{ data }">
          {{ data.previous_qty }} &rarr; {{ data.new_qty }}
        </template>
      </Column>
      <Column field="changed_by" header="By" style="width: 80px" />
      <Column field="notes" header="Notes" style="min-width: 150px" />
    </DataTable>
  </AppLayout>
</template>
