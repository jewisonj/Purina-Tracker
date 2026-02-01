<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useInventoryStore } from '../stores/inventory'
import { useAuthStore } from '../stores/auth'
import { useToast } from 'primevue/usetoast'
import AppLayout from '../components/AppLayout.vue'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import type { Product } from '../types'
import { PRODUCT_GROUPS, type ProductConfig } from '../config/products'

const store = useInventoryStore()
const authStore = useAuthStore()
const toast = useToast()

onMounted(() => {
  store.fetchProducts()
})

/** Map material_no → Product from the API */
const productMap = computed(() => {
  const map = new Map<string, Product>()
  for (const p of store.products) {
    map.set(p.material_no, p)
  }
  return map
})

interface DisplayRow {
  config: ProductConfig
  product: Product | null
  price: number
  qty: number | null
}

interface DisplayGroup {
  rows: DisplayRow[]
}

const searchQuery = ref('')

const displayGroups = computed<DisplayGroup[]>(() => {
  const q = searchQuery.value.toLowerCase().trim()
  const terms = q ? q.split(/\s+/) : []

  return PRODUCT_GROUPS.map(group => ({
    rows: group.products
      .map(cfg => {
        const product = productMap.value.get(cfg.materialNo) || null
        return {
          config: cfg,
          product,
          price: product ? product.retail_with_tax : cfg.defaultPrice,
          qty: product ? product.qty_on_hand : null,
        }
      })
      .filter(row => {
        if (!terms.length) return true
        const name = row.config.displayName.toLowerCase()
        return terms.every(t => name.includes(t))
      }),
  })).filter(group => group.rows.length > 0)
})

async function quickAdjust(row: DisplayRow, delta: number) {
  if (!row.product) return
  try {
    await store.adjustInventory(
      row.product.material_no,
      delta > 0 ? 'restock' : 'sale',
      delta
    )
    toast.add({
      severity: 'success',
      summary: row.config.displayName,
      detail: `Qty: ${(row.qty ?? 0) + delta}`,
      life: 2000,
    })
  } catch (e: any) {
    toast.add({ severity: 'error', summary: 'Error', detail: e.message, life: 4000 })
  }
}
</script>

<template>
  <AppLayout>
    <div class="inventory-page">
      <div class="page-header">
        <h1>Inventory</h1>
        <Button
          icon="pi pi-refresh"
          severity="secondary"
          text
          size="small"
          @click="store.fetchProducts()"
          :loading="store.loading"
        />
      </div>

      <div class="search-bar">
        <i class="pi pi-search search-icon"></i>
        <InputText
          v-model="searchQuery"
          placeholder="Filter products..."
          class="search-input"
        />
        <i
          v-if="searchQuery"
          class="pi pi-times clear-icon"
          @click="searchQuery = ''"
        ></i>
      </div>

      <table class="inv-table">
        <thead>
          <tr>
            <th class="col-product">Product</th>
            <th class="col-price">Price w/tax</th>
            <th class="col-qty">Qty On Hand</th>
          </tr>
        </thead>
        <tbody>
          <template v-for="(group, gi) in displayGroups" :key="gi">
            <tr v-if="gi > 0" class="group-separator"><td colspan="3"></td></tr>
            <tr
              v-for="(row, ri) in group.rows"
              :key="row.config.materialNo"
              :class="{
                'row-out': row.qty === 0,
                'row-low': row.qty !== null && row.qty > 0 && row.product && row.qty <= row.product.reorder_point,
              }"
            >
              <td class="col-product">{{ row.config.displayName }}</td>
              <td class="col-price">${{ row.price.toFixed(2) }}</td>
              <td class="col-qty">
                <div class="qty-cell" v-if="row.product && authStore.isAdmin">
                  <button class="qty-btn minus" @click="quickAdjust(row, -1)" title="Sell 1">&minus;</button>
                  <span class="qty-value">{{ row.qty }}</span>
                  <button class="qty-btn plus" @click="quickAdjust(row, 1)" title="Add 1">+</button>
                </div>
                <span v-else-if="row.product" class="qty-value">{{ row.qty }}</span>
                <span v-else class="qty-na">&mdash;</span>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>
  </AppLayout>
</template>

<style scoped>
.inventory-page {
  max-width: 700px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.page-header h1 {
  margin: 0;
  font-size: 20px;
  color: var(--text);
}

.search-bar {
  position: relative;
  margin-bottom: 10px;
}

.search-icon {
  position: absolute;
  left: 10px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-secondary);
  font-size: 14px;
  pointer-events: none;
}

.search-input {
  width: 100%;
  padding-left: 32px !important;
  padding-right: 32px !important;
  font-size: 14px;
}

.clear-icon {
  position: absolute;
  right: 10px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-secondary);
  font-size: 14px;
  cursor: pointer;
}

.clear-icon:hover {
  color: var(--text);
}

.inv-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
  background: var(--surface);
  border-radius: 8px;
  overflow: hidden;
}

.inv-table thead th {
  background: var(--primary);
  color: #fff;
  padding: 8px 12px;
  text-align: left;
  font-weight: 600;
  font-size: 13px;
  position: sticky;
  top: 0;
  z-index: 1;
}

.inv-table th.col-price,
.inv-table td.col-price {
  text-align: right;
  width: 110px;
}

.inv-table th.col-qty,
.inv-table td.col-qty {
  text-align: center;
  width: 140px;
}

.inv-table tbody td {
  padding: 6px 12px;
  border-bottom: 1px solid var(--border);
  color: var(--text);
}

.inv-table tbody tr:hover {
  background: var(--surface-hover);
}

.group-separator td {
  padding: 0;
  height: 10px;
  border-bottom: 2px solid var(--border);
  background: var(--surface-alt);
}

.col-product {
  font-weight: 500;
}

.col-price {
  font-weight: 600;
}

.qty-cell {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.qty-value {
  font-weight: 700;
  font-size: 15px;
  min-width: 28px;
  text-align: center;
}

.qty-btn {
  width: 28px;
  height: 28px;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: var(--surface-card);
  cursor: pointer;
  font-size: 16px;
  font-weight: 700;
  line-height: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text);
  transition: all 0.15s;
}

.qty-btn:hover {
  background: var(--surface-hover);
}

.qty-btn.minus:hover {
  background: #3a1520;
  border-color: var(--primary);
  color: #f87171;
}

.qty-btn.plus:hover {
  background: #153020;
  border-color: var(--success);
  color: #4ade80;
}

.qty-na {
  color: var(--text-secondary);
}

.row-out td {
  background: #2a1418;
  color: #f87171;
}

.row-low td {
  background: #2a2014;
  color: #fbbf24;
}

@media (max-width: 600px) {
  .inv-table {
    font-size: 13px;
  }

  .inv-table thead th,
  .inv-table tbody td {
    padding: 5px 8px;
  }

  .inv-table th.col-price,
  .inv-table td.col-price {
    width: 80px;
  }

  .inv-table th.col-qty,
  .inv-table td.col-qty {
    width: 110px;
  }

  .qty-btn {
    width: 24px;
    height: 24px;
    font-size: 14px;
  }
}
</style>
