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

  // Calculate Exit Tax net
  const exitNetGain = result ? result.exit_tax.gains - result.exit_tax.losses : 0

  return (
    <div>
      <h1 style={{ marginBottom: '24px' }}>Irish Tax Calculator - {taxYear}</h1>

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
            {loading ? 'Calculating...' : 'Recalculate'}
          </button>
        </div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {result && (
        <>
          {/* Summary Cards */}
          <div className="stat-grid" style={{ marginTop: '24px' }}>
            <div className="stat-card">
              <div className="stat-label">CGT Due (Stocks)</div>
              <div className="stat-value negative">{formatCurrency(result.cgt.tax_due)}</div>
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                33% on gains above €1,270
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Exit Tax Due (EU Funds)</div>
              <div className="stat-value negative">{formatCurrency(result.exit_tax.tax_due)}</div>
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                41% on net gains (no exemption)
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-label">DIRT Due (Interest)</div>
              <div className="stat-value negative">{formatCurrency(result.dirt.tax_to_pay)}</div>
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                33% on deposit interest
              </div>
            </div>
            <div className="stat-card" style={{ borderLeft: '4px solid var(--danger)' }}>
              <div className="stat-label">TOTAL TAX DUE</div>
              <div className="stat-value negative">{formatCurrency(result.summary.total_tax_due)}</div>
            </div>
          </div>

          {/* ===== CGT Section ===== */}
          <div className="card" style={{ marginTop: '24px' }}>
            <div className="tax-section">
              <div className="tax-section-title">
                1. Capital Gains Tax (CGT) - Stocks
                <span className="tax-rate-badge">33%</span>
              </div>
              <p style={{ color: 'var(--text-secondary)', marginBottom: '16px', fontSize: '14px' }}>
                Applies to: US stocks, non-EU ETFs. Uses Irish matching rules (same-day → 4-week → FIFO).
                €1,270 annual exemption available.
              </p>
              <table className="table">
                <tbody>
                  <tr>
                    <td>Total Gains from Sales</td>
                    <td style={{ textAlign: 'right', color: 'var(--success)', fontWeight: 500 }}>
                      +{formatCurrency(result.cgt.gains)}
                    </td>
                  </tr>
                  <tr>
                    <td>Total Losses from Sales</td>
                    <td style={{ textAlign: 'right', color: 'var(--danger)', fontWeight: 500 }}>
                      -{formatCurrency(result.cgt.losses)}
                    </td>
                  </tr>
                  <tr style={{ background: 'var(--bg-secondary)' }}>
                    <td><strong>Net Gain/Loss</strong></td>
                    <td style={{
                      textAlign: 'right',
                      fontWeight: 600,
                      color: result.cgt.net_gain_loss >= 0 ? 'var(--success)' : 'var(--danger)'
                    }}>
                      {result.cgt.net_gain_loss >= 0 ? '+' : ''}{formatCurrency(result.cgt.net_gain_loss)}
                    </td>
                  </tr>
                  <tr>
                    <td>Annual Exemption Used</td>
                    <td style={{ textAlign: 'right' }}>
                      -{formatCurrency(result.cgt.exemption_used)}
                      <span style={{ color: 'var(--text-secondary)' }}> (max €1,270)</span>
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
                  💡 Losses to carry forward to next year: {formatCurrency(result.cgt.losses_to_carry_forward)}
                </div>
              )}
            </div>
          </div>

          {/* ===== Exit Tax Section ===== */}
          <div className="card">
            <div className="tax-section">
              <div className="tax-section-title">
                2. Exit Tax (EU Funds)
                <span className="tax-rate-badge" style={{ background: 'var(--danger)' }}>41%</span>
              </div>
              <p style={{ color: 'var(--text-secondary)', marginBottom: '16px', fontSize: '14px' }}>
                Applies to: Irish/EU domiciled ETFs (ISIN: IE, LU, DE).
                <strong> Losses CAN offset gains within Exit Tax</strong>, but cannot offset CGT gains. No annual exemption.
              </p>
              <table className="table">
                <tbody>
                  <tr>
                    <td>Gains from ETF Sales</td>
                    <td style={{ textAlign: 'right', color: 'var(--success)', fontWeight: 500 }}>
                      +{formatCurrency(result.exit_tax.gains)}
                    </td>
                  </tr>
                  <tr>
                    <td>Losses from ETF Sales</td>
                    <td style={{ textAlign: 'right', color: 'var(--danger)', fontWeight: 500 }}>
                      -{formatCurrency(result.exit_tax.losses)}
                    </td>
                  </tr>
                  <tr style={{ background: 'var(--bg-secondary)' }}>
                    <td><strong>Net Gain/Loss from Sales</strong></td>
                    <td style={{
                      textAlign: 'right',
                      fontWeight: 600,
                      color: exitNetGain >= 0 ? 'var(--success)' : 'var(--danger)'
                    }}>
                      {exitNetGain >= 0 ? '+' : ''}{formatCurrency(exitNetGain)}
                    </td>
                  </tr>
                  <tr>
                    <td>Deemed Disposal Gains (8-year rule)</td>
                    <td style={{ textAlign: 'right' }}>
                      +{formatCurrency(result.exit_tax.deemed_disposal_gains)}
                    </td>
                  </tr>
                  <tr style={{ background: 'var(--bg-white)' }}>
                    <td><strong>Total Taxable (Net Gains + Deemed)</strong></td>
                    <td style={{ textAlign: 'right', fontWeight: 600 }}>
                      {formatCurrency(result.exit_tax.total_taxable)}
                    </td>
                  </tr>
                  <tr style={{ background: 'var(--bg-white)' }}>
                    <td><strong>Exit Tax @ 41%</strong></td>
                    <td style={{ textAlign: 'right', fontWeight: 600, color: 'var(--danger)' }}>
                      {formatCurrency(result.exit_tax.tax_due)}
                    </td>
                  </tr>
                </tbody>
              </table>
              {exitNetGain < 0 && (
                <div className="alert alert-info" style={{ marginTop: '12px' }}>
                  💡 Net loss of {formatCurrency(Math.abs(exitNetGain))} - no Exit Tax due on sales this year.
                  Exit Tax losses cannot be carried forward or offset against CGT.
                </div>
              )}
            </div>
          </div>

          {/* ===== DIRT Section ===== */}
          <div className="card">
            <div className="tax-section">
              <div className="tax-section-title">
                3. DIRT (Deposit Interest)
                <span className="tax-rate-badge">33%</span>
              </div>
              <div className="alert alert-warning" style={{ marginBottom: '16px' }}>
                ⚠️ Trade Republic does NOT withhold DIRT - you must self-declare on Form 11
              </div>
              <table className="table">
                <tbody>
                  <tr>
                    <td>Total Interest Earned</td>
                    <td style={{ textAlign: 'right', fontWeight: 500 }}>
                      {formatCurrency(result.dirt.interest_income)}
                    </td>
                  </tr>
                  <tr>
                    <td>DIRT Already Withheld</td>
                    <td style={{ textAlign: 'right' }}>
                      -{formatCurrency(result.dirt.tax_withheld)}
                    </td>
                  </tr>
                  <tr style={{ background: 'var(--bg-white)' }}>
                    <td><strong>DIRT to Pay @ 33%</strong></td>
                    <td style={{ textAlign: 'right', fontWeight: 600, color: 'var(--danger)' }}>
                      {formatCurrency(result.dirt.tax_to_pay)}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          {/* ===== Dividends Section ===== */}
          <div className="card">
            <div className="tax-section">
              <div className="tax-section-title">
                4. Dividends (Foreign Income)
                <span className="tax-rate-badge" style={{ background: 'var(--warning)' }}>Marginal Rate</span>
              </div>
              <p style={{ color: 'var(--text-secondary)', marginBottom: '16px', fontSize: '14px' }}>
                Foreign dividends are taxed at your marginal income tax rate (20% or 40%).
                Withholding tax paid abroad can be claimed as a credit.
              </p>
              <table className="table">
                <tbody>
                  <tr>
                    <td>Total Dividends Received</td>
                    <td style={{ textAlign: 'right', fontWeight: 500 }}>
                      {formatCurrency(result.dividends.total_dividends)}
                    </td>
                  </tr>
                  <tr>
                    <td>Foreign Withholding Tax Credit</td>
                    <td style={{ textAlign: 'right', color: 'var(--success)' }}>
                      {formatCurrency(result.dividends.withholding_tax_credit)}
                    </td>
                  </tr>
                </tbody>
              </table>
              <div className="alert alert-info" style={{ marginTop: '12px' }}>
                💡 Add dividends to Schedule D (Panel F) on Form 11. Tax depends on your income bracket.
              </div>
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
            {result.summary.payment_deadlines.filter(d => d.amount > 0).length === 0 && (
              <p style={{ color: 'var(--text-secondary)', textAlign: 'center', padding: '20px' }}>
                No tax payments due for {taxYear}
              </p>
            )}
          </div>

          {/* Form 11 Guidance */}
          <div className="card">
            <h2 className="card-title">Form 11 Field Reference</h2>
            <p style={{ color: 'var(--text-secondary)', marginBottom: '16px', fontSize: '14px' }}>
              Use these values when completing your Revenue Online Service (ROS) Form 11:
            </p>
            <div style={{ display: 'grid', gap: '16px' }}>
              <div className="tax-section">
                <h3 style={{ fontSize: '14px', marginBottom: '8px', color: 'var(--primary)' }}>
                  Panel D - Irish Investment Income
                </h3>
                <table className="table">
                  <tbody>
                    <tr>
                      <td>Deposit Interest (Gross)</td>
                      <td style={{ textAlign: 'right', fontWeight: 500 }}>
                        {formatCurrency(result.form_11_guidance.panel_d.deposit_interest_gross)}
                      </td>
                    </tr>
                    <tr>
                      <td>DIRT Deducted at Source</td>
                      <td style={{ textAlign: 'right' }}>
                        {formatCurrency(result.form_11_guidance.panel_d.dirt_deducted)}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <div className="tax-section">
                <h3 style={{ fontSize: '14px', marginBottom: '8px', color: 'var(--primary)' }}>
                  Panel E - Capital Gains
                </h3>
                <table className="table">
                  <tbody>
                    <tr>
                      <td>Total Sale Proceeds (Consideration)</td>
                      <td style={{ textAlign: 'right', fontWeight: 500 }}>
                        {formatCurrency(result.form_11_guidance.panel_e.cgt_consideration)}
                      </td>
                    </tr>
                    <tr>
                      <td>Total Allowable Costs (Cost Basis)</td>
                      <td style={{ textAlign: 'right' }}>
                        {formatCurrency(result.form_11_guidance.panel_e.cgt_allowable_costs)}
                      </td>
                    </tr>
                    <tr>
                      <td>Net Gain Before Exemption</td>
                      <td style={{ textAlign: 'right' }}>
                        {formatCurrency(result.form_11_guidance.panel_e.cgt_net_gain)}
                      </td>
                    </tr>
                    <tr>
                      <td>Annual Exemption Claimed</td>
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
                <h3 style={{ fontSize: '14px', marginBottom: '8px', color: 'var(--primary)' }}>
                  Panel F - Foreign Income
                </h3>
                <table className="table">
                  <tbody>
                    <tr>
                      <td>Foreign Dividends</td>
                      <td style={{ textAlign: 'right', fontWeight: 500 }}>
                        {formatCurrency(result.form_11_guidance.panel_f.foreign_dividends)}
                      </td>
                    </tr>
                    <tr>
                      <td>Foreign Tax Credit (Withholding)</td>
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
              <h2 className="card-title">⏰ Upcoming Deemed Disposals (8-Year Rule)</h2>
              <p style={{ color: 'var(--text-secondary)', marginBottom: '16px' }}>
                EU funds held for 8 years trigger a "deemed disposal" - you pay Exit Tax as if you sold, even if you didn't.
                Plan ahead to have funds available.
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
