import React, { useState } from 'react'
import api from '../services/api'

const Login = ({ onLogin }) => {
  const [isRegister, setIsRegister] = useState(false)
  const [showJoinTeam, setShowJoinTeam] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [teamName, setTeamName] = useState('')
  const [invitationCode, setInvitationCode] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      let response
      if (isRegister) {
        response = await api.post('/auth/register', {
          email,
          password,
          team_name: teamName
        })
      } else {
        response = await api.post('/auth/login', {
          email,
          password
        })
      }

      localStorage.setItem('token', response.data.token)
      localStorage.setItem('user', JSON.stringify(response.data.user))
      onLogin(response.data.user)
    } catch (err) {
      setError(err.response?.data?.error || 'An error occurred')
    } finally {
      setLoading(false)
    }
  }

  const handleJoinTeamWithLogin = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      // Use the new join-with-code endpoint that handles registration/login and joining
      const response = await api.post('/auth/join-with-code', {
        email,
        password,
        invitation_code: invitationCode
      })

      // Store token and user info
      localStorage.setItem('token', response.data.token)
      localStorage.setItem('user', JSON.stringify(response.data.user))
      onLogin(response.data.user)
    } catch (err) {
      setError(err.response?.data?.error || 'An error occurred')
    } finally {
      setLoading(false)
    }
  }

  // Show join team form if user clicked "Join with invitation code"
  if (showJoinTeam) {
    return (
      <div className="container">
        <div className="card" style={{ maxWidth: '400px', margin: '50px auto' }}>
          <h2>Join Team with Invitation Code</h2>
          <p style={{ marginBottom: '15px', color: '#666', fontSize: '14px' }}>
            Enter your login credentials and invitation code to join an existing team.
          </p>
          <form onSubmit={handleJoinTeamWithLogin}>
            <label>
              Email:
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </label>
            <label>
              Password:
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </label>
            <label>
              Invitation Code:
              <input
                type="text"
                value={invitationCode}
                onChange={(e) => setInvitationCode(e.target.value)}
                required
                placeholder="Enter invitation code"
              />
            </label>
            {error && <div className="error">{error}</div>}
            <button type="submit" disabled={loading}>
              {loading ? 'Joining...' : 'Join Team'}
            </button>
          </form>
          <p style={{ marginTop: '20px', textAlign: 'center' }}>
            <a href="#" onClick={(e) => { e.preventDefault(); setShowJoinTeam(false); setError('') }}>
              Back to Login
            </a>
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="container">
      <div className="card" style={{ maxWidth: '400px', margin: '50px auto' }}>
        <h2>{isRegister ? 'Register' : 'Login'}</h2>
        <form onSubmit={handleSubmit}>
          <label>
            Email:
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </label>
          <label>
            Password:
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>
          {isRegister && (
            <label>
              Team Name:
              <input
                type="text"
                value={teamName}
                onChange={(e) => setTeamName(e.target.value)}
                required
              />
            </label>
          )}
          {error && <div className="error">{error}</div>}
          <button type="submit" disabled={loading}>
            {loading ? (isRegister ? 'Registering...' : 'Logging in...') : (isRegister ? 'Register' : 'Login')}
          </button>
        </form>
        <p style={{ marginTop: '20px', textAlign: 'center' }}>
          {isRegister ? (
            <>
              Already have an account?{' '}
              <a href="#" onClick={(e) => { e.preventDefault(); setIsRegister(false); setError('') }}>
                Login
              </a>
            </>
          ) : (
            <>
              Don't have an account?{' '}
              <a href="#" onClick={(e) => { e.preventDefault(); setIsRegister(true); setError('') }}>
                Register
              </a>
            </>
          )}
        </p>
        {!isRegister && (
          <p style={{ marginTop: '10px', textAlign: 'center' }}>
            <a href="#" onClick={(e) => { e.preventDefault(); setShowJoinTeam(true); setError('') }}>
              Join with invitation code
            </a>
          </p>
        )}
      </div>
    </div>
  )
}

export default Login

