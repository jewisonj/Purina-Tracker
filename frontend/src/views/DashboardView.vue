<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useInventoryStore } from '../stores/inventory'
import { useToast } from 'primevue/usetoast'
import AppLayout from '../components/AppLayout.vue'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import InputText from 'primevue/inputtext'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import Select from 'primevue/select'
import InputNumber from 'primevue/inputnumber'
import Textarea from 'primevue/textarea'
import type { Product } from '../types'

const store = useInventoryStore()
const toast = useToast()

const globalFilter = ref('')
const adjustDialogVisible = ref(false)
const bulkDialogVisible = ref(false)

// Single adjustment form
const adjProduct = ref<Product | null>(null)
const adjType = ref('sale')
const adjQty = ref(1)
const adjNotes = ref('')
const adjLoading = ref(false)

// Bulk adjustment
const bulkItems = ref<{ product: Product | null; quantity: number }[]>([])
const bulkLoading = ref(false)

const changeTypes = [
  { label: 'Sale', value: 'sale' },
  { label: 'Restock', value: 'restock' },
  { label: 'Adjustment', value: 'adjustment' },
]

// Display order: product name substrings in the exact order from the price list
const DISPLAY_ORDER: string[] = [
  'EQUINE SENIOR ACTIVE',
  'EQUINE SENIOR',
  'STRATEGY GX',
  'STRATEGY HEALTHY EDGE',
  'ULTIUM GASTRIC CARE',
  'ULTIUM GROWTH',
  'ULTIUM COMP',
  'IMPACT PROFESSIONAL SENIOR',
  'IMPACT PROFESSIONAL MARE',
  'IMPACT PROFESSIONAL PERFORM',
  'IMPACT ALL STAGES',
  'IMPACT HAY STRETCHER',
  'OMOLENE 200',
  'OMOLENE 300',
  'OMOLENE 400',
  'WELLSOLVE',
  'MINI-HORSE',
  'ENRICH PLUS',
  'OMEGA MATCH HORSE RATION',
  'FREE BALANCE',
  'REPLENIMASH 25',
  'AMPLIFY',
  'OUTLAST GASTRIC SUPPORT',
  'SUPERSPORT',
  'EQUITUB CLARIFLY 55',
  'EQUITUB CLARIFLY 125',
  'AHIFLOWER OIL',
  'SYSTEMIQ PROBIOTIC',
  'REPLENIMASH 7',
  'TREATS APPLE',
  'NICKER MAKERS',
  'OUTLAST HORSE TREATS',
  "MARE'S MATCH FOAL",
  "MARE'S MATCH TRANSITION",
]

function getDisplayIndex(product: Product): number {
  const name = product.product_name.toUpperCase()
  for (let i = 0; i < DISPLAY_ORDER.length; i++) {
    if (name.includes(DISPLAY_ORDER[i])) return i
  }
  return -1
}

const priceListProducts = computed(() => {
  const matched = store.products
    .filter(p => getDisplayIndex(p) >= 0)
    .sort((a, b) => getDisplayIndex(a) - getDisplayIndex(b))

  const q = globalFilter.value.toLowerCase().trim()
  if (!q) return matched
  return matched.filter(p => p.product_name.toLowerCase().includes(q))
})

onMounted(() => {
  store.fetchProducts()
})

function rowClass(data: Product) {
  if (data.qty_on_hand === 0) return 'out-of-stock-row'
  if (data.qty_on_hand <= data.reorder_point) return 'low-stock-row'
  return ''
}

async function quickAdjust(product: Product, delta: number) {
  try {
    await store.adjustInventory(
      product.material_no,
      delta > 0 ? 'restock' : 'sale',
      delta
    )
    toast.add({
      severity: 'success',
      summary: `${product.product_name}`,
      detail: `Qty: ${product.qty_on_hand + delta}`,
      life: 2000,
    })
  } catch (e: any) {
    toast.add({ severity: 'error', summary: 'Error', detail: e.message, life: 4000 })
  }
}

function openAdjustDialog(product?: Product) {
  adjProduct.value = product || null
  adjType.value = 'sale'
  adjQty.value = 1
  adjNotes.value = ''
  adjustDialogVisible.value = true
}

async function submitAdjust() {
  if (!adjProduct.value) return
  adjLoading.value = true
  try {
    const qty = adjType.value === 'sale' ? -Math.abs(adjQty.value) : Math.abs(adjQty.value)
    await store.adjustInventory(
      adjProduct.value.material_no,
      adjType.value,
      qty,
      adjNotes.value
    )
    toast.add({
      severity: 'success',
      summary: 'Inventory Updated',
      detail: `${adjProduct.value.product_name}: ${qty > 0 ? '+' : ''}${qty}`,
      life: 3000,
    })
    adjustDialogVisible.value = false
  } catch (e: any) {
    toast.add({ severity: 'error', summary: 'Error', detail: e.message, life: 4000 })
  } finally {
    adjLoading.value = false
  }
}

function openBulkDialog() {
  bulkItems.value = [{ product: null, quantity: 0 }]
  bulkDialogVisible.value = true
}

function addBulkRow() {
  bulkItems.value.push({ product: null, quantity: 0 })
}

function removeBulkRow(index: number) {
  bulkItems.value.splice(index, 1)
}

async function submitBulk() {
  const valid = bulkItems.value.filter(item => item.product && item.quantity > 0)
  if (!valid.length) return

  bulkLoading.value = true
  try {
    for (const item of valid) {
      await store.adjustInventory(
        item.product!.material_no,
        'restock',
        item.quantity
      )
    }
    toast.add({
      severity: 'success',
      summary: 'Bulk Restock Complete',
      detail: `Updated ${valid.length} products`,
      life: 3000,
    })
    bulkDialogVisible.value = false
    await store.fetchProducts()
  } catch (e: any) {
    toast.add({ severity: 'error', summary: 'Error', detail: e.message, life: 4000 })
  } finally {
    bulkLoading.value = false
  }
}
</script>

<template>
  <AppLayout>
    <div class="dashboard">
      <!-- Toolbar -->
      <div class="toolbar">
        <InputText
          v-model="globalFilter"
          placeholder="Search..."
          style="width: 240px; max-width: 100%;"
        />
        <div class="toolbar-actions">
          <Button
            label="Adjust"
            icon="pi pi-pencil"
            severity="secondary"
            size="small"
            @click="openAdjustDialog()"
          />
          <Button
            label="Restock"
            icon="pi pi-truck"
            severity="danger"
            size="small"
            @click="openBulkDialog"
          />
          <Button
            icon="pi pi-refresh"
            severity="secondary"
            text
            size="small"
            @click="store.fetchProducts()"
            :loading="store.loading"
          />
        </div>
      </div>

      <!-- Products Table -->
      <DataTable
        :value="priceListProducts"
        :loading="store.loading"
        :rowClass="rowClass"
        stripedRows
        scrollable
        scrollHeight="calc(100vh - 200px)"
        size="small"
        tableStyle="min-width: 500px"
      >
        <Column field="product_name" header="Product" style="min-width: 200px">
          <template #body="{ data }">
            <strong>{{ data.product_name }}</strong>
          </template>
        </Column>
        <Column field="unit_weight" header="Size" style="width: 80px" />
        <Column field="retail_with_tax" header="Price" style="width: 80px">
          <template #body="{ data }">
            <strong>${{ data.retail_with_tax.toFixed(2) }}</strong>
          </template>
        </Column>
        <Column field="qty_on_hand" header="Qty" style="width: 140px">
          <template #body="{ data }">
            <div class="qty-cell">
              <button class="qty-btn" @click="quickAdjust(data, -1)" title="Sell 1">&minus;</button>
              <span class="qty-value" :class="{
                'qty-low': data.qty_on_hand > 0 && data.qty_on_hand <= data.reorder_point,
                'qty-out': data.qty_on_hand === 0
              }">
                {{ data.qty_on_hand }}
              </span>
              <button class="qty-btn" @click="quickAdjust(data, 1)" title="Add 1">+</button>
            </div>
          </template>
        </Column>
      </DataTable>

      <!-- Single Adjust Dialog -->
      <Dialog
        v-model:visible="adjustDialogVisible"
        header="Adjust Inventory"
        modal
        :style="{ width: '420px' }"
      >
        <div class="dialog-form">
          <div class="field">
            <label>Product</label>
            <Select
              v-model="adjProduct"
              :options="priceListProducts"
              optionLabel="product_name"
              placeholder="Select product"
              filter
              style="width: 100%"
            />
          </div>
          <div v-if="adjProduct" class="field current-qty">
            Current: <strong>{{ adjProduct.qty_on_hand }}</strong>
          </div>
          <div class="field">
            <label>Change Type</label>
            <Select
              v-model="adjType"
              :options="changeTypes"
              optionLabel="label"
              optionValue="value"
              style="width: 100%"
            />
          </div>
          <div class="field">
            <label>Quantity</label>
            <InputNumber v-model="adjQty" :min="1" :max="999" style="width: 100%" />
          </div>
          <div class="field">
            <label>Notes (optional)</label>
            <Textarea v-model="adjNotes" rows="2" style="width: 100%" />
          </div>
        </div>
        <template #footer>
          <Button label="Cancel" severity="secondary" text @click="adjustDialogVisible = false" />
          <Button
            :label="adjType === 'sale' ? `Sell ${adjQty}` : `Add ${adjQty}`"
            severity="danger"
            :loading="adjLoading"
            :disabled="!adjProduct"
            @click="submitAdjust"
          />
        </template>
      </Dialog>

      <!-- Bulk Restock Dialog -->
      <Dialog
        v-model:visible="bulkDialogVisible"
        header="Bulk Restock"
        modal
        :style="{ width: '600px', maxWidth: '95vw' }"
      >
        <p style="margin-bottom: 16px; color: #666; font-size: 13px;">
          Enter quantities for each product received.
        </p>
        <div class="bulk-rows">
          <div v-for="(item, idx) in bulkItems" :key="idx" class="bulk-row">
            <Select
              v-model="item.product"
              :options="priceListProducts"
              optionLabel="product_name"
              placeholder="Select product"
              filter
              style="flex: 1"
            />
            <InputNumber v-model="item.quantity" :min="0" :max="999" style="width: 80px" />
            <Button
              icon="pi pi-times"
              severity="secondary"
              text
              @click="removeBulkRow(idx)"
              :disabled="bulkItems.length === 1"
            />
          </div>
        </div>
        <Button
          label="Add Row"
          icon="pi pi-plus"
          severity="secondary"
          text
          size="small"
          @click="addBulkRow"
          style="margin-top: 8px"
        />
        <template #footer>
          <Button label="Cancel" severity="secondary" text @click="bulkDialogVisible = false" />
          <Button
            label="Submit Restock"
            severity="danger"
            icon="pi pi-check"
            :loading="bulkLoading"
            @click="submitBulk"
          />
        </template>
      </Dialog>
    </div>
  </AppLayout>
</template>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.toolbar-actions {
  display: flex;
  gap: 8px;
}

.qty-cell {
  display: flex;
  align-items: center;
  gap: 6px;
}

.qty-value {
  font-weight: 700;
  font-size: 16px;
  min-width: 32px;
  text-align: center;
}

.qty-low {
  color: #e67e00;
}

.qty-out {
  color: #dc3545;
}

.dialog-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.dialog-form .field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.dialog-form label {
  font-size: 13px;
  font-weight: 600;
  color: #555;
}

.current-qty {
  background: #f0f2f5;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 14px;
}

.bulk-rows {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.bulk-row {
  display: flex;
  gap: 8px;
  align-items: center;
}

@media (max-width: 768px) {
  .toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .toolbar-actions {
    justify-content: flex-end;
  }
}
</style>
