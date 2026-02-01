export interface ProductConfig {
  displayName: string
  materialNo: string
  defaultPrice: number
}

export interface ProductGroup {
  products: ProductConfig[]
}

/**
 * Product groups and display names matching the desired inventory layout.
 * materialNo maps to the Inventory tab in Google Sheets.
 * defaultPrice is the desired retail price (w/ 5.5% WI tax).
 */
export const PRODUCT_GROUPS: ProductGroup[] = [
  {
    products: [
      { displayName: 'Equine Senior\u00AE', materialNo: '3006848-506', defaultPrice: 29.25 },
      { displayName: 'Equine Senior\u00AE Active', materialNo: '3006849-506', defaultPrice: 31.25 },
    ],
  },
  {
    products: [
      { displayName: 'Strategy\u00AE Professional Formula GX', materialNo: '3004620-206', defaultPrice: 25.50 },
      { displayName: 'Strategy\u00AE Healthy Edge\u00AE', materialNo: '3004621-506', defaultPrice: 25.50 },
    ],
  },
  {
    products: [
      { displayName: 'Ultium\u00AE Gastric Care', materialNo: '3004519-506', defaultPrice: 33.75 },
      { displayName: 'Ultium\u00AE Growth', materialNo: '3005651-506', defaultPrice: 34.50 },
      { displayName: 'Ultium\u00AE Competition', materialNo: '3005650-506', defaultPrice: 34.50 },
      { displayName: 'Ultium\u00AE Senior', materialNo: '300492', defaultPrice: 34.00 },
    ],
  },
  {
    products: [
      { displayName: 'Impact\u00AE Professional Senior', materialNo: '3004514-206', defaultPrice: 24.25 },
      { displayName: 'Impact\u00AE Professional Mare & Foal', materialNo: '3004512-206', defaultPrice: 24.50 },
      { displayName: 'Impact\u00AE Professional Performance', materialNo: '3006066-206', defaultPrice: 26.50 },
      { displayName: 'Impact\u00AE All Stages 12% Textured', materialNo: '3004502-506', defaultPrice: 20.00 },
      { displayName: 'Impact\u00AE All Stages 12% Pelleted', materialNo: '3004501-206', defaultPrice: 20.00 },
      { displayName: 'Impact\u00AE Hay Stretcher', materialNo: '3004507-206', defaultPrice: 17.50 },
    ],
  },
  {
    products: [
      { displayName: 'Omolene\u00AE #200 Performance', materialNo: '3006181-506', defaultPrice: 27.00 },
      { displayName: 'Omolene\u00AE #300 Mare & Foal', materialNo: '3006182-506', defaultPrice: 27.00 },
      { displayName: 'Omolene\u00AE #400 Complete Advantage\u00AE', materialNo: '3006183-506', defaultPrice: 27.00 },
    ],
  },
  {
    products: [
      { displayName: 'WellSolve L/S', materialNo: '66924', defaultPrice: 39.00 },
      { displayName: 'Mini-Horse and Pony', materialNo: '3007261-506', defaultPrice: 27.50 },
    ],
  },
  {
    products: [
      { displayName: 'Country Acres 12%', materialNo: '3009502-206', defaultPrice: 12.00 },
    ],
  },
  {
    products: [
      { displayName: 'Enrich Plus\u00AE Ration Balancing', materialNo: '3002564-206', defaultPrice: 38.00 },
      { displayName: 'Omega Match\u00AE Ration Balancing', materialNo: '3005939-205', defaultPrice: 46.00 },
      { displayName: 'Omega Match\u00AE Ahiflower\u00AE Oil Supplement', materialNo: '3005953-946-EA', defaultPrice: 40.00 },
      { displayName: 'Systemiq\u00AE Probiotic Supplement', materialNo: '3009564-246-EA', defaultPrice: 63.00 },
      { displayName: 'Free Balance 12-12 Support', materialNo: '3002464-103', defaultPrice: 38.50 },
    ],
  },
  {
    products: [
      { displayName: 'RepleniMash\u00AE - 7LB', materialNo: '3006758-146-EA', defaultPrice: 13.50 },
      { displayName: 'RepleniMash\u00AE - 25 LB', materialNo: '3006758-103', defaultPrice: 38.00 },
      { displayName: 'Amplify\u00AE High-Fat Horse Supplement', materialNo: '3004870-706', defaultPrice: 64.00 },
      { displayName: 'Outlast\u00AE Gastric Support Supplement', materialNo: '3004500-205', defaultPrice: 45.50 },
      { displayName: 'SuperSport\u00AE Amino Acid Supplement', materialNo: '3002910-203', defaultPrice: 50.25 },
    ],
  },
  {
    products: [
      { displayName: 'EquiTub\u00AE with ClariFly\u00AE - 55LB', materialNo: '3005401-617', defaultPrice: 75.00 },
      { displayName: 'EquiTub\u00AE with ClariFly\u00AE - 125LB', materialNo: '3005401-627', defaultPrice: 155.00 },
    ],
  },
  {
    products: [
      { displayName: "Mare\u2019s Match\u00AE Foal Milk Replacer", materialNo: 'MARES-MATCH-MLK', defaultPrice: 80.00 },
      { displayName: "Mare\u2019s Match\u00AE Transition Pellets - 25LB", materialNo: 'MARES-MATCH-PLT', defaultPrice: 57.00 },
    ],
  },
  {
    products: [
      { displayName: 'Nicker Makers\u00AE Horse Treats', materialNo: '3003256-746-EA', defaultPrice: 6.50 },
      { displayName: 'Outlast\u00AE Horse Treats', materialNo: '3005457-746-EA', defaultPrice: 8.50 },
    ],
  },
]

/** Flat list of all products in display order */
export const ALL_DISPLAY_PRODUCTS: ProductConfig[] = PRODUCT_GROUPS.flatMap(g => g.products)
