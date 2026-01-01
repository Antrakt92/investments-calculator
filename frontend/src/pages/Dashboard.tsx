import { useState, useEffect } from 'react'
import { getPortfolioSummary, getHoldings, getIncomeEvents, calculateTax, getDeemedDisposals, getPersons, getRecentSales, type Holding, type TaxResult, type IncomeEvent, type Person, type RecentSale } from '../services/api'
import { HelpIcon, TAX_TERMS } from '../components/Tooltip'

export default function Dashboard() {
  const [summary, setSummary] = useState<{
    total_assets: number
    assets_by_type: Record<string, number>
    total_transactions: number
  } | null>(null)
  const [holdings, setHoldings] = useState<Holding[]>([])
  const [recentSales, setRecentSales] = useState<RecentSale[]>([])
  const [incomeEvents, setIncomeEvents] = useState<IncomeEvent[]>([])
  const [taxResult, setTaxResult] = useState<TaxResult | null>(null)
  const [deemedDisposals, setDeemedDisposals] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Family mode state
  const [persons, setPersons] = useState<Person[]>([])
  const [selectedPersonId, setSelectedPersonId] = useState<number | undefined>(undefined)

  // Default to 2024 (most recent complete tax year)
  const taxYear = 2024

  // Load persons on mount
  useEffect(() => {
    async function loadPersons() {
      try {
        const data = await getPersons()
        setPersons(data)
      } catch {
        // Ignore - persons feature may not be set up yet
      }
    }
    loadPersons()
  }, [])

  const isFamilyMode = persons.length > 1
  const selectedPerson = persons.find(p => p.id === selectedPersonId)

  // Reload data when person selection changes
  useEffect(() => {
    loadData()
  }, [selectedPersonId])

  async function loadData() {
    try {
      setLoading(true)
      const [summaryData, holdingsData, incomeData, disposals, salesData] = await Promise.all([
        getPortfolioSummary(),
        getHoldings(selectedPersonId),
        getIncomeEvents({ limit: 100, person_id: selectedPersonId }),
        getDeemedDisposals(2, selectedPersonId), // Get disposals within next 2 years
        getRecentSales(28, selectedPersonId).catch(() => []), // Get sales in last 4 weeks
      ])
      setSummary(summaryData)
      setHoldings(holdingsData)
      setIncomeEvents(incomeData)
      setDeemedDisposals(disposals)
      setRecentSales(salesData)

      // Calculate tax for 2024
      try {
        const tax = await calculateTax(taxYear, 0, selectedPersonId)
        setTaxResult(tax)
      } catch {
        // No data for tax calculation yet
      }
    } catch (err) {
      setError('Failed to load data. Make sure the backend is running.')
    } finally {
      setLoading(false)
    }
  }

  const totalCostBasis = holdings.reduce((sum, h) => sum + h.total_cost_basis, 0)
  const totalInterest = incomeEvents
    .filter(e => e.income_type === 'interest')
    .reduce((sum, e) => sum + e.gross_amount, 0)
  const totalDividends = incomeEvents
    .filter(e => e.income_type !== 'interest')
    .reduce((sum, e) => sum + e.gross_amount, 0)

  if (loading) {
    return (
      <div>
        <h1 style={{ marginBottom: '24px' }}>Dashboard - Tax Year {taxYear}</h1>
        <div className="stat-grid">
          {[1, 2, 3, 4].map(i => (
            <div key={i} className="stat-card" style={{ opacity: 0.6 }}>
              <div style={{ width: '60%', height: '14px', background: 'var(--bg-secondary)', borderRadius: '4px' }}></div>
              <div style={{ width: '80%', height: '32px', background: 'var(--bg-secondary)', borderRadius: '4px', marginTop: '12px' }}></div>
              <div style={{ width: '90%', height: '12px', background: 'var(--bg-secondary)', borderRadius: '4px', marginTop: '8px' }}></div>
            </div>
          ))}
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px', marginTop: '24px' }}>
          <div className="card" style={{ opacity: 0.6 }}>
            <div style={{ width: '50%', height: '20px', background: 'var(--bg-secondary)', borderRadius: '4px', marginBottom: '16px' }}></div>
            <div style={{ width: '100%', height: '100px', background: 'var(--bg-secondary)', borderRadius: '4px' }}></div>
          </div>
          <div className="card" style={{ opacity: 0.6 }}>
            <div style={{ width: '50%', height: '20px', background: 'var(--bg-secondary)', borderRadius: '4px', marginBottom: '16px' }}></div>
            <div style={{ width: '100%', height: '100px', background: 'var(--bg-secondary)', borderRadius: '4px' }}></div>
          </div>
        </div>
        <div style={{ textAlign: 'center', padding: '20px', color: 'var(--text-secondary)' }}>
          Loading dashboard data...
        </div>
      </div>
    )
  }

  if (error) {
    return <div className="alert alert-error">{error}</div>
  }

  const hasData = holdings.length > 0 || incomeEvents.length > 0

  return (
    <div>
      <h1 style={{ marginBottom: '24px' }}>
        Dashboard - Tax Year {taxYear}
        {isFamilyMode && selectedPerson && (
          <span style={{
            fontSize: '18px',
            fontWeight: 400,
            color: selectedPerson.color,
            marginLeft: '12px',
          }}>
            ({selectedPerson.name})
          </span>
        )}
      </h1>

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
                  Combined
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
            {selectedPersonId === undefined && (
              <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                Showing combined data for all persons
              </span>
            )}
          </div>
        </div>
      )}

      {/* Family Mode Setup Hint - show when no family mode yet */}
      {!isFamilyMode && hasData && (
        <div className="card" style={{
          marginBottom: '24px',
          background: 'linear-gradient(135deg, rgba(59, 130, 246, 0.05) 0%, rgba(139, 92, 246, 0.05) 100%)',
          border: '1px dashed var(--primary)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
            <div>
              <h3 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '8px', fontSize: '16px' }}>
                <span>👨‍👩‍👧</span> {persons.length === 0 ? 'Set Up Your Profile' : 'Add Spouse/Partner'}
              </h3>
              <p style={{ margin: '8px 0 0', color: 'var(--text-secondary)', fontSize: '14px' }}>
                {persons.length === 0
                  ? 'Create your profile to enable Family Mode. Each family member gets their own €1,270 CGT exemption.'
                  : 'Add your spouse or partner to track investments separately and file joint Form 11.'}
              </p>
            </div>
            <a href="/settings" className="btn btn-secondary" style={{ whiteSpace: 'nowrap' }}>
              {persons.length === 0 ? 'Set Up Profile' : 'Add Person'}
            </a>
          </div>
        </div>
      )}

      {!hasData ? (
        <div className="card" style={{ textAlign: 'center', padding: '60px' }}>
          <div style={{ fontSize: '64px', marginBottom: '16px' }}>PDF</div>
          <h2>No Data Yet</h2>
          <p style={{ color: 'var(--text-secondary)', marginTop: '8px', marginBottom: '24px' }}>
            Upload a Trade Republic tax report to get started with your Irish tax calculation.
          </p>
          <a href="/upload" className="btn btn-primary" style={{ fontSize: '18px', padding: '12px 32px' }}>
            Upload Tax Report
          </a>
        </div>
      ) : (
        <>
          {/* Tax Summary Cards */}
          <div className="stat-grid">
            <div className="stat-card" style={{ borderLeft: '4px solid var(--primary)' }}>
              <div className="stat-label">
                CGT Due (Stocks)
                <HelpIcon text={TAX_TERMS.CGT} />
              </div>
              <div className="stat-value">{formatCurrency(taxResult?.cgt.tax_due || 0)}</div>
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                33% on gains above €1,270
              </div>
            </div>
            <div className="stat-card" style={{ borderLeft: '4px solid var(--danger)' }}>
              <div className="stat-label">
                Exit Tax Due (EU Funds)
                <HelpIcon text={TAX_TERMS.EXIT_TAX} />
              </div>
              <div className="stat-value">{formatCurrency(taxResult?.exit_tax.tax_due || 0)}</div>
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                41% on gains (no exemption)
              </div>
            </div>
            <div className="stat-card" style={{ borderLeft: '4px solid var(--warning)' }}>
              <div className="stat-label">
                DIRT Due (Interest)
                <HelpIcon text={TAX_TERMS.DIRT} />
              </div>
              <div className="stat-value">{formatCurrency(taxResult?.dirt.tax_to_pay || 0)}</div>
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                33% on €{totalInterest.toFixed(2)} interest
              </div>
            </div>
            <div className="stat-card" style={{ borderLeft: '4px solid var(--danger)', background: 'var(--bg-secondary)' }}>
              <div className="stat-label">TOTAL TAX DUE</div>
              <div className="stat-value negative" style={{ fontSize: '32px' }}>
                {formatCurrency(taxResult?.summary.total_tax_due || 0)}
              </div>
            </div>
          </div>

          {/* Portfolio & Income Summary */}
          <div className="grid-2-cols" style={{ marginTop: '24px' }}>
            <div className="card">
              <h2 className="card-title">Portfolio Summary</h2>
              <table className="table">
                <tbody>
                  <tr>
                    <td>Holdings</td>
                    <td style={{ textAlign: 'right', fontWeight: 500 }}>{holdings.length} assets</td>
                  </tr>
                  <tr>
                    <td>Total Cost Basis</td>
                    <td style={{ textAlign: 'right', fontWeight: 500 }}>{formatCurrency(totalCostBasis)}</td>
                  </tr>
                  <tr>
                    <td>Transactions</td>
                    <td style={{ textAlign: 'right', fontWeight: 500 }}>{summary?.total_transactions || 0}</td>
                  </tr>
                </tbody>
              </table>
              <a href="/portfolio" className="btn btn-secondary" style={{ marginTop: '16px', width: '100%' }}>
                View Portfolio
              </a>
            </div>

            <div className="card">
              <h2 className="card-title">Income Summary</h2>
              <table className="table">
                <tbody>
                  <tr>
                    <td>Interest Income</td>
                    <td style={{ textAlign: 'right', fontWeight: 500 }}>{formatCurrency(totalInterest)}</td>
                  </tr>
                  <tr>
                    <td>Dividend Income</td>
                    <td style={{ textAlign: 'right', fontWeight: 500 }}>{formatCurrency(totalDividends)}</td>
                  </tr>
                  <tr>
                    <td>Total Income</td>
                    <td style={{ textAlign: 'right', fontWeight: 600 }}>{formatCurrency(totalInterest + totalDividends)}</td>
                  </tr>
                </tbody>
              </table>
              <a href="/portfolio" className="btn btn-secondary" style={{ marginTop: '16px', width: '100%' }}>
                View Income Details
              </a>
            </div>
          </div>

          {/* Payment Deadlines with Urgency */}
          {taxResult && taxResult.summary.payment_deadlines.some(d => d.amount > 0) && (
            <div className="card" style={{ marginTop: '24px' }}>
              <h2 className="card-title">Upcoming Payment Deadlines</h2>
              {taxResult.summary.payment_deadlines
                .filter(d => d.amount > 0)
                .sort((a, b) => new Date(a.due_date).getTime() - new Date(b.due_date).getTime())
                .map((deadline, i) => {
                  const daysUntil = getDaysUntil(deadline.due_date)
                  const isOverdue = daysUntil < 0
                  const isUrgent = daysUntil >= 0 && daysUntil <= 30
                  const isWarning = daysUntil > 30 && daysUntil <= 90

                  return (
                    <div
                      key={i}
                      className="deadline-item"
                      style={{
                        background: isOverdue ? 'rgba(239, 68, 68, 0.1)' :
                                   isUrgent ? 'rgba(251, 191, 36, 0.1)' :
                                   isWarning ? 'rgba(251, 191, 36, 0.05)' : 'var(--bg-secondary)',
                        borderLeft: isOverdue ? '4px solid var(--error)' :
                                   isUrgent ? '4px solid var(--warning)' : 'none',
                        borderRadius: '8px',
                        padding: '12px 16px',
                        marginBottom: '8px'
                      }}
                    >
                      <div>
                        <div className="deadline-date" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          {formatDate(deadline.due_date)}
                          <span style={{
                            fontSize: '12px',
                            padding: '2px 8px',
                            borderRadius: '12px',
                            fontWeight: 600,
                            background: isOverdue ? 'var(--error)' :
                                       isUrgent ? 'var(--warning)' :
                                       isWarning ? 'rgba(251, 191, 36, 0.3)' : 'var(--bg-secondary)',
                            color: isOverdue || isUrgent ? 'white' : 'var(--text-secondary)'
                          }}>
                            {isOverdue ? 'OVERDUE!' : formatTimeRemaining(daysUntil)}
                          </span>
                        </div>
                        <div style={{ color: 'var(--text-secondary)', fontSize: '14px' }}>
                          {deadline.description}
                        </div>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                        <span className="tax-rate-badge">{deadline.tax_type}</span>
                        <span className="deadline-amount" style={{
                          color: isOverdue ? 'var(--error)' : undefined
                        }}>{formatCurrency(deadline.amount)}</span>
                      </div>
                    </div>
                  )
                })}
            </div>
          )}

          {/* Deemed Disposal Warning */}
          {deemedDisposals.length > 0 && (
            <div className="card" style={{ marginTop: '24px', borderLeft: '4px solid var(--warning)' }}>
              <h2 className="card-title">
                <span style={{ marginRight: '8px' }}>⏰</span>
                Upcoming Deemed Disposals (8-Year Rule)
                <HelpIcon text={TAX_TERMS.DEEMED_DISPOSAL} />
              </h2>
              <p style={{ color: 'var(--text-secondary)', marginBottom: '16px', fontSize: '14px' }}>
                EU funds held for 8 years trigger Exit Tax (41%) even without selling.
              </p>
              {deemedDisposals.slice(0, 3).map((d, i) => {
                const daysUntil = getDaysUntil(d.deemed_disposal_date)
                const isCritical = daysUntil <= 30
                const isUrgent = daysUntil > 30 && daysUntil <= 90
                const isWarning = daysUntil > 90 && daysUntil <= 365
                return (
                  <div key={i} style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    padding: '12px',
                    background: isCritical ? 'rgba(239, 68, 68, 0.1)' :
                               isUrgent ? 'rgba(251, 191, 36, 0.15)' :
                               isWarning ? 'rgba(251, 191, 36, 0.05)' : 'var(--bg-secondary)',
                    borderLeft: isCritical ? '4px solid var(--error)' :
                               isUrgent ? '4px solid var(--warning)' : 'none',
                    borderRadius: '6px',
                    marginBottom: i < deemedDisposals.length - 1 ? '8px' : 0
                  }}>
                    <div>
                      <div style={{ fontWeight: 500 }}>{d.name}</div>
                      <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                        {d.isin} · {d.quantity.toFixed(4)} units
                      </div>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <div style={{
                        fontWeight: 600,
                        display: 'inline-block',
                        padding: '2px 8px',
                        borderRadius: '12px',
                        fontSize: '13px',
                        background: isCritical ? 'var(--error)' :
                                   isUrgent ? 'var(--warning)' :
                                   isWarning ? 'rgba(251, 191, 36, 0.3)' : 'var(--bg-secondary)',
                        color: isCritical || isUrgent ? 'white' : 'var(--text-primary)'
                      }}>
                        {formatTimeRemaining(daysUntil)}
                      </div>
                      <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                        {formatDate(d.deemed_disposal_date)}
                      </div>
                    </div>
                  </div>
                )
              })}
              {deemedDisposals.length > 3 && (
                <div style={{ marginTop: '12px', textAlign: 'center' }}>
                  <a href="/tax" style={{ color: 'var(--primary)', fontSize: '14px' }}>
                    View all {deemedDisposals.length} upcoming disposals →
                  </a>
                </div>
              )}
            </div>
          )}

          {/* Bed & Breakfast Rule Warning */}
          {recentSales.filter(s => s.bed_breakfast_applies && s.sales.some(sale => sale.days_remaining > 0)).length > 0 && (
            <div className="card" style={{ marginTop: '24px', borderLeft: '4px solid var(--error)' }}>
              <h2 className="card-title">
                <span style={{ marginRight: '8px' }}>⚠️</span>
                Bed & Breakfast Rule Active
                <HelpIcon text={TAX_TERMS.BED_BREAKFAST} />
              </h2>
              <p style={{ color: 'var(--text-secondary)', marginBottom: '16px', fontSize: '14px' }}>
                You recently sold assets subject to CGT. Buying them back within 4 weeks triggers the
                bed & breakfast rule, which may reduce or eliminate loss relief.
              </p>
              {recentSales
                .filter(s => s.bed_breakfast_applies && s.sales.some(sale => sale.days_remaining > 0))
                .map((asset, i) => {
                  const activeSale = asset.sales.find(s => s.days_remaining > 0)
                  if (!activeSale) return null
                  return (
                    <div key={i} style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      padding: '12px',
                      background: activeSale.days_remaining <= 7 ? 'rgba(239, 68, 68, 0.1)' :
                                 activeSale.days_remaining <= 14 ? 'rgba(251, 191, 36, 0.1)' : 'var(--bg-secondary)',
                      borderLeft: activeSale.days_remaining <= 7 ? '4px solid var(--error)' :
                                 activeSale.days_remaining <= 14 ? '4px solid var(--warning)' : 'none',
                      borderRadius: '6px',
                      marginBottom: i < recentSales.length - 1 ? '8px' : 0
                    }}>
                      <div>
                        <div style={{ fontWeight: 500 }}>{asset.name}</div>
                        <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                          {asset.isin} · Sold on {new Date(activeSale.date).toLocaleDateString('en-IE', { day: 'numeric', month: 'short', year: 'numeric' })}
                        </div>
                      </div>
                      <div style={{ textAlign: 'right' }}>
                        <div style={{
                          fontWeight: 600,
                          display: 'inline-block',
                          padding: '2px 8px',
                          borderRadius: '12px',
                          fontSize: '13px',
                          background: activeSale.days_remaining <= 7 ? 'var(--error)' :
                                     activeSale.days_remaining <= 14 ? 'var(--warning)' : 'rgba(251, 191, 36, 0.3)',
                          color: activeSale.days_remaining <= 14 ? 'white' : 'var(--text-primary)'
                        }}>
                          {activeSale.days_remaining} days left
                        </div>
                        <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                          Safe to buy: {new Date(activeSale.safe_to_buy_date).toLocaleDateString('en-IE', { day: 'numeric', month: 'short' })}
                        </div>
                      </div>
                    </div>
                  )
                })}
            </div>
          )}

          {/* Assets by Tax Type */}
          {summary && Object.keys(summary.assets_by_type).length > 0 && (
            <div className="card" style={{ marginTop: '24px' }}>
              <h2 className="card-title">Assets by Tax Category</h2>
              <table className="table">
                <thead>
                  <tr>
                    <th>Asset Type</th>
                    <th>Count</th>
                    <th>Tax Treatment</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(summary.assets_by_type).map(([type, count]) => (
                    <tr key={type}>
                      <td style={{ textTransform: 'capitalize' }}>{type.replace('_', ' ')}</td>
                      <td>{count}</td>
                      <td>
                        <span
                          className="tax-rate-badge"
                          style={{
                            background: type === 'etf_eu' ? 'var(--danger)' :
                                       type === 'cash' ? 'var(--warning)' : 'var(--primary)'
                          }}
                        >
                          {getTaxTreatment(type)}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Quick Actions */}
          <div className="card" style={{ marginTop: '24px' }}>
            <h2 className="card-title">Quick Actions</h2>
            <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
              <a href="/tax" className="btn btn-primary">
                View Full Tax Report
              </a>
              <a href="/upload" className="btn btn-secondary">
                Upload Another Report
              </a>
            </div>
          </div>
        </>
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
  return new Date(dateStr).toLocaleDateString('en-IE', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}

function getTaxTreatment(type: string): string {
  switch (type) {
    case 'stock':
      return 'CGT 33%'
    case 'etf_eu':
      return 'Exit Tax 41%'
    case 'etf_non_eu':
      return 'CGT 33%'
    case 'cash':
      return 'DIRT 33%'
    default:
      return 'CGT 33%'
  }
}

function getDaysUntil(dateStr: string): number {
  const target = new Date(dateStr)
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  target.setHours(0, 0, 0, 0)
  return Math.ceil((target.getTime() - today.getTime()) / (1000 * 60 * 60 * 24))
}

function formatTimeRemaining(days: number): string {
  if (days < 0) {
    return 'OVERDUE'
  } else if (days === 0) {
    return 'Today!'
  } else if (days === 1) {
    return '1 day'
  } else if (days < 30) {
    return `${days} days`
  } else if (days < 365) {
    const months = Math.floor(days / 30)
    return months === 1 ? '1 month' : `${months} months`
  } else {
    const years = Math.floor(days / 365)
    const remainingMonths = Math.floor((days % 365) / 30)
    if (remainingMonths === 0) {
      return years === 1 ? '1 year' : `${years} years`
    }
    return years === 1
      ? `1 year ${remainingMonths}m`
      : `${years} years ${remainingMonths}m`
  }
}
