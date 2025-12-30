import { useState, useEffect } from 'react'
import { calculateTax, getDeemedDisposals, type TaxResult } from '../services/api'

export default function TaxCalculator() {
  // Default to 2024 (most recent complete tax year)
  const [taxYear, setTaxYear] = useState(2024)
  const [lossesCarriedForward, setLossesCarriedForward] = useState(0)
  const [result, setResult] = useState<TaxResult | null>(null)
  const [deemedDisposals, setDeemedDisposals] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function calculate() {
    try {
      setLoading(true)
      setError(null)
      const [taxResult, disposals] = await Promise.all([
        calculateTax(taxYear, lossesCarriedForward),
        getDeemedDisposals(3),
      ])
      setResult(taxResult)
      setDeemedDisposals(disposals)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Calculation failed')
    } finally {
      setLoading(false)
    }
  }

  // Auto-calculate when year or losses change
  useEffect(() => {
    calculate()
  }, [taxYear, lossesCarriedForward])

  return (
    <div>
      <h1 style={{ marginBottom: '24px' }}>Irish Tax Calculator</h1>

      <div className="card">
        <div style={{ display: 'flex', gap: '16px', alignItems: 'flex-end' }}>
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">Tax Year</label>
            <select
              className="form-input"
              value={taxYear}
              onChange={e => setTaxYear(Number(e.target.value))}
              style={{ width: '120px' }}
            >
              {[2024, 2023, 2022].map(year => (
                <option key={year} value={year}>{year}</option>
              ))}
            </select>
          </div>
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">CGT Losses Carried Forward</label>
            <input
              type="number"
              className="form-input"
              value={lossesCarriedForward}
              onChange={e => setLossesCarriedForward(Number(e.target.value))}
              style={{ width: '150px' }}
            />
          </div>
          <button className="btn btn-primary" onClick={calculate} disabled={loading}>
            {loading ? 'Calculating...' : 'Calculate Tax'}
          </button>
        </div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {result && (
        <>
          {/* Summary Cards */}
          <div className="stat-grid" style={{ marginTop: '24px' }}>
            <div className="stat-card">
              <div className="stat-label">CGT Due</div>
              <div className="stat-value negative">{formatCurrency(result.cgt.tax_due)}</div>
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                33% rate
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Exit Tax Due</div>
              <div className="stat-value negative">{formatCurrency(result.exit_tax.tax_due)}</div>
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                41% rate
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-label">DIRT Due</div>
              <div className="stat-value negative">{formatCurrency(result.dirt.tax_to_pay)}</div>
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                33% rate
              </div>
            </div>
            <div className="stat-card" style={{ borderLeft: '4px solid var(--danger)' }}>
              <div className="stat-label">Total Tax Due</div>
              <div className="stat-value negative">{formatCurrency(result.summary.total_tax_due)}</div>
            </div>
          </div>

          {/* CGT Section */}
          <div className="card" style={{ marginTop: '24px' }}>
            <div className="tax-section">
              <div className="tax-section-title">
                Capital Gains Tax (CGT)
                <span className="tax-rate-badge">33%</span>
              </div>
              <table className="table">
                <tbody>
                  <tr>
                    <td>Total Gains</td>
                    <td style={{ textAlign: 'right', color: 'var(--success)' }}>
                      {formatCurrency(result.cgt.gains)}
                    </td>
                  </tr>
                  <tr>
                    <td>Total Losses</td>
                    <td style={{ textAlign: 'right', color: 'var(--danger)' }}>
                      -{formatCurrency(result.cgt.losses)}
                    </td>
                  </tr>
                  <tr>
                    <td>Net Gain/Loss</td>
                    <td style={{ textAlign: 'right', fontWeight: 600 }}>
                      {formatCurrency(result.cgt.net_gain_loss)}
                    </td>
                  </tr>
                  <tr>
                    <td>Annual Exemption</td>
                    <td style={{ textAlign: 'right' }}>
                      -{formatCurrency(result.cgt.exemption_used)}
                      <span style={{ color: 'var(--text-secondary)' }}> / €1,270</span>
                    </td>
                  </tr>
                  <tr style={{ background: 'var(--bg-white)' }}>
                    <td><strong>Taxable Gain</strong></td>
                    <td style={{ textAlign: 'right', fontWeight: 600 }}>
                      {formatCurrency(result.cgt.taxable_gain)}
                    </td>
                  </tr>
                  <tr style={{ background: 'var(--bg-white)' }}>
                    <td><strong>CGT @ 33%</strong></td>
                    <td style={{ textAlign: 'right', fontWeight: 600, color: 'var(--danger)' }}>
                      {formatCurrency(result.cgt.tax_due)}
                    </td>
                  </tr>
                </tbody>
              </table>
              {result.cgt.losses_to_carry_forward > 0 && (
                <div className="alert alert-info" style={{ marginTop: '12px' }}>
                  Losses to carry forward: {formatCurrency(result.cgt.losses_to_carry_forward)}
                </div>
              )}
            </div>
          </div>

          {/* Exit Tax Section */}
          <div className="card">
            <div className="tax-section">
              <div className="tax-section-title">
                Exit Tax (EU Funds)
                <span className="tax-rate-badge" style={{ background: 'var(--danger)' }}>41%</span>
              </div>
              <p style={{ color: 'var(--text-secondary)', marginBottom: '12px' }}>
                {result.exit_tax.note}
              </p>
              <table className="table">
                <tbody>
                  <tr>
                    <td>Disposal Gains</td>
                    <td style={{ textAlign: 'right' }}>{formatCurrency(result.exit_tax.gains)}</td>
                  </tr>
                  <tr>
                    <td>Disposal Losses</td>
                    <td style={{ textAlign: 'right' }}>-{formatCurrency(result.exit_tax.losses)}</td>
                  </tr>
                  <tr>
                    <td>Deemed Disposal Gains</td>
                    <td style={{ textAlign: 'right' }}>{formatCurrency(result.exit_tax.deemed_disposal_gains)}</td>
                  </tr>
                  <tr style={{ background: 'var(--bg-white)' }}>
                    <td><strong>Exit Tax @ 41%</strong></td>
                    <td style={{ textAlign: 'right', fontWeight: 600, color: 'var(--danger)' }}>
                      {formatCurrency(result.exit_tax.tax_due)}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          {/* DIRT Section */}
          <div className="card">
            <div className="tax-section">
              <div className="tax-section-title">
                DIRT (Deposit Interest)
                <span className="tax-rate-badge">33%</span>
              </div>
              <div className="alert alert-info" style={{ marginBottom: '12px' }}>
                {result.dirt.note}
              </div>
              <table className="table">
                <tbody>
                  <tr>
                    <td>Interest Income</td>
                    <td style={{ textAlign: 'right' }}>{formatCurrency(result.dirt.interest_income)}</td>
                  </tr>
                  <tr>
                    <td>Tax Withheld</td>
                    <td style={{ textAlign: 'right' }}>{formatCurrency(result.dirt.tax_withheld)}</td>
                  </tr>
                  <tr style={{ background: 'var(--bg-white)' }}>
                    <td><strong>DIRT @ 33%</strong></td>
                    <td style={{ textAlign: 'right', fontWeight: 600, color: 'var(--danger)' }}>
                      {formatCurrency(result.dirt.tax_to_pay)}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          {/* Payment Deadlines */}
          <div className="card">
            <h2 className="card-title">Payment Deadlines</h2>
            {result.summary.payment_deadlines
              .filter(d => d.amount > 0)
              .map((deadline, i) => (
                <div key={i} className="deadline-item">
                  <div>
                    <div className="deadline-date">{formatDate(deadline.due_date)}</div>
                    <div style={{ color: 'var(--text-secondary)', fontSize: '14px' }}>
                      {deadline.description}
                    </div>
                  </div>
                  <div>
                    <span className="tax-rate-badge" style={{ marginRight: '8px' }}>
                      {deadline.tax_type}
                    </span>
                    <span className="deadline-amount">{formatCurrency(deadline.amount)}</span>
                  </div>
                </div>
              ))}
          </div>

          {/* Form 11 Guidance */}
          <div className="card">
            <h2 className="card-title">Form 11 Guidance</h2>
            <div style={{ display: 'grid', gap: '16px' }}>
              <div className="tax-section">
                <h3 style={{ fontSize: '14px', marginBottom: '8px' }}>Panel D - Irish Rental & Investment Income</h3>
                <table className="table">
                  <tbody>
                    <tr>
                      <td>Deposit Interest (Gross)</td>
                      <td style={{ textAlign: 'right' }}>
                        {formatCurrency(result.form_11_guidance.panel_d.deposit_interest_gross)}
                      </td>
                    </tr>
                    <tr>
                      <td>DIRT Deducted</td>
                      <td style={{ textAlign: 'right' }}>
                        {formatCurrency(result.form_11_guidance.panel_d.dirt_deducted)}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <div className="tax-section">
                <h3 style={{ fontSize: '14px', marginBottom: '8px' }}>Panel E - Capital Gains</h3>
                <table className="table">
                  <tbody>
                    <tr>
                      <td>Total Consideration (Proceeds)</td>
                      <td style={{ textAlign: 'right' }}>
                        {formatCurrency(result.form_11_guidance.panel_e.cgt_consideration)}
                      </td>
                    </tr>
                    <tr>
                      <td>Allowable Costs</td>
                      <td style={{ textAlign: 'right' }}>
                        {formatCurrency(result.form_11_guidance.panel_e.cgt_allowable_costs)}
                      </td>
                    </tr>
                    <tr>
                      <td>Net Gain</td>
                      <td style={{ textAlign: 'right' }}>
                        {formatCurrency(result.form_11_guidance.panel_e.cgt_net_gain)}
                      </td>
                    </tr>
                    <tr>
                      <td>Annual Exemption</td>
                      <td style={{ textAlign: 'right' }}>
                        {formatCurrency(result.form_11_guidance.panel_e.cgt_exemption)}
                      </td>
                    </tr>
                    <tr>
                      <td>Exit Tax Gains (Investment Undertakings)</td>
                      <td style={{ textAlign: 'right' }}>
                        {formatCurrency(result.form_11_guidance.panel_e.exit_tax_gains)}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <div className="tax-section">
                <h3 style={{ fontSize: '14px', marginBottom: '8px' }}>Panel F - Foreign Income</h3>
                <table className="table">
                  <tbody>
                    <tr>
                      <td>Foreign Dividends</td>
                      <td style={{ textAlign: 'right' }}>
                        {formatCurrency(result.form_11_guidance.panel_f.foreign_dividends)}
                      </td>
                    </tr>
                    <tr>
                      <td>Foreign Tax Credit</td>
                      <td style={{ textAlign: 'right' }}>
                        {formatCurrency(result.form_11_guidance.panel_f.foreign_tax_credit)}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          {/* Upcoming Deemed Disposals */}
          {deemedDisposals.length > 0 && (
            <div className="card">
              <h2 className="card-title">Upcoming Deemed Disposals (8-Year Rule)</h2>
              <p style={{ color: 'var(--text-secondary)', marginBottom: '16px' }}>
                EU funds held for 8 years are subject to deemed disposal. Plan ahead for these tax events.
              </p>
              <table className="table">
                <thead>
                  <tr>
                    <th>Fund</th>
                    <th>Acquired</th>
                    <th>Deemed Disposal</th>
                    <th>Quantity</th>
                    <th>Cost Basis</th>
                  </tr>
                </thead>
                <tbody>
                  {deemedDisposals.map((d, i) => (
                    <tr key={i}>
                      <td>
                        <div style={{ fontWeight: 500 }}>{d.name}</div>
                        <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>{d.isin}</div>
                      </td>
                      <td>{formatDate(d.acquisition_date)}</td>
                      <td style={{ fontWeight: 500, color: 'var(--warning)' }}>
                        {formatDate(d.deemed_disposal_date)}
                      </td>
                      <td>{d.quantity.toFixed(4)}</td>
                      <td>{formatCurrency(d.cost_basis)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
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
    month: 'short',
    day: 'numeric',
  })
}
