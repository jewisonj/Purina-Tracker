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

type DiscountType = 'amount' | 'percent'

interface LineItem {
  selectedConfig: ProductConfig | null
  qty: number
  discountType: DiscountType
  discountValue: number | null
}

function newLine(): LineItem {
  return { selectedConfig: null, qty: 1, discountType: 'amount', discountValue: null }
}

const lineItems = ref<LineItem[]>([newLine()])

/** Whole-invoice discount, applied after any per-item discounts */
const invoiceDiscountType = ref<DiscountType>('amount')
const invoiceDiscountValue = ref<number | null>(null)

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

function round2(n: number): number {
  return Math.round(n * 100) / 100
}

/** Dollar value of a discount against a base amount. Never negative, never more than the base. */
function calcDiscount(base: number, type: DiscountType, value: number | null | string): number {
  const v = Number(value) || 0
  if (v <= 0 || base <= 0) return 0
  const d = type === 'percent' ? base * Math.min(v, 100) / 100 : Math.min(v, base)
  return round2(d)
}

/** Text shown next to a discount, e.g. "10%" or "$5.00" */
function discountLabel(type: DiscountType, value: number | null | string): string {
  const v = Number(value) || 0
  return type === 'percent' ? `${Math.min(v, 100)}%` : `$${v.toFixed(2)}`
}

/** Line amount before any discount */
function getGross(item: LineItem): number {
  if (!item.selectedConfig || !item.qty) return 0
  return round2(item.qty * getPrice(item.selectedConfig))
}

function getLineDiscount(item: LineItem): number {
  return calcDiscount(getGross(item), item.discountType, item.discountValue)
}

/** Line amount after its own discount */
function getExtended(item: LineItem): number {
  return round2(getGross(item) - getLineDiscount(item))
}

/** Sum of lines after per-item discounts */
const invoiceSubtotal = computed(() => {
  return round2(lineItems.value.reduce((sum, item) => sum + getExtended(item), 0))
})

const lineDiscountTotal = computed(() => {
  return round2(lineItems.value.reduce((sum, item) => sum + getLineDiscount(item), 0))
})

const invoiceDiscount = computed(() => {
  return calcDiscount(invoiceSubtotal.value, invoiceDiscountType.value, invoiceDiscountValue.value)
})

const totalDiscount = computed(() => round2(lineDiscountTotal.value + invoiceDiscount.value))

const invoiceTotal = computed(() => round2(invoiceSubtotal.value - invoiceDiscount.value))

/** Auto-add a new row when the last row gets a product selected */
watch(lineItems, (items) => {
  const last = items[items.length - 1]
  if (last && last.selectedConfig) {
    items.push(newLine())
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
  lineItems.value = [newLine()]
  invoiceDiscountType.value = 'amount'
  invoiceDiscountValue.value = null
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

/** Generate a jsPDF document from the current invoice data. Includes PAID stamp if isPaid is true. */
function generatePDFDoc(validItems: LineItem[], isPaid = false): jsPDF {
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

  // Table. A discounted item gets its own "Discount" row right under it.
  const tableRows: string[][] = []
  const discountRowIdx = new Set<number>()
  for (const item of validItems) {
    const price = getPrice(item.selectedConfig!)
    tableRows.push([
      item.selectedConfig!.displayName,
      item.qty.toString(),
      `$${price.toFixed(2)}`,
      `$${getGross(item).toFixed(2)}`,
    ])
    const lineDisc = getLineDiscount(item)
    if (lineDisc > 0) {
      discountRowIdx.add(tableRows.length)
      tableRows.push([
        `    Discount (${discountLabel(item.discountType, item.discountValue)})`,
        '', '',
        `-$${lineDisc.toFixed(2)}`,
      ])
    }
  }

  // Whole-invoice discount: show the subtotal, then the discount
  if (invoiceDiscount.value > 0) {
    tableRows.push(['', '', 'Subtotal:', `$${invoiceSubtotal.value.toFixed(2)}`])
    discountRowIdx.add(tableRows.length)
    const pct = invoiceDiscountType.value === 'percent'
      ? ` (${discountLabel('percent', invoiceDiscountValue.value)})`
      : ''
    tableRows.push(['', '', `Discount${pct}:`, `-$${invoiceDiscount.value.toFixed(2)}`])
  }

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
      0: { cellWidth: 'auto' },
      1: { cellWidth: 20, halign: 'center' },
      2: { cellWidth: 40, halign: 'right' },
      3: { cellWidth: 32, halign: 'right' },
    },
    didParseCell: (data: any) => {
      if (data.section !== 'body') return
      if (discountRowIdx.has(data.row.index)) {
        data.cell.styles.fontStyle = 'italic'
      }
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

  // PAID stamp
  if (isPaid) {
    doc.saveGraphicsState()
    doc.setGState(new (doc as any).GState({ opacity: 0.18 }))
    doc.setFontSize(80)
    doc.setFont('helvetica', 'bold')
    doc.setTextColor(196, 18, 48)
    const cx = pageWidth / 2
    const cy = 140
    doc.text('PAID', cx, cy, { align: 'center', angle: 35 })
    doc.restoreGraphicsState()
    doc.setTextColor(0, 0, 0)
  }

  return doc
}

function downloadPDF() {
  const validItems = validateInvoice()
  if (!validItems) return

  const doc = generatePDFDoc(validItems, paid.value)
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
    const doc = generatePDFDoc(validItems, paid.value)
    const pdfBlob = doc.output('blob')

    const invoiceData = {
      customer_name: customerName.value.trim(),
      invoice_date: invoiceDate.value,
      items: validItems.map(item => ({
        product_name: item.selectedConfig!.displayName,
        material_no: item.selectedConfig!.materialNo,
        qty: item.qty,
        unit_price: getPrice(item.selectedConfig!),
        discount: getLineDiscount(item),
        extended: getExtended(item),
      })),
      subtotal: invoiceSubtotal.value,
      invoice_discount: invoiceDiscount.value,
      discount_total: totalDiscount.value,
      total: invoiceTotal.value,
      paid: paid.value,
    }

    const result = await fileInvoice(invoiceData, pdfBlob)

    if (result.drive_error) {
      toast.add({ severity: 'warn', summary: 'Drive Upload Failed', detail: `${result.invoice_number} logged to Sheets but Drive failed: ${result.drive_error}`, life: 6000 })
    } else {
      let detail = `${result.invoice_number} filed.`
      if (result.drive_url) {
        detail += ' PDF uploaded to Drive.'
      }
      toast.add({ severity: 'success', summary: 'Invoice Filed', detail, life: 4000 })
    }
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

          <!-- Row 3: optional discount on this item -->
          <div v-if="item.selectedConfig" class="discount-row">
            <span class="detail-label">Item discount</span>
            <div class="discount-control">
              <div class="discount-toggle">
                <button
                  type="button"
                  :class="{ active: item.discountType === 'amount' }"
                  @click="item.discountType = 'amount'"
                >$</button>
                <button
                  type="button"
                  :class="{ active: item.discountType === 'percent' }"
                  @click="item.discountType = 'percent'"
                >%</button>
              </div>
              <input
                v-model.number="item.discountValue"
                type="number"
                inputmode="decimal"
                min="0"
                step="0.01"
                placeholder="0"
                class="discount-input"
              />
            </div>
            <span v-if="getLineDiscount(item) > 0" class="discount-amount">
              −${{ getLineDiscount(item).toFixed(2) }}
            </span>
          </div>
        </div>
      </div>

      <!-- Totals -->
      <div class="invoice-totals">
        <div class="discount-row discount-row--invoice">
          <span class="detail-label">Invoice discount</span>
          <div class="discount-control">
            <div class="discount-toggle">
              <button
                type="button"
                :class="{ active: invoiceDiscountType === 'amount' }"
                @click="invoiceDiscountType = 'amount'"
              >$</button>
              <button
                type="button"
                :class="{ active: invoiceDiscountType === 'percent' }"
                @click="invoiceDiscountType = 'percent'"
              >%</button>
            </div>
            <input
              v-model.number="invoiceDiscountValue"
              type="number"
              inputmode="decimal"
              min="0"
              step="0.01"
              placeholder="0"
              class="discount-input"
            />
          </div>
          <span v-if="invoiceDiscount > 0" class="discount-amount">
            −${{ invoiceDiscount.toFixed(2) }}
          </span>
        </div>

        <div v-if="invoiceDiscount > 0" class="totals-line">
          <span>Subtotal:</span>
          <span>${{ invoiceSubtotal.toFixed(2) }}</span>
        </div>
        <div v-if="totalDiscount > 0" class="totals-line totals-line--discount">
          <span>Total discount:</span>
          <span>−${{ totalDiscount.toFixed(2) }}</span>
        </div>
        <div class="invoice-total">
          <span>Total:</span>
          <strong>${{ invoiceTotal.toFixed(2) }}</strong>
        </div>
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

/* --- Discounts --- */
.discount-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed var(--border);
}

.discount-row--invoice {
  margin-top: 0;
  padding-top: 0;
  border-top: none;
}

.discount-control {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.discount-toggle {
  display: inline-flex;
  border: 1px solid var(--border);
  border-radius: 6px;
  overflow: hidden;
}

.discount-toggle button {
  width: 32px;
  height: 32px;
  border: none;
  background: var(--surface-hover, #333);
  color: var(--text-secondary);
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  padding: 0;
}

.discount-toggle button.active {
  background: var(--primary);
  color: #fff;
}

.discount-input {
  width: 76px;
  height: 32px;
  padding: 0 8px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--surface);
  color: var(--text);
  font-size: 15px;
  text-align: right;
}

.discount-amount {
  margin-left: auto;
  font-size: 14px;
  font-weight: 600;
  color: var(--primary);
}

/* --- Totals --- */
.invoice-totals {
  margin-top: 12px;
  padding: 12px 16px;
  background: var(--surface);
  border-top: 2px solid var(--primary);
  border-radius: 0 0 8px 8px;
  color: var(--text);
}

.totals-line {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 8px;
  font-size: 14px;
  color: var(--text-secondary);
}

.totals-line--discount {
  color: var(--primary);
}

.invoice-total {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 12px;
  margin-top: 8px;
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
