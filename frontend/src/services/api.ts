const API_BASE = '/api'

export interface ValidationWarning {
  type: string
  severity: 'info' | 'warning' | 'error'
  message: string
  line: string | null
  details: Record<string, unknown> | null
}

export interface UploadResponse {
  success: boolean
  message: string
  transactions_imported: number
  income_events_imported: number
  skipped_duplicates: number
  tax_year: number
  period: {
    start: string
    end: string
  }
  summary: {
    buys: { count: number; total: number }
    sells: { count: number; total: number }
    interest: { count: number; total: number }
    dividends: { count: number; total: number }
  }
  validation?: {
    skipped_no_isin: number
    skipped_invalid_format: number
    parsing_errors: number
    warning_count: number
    warning_summary: Record<string, number>
    warnings: ValidationWarning[]
  }
}

export async function clearAllData(): Promise<{
  success: boolean
  message: string
  deleted: {
    transactions: number
    income_events: number
    assets: number
  }
}> {
  const response = await fetch(`${API_BASE}/upload/clear-data`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || 'Failed to clear data')
  }
  return response.json()
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
  notes: string | null
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

export async function uploadPDF(file: File, personId?: number): Promise<UploadResponse> {
  const formData = new FormData()
  formData.append('file', file)

  // Add person_id as query parameter if provided
  const url = personId
    ? `${API_BASE}/upload/trade-republic-pdf?person_id=${personId}`
    : `${API_BASE}/upload/trade-republic-pdf`

  const response = await fetch(url, {
    method: 'POST',
    body: formData,
  })

  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || 'Upload failed')
  }

  return response.json()
}

export async function getHoldings(personId?: number): Promise<Holding[]> {
  const params = new URLSearchParams()
  if (personId !== undefined) params.set('person_id', personId.toString())
  const url = params.toString()
    ? `${API_BASE}/portfolio/holdings?${params}`
    : `${API_BASE}/portfolio/holdings`
  const response = await fetch(url)
  if (!response.ok) throw new Error('Failed to fetch holdings')
  return response.json()
}

export async function getTransactions(params?: {
  isin?: string
  start_date?: string
  end_date?: string
  transaction_type?: string
  person_id?: number
  limit?: number
}): Promise<Transaction[]> {
  const searchParams = new URLSearchParams()
  if (params?.isin) searchParams.set('isin', params.isin)
  if (params?.start_date) searchParams.set('start_date', params.start_date)
  if (params?.end_date) searchParams.set('end_date', params.end_date)
  if (params?.transaction_type) searchParams.set('transaction_type', params.transaction_type)
  if (params?.person_id !== undefined) searchParams.set('person_id', params.person_id.toString())
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
  lossesCarriedForward: number = 0,
  personId?: number
): Promise<TaxResult> {
  const params = new URLSearchParams()
  params.set('losses_carried_forward', lossesCarriedForward.toString())
  if (personId !== undefined) params.set('person_id', personId.toString())
  const response = await fetch(
    `${API_BASE}/tax/calculate/${taxYear}?${params}`
  )
  if (!response.ok) throw new Error('Failed to calculate tax')
  return response.json()
}

export async function getDeemedDisposals(yearsAhead: number = 3, personId?: number): Promise<Array<{
  isin: string
  name: string
  acquisition_date: string
  deemed_disposal_date: string
  quantity: number
  cost_basis: number
  estimated_gain: number | null
  estimated_tax: number | null
}>> {
  const params = new URLSearchParams()
  params.set('years_ahead', yearsAhead.toString())
  if (personId !== undefined) params.set('person_id', personId.toString())
  const response = await fetch(`${API_BASE}/tax/deemed-disposals?${params}`)
  if (!response.ok) throw new Error('Failed to fetch deemed disposals')
  return response.json()
}

export interface IncomeEvent {
  id: number
  income_type: string
  payment_date: string
  gross_amount: number
  withholding_tax: number
  net_amount: number
  source_country: string | null
  asset_name: string | null
  asset_isin: string | null
  tax_treatment: string
}

export async function getIncomeEvents(params?: {
  income_type?: string
  start_date?: string
  end_date?: string
  person_id?: number
  limit?: number
}): Promise<IncomeEvent[]> {
  const searchParams = new URLSearchParams()
  if (params?.income_type) searchParams.set('income_type', params.income_type)
  if (params?.start_date) searchParams.set('start_date', params.start_date)
  if (params?.end_date) searchParams.set('end_date', params.end_date)
  if (params?.person_id !== undefined) searchParams.set('person_id', params.person_id.toString())
  if (params?.limit) searchParams.set('limit', params.limit.toString())

  const response = await fetch(`${API_BASE}/portfolio/income?${searchParams}`)
  if (!response.ok) throw new Error('Failed to fetch income events')
  return response.json()
}

// Transaction CRUD

export interface TransactionCreate {
  isin: string
  name: string
  transaction_type: 'buy' | 'sell'
  transaction_date: string
  quantity: number
  unit_price: number
  fees?: number
  notes?: string
  person_id?: number  // For family mode
}

export interface AssetInfo {
  isin: string
  name: string
  asset_type: string
}

export async function createTransaction(data: TransactionCreate): Promise<{
  success: boolean
  message: string
  transaction: Transaction
}> {
  const response = await fetch(`${API_BASE}/portfolio/transactions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || 'Failed to create transaction')
  }
  return response.json()
}

export async function deleteTransaction(id: number): Promise<{ success: boolean; message: string }> {
  const response = await fetch(`${API_BASE}/portfolio/transactions/${id}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || 'Failed to delete transaction')
  }
  return response.json()
}

export async function getAssets(): Promise<AssetInfo[]> {
  const response = await fetch(`${API_BASE}/portfolio/assets`)
  if (!response.ok) throw new Error('Failed to fetch assets')
  return response.json()
}

export interface TransactionUpdate {
  transaction_date?: string
  quantity?: number
  unit_price?: number
  fees?: number
  notes?: string
}

export async function updateTransaction(
  id: number,
  data: TransactionUpdate
): Promise<{ success: boolean; message: string; transaction: Transaction }> {
  const response = await fetch(`${API_BASE}/portfolio/transactions/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || 'Failed to update transaction')
  }
  return response.json()
}

export async function exportTransactionsCSV(personId?: number): Promise<Blob> {
  const params = new URLSearchParams()
  if (personId !== undefined) params.set('person_id', personId.toString())
  const url = params.toString()
    ? `${API_BASE}/portfolio/transactions/export/csv?${params}`
    : `${API_BASE}/portfolio/transactions/export/csv`
  const response = await fetch(url)
  if (!response.ok) throw new Error('Failed to export transactions')
  return response.blob()
}

export interface LossesCarryForward {
  from_year: number
  losses_to_carry_forward: number
  total_gains: number
  total_losses: number
  net_gain_loss: number
}

export async function getLossesCarryForward(fromYear: number, personId?: number): Promise<LossesCarryForward> {
  const params = personId !== undefined ? `?person_id=${personId}` : ''
  const response = await fetch(`${API_BASE}/tax/losses-to-carry-forward/${fromYear}${params}`)
  if (!response.ok) throw new Error('Failed to fetch losses')
  return response.json()
}

// ===== Person Management (Family Tax Returns) =====

export interface Person {
  id: number
  name: string
  is_primary: boolean
  pps_number: string | null
  color: string
}

export interface PersonCreate {
  name: string
  is_primary?: boolean
  pps_number?: string
  color?: string
}

export interface PersonUpdate {
  name?: string
  pps_number?: string
  color?: string
}

export async function getPersons(): Promise<Person[]> {
  const response = await fetch(`${API_BASE}/persons/`)
  if (!response.ok) throw new Error('Failed to fetch persons')
  return response.json()
}

export async function getPerson(id: number): Promise<Person> {
  const response = await fetch(`${API_BASE}/persons/${id}`)
  if (!response.ok) throw new Error('Failed to fetch person')
  return response.json()
}

export async function createPerson(data: PersonCreate): Promise<Person> {
  const response = await fetch(`${API_BASE}/persons/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || 'Failed to create person')
  }
  return response.json()
}

export async function updatePerson(id: number, data: PersonUpdate): Promise<Person> {
  const response = await fetch(`${API_BASE}/persons/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || 'Failed to update person')
  }
  return response.json()
}

export async function deletePerson(id: number): Promise<{ message: string }> {
  const response = await fetch(`${API_BASE}/persons/${id}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || 'Failed to delete person')
  }
  return response.json()
}

export async function setPrimaryPerson(id: number): Promise<Person> {
  const response = await fetch(`${API_BASE}/persons/${id}/set-primary`, {
    method: 'POST',
  })
  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || 'Failed to set primary person')
  }
  return response.json()
}

export async function getOrCreatePrimaryPerson(): Promise<Person> {
  const response = await fetch(`${API_BASE}/persons/primary/default`)
  if (!response.ok) throw new Error('Failed to get primary person')
  return response.json()
}
