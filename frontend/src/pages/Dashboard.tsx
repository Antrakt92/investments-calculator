import { useState, useEffect } from 'react'
import { getPortfolioSummary, getHoldings, calculateTax, type Holding, type TaxResult } from '../services/api'

export default function Dashboard() {
  const [summary, setSummary] = useState<{
    total_assets: number
    assets_by_type: Record<string, number>
    total_transactions: number
  } | null>(null)
  const [holdings, setHoldings] = useState<Holding[]>([])
  const [taxResult, setTaxResult] = useState<TaxResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadData()
  }, [])

  async function loadData() {
    try {
      setLoading(true)
      const [summaryData, holdingsData] = await Promise.all([
        getPortfolioSummary(),
        getHoldings(),
      ])
      setSummary(summaryData)
      setHoldings(holdingsData)

      // Try to calculate tax for current year
      try {
        const tax = await calculateTax(new Date().getFullYear())
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

  const totalValue = holdings.reduce((sum, h) => sum + h.total_cost_basis, 0)

  if (loading) {
    return <div className="card">Loading...</div>
  }

  if (error) {
    return <div className="alert alert-error">{error}</div>
  }

  return (
    <div>
      <h1 style={{ marginBottom: '24px' }}>Dashboard</h1>

      <div className="stat-grid">
        <div className="stat-card">
          <div className="stat-label">Total Holdings</div>
          <div className="stat-value">{summary?.total_assets || 0}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Total Cost Basis</div>
          <div className="stat-value">{formatCurrency(totalValue)}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Transactions</div>
          <div className="stat-value">{summary?.total_transactions || 0}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Tax Due ({new Date().getFullYear()})</div>
          <div className="stat-value negative">
            {formatCurrency(taxResult?.summary.total_tax_due || 0)}
          </div>
        </div>
      </div>

      {taxResult && taxResult.summary.total_tax_due > 0 && (
        <div className="card" style={{ marginTop: '24px' }}>
          <h2 className="card-title">Payment Deadlines</h2>
          {taxResult.summary.payment_deadlines
            .filter(d => d.amount > 0)
            .map((deadline, i) => (
              <div key={i} className="deadline-item">
                <div>
                  <div className="deadline-date">{formatDate(deadline.due_date)}</div>
                  <div style={{ color: 'var(--text-secondary)', fontSize: '14px' }}>
                    {deadline.description}
                  </div>
                </div>
                <div className="deadline-amount">{formatCurrency(deadline.amount)}</div>
              </div>
            ))}
        </div>
      )}

      {summary && Object.keys(summary.assets_by_type).length > 0 && (
        <div className="card" style={{ marginTop: '24px' }}>
          <h2 className="card-title">Assets by Type</h2>
          <table className="table">
            <thead>
              <tr>
                <th>Type</th>
                <th>Count</th>
                <th>Tax Treatment</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(summary.assets_by_type).map(([type, count]) => (
                <tr key={type}>
                  <td style={{ textTransform: 'capitalize' }}>{type.replace('_', ' ')}</td>
                  <td>{count}</td>
                  <td>{getTaxTreatment(type)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {holdings.length === 0 && (
        <div className="card" style={{ marginTop: '24px', textAlign: 'center', padding: '40px' }}>
          <h2>No Data Yet</h2>
          <p style={{ color: 'var(--text-secondary)', marginTop: '8px' }}>
            Upload a Trade Republic tax report PDF to get started.
          </p>
          <a href="/upload" className="btn btn-primary" style={{ marginTop: '16px' }}>
            Upload PDF
          </a>
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
  return new Date(dateStr).toLocaleDateString('en-IE', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}

function getTaxTreatment(type: string): string {
  switch (type) {
    case 'stock':
      return 'CGT 33% (€1,270 exemption)'
    case 'etf_eu':
      return 'Exit Tax 41% (no exemption)'
    case 'etf_non_eu':
      return 'CGT 33% (€1,270 exemption)'
    case 'cash':
      return 'DIRT 33%'
    default:
      return 'CGT 33%'
  }
}
