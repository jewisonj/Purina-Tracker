<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useInventoryStore } from '../stores/inventory'
import { useToast } from 'primevue/usetoast'
import AppLayout from '../components/AppLayout.vue'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import { ALL_DISPLAY_PRODUCTS, type ProductConfig } from '../config/products'
import type { Product } from '../types'
import { bulkAdjust, fileInvoice } from '../services/api'
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
  paid.value = false
}

/** Validate invoice has items and customer name. Returns valid items or null. */
function validateInvoice(): LineItem[] | null {
  const validItems = lineItems.value.filter(item => item.selectedConfig && item.qty > 0)
  if (!validItems.length) {
    toast.add({ severity: 'warn', summary: 'No items', detail: 'Add at least one product to the invoice.', life: 3000 })
    return null
  }
  if (!customerName.value.trim()) {
    toast.add({ severity: 'warn', summary: 'Missing customer', detail: 'Enter a customer name.', life: 3000 })
    return null
  }
  return validItems
}

/** Generate a jsPDF document from the current invoice data. */
function generatePDFDoc(validItems: LineItem[]): jsPDF {
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

  return doc
}

function downloadPDF() {
  const validItems = validateInvoice()
  if (!validItems) return

  const doc = generatePDFDoc(validItems)
  const datePart = invoiceDate.value.replace(/-/g, '')
  const namePart = customerName.value.trim().replace(/\s+/g, '_').substring(0, 20)
  doc.save(`Invoice_${namePart}_${datePart}.pdf`)

  toast.add({ severity: 'success', summary: 'PDF Downloaded', detail: 'Invoice saved.', life: 2000 })
}

const filingInvoice = ref(false)

async function fileInvoiceHandler() {
  const validItems = validateInvoice()
  if (!validItems) return

  filingInvoice.value = true
  try {
    const doc = generatePDFDoc(validItems)
    const pdfBlob = doc.output('blob')

    const invoiceData = {
      customer_name: customerName.value.trim(),
      invoice_date: invoiceDate.value,
      items: validItems.map(item => ({
        product_name: item.selectedConfig!.displayName,
        material_no: item.selectedConfig!.materialNo,
        qty: item.qty,
        unit_price: getPrice(item.selectedConfig!),
        extended: getExtended(item),
      })),
      total: invoiceTotal.value,
      paid: paid.value,
    }

    const result = await fileInvoice(invoiceData, pdfBlob)

    let detail = `${result.invoice_number} filed.`
    if (result.drive_url) {
      detail += ' PDF uploaded to Drive.'
    }
    toast.add({ severity: 'success', summary: 'Invoice Filed', detail, life: 4000 })
  } catch (err: any) {
    toast.add({ severity: 'error', summary: 'Filing Failed', detail: err.message || 'Could not file invoice.', life: 4000 })
  } finally {
    filingInvoice.value = false
  }
}

const paid = ref(false)
const pullingInventory = ref(false)

async function pullInventory() {
  const validItems = lineItems.value.filter(item => item.selectedConfig && item.qty > 0)
  if (!validItems.length) {
    toast.add({ severity: 'warn', summary: 'No items', detail: 'Add at least one product to pull from inventory.', life: 3000 })
    return
  }

  pullingInventory.value = true
  try {
    const adjustments = validItems.map(item => ({
      material_no: item.selectedConfig!.materialNo,
      change_type: 'sale' as const,
      quantity: -item.qty,
      notes: `Invoice: ${customerName.value.trim() || 'unnamed'}`,
    }))

    await bulkAdjust(adjustments)
    await store.fetchProducts()

    toast.add({
      severity: 'success',
      summary: 'Inventory Updated',
      detail: `${validItems.length} product(s) pulled from inventory.`,
      life: 3000,
    })
  } catch (err: any) {
    toast.add({ severity: 'error', summary: 'Error', detail: err.message || 'Failed to pull inventory.', life: 4000 })
  } finally {
    pullingInventory.value = false
  }
}
</script>

<template>
  <AppLayout>
    <div class="invoice-page">
      <div class="page-header">
        <h1>Invoice</h1>
        <Button label="Clear" icon="pi pi-trash" severity="secondary" text size="small" @click="clearInvoice" />
        <span class="header-spacer"></span>
        <Button label="Download PDF" icon="pi pi-download" severity="danger" size="small" @click="downloadPDF" />
        <Button label="File Invoice" icon="pi pi-folder" severity="info" size="small" :loading="filingInvoice" @click="fileInvoiceHandler" />
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
      <div class="line-items">
        <div
          v-for="(item, idx) in lineItems"
          :key="idx"
          class="line-card"
          :class="{ 'line-card--empty': !item.selectedConfig }"
        >
          <!-- Row 1: Product selector full width -->
          <div class="line-product-row">
            <Select
              v-model="item.selectedConfig"
              :options="productOptions"
              optionLabel="label"
              optionValue="value"
              placeholder="Select product..."
              filter
              class="product-select"
            />
            <button
              v-if="lineItems.length > 1 && idx < lineItems.length - 1"
              class="remove-btn"
              @click="removeRow(idx)"
            >
              <i class="pi pi-times"></i>
            </button>
          </div>

          <!-- Row 2: Qty / Unit Price / Extended -->
          <div v-if="item.selectedConfig" class="line-details-row">
            <div class="detail-cell">
              <span class="detail-label">Qty</span>
              <div class="qty-stepper">
                <button class="qty-btn" @click="item.qty = Math.max(1, item.qty - 1)">−</button>
                <span class="qty-value">{{ item.qty }}</span>
                <button class="qty-btn" @click="item.qty = Math.min(999, item.qty + 1)">+</button>
              </div>
            </div>
            <div class="detail-cell">
              <span class="detail-label">Unit Price</span>
              <span class="detail-value">${{ getPrice(item.selectedConfig).toFixed(2) }}</span>
            </div>
            <div class="detail-cell">
              <span class="detail-label">Extended</span>
              <strong class="detail-value">${{ getExtended(item).toFixed(2) }}</strong>
            </div>
          </div>
        </div>
      </div>

      <!-- Total -->
      <div class="invoice-total">
        <span>Total:</span>
        <strong>${{ invoiceTotal.toFixed(2) }}</strong>
      </div>

      <!-- Footer: Paid + Pull Inventory -->
      <div class="invoice-footer">
        <label class="paid-check">
          <input type="checkbox" v-model="paid" />
          <span>Paid</span>
        </label>
        <Button
          label="Pull Inventory"
          icon="pi pi-box"
          severity="warn"
          size="small"
          :loading="pullingInventory"
          @click="pullInventory"
        />
      </div>
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
  flex-wrap: wrap;
  gap: 8px;
}

.page-header h1 {
  margin: 0;
  font-size: 20px;
  color: var(--text);
}

.header-spacer {
  flex: 1;
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

/* --- Line item cards --- */
.line-items {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.line-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 10px 12px;
}

.line-card--empty {
  border-style: dashed;
}

.line-product-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.product-select {
  flex: 1;
  min-width: 0;
}

.remove-btn {
  background: none;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  padding: 4px 6px;
  border-radius: 4px;
  font-size: 14px;
  flex-shrink: 0;
}

.remove-btn:hover {
  color: var(--primary);
  background: var(--surface-hover, rgba(255,255,255,0.05));
}

.line-details-row {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--border);
}

.detail-cell {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  flex: 1;
}

.detail-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
}

.detail-value {
  font-size: 15px;
  color: var(--text);
}

/* --- Qty stepper --- */
.qty-stepper {
  display: inline-flex;
  align-items: center;
  border: 1px solid var(--border);
  border-radius: 6px;
  overflow: hidden;
}

.qty-btn {
  width: 32px;
  height: 32px;
  border: none;
  background: var(--surface-hover, #333);
  color: var(--text);
  font-size: 18px;
  font-weight: 700;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  line-height: 1;
}

.qty-btn:active {
  background: var(--primary);
  color: #fff;
}

.qty-value {
  width: 36px;
  text-align: center;
  font-weight: 600;
  font-size: 15px;
  background: var(--surface);
}

/* --- Total bar --- */
.invoice-total {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 12px;
  margin-top: 12px;
  padding: 12px 16px;
  background: var(--surface);
  border-top: 2px solid var(--primary);
  border-radius: 0 0 8px 8px;
  font-size: 16px;
  color: var(--text);
}

.invoice-total strong {
  font-size: 18px;
}

/* --- Footer --- */
.invoice-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 14px;
}

.paid-check {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  color: var(--text);
  font-size: 15px;
  font-weight: 600;
  user-select: none;
}

.paid-check input[type="checkbox"] {
  width: 20px;
  height: 20px;
  accent-color: var(--primary);
  cursor: pointer;
}

@media (max-width: 600px) {
  .page-header h1 {
    width: 100%;
  }

  .header-actions {
    width: 100%;
  }

  .customer-row {
    flex-direction: column;
  }

  .line-details-row {
    gap: 8px;
  }

  .detail-value {
    font-size: 14px;
  }

  .qty-btn {
    width: 36px;
    height: 36px;
  }
}
</style>
