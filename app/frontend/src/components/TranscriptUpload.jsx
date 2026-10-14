import React, { useState, useEffect } from 'react'
import api from '../services/api'

// Upload a meeting transcript and process it under a chosen defense profile.
// This is the demo surface: pick "none" to see the injection land, then switch
// defenses to watch them block or neutralize the same payload.
const TranscriptUpload = ({ onSuccess }) => {
  const [file, setFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)
  const [defenses, setDefenses] = useState([])
  const [defense, setDefense] = useState('none')

  useEffect(() => {
    api.get('/ai/defenses')
      .then((res) => setDefenses(res.data.defenses || []))
      .catch(() => setDefenses([{ name: 'none', description: 'Baseline', available: true }]))
  }, [])

  const handleFileChange = (e) => {
    setFile(e.target.files[0])
    setError('')
    setResult(null)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!file) {
      setError('Please select a file')
      return
    }
    setLoading(true)
    setError('')
    setResult(null)

    const formData = new FormData()
    formData.append('file', file)
    try {
      const response = await api.post(
        `/ai/process-transcript?defense=${encodeURIComponent(defense)}`,
        formData,
        { headers: { 'Content-Type': 'multipart/form-data' } }
      )
      setResult(response.data.result)
      if (onSuccess) onSuccess()
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to process transcript')
    } finally {
      setLoading(false)
    }
  }

  const statusColor = { processed: '#2b7', blocked: '#e67', unavailable: '#999' }

  return (
    <div className="card">
      <h2>Process Meeting Transcript</h2>
      <p style={{ marginBottom: '15px', color: '#666' }}>
        Upload a meeting transcript (.txt or .md). Choose a <strong>defense</strong> to
        compare how each mitigation handles the same transcript.
      </p>

      <form onSubmit={handleSubmit}>
        <label>
          Defense:
          <select value={defense} onChange={(e) => setDefense(e.target.value)} disabled={loading}>
            {defenses.map((d) => (
              <option key={d.name} value={d.name} disabled={!d.available}>
                {d.name}{!d.available ? ` (unavailable: ${d.unavailable_reason})` : ''}
              </option>
            ))}
          </select>
        </label>
        <p style={{ color: '#888', fontSize: '0.85em', margin: '4px 0 12px' }}>
          {defenses.find((d) => d.name === defense)?.description}
        </p>

        <label>
          Select File (.txt or .md):
          <input type="file" accept=".txt,.md,.markdown" onChange={handleFileChange} disabled={loading} />
        </label>

        {error && <div className="error">{error}</div>}

        <button type="submit" disabled={loading || !file} style={{ marginTop: '10px' }}>
          {loading ? 'Processing...' : 'Process Transcript'}
        </button>
      </form>

      {result && (
        <div style={{ marginTop: '15px' }}>
          <div style={{ padding: '8px 12px', borderRadius: '6px', color: '#fff',
                        background: statusColor[result.status] || '#555', display: 'inline-block' }}>
            {result.status.toUpperCase()}
            {result.blocked_by ? ` — blocked by ${result.blocked_by}` : ''}
            {result.unavailable_reason ? ` — ${result.unavailable_reason}` : ''}
          </div>

          {result.detector_detail?.reasoning && (
            <p style={{ color: '#666', fontSize: '0.85em' }}>
              Detector: {result.detector_detail.reasoning}
            </p>
          )}

          {result.status === 'processed' && (
            <>
              <p style={{ marginTop: '10px' }}>
                <strong>{result.tasks?.length || 0}</strong> task(s) created ·{' '}
                <strong>{result.tool_calls?.length || 0}</strong> tool call(s)
                {result.refused ? ' · agent refused' : ''}
              </p>
              {result.tasks?.length > 0 && (
                <ul style={{ marginLeft: '20px' }}>
                  {result.tasks.map((t, i) => (
                    <li key={i}>
                      {t.title} <span style={{ color: '#888' }}>
                        (team_id={t.team_id ?? '?'}{t.assigned_to_email ? `, ${t.assigned_to_email}` : ''})
                      </span>
                    </li>
                  ))}
                </ul>
              )}
              {result.raw_output && (
                <details style={{ marginTop: '8px' }}>
                  <summary style={{ cursor: 'pointer', color: '#666' }}>Raw agent output</summary>
                  <pre style={{ whiteSpace: 'pre-wrap', fontSize: '0.8em', background: '#f6f6f6', padding: '8px' }}>
                    {result.raw_output}
                  </pre>
                </details>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}

export default TranscriptUpload
