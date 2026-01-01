import { useState, useEffect } from 'react'
import {
  getHoldings,
  getTransactions,
  getIncomeEvents,
  getAssets,
  getPersons,
  createTransaction,
  deleteTransaction,
  updateTransaction,
  exportTransactionsCSV,
  type Holding,
  type Transaction,
  type IncomeEvent,
  type AssetInfo,
  type TransactionCreate,
  type TransactionUpdate,
  type Person
} from '../services/api'

export default function Portfolio() {
  const [holdings, setHoldings] = useState<Holding[]>([])
  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [incomeEvents, setIncomeEvents] = useState<IncomeEvent[]>([])
  const [assets, setAssets] = useState<AssetInfo[]>([])
  const [activeTab, setActiveTab] = useState<'holdings' | 'transactions' | 'income'>('holdings')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [transFilter, setTransFilter] = useState<'all' | 'buy' | 'sell'>('all')
  const [incomeFilter, setIncomeFilter] = useState<'all' | 'interest' | 'dividend'>('all')

  // Family mode state
  const [persons, setPersons] = useState<Person[]>([])
  const [selectedPersonId, setSelectedPersonId] = useState<number | undefined>(undefined)

  // Transaction form state
  const [showForm, setShowForm] = useState(false)
  const [formLoading, setFormLoading] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const [formSuccess, setFormSuccess] = useState<string | null>(null)
  const [editingTransaction, setEditingTransaction] = useState<Transaction | null>(null)
  const [formData, setFormData] = useState<TransactionCreate>({
    isin: '',
    name: '',
    transaction_type: 'buy',
    transaction_date: new Date().toISOString().split('T')[0],
    quantity: 0,
    unit_price: 0,
    fees: 0,
    notes: '',
  })

  useEffect(() => {
    loadPersons()
  }, [])

  useEffect(() => {
    loadData()
  }, [selectedPersonId])

  async function loadPersons() {
    try {
      const data = await getPersons()
      setPersons(data)
      // Default to 'all' (undefined) for combined view
    } catch {
      // Ignore - persons feature may not be set up yet
    }
  }

  const isFamilyMode = persons.length > 1
  const selectedPerson = persons.find(p => p.id === selectedPersonId)

  async function loadData() {
    try {
      setLoading(true)
      const [holdingsData, transactionsData, incomeData, assetsData] = await Promise.all([
        getHoldings(selectedPersonId),
        getTransactions({ limit: 100, person_id: selectedPersonId }),
        getIncomeEvents({ limit: 100, person_id: selectedPersonId }),
        getAssets(),
      ])
      setHoldings(holdingsData)
      setTransactions(transactionsData)
      setIncomeEvents(incomeData)
      setAssets(assetsData)
    } catch (err) {
      setError('Failed to load portfolio data')
    } finally {
      setLoading(false)
    }
  }

  async function handleSubmitTransaction(e: React.FormEvent) {
    e.preventDefault()
    setFormError(null)
    setFormSuccess(null)

    // Validation
    if (!editingTransaction) {
      if (!formData.isin.trim()) {
        setFormError('ISIN is required')
        return
      }
      if (!formData.name.trim()) {
        setFormError('Asset name is required')
        return
      }
    }
    if (formData.quantity <= 0) {
      setFormError('Quantity must be greater than 0')
      return
    }
    if (formData.unit_price <= 0) {
      setFormError('Price must be greater than 0')
      return
    }

    try {
      setFormLoading(true)

      if (editingTransaction) {
        // Update existing transaction
        const updateData: TransactionUpdate = {
          transaction_date: formData.transaction_date,
          quantity: formData.quantity,
          unit_price: formData.unit_price,
          fees: formData.fees,
          notes: formData.notes,
        }
        const result = await updateTransaction(editingTransaction.id, updateData)
        setFormSuccess(result.message)
      } else {
        // Create new transaction (include person_id if in family mode)
        const transactionData: TransactionCreate = {
          ...formData,
          person_id: selectedPersonId,
        }
        const result = await createTransaction(transactionData)
        setFormSuccess(result.message)
      }

      // Reset form
      resetForm()
      // Reload data
      await loadData()
      // Close form after short delay
      setTimeout(() => {
        setShowForm(false)
        setFormSuccess(null)
      }, 1500)
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Failed to save transaction')
    } finally {
      setFormLoading(false)
    }
  }

  function resetForm() {
    setFormData({
      isin: '',
      name: '',
      transaction_type: 'buy',
      transaction_date: new Date().toISOString().split('T')[0],
      quantity: 0,
      unit_price: 0,
      fees: 0,
      notes: '',
    })
    setEditingTransaction(null)
  }

  function handleEditTransaction(trans: Transaction) {
    setEditingTransaction(trans)
    setFormData({
      isin: trans.isin,
      name: trans.name,
      transaction_type: trans.transaction_type as 'buy' | 'sell',
      transaction_date: trans.transaction_date,
      quantity: trans.quantity,
      unit_price: trans.unit_price,
      fees: trans.fees,
      notes: trans.notes || '',
    })
    setShowForm(true)
    setFormError(null)
    setFormSuccess(null)
  }

  async function handleExportCSV() {
    try {
      // Pass selectedPersonId to filter exports in family mode
      const blob = await exportTransactionsCSV(selectedPersonId)
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      // Include person name in filename if filtering
      const personSuffix = selectedPerson ? `_${selectedPerson.name.toLowerCase().replace(/\s+/g, '_')}` : ''
      a.download = `transactions${personSuffix}_${new Date().toISOString().split('T')[0]}.csv`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } catch (err) {
      alert('Failed to export CSV')
    }
  }

  async function handleDeleteTransaction(id: number) {
    if (!confirm('Are you sure you want to delete this transaction?')) {
      return
    }
    try {
      await deleteTransaction(id)
      await loadData()
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to delete transaction')
    }
  }

  function handleAssetSelect(isin: string) {
    const asset = assets.find(a => a.isin === isin)
    if (asset) {
      setFormData(prev => ({
        ...prev,
        isin: asset.isin,
        name: asset.name,
      }))
    }
  }

  const filteredTransactions = transactions.filter(t => {
    if (transFilter === 'all') return true
    return t.transaction_type === transFilter
  })

  const filteredIncome = incomeEvents.filter(e => {
    if (incomeFilter === 'all') return true
    return e.income_type === incomeFilter
  })

  // Calculate income totals
  const interestTotal = incomeEvents
    .filter(e => e.income_type === 'interest')
    .reduce((sum, e) => sum + e.gross_amount, 0)
  const dividendTotal = incomeEvents
    .filter(e => e.income_type === 'dividend' || e.income_type === 'distribution')
    .reduce((sum, e) => sum + e.gross_amount, 0)
  const withholdingTotal = incomeEvents.reduce((sum, e) => sum + e.withholding_tax, 0)

  if (loading) {
    return <div className="card">Loading...</div>
  }

  if (error) {
    return <div className="alert alert-error">{error}</div>
  }

  return (
    <div>
      <h1 style={{ marginBottom: '24px' }}>Portfolio</h1>

      {/* Person Filter - only shown in family mode */}
      {isFamilyMode && (
        <div className="card" style={{ marginBottom: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>
            <span style={{ fontWeight: 500 }}>Viewing:</span>
            <div style={{ display: 'flex', gap: '8px' }}>
              <button
                onClick={() => setSelectedPersonId(undefined)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '8px 16px',
                  borderRadius: '8px',
                  border: selectedPersonId === undefined
                    ? '2px solid var(--primary)'
                    : '2px solid var(--border-color)',
                  background: selectedPersonId === undefined
                    ? 'var(--primary-light)'
                    : 'var(--bg-white)',
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                }}
              >
                <span style={{ fontWeight: selectedPersonId === undefined ? 600 : 400 }}>
                  All
                </span>
              </button>
              {persons.map(person => (
                <button
                  key={person.id}
                  onClick={() => setSelectedPersonId(person.id)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    padding: '8px 16px',
                    borderRadius: '8px',
                    border: selectedPersonId === person.id
                      ? `2px solid ${person.color}`
                      : '2px solid var(--border-color)',
                    background: selectedPersonId === person.id
                      ? `${person.color}15`
                      : 'var(--bg-white)',
                    cursor: 'pointer',
                    transition: 'all 0.2s',
                  }}
                >
                  <div
                    style={{
                      width: '24px',
                      height: '24px',
                      borderRadius: '50%',
                      background: person.color,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: 'white',
                      fontSize: '12px',
                      fontWeight: 600,
                    }}
                  >
                    {person.name.charAt(0).toUpperCase()}
                  </div>
                  <span style={{ fontWeight: selectedPersonId === person.id ? 600 : 400 }}>
                    {person.name}
                  </span>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      <div style={{ marginBottom: '16px' }}>
        <button
          className={`btn ${activeTab === 'holdings' ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setActiveTab('holdings')}
          style={{ marginRight: '8px' }}
        >
          Holdings ({holdings.length})
        </button>
        <button
          className={`btn ${activeTab === 'transactions' ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setActiveTab('transactions')}
          style={{ marginRight: '8px' }}
        >
          Transactions ({transactions.length})
        </button>
        <button
          className={`btn ${activeTab === 'income' ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setActiveTab('income')}
        >
          Income ({incomeEvents.length})
        </button>
      </div>

      {activeTab === 'holdings' && (
        <div className="card">
          {holdings.length === 0 ? (
            <p style={{ textAlign: 'center', padding: '40px', color: 'var(--text-secondary)' }}>
              No holdings found. Upload a Trade Republic tax report to see your portfolio.
            </p>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Asset</th>
                  <th>Type</th>
                  <th>Quantity</th>
                  <th>Avg Cost</th>
                  <th>Cost Basis</th>
                  <th>Tax</th>
                </tr>
              </thead>
              <tbody>
                {holdings.map(holding => (
                  <tr key={holding.isin}>
                    <td>
                      <div style={{ fontWeight: 500 }}>{holding.name}</div>
                      <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                        {holding.isin}
                      </div>
                    </td>
                    <td style={{ textTransform: 'capitalize' }}>
                      {holding.asset_type.replace('_', ' ')}
                    </td>
                    <td>{holding.quantity.toFixed(4)}</td>
                    <td>{formatCurrency(holding.average_cost)}</td>
                    <td>{formatCurrency(holding.total_cost_basis)}</td>
                    <td>
                      <span
                        className="tax-rate-badge"
                        style={{
                          background: holding.is_exit_tax_asset ? 'var(--danger)' : 'var(--primary)',
                        }}
                      >
                        {holding.is_exit_tax_asset ? 'Exit 41%' : 'CGT 33%'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {activeTab === 'transactions' && (
        <div className="card">
          <div style={{ marginBottom: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <button
                className={`btn ${transFilter === 'all' ? 'btn-primary' : 'btn-secondary'}`}
                onClick={() => setTransFilter('all')}
                style={{ marginRight: '8px' }}
              >
                All
              </button>
              <button
                className={`btn ${transFilter === 'buy' ? 'btn-primary' : 'btn-secondary'}`}
                onClick={() => setTransFilter('buy')}
                style={{ marginRight: '8px' }}
              >
                Buys
              </button>
              <button
                className={`btn ${transFilter === 'sell' ? 'btn-primary' : 'btn-secondary'}`}
                onClick={() => setTransFilter('sell')}
              >
                Sells
              </button>
            </div>
            <div>
              {transactions.length > 0 && (
                <button
                  className="btn btn-secondary"
                  onClick={handleExportCSV}
                  style={{ marginRight: '8px' }}
                >
                  Export CSV
                </button>
              )}
              <button
                className="btn btn-primary"
                onClick={() => {
                  if (showForm) {
                    setShowForm(false)
                    resetForm()
                  } else {
                    resetForm()
                    setShowForm(true)
                  }
                }}
              >
                {showForm ? 'Cancel' : '+ Add Transaction'}
              </button>
            </div>
          </div>

          {/* Transaction Form */}
          {showForm && (
            <div style={{
              background: 'var(--bg-secondary)',
              padding: '20px',
              borderRadius: '8px',
              marginBottom: '20px',
              border: '1px solid var(--border-color)'
            }}>
              <h3 style={{ marginTop: 0, marginBottom: '16px' }}>
                {editingTransaction ? `Edit Transaction - ${editingTransaction.name}` : 'Add Transaction'}
              </h3>

              {formError && (
                <div className="alert alert-error" style={{ marginBottom: '16px' }}>
                  {formError}
                </div>
              )}
              {formSuccess && (
                <div className="alert alert-success" style={{ marginBottom: '16px' }}>
                  {formSuccess}
                </div>
              )}

              <form onSubmit={handleSubmitTransaction}>
                {/* Asset Selection - only show when adding new */}
                {!editingTransaction && assets.length > 0 && (
                  <div style={{ marginBottom: '16px' }}>
                    <label style={{ display: 'block', marginBottom: '4px', fontWeight: 500 }}>
                      Select Existing Asset (optional)
                    </label>
                    <select
                      className="form-input"
                      onChange={(e) => handleAssetSelect(e.target.value)}
                      style={{ width: '100%', padding: '8px', borderRadius: '4px' }}
                    >
                      <option value="">-- Or enter new asset below --</option>
                      {assets.map(a => (
                        <option key={a.isin} value={a.isin}>
                          {a.name} ({a.isin})
                        </option>
                      ))}
                    </select>
                  </div>
                )}

                {/* ISIN/Name fields - only show when adding new */}
                {!editingTransaction && (
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '16px' }}>
                    <div>
                      <label style={{ display: 'block', marginBottom: '4px', fontWeight: 500 }}>
                        ISIN *
                      </label>
                      <input
                        type="text"
                        className="form-input"
                        placeholder="e.g. US0378331005"
                        value={formData.isin}
                        onChange={(e) => setFormData(prev => ({ ...prev, isin: e.target.value.toUpperCase() }))}
                        style={{ width: '100%', padding: '8px', borderRadius: '4px' }}
                      />
                    </div>
                    <div>
                      <label style={{ display: 'block', marginBottom: '4px', fontWeight: 500 }}>
                        Asset Name *
                      </label>
                      <input
                        type="text"
                        className="form-input"
                        placeholder="e.g. Apple Inc."
                        value={formData.name}
                        onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                        style={{ width: '100%', padding: '8px', borderRadius: '4px' }}
                      />
                    </div>
                  </div>
                )}

                <div style={{ display: 'grid', gridTemplateColumns: editingTransaction ? 'repeat(4, 1fr)' : 'repeat(5, 1fr)', gap: '16px', marginTop: '16px' }}>
                  {/* Type selector - only show when adding new */}
                  {!editingTransaction && (
                    <div>
                      <label style={{ display: 'block', marginBottom: '4px', fontWeight: 500 }}>
                        Type *
                      </label>
                      <select
                        className="form-input"
                        value={formData.transaction_type}
                        onChange={(e) => setFormData(prev => ({ ...prev, transaction_type: e.target.value as 'buy' | 'sell' }))}
                        style={{ width: '100%', padding: '8px', borderRadius: '4px' }}
                      >
                        <option value="buy">Buy</option>
                        <option value="sell">Sell</option>
                      </select>
                    </div>
                  )}
                  <div>
                    <label style={{ display: 'block', marginBottom: '4px', fontWeight: 500 }}>
                      Date *
                    </label>
                    <input
                      type="date"
                      className="form-input"
                      value={formData.transaction_date}
                      onChange={(e) => setFormData(prev => ({ ...prev, transaction_date: e.target.value }))}
                      style={{ width: '100%', padding: '8px', borderRadius: '4px' }}
                    />
                  </div>
                  <div>
                    <label style={{ display: 'block', marginBottom: '4px', fontWeight: 500 }}>
                      Quantity *
                    </label>
                    <input
                      type="number"
                      step="0.0001"
                      min="0"
                      className="form-input"
                      placeholder="0.0000"
                      value={formData.quantity || ''}
                      onChange={(e) => setFormData(prev => ({ ...prev, quantity: parseFloat(e.target.value) || 0 }))}
                      style={{ width: '100%', padding: '8px', borderRadius: '4px' }}
                    />
                  </div>
                  <div>
                    <label style={{ display: 'block', marginBottom: '4px', fontWeight: 500 }}>
                      Price (EUR) *
                    </label>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      className="form-input"
                      placeholder="0.00"
                      value={formData.unit_price || ''}
                      onChange={(e) => setFormData(prev => ({ ...prev, unit_price: parseFloat(e.target.value) || 0 }))}
                      style={{ width: '100%', padding: '8px', borderRadius: '4px' }}
                    />
                  </div>
                  <div>
                    <label style={{ display: 'block', marginBottom: '4px', fontWeight: 500 }}>
                      Fees (EUR)
                    </label>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      className="form-input"
                      placeholder="0.00"
                      value={formData.fees || ''}
                      onChange={(e) => setFormData(prev => ({ ...prev, fees: parseFloat(e.target.value) || 0 }))}
                      style={{ width: '100%', padding: '8px', borderRadius: '4px' }}
                    />
                  </div>
                </div>

                {/* Notes field */}
                <div style={{ marginTop: '16px' }}>
                  <label style={{ display: 'block', marginBottom: '4px', fontWeight: 500 }}>
                    Notes (optional)
                  </label>
                  <textarea
                    className="form-input"
                    placeholder="Add any notes about this transaction..."
                    value={formData.notes || ''}
                    onChange={(e) => setFormData(prev => ({ ...prev, notes: e.target.value }))}
                    style={{
                      width: '100%',
                      padding: '8px',
                      borderRadius: '4px',
                      minHeight: '60px',
                      resize: 'vertical'
                    }}
                  />
                </div>

                {/* Preview */}
                {formData.quantity > 0 && formData.unit_price > 0 && (
                  <div style={{
                    marginTop: '16px',
                    padding: '12px',
                    background: 'var(--bg-primary)',
                    borderRadius: '4px',
                    fontSize: '14px'
                  }}>
                    <strong>Total Amount:</strong> {formatCurrency(formData.quantity * formData.unit_price)}
                    {(formData.fees || 0) > 0 && (
                      <span style={{ marginLeft: '16px' }}>
                        <strong>Net:</strong> {formatCurrency(
                          formData.transaction_type === 'buy'
                            ? formData.quantity * formData.unit_price + (formData.fees || 0)
                            : formData.quantity * formData.unit_price - (formData.fees || 0)
                        )}
                      </span>
                    )}
                  </div>
                )}

                <div style={{ marginTop: '16px' }}>
                  <button
                    type="submit"
                    className="btn btn-primary"
                    disabled={formLoading}
                    style={{ marginRight: '8px' }}
                  >
                    {formLoading ? 'Saving...' : editingTransaction ? 'Update Transaction' : 'Add Transaction'}
                  </button>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => {
                      setShowForm(false)
                      resetForm()
                      setFormError(null)
                      setFormSuccess(null)
                    }}
                  >
                    Cancel
                  </button>
                </div>
              </form>
            </div>
          )}

          {filteredTransactions.length === 0 ? (
            <p style={{ textAlign: 'center', padding: '40px', color: 'var(--text-secondary)' }}>
              No transactions found.
            </p>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Asset</th>
                  <th>Type</th>
                  <th>Quantity</th>
                  <th>Price</th>
                  <th>Amount</th>
                  <th>Gain/Loss</th>
                  <th style={{ width: '120px' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredTransactions.map(trans => (
                  <tr key={trans.id}>
                    <td>{formatDate(trans.transaction_date)}</td>
                    <td>
                      <div style={{ fontWeight: 500 }}>{trans.name}</div>
                      <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                        {trans.isin}
                      </div>
                      {trans.notes && (
                        <div style={{
                          fontSize: '11px',
                          color: 'var(--primary)',
                          fontStyle: 'italic',
                          marginTop: '2px'
                        }}>
                          {trans.notes.length > 50 ? trans.notes.substring(0, 50) + '...' : trans.notes}
                        </div>
                      )}
                    </td>
                    <td>
                      <span
                        style={{
                          color: trans.transaction_type === 'buy' ? 'var(--success)' : 'var(--danger)',
                          fontWeight: 500,
                          textTransform: 'uppercase',
                        }}
                      >
                        {trans.transaction_type}
                      </span>
                    </td>
                    <td>{trans.quantity.toFixed(4)}</td>
                    <td>{formatCurrency(trans.unit_price)}</td>
                    <td>{formatCurrency(trans.gross_amount)}</td>
                    <td>
                      {trans.realized_gain_loss !== null && (
                        <span
                          style={{
                            color: trans.realized_gain_loss >= 0 ? 'var(--success)' : 'var(--danger)',
                            fontWeight: 500,
                          }}
                        >
                          {trans.realized_gain_loss >= 0 ? '+' : ''}
                          {formatCurrency(trans.realized_gain_loss)}
                        </span>
                      )}
                    </td>
                    <td>
                      <button
                        className="btn btn-secondary"
                        style={{
                          padding: '4px 8px',
                          fontSize: '12px',
                          marginRight: '4px',
                        }}
                        onClick={() => handleEditTransaction(trans)}
                        title="Edit transaction"
                      >
                        Edit
                      </button>
                      <button
                        className="btn btn-secondary"
                        style={{
                          padding: '4px 8px',
                          fontSize: '12px',
                          color: 'var(--danger)',
                        }}
                        onClick={() => handleDeleteTransaction(trans.id)}
                        title="Delete transaction"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {activeTab === 'income' && (
        <div>
          {/* Income Summary */}
          <div className="stat-grid" style={{ marginBottom: '16px' }}>
            <div className="stat-card">
              <div className="stat-label">Interest (DIRT 33%)</div>
              <div className="stat-value">{formatCurrency(interestTotal)}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Dividends (Marginal Rate)</div>
              <div className="stat-value">{formatCurrency(dividendTotal)}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Withholding Tax Paid</div>
              <div className="stat-value">{formatCurrency(withholdingTotal)}</div>
            </div>
          </div>

          <div className="card">
            <div style={{ marginBottom: '16px' }}>
              <button
                className={`btn ${incomeFilter === 'all' ? 'btn-primary' : 'btn-secondary'}`}
                onClick={() => setIncomeFilter('all')}
                style={{ marginRight: '8px' }}
              >
                All
              </button>
              <button
                className={`btn ${incomeFilter === 'interest' ? 'btn-primary' : 'btn-secondary'}`}
                onClick={() => setIncomeFilter('interest')}
                style={{ marginRight: '8px' }}
              >
                Interest
              </button>
              <button
                className={`btn ${incomeFilter === 'dividend' ? 'btn-primary' : 'btn-secondary'}`}
                onClick={() => setIncomeFilter('dividend')}
              >
                Dividends
              </button>
            </div>

            {filteredIncome.length === 0 ? (
              <p style={{ textAlign: 'center', padding: '40px', color: 'var(--text-secondary)' }}>
                No income events found.
              </p>
            ) : (
              <table className="table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Type</th>
                    <th>Source</th>
                    <th>Gross Amount</th>
                    <th>Withholding Tax</th>
                    <th>Net Amount</th>
                    <th>Tax Treatment</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredIncome.map(event => (
                    <tr key={event.id}>
                      <td>{formatDate(event.payment_date)}</td>
                      <td style={{ textTransform: 'capitalize' }}>{event.income_type}</td>
                      <td>
                        {event.asset_name ? (
                          <div>
                            <div style={{ fontWeight: 500 }}>{event.asset_name}</div>
                            <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                              {event.asset_isin}
                            </div>
                          </div>
                        ) : (
                          <span>{event.source_country || 'Trade Republic'}</span>
                        )}
                      </td>
                      <td>{formatCurrency(event.gross_amount)}</td>
                      <td style={{ color: event.withholding_tax > 0 ? 'var(--danger)' : 'inherit' }}>
                        {event.withholding_tax > 0 ? `-${formatCurrency(event.withholding_tax)}` : '€0.00'}
                      </td>
                      <td style={{ fontWeight: 500 }}>{formatCurrency(event.net_amount)}</td>
                      <td>
                        <span
                          className="tax-rate-badge"
                          style={{
                            background: event.income_type === 'interest' ? 'var(--primary)' : 'var(--warning)',
                          }}
                        >
                          {event.tax_treatment}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-IE', {
    style: 'currency',
    currency: 'EUR',
  }).format(amount)
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('en-IE')
}
