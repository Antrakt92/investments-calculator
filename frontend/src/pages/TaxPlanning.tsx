import { useState, useEffect } from 'react'
import {
  getHoldings,
  getPersons,
  calculateWhatIf,
  getLossHarvestingOpportunities,
  type Holding,
  type Person,
  type WhatIfResult,
  type LossHarvestingOpportunity
} from '../services/api'

export default function TaxPlanning() {
  const [activeTab, setActiveTab] = useState<'whatif' | 'harvesting'>('whatif')
  const [holdings, setHoldings] = useState<Holding[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Family mode state
  const [persons, setPersons] = useState<Person[]>([])
  const [selectedPersonId, setSelectedPersonId] = useState<number | undefined>(undefined)

  // What-if state
  const [selectedIsin, setSelectedIsin] = useState('')
  const [quantity, setQuantity] = useState('')
  const [salePrice, setSalePrice] = useState('')
  const [whatIfResult, setWhatIfResult] = useState<WhatIfResult | null>(null)
  const [whatIfLoading, setWhatIfLoading] = useState(false)
  const [whatIfError, setWhatIfError] = useState<string | null>(null)

  // Loss harvesting state
  const [opportunities, setOpportunities] = useState<LossHarvestingOpportunity[]>([])
  const [harvestingLoading, setHarvestingLoading] = useState(false)
  const [currentPrices, setCurrentPrices] = useState<Record<string, string>>({})

  useEffect(() => {
    loadInitialData()
  }, [])

  useEffect(() => {
    loadHoldings()
    if (activeTab === 'harvesting') {
      loadOpportunities()
    }
  }, [selectedPersonId])

  async function loadInitialData() {
    try {
      const [personsData, holdingsData] = await Promise.all([
        getPersons().catch(() => []),
        getHoldings()
      ])
      setPersons(personsData)
      setHoldings(holdingsData)
    } catch (err) {
      setError('Failed to load data')
    } finally {
      setLoading(false)
    }
  }

  async function loadHoldings() {
    try {
      const data = await getHoldings(selectedPersonId)
      setHoldings(data)
      // Reset selection if current selection not in new holdings
      if (selectedIsin && !data.find(h => h.isin === selectedIsin)) {
        setSelectedIsin('')
        setWhatIfResult(null)
      }
    } catch {
      // Ignore
    }
  }

  async function loadOpportunities() {
    try {
      setHarvestingLoading(true)
      const data = await getLossHarvestingOpportunities(selectedPersonId)
      setOpportunities(data)
    } catch {
      // Ignore
    } finally {
      setHarvestingLoading(false)
    }
  }

  const isFamilyMode = persons.length > 1
  const selectedHolding = holdings.find(h => h.isin === selectedIsin)

  async function handleCalculateWhatIf(e: React.FormEvent) {
    e.preventDefault()
    if (!selectedIsin || !quantity || !salePrice) return

    try {
      setWhatIfLoading(true)
      setWhatIfError(null)
      const result = await calculateWhatIf(
        selectedIsin,
        parseFloat(quantity),
        parseFloat(salePrice),
        selectedPersonId
      )
      setWhatIfResult(result)
    } catch (err) {
      setWhatIfError(err instanceof Error ? err.message : 'Calculation failed')
      setWhatIfResult(null)
    } finally {
      setWhatIfLoading(false)
    }
  }

  function formatCurrency(value: number): string {
    return new Intl.NumberFormat('en-IE', {
      style: 'currency',
      currency: 'EUR'
    }).format(value)
  }

  function calculateUnrealizedGainLoss(opp: LossHarvestingOpportunity): number | null {
    const price = currentPrices[opp.isin]
    if (!price) return null
    const currentValue = parseFloat(price) * opp.quantity
    return currentValue - opp.total_cost_basis
  }

  function calculatePotentialTaxSavings(opp: LossHarvestingOpportunity): number | null {
    const gainLoss = calculateUnrealizedGainLoss(opp)
    if (gainLoss === null || gainLoss >= 0) return null
    const taxRate = opp.tax_type === 'Exit Tax' ? 0.41 : 0.33
    return Math.abs(gainLoss) * taxRate
  }

  if (loading) {
    return <div className="loading">Loading...</div>
  }

  return (
    <div>
      <h1>Tax Planning Tools</h1>

      {/* Person Selector for Family Mode */}
      {isFamilyMode && (
        <div className="card" style={{ marginBottom: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>
            <span style={{ fontWeight: 500 }}>Filter by person:</span>
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              <button
                className={`btn ${selectedPersonId === undefined ? 'btn-primary' : 'btn-secondary'}`}
                onClick={() => setSelectedPersonId(undefined)}
                style={{ padding: '6px 12px' }}
              >
                All
              </button>
              {persons.map(person => (
                <button
                  key={person.id}
                  className={`btn ${selectedPersonId === person.id ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => setSelectedPersonId(person.id)}
                  style={{
                    padding: '6px 12px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px'
                  }}
                >
                  <div style={{
                    width: '20px',
                    height: '20px',
                    borderRadius: '50%',
                    backgroundColor: person.color,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '11px',
                    color: 'white',
                    fontWeight: 600
                  }}>
                    {person.name.charAt(0).toUpperCase()}
                  </div>
                  {person.name}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="tabs" style={{ marginBottom: '24px' }}>
        <button
          className={`tab ${activeTab === 'whatif' ? 'active' : ''}`}
          onClick={() => setActiveTab('whatif')}
        >
          What-If Calculator
        </button>
        <button
          className={`tab ${activeTab === 'harvesting' ? 'active' : ''}`}
          onClick={() => {
            setActiveTab('harvesting')
            loadOpportunities()
          }}
        >
          Loss Harvesting
        </button>
      </div>

      {error && <div className="error-message">{error}</div>}

      {/* What-If Calculator Tab */}
      {activeTab === 'whatif' && (
        <div className="card">
          <h2 style={{ marginTop: 0 }}>What-If Tax Scenario</h2>
          <p style={{ color: 'var(--text-secondary)', marginBottom: '24px' }}>
            Calculate the estimated tax impact before selling a position.
          </p>

          {holdings.length === 0 ? (
            <p style={{ color: 'var(--text-secondary)' }}>
              No holdings found. Upload transactions first.
            </p>
          ) : (
            <form onSubmit={handleCalculateWhatIf}>
              <div style={{ display: 'grid', gap: '16px', maxWidth: '500px' }}>
                <div className="form-group">
                  <label className="form-label">Select Asset</label>
                  <select
                    className="form-input"
                    value={selectedIsin}
                    onChange={e => {
                      setSelectedIsin(e.target.value)
                      setWhatIfResult(null)
                      setQuantity('')
                      setSalePrice('')
                    }}
                  >
                    <option value="">-- Select an asset --</option>
                    {holdings.map(h => (
                      <option key={h.isin} value={h.isin}>
                        {h.name} ({h.quantity.toFixed(4)} units @ {formatCurrency(h.average_cost)})
                      </option>
                    ))}
                  </select>
                </div>

                {selectedHolding && (
                  <>
                    <div style={{
                      padding: '12px',
                      background: 'var(--bg-secondary)',
                      borderRadius: '8px',
                      fontSize: '14px'
                    }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                        <span>Available:</span>
                        <strong>{selectedHolding.quantity.toFixed(4)} units</strong>
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                        <span>Avg Cost:</span>
                        <strong>{formatCurrency(selectedHolding.average_cost)}</strong>
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span>Tax Type:</span>
                        <strong style={{
                          color: selectedHolding.is_exit_tax_asset ? 'var(--warning)' : 'var(--primary)'
                        }}>
                          {selectedHolding.is_exit_tax_asset ? 'Exit Tax (41%)' : 'CGT (33%)'}
                        </strong>
                      </div>
                    </div>

                    <div className="form-group">
                      <label className="form-label">Quantity to Sell</label>
                      <input
                        type="number"
                        className="form-input"
                        value={quantity}
                        onChange={e => setQuantity(e.target.value)}
                        placeholder="e.g. 10"
                        step="0.0001"
                        min="0.0001"
                        max={selectedHolding.quantity}
                      />
                      <button
                        type="button"
                        className="btn btn-secondary"
                        style={{ marginTop: '8px', padding: '4px 8px', fontSize: '12px' }}
                        onClick={() => setQuantity(selectedHolding.quantity.toString())}
                      >
                        Sell All
                      </button>
                    </div>

                    <div className="form-group">
                      <label className="form-label">Sale Price per Unit (EUR)</label>
                      <input
                        type="number"
                        className="form-input"
                        value={salePrice}
                        onChange={e => setSalePrice(e.target.value)}
                        placeholder="e.g. 150.00"
                        step="0.01"
                        min="0.01"
                      />
                    </div>

                    <button
                      type="submit"
                      className="btn btn-primary"
                      disabled={whatIfLoading || !quantity || !salePrice}
                    >
                      {whatIfLoading ? 'Calculating...' : 'Calculate Tax Impact'}
                    </button>
                  </>
                )}
              </div>
            </form>
          )}

          {whatIfError && (
            <div className="error-message" style={{ marginTop: '16px' }}>
              {whatIfError}
            </div>
          )}

          {whatIfResult && (
            <div style={{ marginTop: '24px' }}>
              <h3 style={{ marginBottom: '16px' }}>Estimated Tax Impact</h3>

              <div style={{
                display: 'grid',
                gap: '16px',
                gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))'
              }}>
                {/* Proceeds */}
                <div style={{
                  padding: '16px',
                  background: 'var(--bg-secondary)',
                  borderRadius: '8px'
                }}>
                  <div style={{ color: 'var(--text-secondary)', marginBottom: '4px' }}>
                    Total Proceeds
                  </div>
                  <div style={{ fontSize: '24px', fontWeight: 600 }}>
                    {formatCurrency(whatIfResult.scenario.total_proceeds)}
                  </div>
                </div>

                {/* Cost Basis */}
                <div style={{
                  padding: '16px',
                  background: 'var(--bg-secondary)',
                  borderRadius: '8px'
                }}>
                  <div style={{ color: 'var(--text-secondary)', marginBottom: '4px' }}>
                    Cost Basis (FIFO)
                  </div>
                  <div style={{ fontSize: '24px', fontWeight: 600 }}>
                    {formatCurrency(whatIfResult.cost_basis.total)}
                  </div>
                </div>

                {/* Gain/Loss */}
                <div style={{
                  padding: '16px',
                  background: whatIfResult.result.is_gain ? 'rgba(34, 197, 94, 0.1)' : 'rgba(239, 68, 68, 0.1)',
                  borderRadius: '8px',
                  borderLeft: `4px solid ${whatIfResult.result.is_gain ? 'var(--success)' : 'var(--error)'}`
                }}>
                  <div style={{ color: 'var(--text-secondary)', marginBottom: '4px' }}>
                    {whatIfResult.result.is_gain ? 'Gain' : 'Loss'}
                  </div>
                  <div style={{
                    fontSize: '24px',
                    fontWeight: 600,
                    color: whatIfResult.result.is_gain ? 'var(--success)' : 'var(--error)'
                  }}>
                    {whatIfResult.result.is_gain ? '+' : ''}{formatCurrency(whatIfResult.result.gain_loss)}
                  </div>
                </div>

                {/* Estimated Tax */}
                <div style={{
                  padding: '16px',
                  background: 'var(--bg-white)',
                  borderRadius: '8px',
                  border: '2px solid var(--primary)'
                }}>
                  <div style={{ color: 'var(--text-secondary)', marginBottom: '4px' }}>
                    Estimated {whatIfResult.tax_type} ({whatIfResult.result.tax_rate})
                  </div>
                  <div style={{ fontSize: '24px', fontWeight: 600, color: 'var(--primary)' }}>
                    {formatCurrency(whatIfResult.result.estimated_tax)}
                  </div>
                </div>
              </div>

              {/* Exemption Info */}
              <div style={{
                marginTop: '16px',
                padding: '12px',
                background: 'var(--bg-secondary)',
                borderRadius: '8px',
                fontSize: '14px'
              }}>
                <strong>Note:</strong> {whatIfResult.result.exemption_info}
              </div>

              {/* Lots Used */}
              {whatIfResult.cost_basis.lots_used.length > 0 && (
                <div style={{ marginTop: '16px' }}>
                  <h4 style={{ marginBottom: '8px' }}>Cost Basis Breakdown (FIFO)</h4>
                  <table className="table" style={{ fontSize: '14px' }}>
                    <thead>
                      <tr>
                        <th>Acquisition Date</th>
                        <th style={{ textAlign: 'right' }}>Quantity</th>
                        <th style={{ textAlign: 'right' }}>Unit Cost</th>
                        <th style={{ textAlign: 'right' }}>Cost Basis</th>
                      </tr>
                    </thead>
                    <tbody>
                      {whatIfResult.cost_basis.lots_used.map((lot, idx) => (
                        <tr key={idx}>
                          <td>{new Date(lot.acquisition_date).toLocaleDateString()}</td>
                          <td style={{ textAlign: 'right' }}>{lot.quantity.toFixed(4)}</td>
                          <td style={{ textAlign: 'right' }}>{formatCurrency(lot.unit_cost)}</td>
                          <td style={{ textAlign: 'right' }}>{formatCurrency(lot.cost_basis)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Disclaimer */}
              <div style={{
                marginTop: '16px',
                padding: '12px',
                background: 'rgba(251, 191, 36, 0.1)',
                borderRadius: '8px',
                fontSize: '13px',
                color: 'var(--warning)'
              }}>
                {whatIfResult.note}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Loss Harvesting Tab */}
      {activeTab === 'harvesting' && (
        <div className="card">
          <h2 style={{ marginTop: 0 }}>Loss Harvesting Opportunities</h2>
          <p style={{ color: 'var(--text-secondary)', marginBottom: '24px' }}>
            Identify positions with unrealized losses that could be sold to offset gains and reduce your tax bill.
            <br />
            <strong>Warning:</strong> Watch out for the 4-week "bed & breakfast" rule if you rebuy.
          </p>

          {harvestingLoading ? (
            <p>Loading opportunities...</p>
          ) : opportunities.length === 0 ? (
            <p style={{ color: 'var(--text-secondary)' }}>
              No positions found. Upload transactions first.
            </p>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Asset</th>
                  <th>Tax Type</th>
                  <th style={{ textAlign: 'right' }}>Quantity</th>
                  <th style={{ textAlign: 'right' }}>Avg Cost</th>
                  <th style={{ textAlign: 'right' }}>Cost Basis</th>
                  <th style={{ textAlign: 'right' }}>Current Price</th>
                  <th style={{ textAlign: 'right' }}>Unrealized</th>
                  <th style={{ textAlign: 'right' }}>Tax Savings</th>
                </tr>
              </thead>
              <tbody>
                {opportunities.map(opp => {
                  const unrealized = calculateUnrealizedGainLoss(opp)
                  const savings = calculatePotentialTaxSavings(opp)

                  return (
                    <tr key={opp.isin}>
                      <td>
                        <div style={{ fontWeight: 500 }}>{opp.name}</div>
                        <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                          {opp.isin}
                        </div>
                      </td>
                      <td>
                        <span style={{
                          padding: '2px 8px',
                          borderRadius: '4px',
                          fontSize: '12px',
                          background: opp.tax_type === 'Exit Tax' ? 'rgba(251, 191, 36, 0.2)' : 'rgba(59, 130, 246, 0.2)',
                          color: opp.tax_type === 'Exit Tax' ? 'var(--warning)' : 'var(--primary)'
                        }}>
                          {opp.tax_type}
                        </span>
                      </td>
                      <td style={{ textAlign: 'right' }}>{opp.quantity.toFixed(4)}</td>
                      <td style={{ textAlign: 'right' }}>{formatCurrency(opp.average_cost)}</td>
                      <td style={{ textAlign: 'right' }}>{formatCurrency(opp.total_cost_basis)}</td>
                      <td style={{ textAlign: 'right' }}>
                        <input
                          type="number"
                          className="form-input"
                          style={{ width: '100px', padding: '4px 8px', textAlign: 'right' }}
                          placeholder="Enter"
                          step="0.01"
                          value={currentPrices[opp.isin] || ''}
                          onChange={e => setCurrentPrices({
                            ...currentPrices,
                            [opp.isin]: e.target.value
                          })}
                        />
                      </td>
                      <td style={{
                        textAlign: 'right',
                        color: unrealized === null ? 'var(--text-secondary)' :
                          unrealized >= 0 ? 'var(--success)' : 'var(--error)'
                      }}>
                        {unrealized === null ? '-' :
                          `${unrealized >= 0 ? '+' : ''}${formatCurrency(unrealized)}`}
                      </td>
                      <td style={{
                        textAlign: 'right',
                        fontWeight: savings ? 600 : 400,
                        color: savings ? 'var(--success)' : 'var(--text-secondary)'
                      }}>
                        {savings === null ? '-' : formatCurrency(savings)}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}

          <div style={{
            marginTop: '24px',
            padding: '16px',
            background: 'var(--bg-secondary)',
            borderRadius: '8px'
          }}>
            <h4 style={{ marginTop: 0 }}>How Tax Loss Harvesting Works</h4>
            <ol style={{ margin: 0, paddingLeft: '20px', lineHeight: 1.8 }}>
              <li>Sell investments that are currently at a loss</li>
              <li>Use those losses to offset capital gains from profitable sales</li>
              <li>If losses exceed gains, carry forward to future years (CGT only)</li>
              <li><strong>Important:</strong> Wait at least 4 weeks before rebuying the same asset to avoid the "bed & breakfast" rule</li>
            </ol>
          </div>
        </div>
      )}
    </div>
  )
}
