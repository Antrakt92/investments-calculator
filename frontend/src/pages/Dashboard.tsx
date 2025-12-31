import { useState, useEffect } from 'react'
import { getPortfolioSummary, getHoldings, getIncomeEvents, calculateTax, type Holding, type TaxResult, type IncomeEvent } from '../services/api'

export default function Dashboard() {
  const [summary, setSummary] = useState<{
    total_assets: number
    assets_by_type: Record<string, number>
    total_transactions: number
  } | null>(null)
  const [holdings, setHoldings] = useState<Holding[]>([])
  const [incomeEvents, setIncomeEvents] = useState<IncomeEvent[]>([])
  const [taxResult, setTaxResult] = useState<TaxResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Default to 2024 (most recent complete tax year)
  const taxYear = 2024

  useEffect(() => {
    loadData()
  }, [])

  async function loadData() {
    try {
      setLoading(true)
      const [summaryData, holdingsData, incomeData] = await Promise.all([
        getPortfolioSummary(),
        getHoldings(),
        getIncomeEvents({ limit: 100 }),
      ])
      setSummary(summaryData)
      setHoldings(holdingsData)
      setIncomeEvents(incomeData)

      // Calculate tax for 2024
      try {
        const tax = await calculateTax(taxYear)
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
    return <div className="card">Loading...</div>
  }

  if (error) {
    return <div className="alert alert-error">{error}</div>
  }

  const hasData = holdings.length > 0 || incomeEvents.length > 0

  return (
    <div>
      <h1 style={{ marginBottom: '24px' }}>Dashboard - Tax Year {taxYear}</h1>

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
              <div className="stat-label">CGT Due (Stocks)</div>
              <div className="stat-value">{formatCurrency(taxResult?.cgt.tax_due || 0)}</div>
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                33% on gains above €1,270
              </div>
            </div>
            <div className="stat-card" style={{ borderLeft: '4px solid var(--danger)' }}>
              <div className="stat-label">Exit Tax Due (EU Funds)</div>
              <div className="stat-value">{formatCurrency(taxResult?.exit_tax.tax_due || 0)}</div>
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                41% on gains (no exemption)
              </div>
            </div>
            <div className="stat-card" style={{ borderLeft: '4px solid var(--warning)' }}>
              <div className="stat-label">DIRT Due (Interest)</div>
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
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px', marginTop: '24px' }}>
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

          {/* Payment Deadlines */}
          {taxResult && taxResult.summary.payment_deadlines.some(d => d.amount > 0) && (
            <div className="card" style={{ marginTop: '24px' }}>
              <h2 className="card-title">Upcoming Payment Deadlines</h2>
              {taxResult.summary.payment_deadlines
                .filter(d => d.amount > 0)
                .sort((a, b) => new Date(a.due_date).getTime() - new Date(b.due_date).getTime())
                .map((deadline, i) => (
                  <div key={i} className="deadline-item">
                    <div>
                      <div className="deadline-date">{formatDate(deadline.due_date)}</div>
                      <div style={{ color: 'var(--text-secondary)', fontSize: '14px' }}>
                        {deadline.description}
                      </div>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <span className="tax-rate-badge">{deadline.tax_type}</span>
                      <span className="deadline-amount">{formatCurrency(deadline.amount)}</span>
                    </div>
                  </div>
                ))}
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
