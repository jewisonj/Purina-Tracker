export interface Product {
  row_number: number
  material_no: string
  formula_code: string
  product_name: string
  product_form: string
  unit_weight: string
  purina_cost: number
  pallet_cost: number
  markup_pct: number
  retail_pre_tax: number
  retail_with_tax: number
  qty_on_hand: number
  reorder_point: number
  last_updated: string
  notes: string
}

export interface LogEntry {
  timestamp: string
  product_name: string
  material_no: string
  change_type: string
  qty_changed: number
  previous_qty: number
  new_qty: number
  changed_by: string
  notes: string
}

export interface InventoryAdjustment {
  material_no: string
  change_type: 'sale' | 'restock' | 'adjustment'
  quantity: number
  notes?: string
}
