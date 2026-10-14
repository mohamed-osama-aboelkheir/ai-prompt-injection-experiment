import React, { useState, useEffect } from 'react'
import api from '../services/api'

const TaskList = ({ tasks, onUpdate, user }) => {
  const [editingId, setEditingId] = useState(null)
  const [editTitle, setEditTitle] = useState('')
  const [editDescription, setEditDescription] = useState('')
  const [editStatus, setEditStatus] = useState('')
  const [editAssignedTo, setEditAssignedTo] = useState('')
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [newTitle, setNewTitle] = useState('')
  const [newDescription, setNewDescription] = useState('')
  const [newStatus, setNewStatus] = useState('pending')
  const [newAssignedTo, setNewAssignedTo] = useState('')
  const [teamMembers, setTeamMembers] = useState([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    // Load team members for all users
    if (user?.team_id) {
      loadTeamMembers()
    }
  }, [user])

  const loadTeamMembers = async () => {
    try {
      const response = await api.get('/team/members')
      setTeamMembers(response.data.members || [])
    } catch (err) {
      // Not an admin or error loading members
      console.error('Failed to load team members:', err)
    }
  }

  const startEdit = (task) => {
    setEditingId(task.id)
    setEditTitle(task.title)
    setEditDescription(task.description || '')
    setEditStatus(task.status)
    setEditAssignedTo(task.assigned_to || '')
  }

  const cancelEdit = () => {
    setEditingId(null)
    setEditTitle('')
    setEditDescription('')
    setEditStatus('')
    setEditAssignedTo('')
  }

  const saveEdit = async (taskId) => {
    setLoading(true)
    try {
      await api.put(`/tasks/${taskId}`, {
        title: editTitle,
        description: editDescription,
        status: editStatus,
        assigned_to: editAssignedTo || null
      })
      cancelEdit()
      onUpdate()
    } catch (err) {
      alert(err.response?.data?.error || 'Failed to update task')
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (taskId) => {
    if (!window.confirm('Are you sure you want to delete this task?')) {
      return
    }
    setLoading(true)
    try {
      await api.delete(`/tasks/${taskId}`)
      onUpdate()
    } catch (err) {
      alert(err.response?.data?.error || 'Failed to delete task')
    } finally {
      setLoading(false)
    }
  }

  const handleCreate = async (e) => {
    e.preventDefault()
    setLoading(true)
    try {
      await api.post('/tasks', {
        title: newTitle,
        description: newDescription,
        status: newStatus,
        assigned_to: newAssignedTo || null
      })
      setNewTitle('')
      setNewDescription('')
      setNewStatus('pending')
      setNewAssignedTo('')
      setShowCreateForm(false)
      onUpdate()
    } catch (err) {
      alert(err.response?.data?.error || 'Failed to create task')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
        <h2>Tasks ({tasks.length})</h2>
        <button 
          onClick={() => setShowCreateForm(!showCreateForm)}
          style={{ fontSize: '14px', padding: '8px 16px' }}
        >
          {showCreateForm ? 'Cancel' : '+ Create Task'}
        </button>
      </div>

      {showCreateForm && (
        <div style={{ 
          border: '1px solid #ddd', 
          borderRadius: '4px', 
          padding: '15px', 
          marginBottom: '15px',
          backgroundColor: '#f9f9f9'
        }}>
          <h3>Create New Task</h3>
          <form onSubmit={handleCreate}>
            <label>
              Title:
              <input
                type="text"
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                required
              />
            </label>
            <label>
              Description:
              <textarea
                value={newDescription}
                onChange={(e) => setNewDescription(e.target.value)}
                rows="3"
              />
            </label>
            <label>
              Status:
              <select
                value={newStatus}
                onChange={(e) => setNewStatus(e.target.value)}
              >
                <option value="pending">Pending</option>
                <option value="in_progress">In Progress</option>
                <option value="completed">Completed</option>
              </select>
            </label>
            {teamMembers.length > 0 && (
              <label>
                Assign To:
                <select
                  value={newAssignedTo}
                  onChange={(e) => setNewAssignedTo(e.target.value)}
                >
                  <option value="">Unassigned</option>
                  {teamMembers.map(member => (
                    <option key={member.id} value={member.id}>
                      {member.email} ({member.role})
                    </option>
                  ))}
                </select>
              </label>
            )}
            <div style={{ marginTop: '10px' }}>
              <button type="submit" disabled={loading}>
                {loading ? 'Creating...' : 'Create Task'}
              </button>
              <button 
                type="button"
                onClick={() => {
                  setShowCreateForm(false)
                  setNewTitle('')
                  setNewDescription('')
                  setNewStatus('pending')
                  setNewAssignedTo('')
                }}
                style={{ marginLeft: '10px', backgroundColor: '#6c757d' }}
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {tasks.length === 0 ? (
        <p>No tasks yet. Create a task or upload a meeting transcript to create tasks.</p>
      ) : (
        tasks.map(task => (
        <div key={task.id} style={{ 
          border: '1px solid #ddd', 
          borderRadius: '4px', 
          padding: '15px', 
          marginBottom: '10px' 
        }}>
          {editingId === task.id ? (
            <div>
              <label>
                Title:
                <input
                  type="text"
                  value={editTitle}
                  onChange={(e) => setEditTitle(e.target.value)}
                />
              </label>
              <label>
                Description:
                <textarea
                  value={editDescription}
                  onChange={(e) => setEditDescription(e.target.value)}
                  rows="3"
                />
              </label>
              <label>
                Status:
                <select
                  value={editStatus}
                  onChange={(e) => setEditStatus(e.target.value)}
                >
                  <option value="pending">Pending</option>
                  <option value="in_progress">In Progress</option>
                  <option value="completed">Completed</option>
                </select>
              </label>
              {teamMembers.length > 0 && (
                <label>
                  Assign To:
                  <select
                    value={editAssignedTo}
                    onChange={(e) => setEditAssignedTo(e.target.value)}
                  >
                    <option value="">Unassigned</option>
                    {teamMembers.map(member => (
                      <option key={member.id} value={member.id}>
                        {member.email} ({member.role})
                      </option>
                    ))}
                  </select>
                </label>
              )}
              <div style={{ marginTop: '10px' }}>
                <button onClick={() => saveEdit(task.id)} disabled={loading}>
                  Save
                </button>
                <button onClick={cancelEdit} style={{ marginLeft: '10px', backgroundColor: '#6c757d' }}>
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <div>
              <h3>{task.title}</h3>
              {task.description && <p>{task.description}</p>}
              <div style={{ marginTop: '10px', fontSize: '14px', color: '#666' }}>
                <span>Status: {task.status}</span>
                {task.assigned_to && (
                  <span style={{ marginLeft: '15px' }}>
                    Assigned to: {teamMembers.find(m => m.id === task.assigned_to)?.email || `User #${task.assigned_to}`}
                  </span>
                )}
              </div>
              <div style={{ marginTop: '10px' }}>
                <button 
                  onClick={() => startEdit(task)} 
                  style={{ fontSize: '12px', padding: '5px 10px', marginRight: '5px' }}
                >
                  Edit
                </button>
                <button 
                  onClick={() => handleDelete(task.id)}
                  disabled={loading}
                  style={{ 
                    fontSize: '12px', 
                    padding: '5px 10px',
                    backgroundColor: '#dc3545',
                    color: 'white'
                  }}
                >
                  Delete
                </button>
              </div>
            </div>
          )}
        </div>
      )))}
    </div>
  )
}

export default TaskList

