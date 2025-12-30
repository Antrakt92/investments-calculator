import { useState, useEffect } from 'react'
import { getHoldings, getTransactions, type Holding, type Transaction } from '../services/api'

export default function Portfolio() {
  const [holdings, setHoldings] = useState<Holding[]>([])
  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [activeTab, setActiveTab] = useState<'holdings' | 'transactions'>('holdings')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<'all' | 'buy' | 'sell'>('all')

  useEffect(() => {
    loadData()
  }, [])

  async function loadData() {
    try {
      setLoading(true)
      const [holdingsData, transactionsData] = await Promise.all([
        getHoldings(),
        getTransactions({ limit: 100 }),
      ])
      setHoldings(holdingsData)
      setTransactions(transactionsData)
    } catch (err) {
      setError('Failed to load portfolio data')
    } finally {
      setLoading(false)
    }
  }

  const filteredTransactions = transactions.filter(t => {
    if (filter === 'all') return true
    return t.transaction_type === filter
  })

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
        >
          Transactions ({transactions.length})
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
              className={`btn ${filter === 'all' ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setFilter('all')}
              style={{ marginRight: '8px' }}
            >
              All
            </button>
            <button
              className={`btn ${filter === 'buy' ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setFilter('buy')}
              style={{ marginRight: '8px' }}
            >
              Buys
            </button>
            <button
              className={`btn ${filter === 'sell' ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setFilter('sell')}
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
