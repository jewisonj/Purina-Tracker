import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Product, LogEntry } from '../types'
import * as api from '../services/api'

export const useInventoryStore = defineStore('inventory', () => {
  const products = ref<Product[]>([])
  const logEntries = ref<LogEntry[]>([])
  const loading = ref(false)
  const error = ref('')

  const lowStockProducts = computed(() =>
    products.value.filter(p => p.qty_on_hand <= p.reorder_point)
  )

  const totalProducts = computed(() => products.value.length)
  const lowStockCount = computed(() => lowStockProducts.value.length)

  async function fetchProducts() {
    loading.value = true
    error.value = ''
    try {
      products.value = await api.getProducts()
    } catch (e: any) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function fetchLog(limit = 100) {
    loading.value = true
    error.value = ''
    try {
      logEntries.value = await api.getLog(limit)
    } catch (e: any) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function adjustInventory(
    materialNo: string,
    changeType: string,
    quantity: number,
    notes = ''
  ) {
    const updated = await api.adjustInventory({
      material_no: materialNo,
      change_type: changeType as any,
      quantity,
      notes,
    })
    // Update local state
    const idx = products.value.findIndex(p => p.material_no === materialNo)
    if (idx >= 0) products.value[idx] = updated
    return updated
  }

  async function updateMarkup(materialNo: string, markupPct: number) {
    const updated = await api.updateMarkup(materialNo, markupPct)
    const idx = products.value.findIndex(p => p.material_no === materialNo)
    if (idx >= 0) products.value[idx] = updated
    return updated
  }

  async function updateReorder(materialNo: string, reorderPoint: number) {
    const updated = await api.updateReorder(materialNo, reorderPoint)
    const idx = products.value.findIndex(p => p.material_no === materialNo)
    if (idx >= 0) products.value[idx] = updated
    return updated
  }

  return {
    products,
    logEntries,
    loading,
    error,
    lowStockProducts,
    totalProducts,
    lowStockCount,
    fetchProducts,
    fetchLog,
    adjustInventory,
    updateMarkup,
    updateReorder,
  }
})
