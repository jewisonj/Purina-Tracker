<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import AppLayout from '../components/AppLayout.vue'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import InputText from 'primevue/inputtext'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import { useToast } from 'primevue/usetoast'
import * as api from '../services/api'
import type { Invoice } from '../types'

const toast = useToast()
const invoices = ref<Invoice[]>([])
const loading = ref(false)
const searchQuery = ref('')
const updatingInvoice = ref<string | null>(null)

const filteredInvoices = computed(() => {
  const q = searchQuery.value.toLowerCase().trim()
  if (!q) return invoices.value
  return invoices.value.filter(
    inv =>
      inv.customer.toLowerCase().includes(q) ||
      inv.invoice_number.toLowerCase().includes(q)
  )
})

async function loadInvoices() {
  loading.value = true
  try {
    const result = await api.getInvoices()
    invoices.value = result.invoices
  } catch (e: any) {
    toast.add({ severity: 'error', summary: 'Error', detail: e.message, life: 4000 })
  } finally {
    loading.value = false
  }
}

async function togglePaidStatus(invoice: Invoice) {
  updatingInvoice.value = invoice.invoice_number
  try {
    const newStatus = !invoice.paid
    const result = await api.updateInvoiceStatus(invoice.invoice_number, newStatus)
    invoice.paid = newStatus

    let detail = `${invoice.invoice_number} marked as ${newStatus ? 'Paid' : 'Unpaid'}`
    if (result.watermark_queued) {
      detail += ' (PAID watermark being added to PDF)'
    }

    toast.add({
      severity: 'success',
      summary: 'Updated',
      detail,
      life: 3000
    })
  } catch (e: any) {
    toast.add({ severity: 'error', summary: 'Error', detail: e.message, life: 4000 })
  } finally {
    updatingInvoice.value = null
  }
}

function openDriveLink(url: string) {
  if (url) {
    window.open(url, '_blank')
  }
}

onMounted(() => {
  loadInvoices()
})
</script>

<template>
  <AppLayout>
    <h1 class="page-title">Invoice Records</h1>

    <div class="toolbar">
      <InputText
        v-model="searchQuery"
        placeholder="Search by customer or invoice #..."
        style="width: 300px; max-width: 100%;"
      />
      <Button
        icon="pi pi-refresh"
        label="Refresh"
        severity="secondary"
        @click="loadInvoices"
        :loading="loading"
      />
    </div>

    <DataTable
      :value="filteredInvoices"
      :loading="loading"
      stripedRows
      scrollable
      scrollHeight="calc(100vh - 260px)"
      size="small"
      tableStyle="min-width: 900px"
    >
      <Column field="invoice_number" header="Invoice #" style="width: 120px">
        <template #body="{ data }">
          <strong>{{ data.invoice_number }}</strong>
        </template>
      </Column>
      <Column field="date" header="Date" style="width: 110px" />
      <Column field="customer" header="Customer" style="min-width: 150px" />
      <Column field="items_summary" header="Items" style="min-width: 200px">
        <template #body="{ data }">
          <span class="items-summary">{{ data.items_summary }}</span>
        </template>
      </Column>
      <Column field="total" header="Total" style="width: 100px">
        <template #body="{ data }">
          <strong>{{ data.total }}</strong>
        </template>
      </Column>
      <Column field="paid" header="Status" style="width: 100px">
        <template #body="{ data }">
          <Tag
            :value="data.paid ? 'Paid' : 'Unpaid'"
            :severity="data.paid ? 'success' : 'warn'"
          />
        </template>
      </Column>
      <Column header="Actions" style="width: 180px">
        <template #body="{ data }">
          <div class="action-buttons">
            <Button
              :icon="data.paid ? 'pi pi-times' : 'pi pi-check'"
              :label="data.paid ? 'Unpaid' : 'Paid'"
              :severity="data.paid ? 'secondary' : 'success'"
              size="small"
              @click="togglePaidStatus(data)"
              :loading="updatingInvoice === data.invoice_number"
            />
            <Button
              v-if="data.drive_url"
              icon="pi pi-external-link"
              label="PDF"
              severity="info"
              size="small"
              @click="openDriveLink(data.drive_url)"
            />
          </div>
        </template>
      </Column>
    </DataTable>

    <div v-if="!loading && filteredInvoices.length === 0" class="empty-state">
      <p>No invoices found.</p>
    </div>
  </AppLayout>
</template>

<style scoped>
.page-title {
  margin: 0 0 20px 0;
  font-size: 1.5rem;
  font-weight: 600;
}

.toolbar {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.items-summary {
  font-size: 0.85rem;
  color: var(--text-color-secondary);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.action-buttons {
  display: flex;
  gap: 8px;
}

.empty-state {
  text-align: center;
  padding: 40px;
  color: var(--text-color-secondary);
}
</style>
