import React, { useState, useEffect } from 'react'
import api from '../services/api'

const TeamManagement = ({ user, onUpdate }) => {
  const [invitationCodes, setInvitationCodes] = useState([])
  const [members, setMembers] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [copiedCodeId, setCopiedCodeId] = useState(null)
  const [showGenerateForm, setShowGenerateForm] = useState(false)
  const [generateEmail, setGenerateEmail] = useState('')

  useEffect(() => {
    loadInvitationCodes()
    loadMembers()
  }, [])

  const loadInvitationCodes = async () => {
    try {
      const response = await api.get('/team/invitation-codes')
      setInvitationCodes(response.data.invitation_codes || [])
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to load invitation codes')
    }
  }

  const handleGenerateCode = async (e) => {
    e.preventDefault()
    if (!generateEmail) {
      setError('Email is required')
      return
    }
    
    setLoading(true)
    setError('')
    try {
      const response = await api.post('/team/invitation-code', {
        email: generateEmail
      })
      setGenerateEmail('')
      setShowGenerateForm(false)
      loadInvitationCodes()
      alert('Invitation code generated!')
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to generate invitation code')
    } finally {
      setLoading(false)
    }
  }

  const loadMembers = async () => {
    try {
      const response = await api.get('/team/members')
      setMembers(response.data.members)
    } catch (err) {
      console.error('Failed to load members:', err)
    }
  }

  const handlePromote = async (userId) => {
    if (!window.confirm('Promote this user to admin?')) {
      return
    }

    setLoading(true)
    try {
      await api.put('/team/promote', { user_id: userId })
      loadMembers()
      onUpdate()
    } catch (err) {
      alert(err.response?.data?.error || 'Failed to promote user')
    } finally {
      setLoading(false)
    }
  }

  const handleCopyCode = async (code, codeId) => {
    if (!code) return
    
    try {
      await navigator.clipboard.writeText(code)
      setCopiedCodeId(codeId)
      setTimeout(() => setCopiedCodeId(null), 2000)
    } catch (err) {
      // Fallback for older browsers
      const textArea = document.createElement('textarea')
      textArea.value = code
      textArea.style.position = 'fixed'
      textArea.style.opacity = '0'
      document.body.appendChild(textArea)
      textArea.select()
      try {
        document.execCommand('copy')
        setCopiedCodeId(codeId)
        setTimeout(() => setCopiedCodeId(null), 2000)
      } catch (err) {
        alert('Failed to copy invitation code')
      }
      document.body.removeChild(textArea)
    }
  }

  return (
    <div className="card">
      <h2>Team Management (Admin)</h2>
      {error && <div className="error">{error}</div>}
      
      <div style={{ marginBottom: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
          <h3>Invitation Codes</h3>
          <button
            onClick={() => setShowGenerateForm(!showGenerateForm)}
            disabled={loading}
            style={{ 
              fontSize: '14px', 
              padding: '8px 16px',
              backgroundColor: '#28a745'
            }}
          >
            {showGenerateForm ? 'Cancel' : '+ Generate Code'}
          </button>
        </div>

        {showGenerateForm && (
          <div style={{ 
            border: '1px solid #ddd', 
            borderRadius: '4px', 
            padding: '15px', 
            marginBottom: '15px',
            backgroundColor: '#f9f9f9'
          }}>
            <h4>Generate Invitation Code</h4>
            <form onSubmit={handleGenerateCode}>
              <label>
                Email Address:
                <input
                  type="email"
                  value={generateEmail}
                  onChange={(e) => setGenerateEmail(e.target.value)}
                  required
                  placeholder="Enter email address"
                  style={{ marginTop: '5px' }}
                />
              </label>
              <p style={{ fontSize: '12px', color: '#666', marginTop: '5px' }}>
                This code will only work for the specified email address.
              </p>
              <button type="submit" disabled={loading} style={{ marginTop: '10px' }}>
                {loading ? 'Generating...' : 'Generate Code'}
              </button>
            </form>
          </div>
        )}

        {invitationCodes.length === 0 ? (
          <p style={{ color: '#666' }}>No invitation codes generated yet. Click "Generate Code" to create one.</p>
        ) : (
          <div>
            <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: '10px' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #ddd' }}>
                  <th style={{ padding: '10px', textAlign: 'left' }}>Email</th>
                  <th style={{ padding: '10px', textAlign: 'left' }}>Code</th>
                  <th style={{ padding: '10px', textAlign: 'left' }}>Status</th>
                  <th style={{ padding: '10px', textAlign: 'left' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {invitationCodes.map(code => (
                  <tr key={code.id} style={{ borderBottom: '1px solid #eee' }}>
                    <td style={{ padding: '10px' }}>{code.email}</td>
                    <td style={{ padding: '10px', fontFamily: 'monospace', fontSize: '16px', fontWeight: 'bold' }}>
                      <span
                        onClick={() => handleCopyCode(code.code, code.id)}
                        style={{
                          cursor: 'pointer',
                          color: copiedCodeId === code.id ? '#28a745' : 'inherit',
                          userSelect: 'none'
                        }}
                        title="Click to copy"
                      >
                        {code.code}
                        {copiedCodeId === code.id && (
                          <span style={{ marginLeft: '10px', fontSize: '12px', color: '#28a745' }}>✓ Copied!</span>
                        )}
                      </span>
                    </td>
                    <td style={{ padding: '10px' }}>
                      {code.used ? (
                        <span style={{ color: '#6c757d' }}>Used</span>
                      ) : (
                        <span style={{ color: '#28a745' }}>Active</span>
                      )}
                    </td>
                    <td style={{ padding: '10px' }}>
                      {!code.used && (
                        <span style={{ fontSize: '12px', color: '#666' }}>
                          Click code to copy
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p style={{ fontSize: '12px', color: '#666', marginTop: '10px' }}>
              <strong>Note:</strong> Each code is email-specific and can only be used once by the specified email address.
            </p>
          </div>
        )}
      </div>

      <div>
        <h3>Team Members</h3>
        {members.length === 0 ? (
          <p>No members yet.</p>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #ddd' }}>
                <th style={{ padding: '10px', textAlign: 'left' }}>Email</th>
                <th style={{ padding: '10px', textAlign: 'left' }}>Role</th>
                <th style={{ padding: '10px', textAlign: 'left' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {members.map(member => (
                <tr key={member.id} style={{ borderBottom: '1px solid #eee' }}>
                  <td style={{ padding: '10px' }}>{member.email}</td>
                  <td style={{ padding: '10px' }}>{member.role}</td>
                  <td style={{ padding: '10px' }}>
                    {member.role === 'member' && (
                      <button
                        onClick={() => handlePromote(member.id)}
                        disabled={loading}
                        style={{ fontSize: '12px', padding: '5px 10px' }}
                      >
                        Promote to Admin
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

export default TeamManagement

