import { useState, useEffect, useRef } from 'react'
import {
  getPersons,
  createPerson,
  updatePerson,
  deletePerson,
  setPrimaryPerson,
  exportBackup,
  importBackup,
  type Person,
  type PersonCreate,
  type BackupData,
} from '../services/api'

const COLORS = [
  '#3B82F6', // Blue (default)
  '#EC4899', // Pink
  '#10B981', // Green
  '#F59E0B', // Amber
  '#8B5CF6', // Purple
  '#06B6D4', // Cyan
]

export default function Settings() {
  const [persons, setPersons] = useState<Person[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showAddForm, setShowAddForm] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)

  // Form state
  const [formName, setFormName] = useState('')
  const [formColor, setFormColor] = useState(COLORS[1]) // Pink for spouse by default
  const [formPPS, setFormPPS] = useState('')

  // Backup/restore state
  const [backupLoading, setBackupLoading] = useState(false)
  const [backupMessage, setBackupMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    loadPersons()
  }, [])

  async function loadPersons() {
    try {
      setLoading(true)
      const data = await getPersons()
      setPersons(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load')
    } finally {
      setLoading(false)
    }
  }

  async function handleAddPerson() {
    if (!formName.trim()) return

    try {
      const newPerson: PersonCreate = {
        name: formName.trim(),
        color: formColor,
        pps_number: formPPS.trim() || undefined,
        is_primary: persons.length === 0, // First person is primary
      }
      await createPerson(newPerson)
      setFormName('')
      setFormPPS('')
      setFormColor(COLORS[1])
      setShowAddForm(false)
      loadPersons()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add person')
    }
  }

  async function handleUpdatePerson(id: number) {
    if (!formName.trim()) return

    try {
      await updatePerson(id, {
        name: formName.trim(),
        color: formColor,
        pps_number: formPPS.trim() || undefined,
      })
      setEditingId(null)
      setFormName('')
      setFormPPS('')
      loadPersons()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update')
    }
  }

  async function handleDeletePerson(id: number) {
    if (!confirm('Delete this person? Their transactions will become unassigned.')) return

    try {
      await deletePerson(id)
      loadPersons()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete')
    }
  }

  async function handleSetPrimary(id: number) {
    try {
      await setPrimaryPerson(id)
      loadPersons()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to set primary')
    }
  }

  function startEdit(person: Person) {
    setEditingId(person.id)
    setFormName(person.name)
    setFormColor(person.color)
    setFormPPS(person.pps_number || '')
  }

  function cancelEdit() {
    setEditingId(null)
    setFormName('')
    setFormPPS('')
    setFormColor(COLORS[1])
  }

  async function handleExportBackup() {
    try {
      setBackupLoading(true)
      setBackupMessage(null)
      const data = await exportBackup()

      // Create downloadable file
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `tax-calculator-backup-${new Date().toISOString().split('T')[0]}.json`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)

      setBackupMessage({
        type: 'success',
        text: `Backup created: ${data.counts.persons} persons, ${data.counts.assets} assets, ${data.counts.transactions} transactions, ${data.counts.income_events} income events`
      })
    } catch (err) {
      setBackupMessage({ type: 'error', text: err instanceof Error ? err.message : 'Export failed' })
    } finally {
      setBackupLoading(false)
    }
  }

  async function handleImportBackup(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (!file) return

    try {
      setBackupLoading(true)
      setBackupMessage(null)

      const text = await file.text()
      const data = JSON.parse(text) as BackupData

      if (!data.export_version || !data.data) {
        throw new Error('Invalid backup file format')
      }

      const shouldClear = window.confirm(
        'Do you want to REPLACE all existing data?\n\n' +
        'Click OK to replace everything with the backup.\n' +
        'Click Cancel to MERGE the backup with existing data (duplicates will be skipped).'
      )

      const result = await importBackup(data, shouldClear)
      setBackupMessage({ type: 'success', text: result.message })

      // Reload persons
      loadPersons()
    } catch (err) {
      setBackupMessage({ type: 'error', text: err instanceof Error ? err.message : 'Import failed' })
    } finally {
      setBackupLoading(false)
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    }
  }

  const isFamilyMode = persons.length > 1

  return (
    <div>
      <h1 style={{ marginBottom: '24px' }}>Settings</h1>

      {error && (
        <div className="alert alert-error" style={{ marginBottom: '16px' }}>
          {error}
          <button onClick={() => setError(null)} style={{ float: 'right', background: 'none', border: 'none', cursor: 'pointer' }}>×</button>
        </div>
      )}

      {/* Family Tax Returns Section */}
      <div className="card">
        <h2 className="card-title">
          <span style={{ marginRight: '8px' }}>👨‍👩‍👧</span>
          Family Tax Returns
        </h2>

        <p style={{ color: 'var(--text-secondary)', marginBottom: '16px' }}>
          {isFamilyMode ? (
            <>Track investments separately for each family member. Each person gets their own €1,270 CGT exemption.</>
          ) : (
            <>Add your spouse or partner to track investments separately and file joint Form 11.</>
          )}
        </p>

        {/* Current persons list */}
        {loading ? (
          <div style={{ padding: '20px', textAlign: 'center', color: 'var(--text-secondary)' }}>
            Loading...
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {persons.map(person => (
              <div
                key={person.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '12px',
                  padding: '12px 16px',
                  background: 'var(--bg-secondary)',
                  borderRadius: '8px',
                  borderLeft: `4px solid ${person.color}`,
                }}
              >
                {editingId === person.id ? (
                  // Edit mode
                  <div style={{ flex: 1, display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
                    <input
                      type="text"
                      className="form-input"
                      value={formName}
                      onChange={e => setFormName(e.target.value)}
                      placeholder="Name"
                      style={{ width: '150px' }}
                      autoFocus
                    />
                    <input
                      type="text"
                      className="form-input"
                      value={formPPS}
                      onChange={e => setFormPPS(e.target.value)}
                      placeholder="PPS (optional)"
                      style={{ width: '120px' }}
                    />
                    <div style={{ display: 'flex', gap: '4px' }}>
                      {COLORS.map(color => (
                        <button
                          key={color}
                          onClick={() => setFormColor(color)}
                          style={{
                            width: '24px',
                            height: '24px',
                            borderRadius: '50%',
                            background: color,
                            border: formColor === color ? '2px solid var(--text-primary)' : '2px solid transparent',
                            cursor: 'pointer',
                          }}
                        />
                      ))}
                    </div>
                    <button className="btn btn-primary" onClick={() => handleUpdatePerson(person.id)} style={{ padding: '6px 12px' }}>
                      Save
                    </button>
                    <button className="btn btn-secondary" onClick={cancelEdit} style={{ padding: '6px 12px' }}>
                      Cancel
                    </button>
                  </div>
                ) : (
                  // View mode
                  <>
                    <div
                      style={{
                        width: '32px',
                        height: '32px',
                        borderRadius: '50%',
                        background: person.color,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: 'white',
                        fontWeight: 600,
                        fontSize: '14px',
                      }}
                    >
                      {person.name.charAt(0).toUpperCase()}
                    </div>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: 500, display: 'flex', alignItems: 'center', gap: '8px' }}>
                        {person.name}
                        {person.is_primary && (
                          <span style={{
                            fontSize: '11px',
                            padding: '2px 6px',
                            background: 'var(--primary)',
                            color: 'white',
                            borderRadius: '4px',
                          }}>
                            Primary
                          </span>
                        )}
                      </div>
                      {person.pps_number && (
                        <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                          PPS: {person.pps_number}
                        </div>
                      )}
                    </div>
                    <div style={{ display: 'flex', gap: '8px' }}>
                      {!person.is_primary && (
                        <button
                          className="btn btn-secondary"
                          onClick={() => handleSetPrimary(person.id)}
                          style={{ padding: '4px 8px', fontSize: '12px' }}
                          title="Set as primary taxpayer"
                        >
                          Make Primary
                        </button>
                      )}
                      <button
                        className="btn btn-secondary"
                        onClick={() => startEdit(person)}
                        style={{ padding: '4px 8px', fontSize: '12px' }}
                      >
                        Edit
                      </button>
                      {!person.is_primary && (
                        <button
                          className="btn btn-secondary"
                          onClick={() => handleDeletePerson(person.id)}
                          style={{ padding: '4px 8px', fontSize: '12px', color: 'var(--danger)' }}
                        >
                          Delete
                        </button>
                      )}
                    </div>
                  </>
                )}
              </div>
            ))}

            {/* Add person form or button */}
            {showAddForm ? (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '12px 16px',
                  background: 'var(--bg-secondary)',
                  borderRadius: '8px',
                  flexWrap: 'wrap',
                }}
              >
                <input
                  type="text"
                  className="form-input"
                  value={formName}
                  onChange={e => setFormName(e.target.value)}
                  placeholder={persons.length === 0 ? "Your name" : "Spouse/Partner name"}
                  style={{ width: '150px' }}
                  autoFocus
                />
                <input
                  type="text"
                  className="form-input"
                  value={formPPS}
                  onChange={e => setFormPPS(e.target.value)}
                  placeholder="PPS (optional)"
                  style={{ width: '120px' }}
                />
                <div style={{ display: 'flex', gap: '4px' }}>
                  {COLORS.map(color => (
                    <button
                      key={color}
                      onClick={() => setFormColor(color)}
                      style={{
                        width: '24px',
                        height: '24px',
                        borderRadius: '50%',
                        background: color,
                        border: formColor === color ? '2px solid var(--text-primary)' : '2px solid transparent',
                        cursor: 'pointer',
                      }}
                    />
                  ))}
                </div>
                <button className="btn btn-primary" onClick={handleAddPerson} style={{ padding: '6px 12px' }}>
                  Add
                </button>
                <button className="btn btn-secondary" onClick={() => { setShowAddForm(false); setFormName(''); setFormPPS(''); }} style={{ padding: '6px 12px' }}>
                  Cancel
                </button>
              </div>
            ) : (
              <button
                className="btn btn-secondary"
                onClick={() => {
                  setShowAddForm(true)
                  setFormColor(persons.length === 0 ? COLORS[0] : COLORS[1])
                }}
                style={{ alignSelf: 'flex-start' }}
              >
                {persons.length === 0 ? '+ Set Up Your Profile' : '+ Add Spouse/Partner'}
              </button>
            )}
          </div>
        )}

        {isFamilyMode && (
          <div className="alert alert-info" style={{ marginTop: '16px' }}>
            <strong>Family Mode Enabled</strong>
            <br />
            When uploading PDFs, you&apos;ll be asked whose transactions they are.
            Each person&apos;s taxes are calculated separately with their own exemptions.
          </div>
        )}
      </div>

      {/* Backup & Restore Section */}
      <div className="card" style={{ marginTop: '24px' }}>
        <h2 className="card-title">
          <span style={{ marginRight: '8px' }}>💾</span>
          Backup & Restore
        </h2>

        <p style={{ color: 'var(--text-secondary)', marginBottom: '16px' }}>
          Export your data as a JSON file for backup, or import from a previous backup.
        </p>

        {backupMessage && (
          <div
            className={`alert ${backupMessage.type === 'success' ? 'alert-success' : 'alert-error'}`}
            style={{ marginBottom: '16px' }}
          >
            {backupMessage.text}
            <button
              onClick={() => setBackupMessage(null)}
              style={{ float: 'right', background: 'none', border: 'none', cursor: 'pointer' }}
            >
              ×
            </button>
          </div>
        )}

        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
          <button
            className="btn btn-primary"
            onClick={handleExportBackup}
            disabled={backupLoading}
          >
            {backupLoading ? 'Exporting...' : 'Export Backup'}
          </button>

          <input
            type="file"
            ref={fileInputRef}
            accept=".json"
            onChange={handleImportBackup}
            style={{ display: 'none' }}
          />
          <button
            className="btn btn-secondary"
            onClick={() => fileInputRef.current?.click()}
            disabled={backupLoading}
          >
            {backupLoading ? 'Importing...' : 'Import Backup'}
          </button>
        </div>

        <div style={{
          marginTop: '16px',
          padding: '12px',
          background: 'var(--bg-secondary)',
          borderRadius: '8px',
          fontSize: '13px',
          color: 'var(--text-secondary)'
        }}>
          <strong>Tip:</strong> Export includes all persons, assets, transactions, and income events.
          When importing, you can choose to replace all data or merge with existing data.
        </div>
      </div>

      {/* About Section */}
      <div className="card" style={{ marginTop: '24px' }}>
        <h2 className="card-title">About</h2>
        <table className="table">
          <tbody>
            <tr>
              <td>Version</td>
              <td style={{ textAlign: 'right' }}>0.3</td>
            </tr>
            <tr>
              <td>Tax Year</td>
              <td style={{ textAlign: 'right' }}>2024</td>
            </tr>
            <tr>
              <td>CGT Rate</td>
              <td style={{ textAlign: 'right' }}>33% (€1,270 exemption per person)</td>
            </tr>
            <tr>
              <td>Exit Tax Rate</td>
              <td style={{ textAlign: 'right' }}>41% (no exemption)</td>
            </tr>
            <tr>
              <td>DIRT Rate</td>
              <td style={{ textAlign: 'right' }}>33%</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  )
}
