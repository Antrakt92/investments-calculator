const API_BASE = '/api'

export interface UploadResponse {
  success: boolean
  message: string
  transactions_imported: number
  income_events_imported: number
  tax_year: number
}

export interface Holding {
  isin: string
  name: string
  asset_type: string
  quantity: number
  average_cost: number
  total_cost_basis: number
  is_exit_tax_asset: boolean
}

export interface Transaction {
  id: number
  isin: string
  name: string
  transaction_type: string
  transaction_date: string
  quantity: number
  unit_price: number
  gross_amount: number
  fees: number
  net_amount: number
  realized_gain_loss: number | null
}

export interface TaxResult {
  tax_year: number
  cgt: {
    description: string
    gains: number
    losses: number
    net_gain_loss: number
    annual_exemption: number
    exemption_used: number
    taxable_gain: number
    tax_rate: string
    tax_due: number
    losses_to_carry_forward: number
    payment_periods: {
      jan_nov: { gains: number; tax: number; due_date: string }
      december: { gains: number; tax: number; due_date: string }
    }
  }
  exit_tax: {
    description: string
    gains: number
    losses: number
    deemed_disposal_gains: number
    total_taxable: number
    tax_rate: string
    tax_due: number
    note: string
    upcoming_deemed_disposals: Array<{
      isin: string
      name: string
      acquisition_date: string
      deemed_disposal_date: string
      quantity: number
      cost_basis: number
    }>
  }
  dirt: {
    description: string
    interest_income: number
    tax_withheld: number
    tax_rate: string
    tax_due: number
    tax_to_pay: number
    note: string
  }
  dividends: {
    description: string
    total_dividends: number
    withholding_tax_credit: number
    note: string
  }
  summary: {
    total_tax_due: number
    payment_deadlines: Array<{
      description: string
      due_date: string
      amount: number
      tax_type: string
    }>
  }
  form_11_guidance: {
    panel_d: { deposit_interest_gross: number; dirt_deducted: number }
    panel_e: {
      cgt_consideration: number
      cgt_allowable_costs: number
      cgt_net_gain: number
      cgt_exemption: number
      cgt_taxable: number
      exit_tax_gains: number
    }
    panel_f: { foreign_dividends: number; foreign_tax_credit: number }
  }
}

export async function uploadPDF(file: File): Promise<UploadResponse> {
  const formData = new FormData()
  formData.append('file', file)

  const response = await fetch(`${API_BASE}/upload/trade-republic-pdf`, {
    method: 'POST',
    body: formData,
  })

  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || 'Upload failed')
  }

  return response.json()
}

export async function getHoldings(): Promise<Holding[]> {
  const response = await fetch(`${API_BASE}/portfolio/holdings`)
  if (!response.ok) throw new Error('Failed to fetch holdings')
  return response.json()
}

export async function getTransactions(params?: {
  isin?: string
  start_date?: string
  end_date?: string
  transaction_type?: string
  limit?: number
}): Promise<Transaction[]> {
  const searchParams = new URLSearchParams()
  if (params?.isin) searchParams.set('isin', params.isin)
  if (params?.start_date) searchParams.set('start_date', params.start_date)
  if (params?.end_date) searchParams.set('end_date', params.end_date)
  if (params?.transaction_type) searchParams.set('transaction_type', params.transaction_type)
  if (params?.limit) searchParams.set('limit', params.limit.toString())

  const response = await fetch(`${API_BASE}/portfolio/transactions?${searchParams}`)
  if (!response.ok) throw new Error('Failed to fetch transactions')
  return response.json()
}

export async function getPortfolioSummary(): Promise<{
  total_assets: number
  assets_by_type: Record<string, number>
  total_transactions: number
}> {
  const response = await fetch(`${API_BASE}/portfolio/summary`)
  if (!response.ok) throw new Error('Failed to fetch summary')
  return response.json()
}

export async function calculateTax(
  taxYear: number,
  lossesCarriedForward: number = 0
): Promise<TaxResult> {
  const response = await fetch(
    `${API_BASE}/tax/calculate/${taxYear}?losses_carried_forward=${lossesCarriedForward}`
  )
  if (!response.ok) throw new Error('Failed to calculate tax')
  return response.json()
}

export async function getDeemedDisposals(yearsAhead: number = 3): Promise<Array<{
  isin: string
  name: string
  acquisition_date: string
  deemed_disposal_date: string
  quantity: number
  cost_basis: number
  estimated_gain: number | null
  estimated_tax: number | null
}>> {
  const response = await fetch(`${API_BASE}/tax/deemed-disposals?years_ahead=${yearsAhead}`)
  if (!response.ok) throw new Error('Failed to fetch deemed disposals')
  return response.json()
}
