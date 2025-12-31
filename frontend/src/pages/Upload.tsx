import { useState, useRef } from 'react'
import { uploadPDF, clearAllData, type UploadResponse } from '../services/api'

export default function Upload() {
  const [uploading, setUploading] = useState(false)
  const [clearing, setClearing] = useState(false)
  const [result, setResult] = useState<UploadResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [clearMessage, setClearMessage] = useState<string | null>(null)
  const [dragActive, setDragActive] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  async function handleFile(file: File) {
    if (!file.name.endsWith('.pdf')) {
      setError('Please upload a PDF file')
      return
    }

    try {
      setUploading(true)
      setError(null)
      setResult(null)
      setClearMessage(null)
      const response = await uploadPDF(file)
      setResult(response)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  async function handleClearData() {
    if (!confirm('Are you sure you want to delete all data? This cannot be undone.')) {
      return
    }

    try {
      setClearing(true)
      setError(null)
      setResult(null)
      const response = await clearAllData()
      setClearMessage(`Deleted ${response.deleted.transactions} transactions, ${response.deleted.income_events} income events, and ${response.deleted.assets} assets.`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to clear data')
    } finally {
      setClearing(false)
    }
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault()
    setDragActive(false)
    if (e.dataTransfer.files?.[0]) {
      handleFile(e.dataTransfer.files[0])
    }
  }

  function handleDrag(e: React.DragEvent) {
    e.preventDefault()
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true)
    } else if (e.type === 'dragleave') {
      setDragActive(false)
    }
  }

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    if (e.target.files?.[0]) {
      handleFile(e.target.files[0])
    }
  }

  return (
    <div>
      <h1 style={{ marginBottom: '24px' }}>Upload Trade Republic Tax Report</h1>

      <div className="card">
        <div
          className={`upload-zone ${dragActive ? 'active' : ''}`}
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
          onClick={() => inputRef.current?.click()}
        >
          <input
            ref={inputRef}
            type="file"
            accept=".pdf"
            onChange={handleChange}
          />
          {uploading ? (
            <div>
              <div style={{ fontSize: '48px', marginBottom: '16px' }}>Processing...</div>
              <p>Parsing your tax report...</p>
            </div>
          ) : (
            <div>
              <div style={{ fontSize: '48px', marginBottom: '16px' }}>PDF</div>
              <p style={{ fontSize: '18px', marginBottom: '8px' }}>
                Drop your Trade Republic tax report here
              </p>
              <p style={{ color: 'var(--text-secondary)' }}>
                or click to select a file
              </p>
            </div>
          )}
        </div>

        {error && (
          <div className="alert alert-error" style={{ marginTop: '16px' }}>
            {error}
          </div>
        )}

        {clearMessage && (
          <div className="alert alert-success" style={{ marginTop: '16px' }}>
            {clearMessage}
          </div>
        )}

        {result && (
          <div style={{ marginTop: '24px' }}>
            <div className="alert alert-success">
              <strong>Upload successful!</strong>
              <p style={{ marginTop: '8px' }}>
                Tax Year: <strong>{result.tax_year}</strong> ({result.period.start} to {result.period.end})
              </p>
              {result.skipped_duplicates > 0 && (
                <p style={{ marginTop: '4px', color: 'var(--warning)' }}>
                  Skipped {result.skipped_duplicates} duplicate records
                </p>
              )}
            </div>

            {/* Data Summary */}
            <h3 style={{ marginTop: '24px', marginBottom: '16px' }}>Imported Data Summary</h3>
            <div className="stat-grid">
              <div className="stat-card">
                <div className="stat-label">Buys</div>
                <div className="stat-value">{result.summary.buys.count}</div>
                <div style={{ fontSize: '14px', color: 'var(--text-secondary)' }}>
                  {formatCurrency(result.summary.buys.total)}
                </div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Sells</div>
                <div className="stat-value">{result.summary.sells.count}</div>
                <div style={{ fontSize: '14px', color: 'var(--text-secondary)' }}>
                  {formatCurrency(result.summary.sells.total)}
                </div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Interest Payments</div>
                <div className="stat-value">{result.summary.interest.count}</div>
                <div style={{ fontSize: '14px', color: 'var(--text-secondary)' }}>
                  {formatCurrency(result.summary.interest.total)}
                </div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Dividends</div>
                <div className="stat-value">{result.summary.dividends.count}</div>
                <div style={{ fontSize: '14px', color: 'var(--text-secondary)' }}>
                  {formatCurrency(result.summary.dividends.total)}
                </div>
              </div>
            </div>

            <div style={{ marginTop: '24px', display: 'flex', gap: '12px' }}>
              <a href="/portfolio" className="btn btn-primary">
                View Portfolio
              </a>
              <a href="/tax" className="btn btn-secondary">
                Calculate Tax
              </a>
            </div>
          </div>
        )}
      </div>

      <div className="card">
        <h2 className="card-title">Supported Data</h2>
        <p style={{ marginBottom: '16px', color: 'var(--text-secondary)' }}>
          The parser extracts the following from Trade Republic annual tax reports:
        </p>
        <table className="table">
          <thead>
            <tr>
              <th>Section</th>
              <th>Description</th>
              <th>Tax Treatment</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><strong>Section V</strong></td>
              <td>Interest payments</td>
              <td>DIRT 33%</td>
            </tr>
            <tr>
              <td><strong>Section V</strong></td>
              <td>Dividends & distributions</td>
              <td>Marginal income tax rate</td>
            </tr>
            <tr>
              <td><strong>Section VII</strong></td>
              <td>Stock trades (Buy/Sell)</td>
              <td>CGT 33% (€1,270 exemption)</td>
            </tr>
            <tr>
              <td><strong>Section VII</strong></td>
              <td>EU ETF trades (Buy/Sell)</td>
              <td>Exit Tax 41% (no exemption)</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div className="card">
        <h2 className="card-title">Important Notes</h2>
        <div className="alert alert-info">
          <strong>Trade Republic uses FIFO</strong>, but Irish CGT requires different matching rules:
          <ol style={{ marginTop: '8px', marginLeft: '20px' }}>
            <li>Same-day acquisitions</li>
            <li>Acquisitions within the next 4 weeks (bed &amp; breakfast rule)</li>
            <li>FIFO for remaining shares</li>
          </ol>
          <p style={{ marginTop: '8px' }}>
            This calculator recalculates gains using the correct Irish rules.
          </p>
        </div>
      </div>

      {/* Data Management */}
      <div className="card" style={{ borderColor: 'var(--danger)' }}>
        <h2 className="card-title" style={{ color: 'var(--danger)' }}>Data Management</h2>
        <p style={{ marginBottom: '16px', color: 'var(--text-secondary)' }}>
          If you need to start fresh or re-import your data, you can clear all existing data below.
        </p>
        <button
          className="btn"
          style={{ background: 'var(--danger)', color: 'white' }}
          onClick={handleClearData}
          disabled={clearing}
        >
          {clearing ? 'Clearing...' : 'Clear All Data'}
        </button>
      </div>
    </div>
  )
}

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-IE', {
    style: 'currency',
    currency: 'EUR',
  }).format(amount)
}
