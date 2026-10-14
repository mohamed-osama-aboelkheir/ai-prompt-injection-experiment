import React, { useState, useEffect } from 'react'
import api from '../services/api'
import TaskList from './TaskList'
import TeamManagement from './TeamManagement'
import TranscriptUpload from './TranscriptUpload'

const Dashboard = ({ user, onLogout }) => {
  const [tasks, setTasks] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    loadTasks()
  }, [])

  const loadTasks = async () => {
    try {
      const response = await api.get('/tasks')
      setTasks(response.data.tasks)
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to load tasks')
    } finally {
      setLoading(false)
    }
  }

  const handleLogout = () => {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    onLogout()
  }

  if (loading) {
    return <div className="container">Loading...</div>
  }

  return (
    <div className="container">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <div>
          <h1>TasksAI Dashboard</h1>
          <p>Welcome, {user.email} ({user.role})</p>
        </div>
        <button onClick={handleLogout}>Logout</button>
      </div>

      {error && <div className="error">{error}</div>}

      {user.role === 'admin' && (
        <TeamManagement user={user} onUpdate={loadTasks} />
      )}

      <TranscriptUpload onSuccess={loadTasks} />

      <TaskList tasks={tasks} onUpdate={loadTasks} user={user} />
    </div>
  )
}

export default Dashboard

