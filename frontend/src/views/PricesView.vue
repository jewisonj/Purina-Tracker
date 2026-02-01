<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useInventoryStore } from '../stores/inventory'
import { useToast } from 'primevue/usetoast'
import { importPriceList } from '../services/api'
import AppLayout from '../components/AppLayout.vue'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import Button from 'primevue/button'
import FileUpload from 'primevue/fileupload'
import type { Product } from '../types'

const store = useInventoryStore()
const toast = useToast()

const globalFilter = ref('')
const editingRows = ref<Product[]>([])
const uploading = ref(false)

const filteredProducts = computed(() => {
  const q = globalFilter.value.toLowerCase().trim()
  if (!q) return store.products
  return store.products.filter(
    p =>
      p.product_name.toLowerCase().includes(q) ||
      p.formula_code.toLowerCase().includes(q)
  )
})

onMounted(() => {
  if (!store.products.length) store.fetchProducts()
})

function ceilQuarter(val: number): number {
  return Math.ceil(val * 4) / 4
}

function previewPreTax(cost: number, markup: number): number {
  return ceilQuarter(cost * (1 + markup))
}

function previewWithTax(preTax: number): number {
  return ceilQuarter(preTax * 1.055)
}

function formatCurrency(val: number) {
  return '$' + val.toFixed(2)
}

function formatPct(val: number) {
  return (val * 100).toFixed(0) + '%'
}

async function saveMarkup(product: Product, newMarkup: number) {
  try {
    await store.updateMarkup(product.material_no, newMarkup)
    toast.add({
      severity: 'success',
      summary: 'Markup Updated',
      detail: `${product.product_name}: ${formatPct(newMarkup)}`,
      life: 2000,
    })
  } catch (e: any) {
    toast.add({ severity: 'error', summary: 'Error', detail: e.message, life: 4000 })
  }
}

async function handleUpload(event: any) {
  const file = event.files?.[0]
  if (!file) return
  uploading.value = true
  try {
    const result = await importPriceList(file)
    toast.add({
      severity: 'success',
      summary: 'Price List Imported',
      detail: result.message,
      life: 5000,
    })
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
    <h1 class="page-title">Pricing</h1>

    <div class="toolbar" style="margin-bottom: 16px">
      <InputText
        v-model="globalFilter"
        placeholder="Search products..."
        style="width: 300px; max-width: 100%;"
      />
      <FileUpload
        mode="basic"
        accept=".csv"
        :auto="true"
        chooseLabel="Import CSV"
        chooseIcon="pi pi-upload"
        :customUpload="true"
        @uploader="handleUpload"
        :disabled="uploading"
      />
    </div>

    <DataTable
      v-model:editingRows="editingRows"
      :value="filteredProducts"
      :loading="store.loading"
      editMode="cell"
      stripedRows
      scrollable
      scrollHeight="calc(100vh - 260px)"
      sortField="product_name"
      :sortOrder="1"
      size="small"
      tableStyle="min-width: 800px"
    >
      <Column field="product_name" header="Product" sortable style="min-width: 220px">
        <template #body="{ data }">
          <strong>{{ data.product_name }}</strong>
          <span style="color: #888; font-size: 11px; margin-left: 8px;">{{ data.formula_code }}</span>
        </template>
      </Column>
      <Column field="unit_weight" header="Weight" sortable style="width: 80px" />
      <Column field="purina_cost" header="Purina Cost" sortable style="width: 110px">
        <template #body="{ data }">{{ formatCurrency(data.purina_cost) }}</template>
      </Column>
      <Column field="markup_pct" header="Markup %" sortable style="width: 140px">
        <template #body="{ data }">
          <div class="markup-cell">
            <InputNumber
              :modelValue="data.markup_pct * 100"
              @update:modelValue="(v: number | null) => { if (v !== null) saveMarkup(data, v / 100) }"
              suffix="%"
              :min="0"
              :max="100"
              :minFractionDigits="0"
              :maxFractionDigits="0"
              style="width: 80px"
              inputStyle="text-align: center; font-size: 13px;"
            />
          </div>
        </template>
      </Column>
      <Column header="Pre-Tax" style="width: 100px">
        <template #body="{ data }">
          {{ formatCurrency(previewPreTax(data.purina_cost, data.markup_pct)) }}
        </template>
      </Column>
      <Column header="w/ Tax" style="width: 100px">
        <template #body="{ data }">
          <strong>{{ formatCurrency(previewWithTax(previewPreTax(data.purina_cost, data.markup_pct))) }}</strong>
        </template>
      </Column>
      <Column field="pallet_cost" header="Pallet" sortable style="width: 100px">
        <template #body="{ data }">{{ data.pallet_cost ? formatCurrency(data.pallet_cost) : '—' }}</template>
      </Column>
    </DataTable>
  </AppLayout>
</template>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.markup-cell {
  display: flex;
  align-items: center;
}
</style>
