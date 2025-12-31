import { useState, useEffect } from 'react'
import { getHoldings, getTransactions, getIncomeEvents, type Holding, type Transaction, type IncomeEvent } from '../services/api'

export default function Portfolio() {
  const [holdings, setHoldings] = useState<Holding[]>([])
  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [incomeEvents, setIncomeEvents] = useState<IncomeEvent[]>([])
  const [activeTab, setActiveTab] = useState<'holdings' | 'transactions' | 'income'>('holdings')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [transFilter, setTransFilter] = useState<'all' | 'buy' | 'sell'>('all')
  const [incomeFilter, setIncomeFilter] = useState<'all' | 'interest' | 'dividend'>('all')

  useEffect(() => {
    loadData()
  }, [])

  async function loadData() {
    try {
      setLoading(true)
      const [holdingsData, transactionsData, incomeData] = await Promise.all([
        getHoldings(),
        getTransactions({ limit: 100 }),
        getIncomeEvents({ limit: 100 }),
      ])
      setHoldings(holdingsData)
      setTransactions(transactionsData)
      setIncomeEvents(incomeData)
    } catch (err) {
      setError('Failed to load portfolio data')
    } finally {
      setLoading(false)
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
          <div style={{ marginBottom: '16px' }}>
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
