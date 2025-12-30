import { useState, useRef } from 'react'
import { uploadPDF, type UploadResponse } from '../services/api'

export default function Upload() {
  const [uploading, setUploading] = useState(false)
  const [result, setResult] = useState<UploadResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
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
      const response = await uploadPDF(file)
      setResult(response)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      setUploading(false)
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

        {result && (
          <div className="alert alert-success" style={{ marginTop: '16px' }}>
            <strong>Upload successful!</strong>
            <p style={{ marginTop: '8px' }}>
              Imported {result.transactions_imported} transactions and{' '}
              {result.income_events_imported} income events for tax year {result.tax_year}.
            </p>
          </div>
        )}
      </div>

      <div className="card">
        <h2 className="card-title">Supported Data</h2>
        <p style={{ marginBottom: '16px', color: 'var(--text-secondary)' }}>
          The parser extracts the following from Trade Republic annual tax reports:
        </p>
        <ul style={{ marginLeft: '20px', lineHeight: '2' }}>
          <li><strong>Section V:</strong> Interest payments, dividends, distributions</li>
          <li><strong>Section VI:</strong> Realized gains and losses</li>
          <li><strong>Section VII:</strong> Transaction history (buys and sells)</li>
        </ul>
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
    </div>
  )
}
