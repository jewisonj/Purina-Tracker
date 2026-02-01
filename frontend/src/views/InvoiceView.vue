<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useInventoryStore } from '../stores/inventory'
import { useToast } from 'primevue/usetoast'
import AppLayout from '../components/AppLayout.vue'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import Select from 'primevue/select'
import { ALL_DISPLAY_PRODUCTS, type ProductConfig } from '../config/products'
import type { Product } from '../types'
import { jsPDF } from 'jspdf'
import autoTable from 'jspdf-autotable'

const store = useInventoryStore()
const toast = useToast()

onMounted(() => {
  if (!store.products.length) store.fetchProducts()
})

const customerName = ref('')
const invoiceDate = ref(new Date().toISOString().split('T')[0])

interface LineItem {
  selectedConfig: ProductConfig | null
  qty: number
}

const lineItems = ref<LineItem[]>([{ selectedConfig: null, qty: 1 }])

/** Map material_no → Product from API */
const productMap = computed(() => {
  const map = new Map<string, Product>()
  for (const p of store.products) {
    map.set(p.material_no, p)
  }
  return map
})

/** Product options for dropdown - show display names, map to config */
const productOptions = computed(() => {
  return ALL_DISPLAY_PRODUCTS.map(cfg => ({
    label: cfg.displayName,
    value: cfg,
    price: getPrice(cfg),
  }))
})

function getPrice(cfg: ProductConfig): number {
  const p = productMap.value.get(cfg.materialNo)
  return p ? p.retail_with_tax : cfg.defaultPrice
}

function getExtended(item: LineItem): number {
  if (!item.selectedConfig || !item.qty) return 0
  return item.qty * getPrice(item.selectedConfig)
}

const invoiceTotal = computed(() => {
  return lineItems.value.reduce((sum, item) => sum + getExtended(item), 0)
})

/** Auto-add a new row when the last row gets a product selected */
watch(lineItems, (items) => {
  const last = items[items.length - 1]
  if (last && last.selectedConfig) {
    items.push({ selectedConfig: null, qty: 1 })
  }
}, { deep: true })

function removeRow(index: number) {
  if (lineItems.value.length > 1) {
    lineItems.value.splice(index, 1)
  }
}

function clearInvoice() {
  customerName.value = ''
  invoiceDate.value = new Date().toISOString().split('T')[0]
  lineItems.value = [{ selectedConfig: null, qty: 1 }]
}

function downloadPDF() {
  const validItems = lineItems.value.filter(item => item.selectedConfig && item.qty > 0)
  if (!validItems.length) {
    toast.add({ severity: 'warn', summary: 'No items', detail: 'Add at least one product to the invoice.', life: 3000 })
    return
  }
  if (!customerName.value.trim()) {
    toast.add({ severity: 'warn', summary: 'Missing customer', detail: 'Enter a customer name.', life: 3000 })
    return
  }

  const doc = new jsPDF()
  const pageWidth = doc.internal.pageSize.getWidth()

  // Header
  doc.setFontSize(18)
  doc.setFont('helvetica', 'bold')
  doc.text('J and J Stables LLC', 14, 22)
  doc.setFontSize(10)
  doc.setFont('helvetica', 'normal')
  doc.text('Platteville, WI', 14, 28)

  // INVOICE title
  doc.setFontSize(22)
  doc.setFont('helvetica', 'bold')
  doc.text('INVOICE', pageWidth - 14, 22, { align: 'right' })

  // Customer info
  doc.setFontSize(11)
  doc.setFont('helvetica', 'normal')
  const infoY = 42
  doc.text(`Customer:  ${customerName.value.trim()}`, 14, infoY)
  doc.text(`Date:  ${invoiceDate.value}`, 14, infoY + 7)

  // Table
  const tableRows = validItems.map(item => {
    const price = getPrice(item.selectedConfig!)
    const extended = item.qty * price
    return [
      item.selectedConfig!.displayName,
      item.qty.toString(),
      `$${price.toFixed(2)}`,
      `$${extended.toFixed(2)}`,
    ]
  })

  // Total row
  tableRows.push([
    '', '', 'Total:',
    `$${invoiceTotal.value.toFixed(2)}`,
  ])

  autoTable(doc, {
    startY: infoY + 14,
    head: [['Product', 'Qty', 'Unit Price', 'Extended']],
    body: tableRows,
    theme: 'grid',
    headStyles: {
      fillColor: [196, 18, 48], // Purina red
      fontSize: 10,
      fontStyle: 'bold',
    },
    bodyStyles: {
      fontSize: 10,
    },
    columnStyles: {
      0: { cellWidth: 90 },
      1: { cellWidth: 20, halign: 'center' },
      2: { cellWidth: 35, halign: 'right' },
      3: { cellWidth: 35, halign: 'right' },
    },
    didParseCell: (data: any) => {
      // Bold the total row
      if (data.row.index === tableRows.length - 1) {
        data.cell.styles.fontStyle = 'bold'
        data.cell.styles.fontSize = 11
      }
    },
  })

  // Footer
  const finalY = (doc as any).lastAutoTable?.finalY || 200
  doc.setFontSize(10)
  doc.setFont('helvetica', 'italic')
  doc.text('Thank you for your business!', pageWidth / 2, finalY + 12, { align: 'center' })

  // Download
  const datePart = invoiceDate.value.replace(/-/g, '')
  const namePart = customerName.value.trim().replace(/\s+/g, '_').substring(0, 20)
  doc.save(`Invoice_${namePart}_${datePart}.pdf`)

  toast.add({ severity: 'success', summary: 'PDF Downloaded', detail: 'Invoice saved.', life: 2000 })
}
</script>

<template>
  <AppLayout>
    <div class="invoice-page">
      <div class="page-header">
        <h1>Invoice</h1>
        <div class="header-actions">
          <Button label="Clear" icon="pi pi-trash" severity="secondary" text size="small" @click="clearInvoice" />
          <Button label="Download PDF" icon="pi pi-download" severity="danger" size="small" @click="downloadPDF" />
        </div>
      </div>

      <!-- Customer Info -->
      <div class="customer-row">
        <div class="field">
          <label>Customer Name</label>
          <InputText v-model="customerName" placeholder="Enter customer name" style="width: 100%;" />
        </div>
        <div class="field">
          <label>Date</label>
          <InputText type="date" v-model="invoiceDate" style="width: 160px;" />
        </div>
      </div>

      <!-- Line Items -->
      <table class="line-items-table">
        <thead>
          <tr>
            <th class="col-product">Product</th>
            <th class="col-qty">Qty</th>
            <th class="col-price">Unit Price</th>
            <th class="col-ext">Extended</th>
            <th class="col-action"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(item, idx) in lineItems" :key="idx">
            <td class="col-product">
              <Select
                v-model="item.selectedConfig"
                :options="productOptions"
                optionLabel="label"
                optionValue="value"
                placeholder="Select product..."
                filter
                style="width: 100%;"
              />
            </td>
            <td class="col-qty">
              <InputNumber
                v-model="item.qty"
                :min="1"
                :max="999"
                style="width: 70px;"
                inputStyle="text-align: center;"
              />
            </td>
            <td class="col-price">
              <span v-if="item.selectedConfig">${{ getPrice(item.selectedConfig).toFixed(2) }}</span>
            </td>
            <td class="col-ext">
              <strong v-if="item.selectedConfig && item.qty">${{ getExtended(item).toFixed(2) }}</strong>
            </td>
            <td class="col-action">
              <Button
                v-if="lineItems.length > 1 && idx < lineItems.length - 1"
                icon="pi pi-times"
                severity="secondary"
                text
                size="small"
                @click="removeRow(idx)"
              />
            </td>
          </tr>
        </tbody>
        <tfoot>
          <tr class="total-row">
            <td colspan="3" style="text-align: right; font-weight: 700; font-size: 15px;">Total:</td>
            <td class="col-ext" style="font-weight: 700; font-size: 15px;">${{ invoiceTotal.toFixed(2) }}</td>
            <td></td>
          </tr>
        </tfoot>
      </table>
    </div>
  </AppLayout>
</template>

<style scoped>
.invoice-page {
  max-width: 800px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.page-header h1 {
  margin: 0;
  font-size: 20px;
  color: var(--text);
}

.header-actions {
  display: flex;
  gap: 8px;
}

.customer-row {
  display: flex;
  gap: 16px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.field:first-child {
  flex: 1;
  min-width: 200px;
}

.field label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
}

.line-items-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
  background: var(--surface);
  border-radius: 8px;
  overflow: hidden;
}

.line-items-table thead th {
  background: var(--primary);
  color: #fff;
  padding: 8px 10px;
  text-align: left;
  font-weight: 600;
  font-size: 12px;
}

.line-items-table tbody td {
  padding: 6px 10px;
  border-bottom: 1px solid var(--border);
  vertical-align: middle;
  color: var(--text);
}

.line-items-table th.col-qty,
.line-items-table td.col-qty {
  width: 80px;
  text-align: center;
}

.line-items-table th.col-price,
.line-items-table td.col-price {
  width: 100px;
  text-align: right;
}

.line-items-table th.col-ext,
.line-items-table td.col-ext {
  width: 100px;
  text-align: right;
}

.line-items-table th.col-action,
.line-items-table td.col-action {
  width: 40px;
  text-align: center;
}

.total-row td {
  border-top: 2px solid var(--primary);
  padding: 10px;
  color: var(--text);
}

@media (max-width: 600px) {
  .customer-row {
    flex-direction: column;
  }

  .line-items-table {
    font-size: 13px;
  }

  .line-items-table thead th,
  .line-items-table tbody td {
    padding: 4px 6px;
  }
}
</style>
