import React, { useState } from 'react'
import { useNavigate } from '../router'
import axios from 'axios'
import { API_BASE_URL } from '../config'
import './Login.css'

function ResetPassword() {
  const navigate = useNavigate()
  const params = new URLSearchParams(window.location.search)
  const [token, setToken] = useState(params.get('token') || '')
  const [password, setPassword] = useState('')
  const [status, setStatus] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const apiBase = API_BASE_URL

  const handleSubmit = async (event) => {
    event.preventDefault()
    setStatus('')
    setIsSubmitting(true)
    try {
      const response = await axios.post(`${apiBase}/auth/reset-password`, { token, password })
      setStatus(response.data?.message || 'Password updated successfully.')
      window.setTimeout(() => navigate('/login'), 1200)
    } catch (err) {
      const message = err?.response?.data?.detail || err?.response?.data?.message || 'Reset failed.'
      setStatus(message)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-header">
          <h1>Reset Password</h1>
          <p>Create a new password to access your account.</p>
        </div>
        <form onSubmit={handleSubmit}>
          <label className="field">
            Reset token
            <input
              type="text"
              value={token}
              onChange={(event) => setToken(event.target.value)}
              placeholder="Paste reset token"
              required
            />
          </label>
          <label className="field">
            New password
            <input
              type="password"
              minLength={8}
              maxLength={128}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="Create a new password"
              required
            />
          </label>
          {status && <div className="login-error">{status}</div>}
          <button className="action-btn primary-btn login-btn" type="submit" disabled={isSubmitting}>
            {isSubmitting ? 'Updating...' : 'Update Password'}
          </button>
        </form>
        <button type="button" className="bootstrap-toggle" onClick={() => navigate('/login')}>
          Back to login
        </button>
      </div>
    </div>
  )
}

export default ResetPassword
