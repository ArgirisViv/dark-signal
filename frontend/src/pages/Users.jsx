import React, { useEffect, useState } from 'react'
import axios from 'axios'
import { API_BASE_URL } from '../config'
import { useAuth } from '../context/AuthContext'
import './Users.css'

const parseCsvLine = (line) => {
  const values = []
  let value = ''
  let quoted = false
  for (let index = 0; index < line.length; index += 1) {
    const character = line[index]
    if (character === '"' && quoted && line[index + 1] === '"') {
      value += '"'
      index += 1
    } else if (character === '"') {
      quoted = !quoted
    } else if (character === ',' && !quoted) {
      values.push(value.trim())
      value = ''
    } else {
      value += character
    }
  }
  values.push(value.trim())
  return values
}

function AccountMetricIcon({ type }) {
  const commonProps = {
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.8,
    strokeLinecap: 'round',
    strokeLinejoin: 'round',
    'aria-hidden': true,
  }
  if (type === 'admin') {
    return <svg {...commonProps}><path d="M12 3 19 6v5c0 4.6-2.8 8-7 10-4.2-2-7-5.4-7-10V6l7-3Z" /><path d="m9.2 12 1.8 1.8 3.9-4.1" /></svg>
  }
  if (type === 'analyst') {
    return <svg {...commonProps}><path d="M4 19V9" /><path d="M10 19V5" /><path d="M16 19v-7" /><path d="M22 19H2" /><path d="m4 7 6-4 6 6 5-4" /></svg>
  }
  if (type === 'viewer') {
    return <svg {...commonProps}><path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Z" /><circle cx="12" cy="12" r="2.5" /></svg>
  }
  return <svg {...commonProps}><path d="M16 20v-1.5a4.5 4.5 0 0 0-4.5-4.5h-5A4.5 4.5 0 0 0 2 18.5V20" /><circle cx="9" cy="7" r="4" /><path d="M17 11a3.5 3.5 0 0 0 0-7" /><path d="M22 20v-1.5a4.5 4.5 0 0 0-3-4.2" /></svg>
}

function DirectoryActionIcon({ type }) {
  const commonProps = {
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.8,
    strokeLinecap: 'round',
    strokeLinejoin: 'round',
    'aria-hidden': true,
  }
  if (type === 'delete') {
    return <svg {...commonProps}><path d="M4 7h16" /><path d="M9 7V4h6v3" /><path d="m7 7 1 13h8l1-13" /><path d="M10 11v5M14 11v5" /></svg>
  }
  if (type === 'previous') {
    return <svg {...commonProps}><path d="m15 18-6-6 6-6" /></svg>
  }
  if (type === 'next') {
    return <svg {...commonProps}><path d="m9 18 6-6-6-6" /></svg>
  }
  return <svg {...commonProps}><path d="M4 20h4l10.5-10.5a2.8 2.8 0 0 0-4-4L4 16v4Z" /><path d="m13.5 6.5 4 4" /></svg>
}

function Users() {
  const { userEmail, userRole } = useAuth()
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [activeUser, setActiveUser] = useState(null)
  const [selectedProfile, setSelectedProfile] = useState(null)
  const [riskTrend, setRiskTrend] = useState([])
  const [isProfileLoading, setIsProfileLoading] = useState(false)
  const [profileError, setProfileError] = useState('')
  const [trainingAssignments, setTrainingAssignments] = useState([])
  const [trainingModules, setTrainingModules] = useState([])
  const [selectedModuleId, setSelectedModuleId] = useState('')
  const [csvPreview, setCsvPreview] = useState([])
  const [csvFileName, setCsvFileName] = useState('')
  const [isCsvImporting, setIsCsvImporting] = useState(false)
  const [isLdapOpen, setIsLdapOpen] = useState(false)
  const [ldapGroups, setLdapGroups] = useState([])
  const [selectedLdapGroups, setSelectedLdapGroups] = useState([])
  const [ldapPreview, setLdapPreview] = useState([])
  const [ldapSearch, setLdapSearch] = useState('')
  const [ldapBusy, setLdapBusy] = useState('')
  const [ldapError, setLdapError] = useState('')
  const [assignmentTitle, setAssignmentTitle] = useState('')
  const [assignmentType, setAssignmentType] = useState('Micro-learning')
  const [isAssignmentSaving, setIsAssignmentSaving] = useState(false)
  const [assignmentError, setAssignmentError] = useState('')
  const [users, setUsers] = useState([])
  const [toastMessage, setToastMessage] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState('')
  const [searchTerm, setSearchTerm] = useState('')
  const [roleFilter, setRoleFilter] = useState('all')
  const [page, setPage] = useState(0)
  const [hasNextPage, setHasNextPage] = useState(false)
  const [totalCount, setTotalCount] = useState(0)
  const [roleCounts, setRoleCounts] = useState({ admin: 0, analyst: 0, viewer: 0 })
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    role: 'Viewer',
    password: '',
  })
  const roleLabels = {
    admin: 'Admin',
    analyst: 'Analyst',
    viewer: 'Viewer',
    trainee: 'Trainee',
    employee: 'Trainee',
    manager: 'Analyst',
  }

  const formatRole = (value) => {
    const normalized = value ? value.toLowerCase() : ''
    return roleLabels[normalized] || (normalized ? normalized[0].toUpperCase() + normalized.slice(1) : '—')
  }

  const canManageUsers = userRole === 'admin'

  const formatTimestamp = (value) => {
    if (!value) return '—'
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) return '—'
    return date.toLocaleString()
  }

  const adminCount = roleCounts.admin || 0
  const analystCount = roleCounts.analyst || 0
  const viewerCount = roleCounts.viewer || 0
  const totalUsers = adminCount + analystCount + viewerCount
  const accountShare = (count) => (totalUsers ? Math.round((count / totalUsers) * 100) : 0)


  const apiBase = API_BASE_URL
  const pageSize = 20

  const showToast = (message) => {
    setToastMessage(message)
    window.setTimeout(() => setToastMessage(''), 2000)
  }

  const fetchUsers = async (options = {}) => {
    setIsLoading(true)
    setErrorMessage('')
    try {
      const response = await axios.get(`${apiBase}/users/`, { params: options })
      setUsers(response.data.items || [])
      setTotalCount(response.data.total || 0)
      setHasNextPage(Boolean(response.data.has_more))
      setRoleCounts(response.data.role_counts || { admin: 0, analyst: 0, viewer: 0 })
    } catch (error) {
      setErrorMessage(error?.response?.data?.detail || 'Failed to load users.')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchUsers({ limit: pageSize, offset: 0 })
  }, [])

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const params = {}
      if (searchTerm.trim()) params.search = searchTerm.trim()
      if (roleFilter !== 'all') params.role = roleFilter
      params.limit = pageSize
      params.offset = page * pageSize
      fetchUsers(params)
    }, 300)
    return () => window.clearTimeout(timer)
  }, [searchTerm, roleFilter, page])

  const handleCreateUser = async () => {
    if (!formData.email.trim()) {
      showToast('Email address is required.')
      return
    }
    if (formData.password.length < 8) {
      showToast('Temporary password must contain at least 8 characters.')
      return
    }
    try {
      const payload = {
        email: formData.email,
        password: formData.password,
        role: formData.role.toLowerCase(),
        full_name: formData.name || null,
      }
      const response = await axios.post(`${apiBase}/users/`, payload)
      setUsers((prev) => [...prev, response.data])
      setIsModalOpen(false)
      showToast('User created.')
    } catch (error) {
      const errorMessage = error?.response?.data?.detail || error?.response?.data?.message
      showToast(errorMessage ? `Failed: ${errorMessage}` : 'Failed to create user.')
    }
  }

  const handleUpdateUser = async () => {
    if (!activeUser) return
    if (formData.password && formData.password.length < 8) {
      showToast('New password must contain at least 8 characters.')
      return
    }
    try {
      const payload = {
        email: formData.email || null,
        role: formData.role.toLowerCase(),
        full_name: formData.name || null,
      }
      if (formData.password) {
        payload.password = formData.password
      }
      const response = await axios.patch(`${apiBase}/users/${activeUser.id}`, payload)
      setUsers((prev) =>
        prev.map((user) => (user.id === activeUser.id ? response.data : user))
      )
      setIsModalOpen(false)
      setActiveUser(null)
      showToast('User updated.')
    } catch (error) {
      const errorMessage = error?.response?.data?.detail || error?.response?.data?.message
      showToast(errorMessage ? `Failed: ${errorMessage}` : 'Failed to update user.')
    }
  }

  const handleDeleteUser = async (user) => {
    if (user.email?.toLowerCase() === userEmail?.toLowerCase()) {
      showToast('You cannot delete the account you are currently signed in with.')
      return
    }
    if (!window.confirm(`Delete ${user.full_name || user.email}?`)) return
    try {
      await axios.delete(`${apiBase}/users/${user.id}`)
      setUsers((prev) => prev.filter((item) => item.id !== user.id))
      showToast('User deleted.')
    } catch (error) {
      const errorMessage = error?.response?.data?.detail || error?.response?.data?.message
      showToast(errorMessage ? `Failed: ${errorMessage}` : 'Failed to delete user.')
    }
  }

  const handleOpenRiskProfile = async (user) => {
    setSelectedProfile({ id: user.id, full_name: user.full_name, email: user.email, loading: true })
    setIsProfileLoading(true)
    setProfileError('')
    setAssignmentError('')
    setAssignmentTitle('')
    try {
      const [profileResponse, assignmentsResponse, modulesResponse, trendResponse] = await Promise.all([
        axios.get(`${apiBase}/users/${user.id}/risk-profile`),
        axios.get(`${apiBase}/users/${user.id}/training-assignments`),
        axios.get(`${apiBase}/users/training-modules`),
        axios.get(`${apiBase}/users/${user.id}/risk-trend`),
      ])
      setSelectedProfile(profileResponse.data)
      setTrainingAssignments(assignmentsResponse.data || [])
      setTrainingModules(modulesResponse.data || [])
      setRiskTrend(trendResponse.data || [])
    } catch (error) {
      setProfileError(error?.response?.data?.detail || 'Failed to load this user profile.')
    } finally {
      setIsProfileLoading(false)
    }
  }

  const handleCreateAssignment = async () => {
    if (!selectedProfile || (!selectedModuleId && !assignmentTitle.trim())) return
    setIsAssignmentSaving(true)
    setAssignmentError('')
    try {
      const response = await axios.post(`${apiBase}/users/${selectedProfile.id}/training-assignments`, {
        title: selectedModuleId ? null : assignmentTitle.trim(),
        assignment_type: assignmentType,
        module_id: selectedModuleId ? Number(selectedModuleId) : null,
      })
      setTrainingAssignments((current) => [response.data, ...current])
      setAssignmentTitle('')
      setSelectedModuleId('')
    } catch (error) {
      setAssignmentError(error?.response?.data?.detail || 'Failed to assign training.')
    } finally {
      setIsAssignmentSaving(false)
    }
  }

  const handleAssignmentStatusChange = async (assignmentId, status) => {
    setAssignmentError('')
    try {
      const response = await axios.patch(`${apiBase}/users/training-assignments/${assignmentId}`, { status })
      setTrainingAssignments((current) =>
        current.map((assignment) => (assignment.id === assignmentId ? response.data : assignment))
      )
    } catch (error) {
      setAssignmentError(error?.response?.data?.detail || 'Failed to update training status.')
    }
  }

  const handleCsvFile = async (event) => {
    const file = event.target.files?.[0]
    if (!file) return
    const lines = (await file.text()).split(/\r?\n/).filter((line) => line.trim())
    const headers = parseCsvLine(lines.shift() || '').map((value) => value.trim().toLowerCase())
    const requiredIndex = headers.indexOf('email')
    if (requiredIndex < 0) {
      showToast('CSV must include an email column.')
      return
    }
    const rows = lines.map((line) => {
      const values = parseCsvLine(line)
      const read = (name, fallback = '') => {
        const index = headers.indexOf(name)
        return index >= 0 ? values[index] || fallback : fallback
      }
      return {
        email: values[requiredIndex],
        full_name: read('full_name') || read('name') || null,
        department: read('department') || null,
        risk: read('risk', 'Low') || 'Low',
      }
    }).filter((row) => row.email)
    setCsvFileName(file.name)
    setCsvPreview(rows)
  }

  const handleCsvImport = async () => {
    if (!csvPreview.length) return
    setIsCsvImporting(true)
    try {
      const response = await axios.post(`${apiBase}/users/import-csv`, { users: csvPreview })
      showToast(`Imported ${response.data.created_count}; skipped ${response.data.skipped_count}.`)
      setCsvPreview([])
      setCsvFileName('')
      fetchUsers({ limit: pageSize, offset: 0 })
    } catch (error) {
      showToast(error?.response?.data?.detail || 'CSV import failed.')
    } finally {
      setIsCsvImporting(false)
    }
  }

  const loadLdapGroups = async (search = '') => {
    setLdapBusy('groups')
    setLdapError('')
    try {
      const response = await axios.get(`${apiBase}/directory-integration/groups`, { params: search.trim() ? { search: search.trim() } : {} })
      setLdapGroups(response.data.items || [])
    } catch (error) {
      setLdapError(error?.response?.data?.detail || 'LDAP groups could not be loaded. Configure and test the directory connection in Settings first.')
    } finally { setLdapBusy('') }
  }

  const openLdapImport = () => {
    setSelectedLdapGroups([])
    setLdapPreview([])
    setLdapSearch('')
    setIsLdapOpen(true)
    loadLdapGroups()
  }

  const previewLdapRecipients = async () => {
    setLdapBusy('preview')
    setLdapError('')
    try {
      const response = await axios.post(`${apiBase}/directory-integration/preview`, { group_dns: selectedLdapGroups })
      setLdapPreview(response.data.items || [])
    } catch (error) {
      setLdapError(error?.response?.data?.detail || 'LDAP recipient preview failed.')
    } finally { setLdapBusy('') }
  }

  const importLdapRecipients = async () => {
    setLdapBusy('import')
    setLdapError('')
    try {
      const response = await axios.post(`${apiBase}/directory-integration/import`, { group_dns: selectedLdapGroups })
      showToast(`LDAP sync completed: ${response.data.created_count} imported, ${response.data.skipped_count} skipped.`)
      setIsLdapOpen(false)
    } catch (error) {
      setLdapError(error?.response?.data?.detail || 'LDAP recipient import failed.')
    } finally { setLdapBusy('') }
  }

  const riskBadgeClass = (risk) => {
    const normalized = risk?.toLowerCase()
    if (normalized === 'high') return 'danger'
    if (normalized === 'medium') return 'warning'
    return 'success'
  }

  if (isLoading) {
    return (
      <div className="container loading">
        <div className="spinner"></div>
      </div>
    )
  }

  if (errorMessage) {
    return (
      <div className="container error">
        Error: {errorMessage}
        <div style={{ marginTop: '1rem' }}>
          <button className="action-btn secondary-btn" onClick={fetchUsers}>
            Retry
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="container">
      <div className="page-header">
        <div>
          <h1 className="page-title">User Management</h1>
          <p className="page-subtitle">Manage the Admin, Analyst, and Viewer accounts that can sign in to the application.</p>
        </div>
        <div className="user-header-actions">
          {canManageUsers && (
            <button type="button" className="action-btn ldap-import-btn" onClick={openLdapImport}>
              <span className="ldap-button-icon"><AccountMetricIcon type="total" /></span>
              Import from LDAP
            </button>
          )}
          <label className="action-btn secondary-btn">
            Import email recipients CSV
            <input type="file" accept=".csv,text/csv" hidden onChange={handleCsvFile} />
          </label>
          <button
            className="action-btn primary-btn"
            disabled={!canManageUsers}
            title={!canManageUsers ? 'Admin access required' : undefined}
            onClick={() => {
              setFormData({
                name: '',
                email: '',
                role: 'Viewer',
                password: '',
              })
              setActiveUser(null)
              setIsModalOpen(true)
            }}
          >
            + Add User
          </button>
        </div>
      </div>

      {isLdapOpen && (
        <div className="ldap-modal-backdrop" onMouseDown={() => setIsLdapOpen(false)}>
          <section className="ldap-import-modal" role="dialog" aria-modal="true" aria-labelledby="ldap-import-title" onMouseDown={(event) => event.stopPropagation()}>
            <header className="ldap-import-header">
              <div><span className="profile-eyebrow">Enterprise directory</span><h2 id="ldap-import-title">Import email recipients from LDAP</h2><p>Select directory groups, preview their members and import them as campaign recipients without login access.</p></div>
              <button className="icon-btn" aria-label="Close LDAP import" onClick={() => setIsLdapOpen(false)}>✕</button>
            </header>
            <div className="ldap-import-steps"><span className={ldapPreview.length ? 'complete' : 'active'}><b>1</b>Select groups</span><i /><span className={ldapPreview.length ? 'active' : ''}><b>2</b>Preview recipients</span><i /><span><b>3</b>Import</span></div>
            {ldapError && <div className="ldap-import-error">{ldapError}</div>}
            <div className="ldap-browser-toolbar"><input placeholder="Search directory groups…" value={ldapSearch} onChange={(event) => setLdapSearch(event.target.value)} onKeyDown={(event) => event.key === 'Enter' && loadLdapGroups(ldapSearch)} /><button className="action-btn secondary-btn" onClick={() => loadLdapGroups(ldapSearch)} disabled={Boolean(ldapBusy)}>{ldapBusy === 'groups' ? 'Searching…' : 'Search groups'}</button></div>
            <div className="ldap-import-body">
              <div className="ldap-group-list">
                <div className="ldap-column-title"><strong>Directory groups</strong><span>{selectedLdapGroups.length} selected</span></div>
                {ldapGroups.length === 0 && !ldapBusy && <p className="ldap-empty">No groups available.</p>}
                {ldapGroups.map((group) => (
                  <label className="ldap-group-row" key={group.dn}>
                    <input type="checkbox" checked={selectedLdapGroups.includes(group.dn)} onChange={(event) => { setSelectedLdapGroups((current) => event.target.checked ? [...current, group.dn] : current.filter((dn) => dn !== group.dn)); setLdapPreview([]) }} />
                    <span><strong>{group.name}</strong><small>{group.dn}</small></span><b>{group.member_count}</b>
                  </label>
                ))}
              </div>
              <div className="ldap-preview-list">
                <div className="ldap-column-title"><strong>Recipient preview</strong><span>{ldapPreview.length} found</span></div>
                {!ldapPreview.length ? <div className="ldap-preview-placeholder"><AccountMetricIcon type="total" /><strong>Preview before importing</strong><p>Select one or more groups, then validate the recipients that Dark Signal found.</p></div> : <div className="ldap-preview-scroll">{ldapPreview.map((recipient) => <div className="ldap-recipient-row" key={recipient.email}><span>{(recipient.full_name || recipient.email).slice(0, 1).toUpperCase()}</span><div><strong>{recipient.full_name || 'Unnamed recipient'}</strong><small>{recipient.email} · {recipient.department || 'No department'}</small></div></div>)}</div>}
              </div>
            </div>
            <footer className="ldap-import-footer"><p>Existing email addresses are safely skipped. LDAP recipients cannot sign in to the application.</p><div><button className="action-btn secondary-btn" onClick={() => setIsLdapOpen(false)}>Cancel</button><button className="action-btn secondary-btn" disabled={Boolean(ldapBusy) || !selectedLdapGroups.length} onClick={previewLdapRecipients}>{ldapBusy === 'preview' ? 'Loading preview…' : 'Preview recipients'}</button><button className="action-btn primary-btn" disabled={Boolean(ldapBusy) || !ldapPreview.length} onClick={importLdapRecipients}>{ldapBusy === 'import' ? 'Importing…' : `Import ${ldapPreview.length} recipients`}</button></div></footer>
          </section>
        </div>
      )}

      {csvPreview.length > 0 && (
        <div className="card csv-import-preview">
          <div>
            <strong>{csvFileName}</strong>
            <p className="muted">{csvPreview.length} email recipients ready. Columns: email, full_name, department and risk. These records cannot sign in.</p>
          </div>
          <div className="table-actions">
            <button className="action-btn secondary-btn" onClick={() => setCsvPreview([])}>Cancel</button>
            <button className="action-btn primary-btn" disabled={isCsvImporting} onClick={handleCsvImport}>{isCsvImporting ? 'Importing...' : `Import ${csvPreview.length} recipients`}</button>
          </div>
        </div>
      )}

      <section className="account-overview" aria-label="Application account overview">
        <button
          type="button"
          className={`account-summary-card total ${roleFilter === 'all' ? 'selected' : ''}`}
          onClick={() => {
            setRoleFilter('all')
            setPage(0)
          }}
        >
          <div className="account-card-top">
            <span className="account-card-icon"><AccountMetricIcon type="total" /></span>
            <span className="account-card-tag">Directory</span>
          </div>
          <div className="account-card-metric">
            <span>Application Accounts</span>
            <strong>{totalUsers}</strong>
          </div>
          <p>Accounts authorized to sign in to Dark Signal.</p>
          <div className="account-card-footer">
            <span>All login roles</span>
            <strong>{totalUsers} configured</strong>
          </div>
        </button>

        <button
          type="button"
          className={`account-summary-card admin ${roleFilter === 'admin' ? 'selected' : ''}`}
          onClick={() => {
            setRoleFilter('admin')
            setPage(0)
          }}
        >
          <div className="account-card-top">
            <span className="account-card-icon"><AccountMetricIcon type="admin" /></span>
            <span className="account-card-tag">Full access</span>
          </div>
          <div className="account-card-metric">
            <span>Administrators</span>
            <strong>{adminCount}</strong>
          </div>
          <p>Platform control, account administration and settings.</p>
          <div className="account-card-footer">
            <span>Role share</span>
            <strong>{accountShare(adminCount)}%</strong>
          </div>
        </button>

        <button
          type="button"
          className={`account-summary-card analyst ${roleFilter === 'analyst' ? 'selected' : ''}`}
          onClick={() => {
            setRoleFilter('analyst')
            setPage(0)
          }}
        >
          <div className="account-card-top">
            <span className="account-card-icon"><AccountMetricIcon type="analyst" /></span>
            <span className="account-card-tag">Operations</span>
          </div>
          <div className="account-card-metric">
            <span>Analysts</span>
            <strong>{analystCount}</strong>
          </div>
          <p>Campaign and phishing-scenario creation and management.</p>
          <div className="account-card-footer">
            <span>Role share</span>
            <strong>{accountShare(analystCount)}%</strong>
          </div>
        </button>

        <button
          type="button"
          className={`account-summary-card viewer ${roleFilter === 'viewer' ? 'selected' : ''}`}
          onClick={() => {
            setRoleFilter('viewer')
            setPage(0)
          }}
        >
          <div className="account-card-top">
            <span className="account-card-icon"><AccountMetricIcon type="viewer" /></span>
            <span className="account-card-tag">Read only</span>
          </div>
          <div className="account-card-metric">
            <span>Viewers</span>
            <strong>{viewerCount}</strong>
          </div>
          <p>Visibility across the platform with export permissions.</p>
          <div className="account-card-footer">
            <span>Role share</span>
            <strong>{accountShare(viewerCount)}%</strong>
          </div>
        </button>
      </section>

      <div className="card table-card">
        <div className="table-header">
          <h2>Directory</h2>
          <div className="table-actions">
            <input
              className="table-input"
              placeholder="Search users..."
              value={searchTerm}
              onChange={(event) => {
                setSearchTerm(event.target.value)
                setPage(0)
              }}
            />
            <select
              className="table-select"
              value={roleFilter}
              onChange={(event) => {
                setRoleFilter(event.target.value)
                setPage(0)
              }}
            >
              <option value="all">All roles</option>
              <option value="analyst">Analyst</option>
              <option value="viewer">Viewer</option>
              <option value="admin">Admin</option>
            </select>
          </div>
        </div>
        <table className="data-table">
          <thead>
            <tr>
              <th>User</th>
              <th>Role</th>
              <th>Last Activity</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.length === 0 && (
              <tr className="empty-row">
                <td colSpan={4}>No application accounts yet.</td>
              </tr>
            )}
            {users.map((user) => (
              <tr key={user.id}>
                <td>{user.full_name || user.email}</td>
                <td>{formatRole(user.role)}</td>
                <td>{formatTimestamp(user.last_activity)}</td>
                <td>
                  {canManageUsers ? (
                    <div className="directory-row-actions">
                      <button
                        type="button"
                        className="directory-action-btn edit"
                        onClick={() => {
                          setActiveUser(user)
                          setFormData({
                            name: user.full_name || '',
                            email: user.email || '',
                            role: formatRole(user.role),
                            password: '',
                          })
                          setIsModalOpen(true)
                        }}
                      >
                        <DirectoryActionIcon type="edit" />
                        <span>Edit</span>
                      </button>
                      <button
                        type="button"
                        className="directory-action-btn delete"
                        disabled={user.email?.toLowerCase() === userEmail?.toLowerCase()}
                        title={
                          user.email?.toLowerCase() === userEmail?.toLowerCase()
                            ? 'You cannot delete your active account'
                            : 'Delete user'
                        }
                        onClick={() => handleDeleteUser(user)}
                      >
                        <DirectoryActionIcon type="delete" />
                        <span>Delete</span>
                      </button>
                    </div>
                  ) : (
                    <span className="muted">View only</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="table-footer">
          <span className="pagination-info">
            Page {Math.min(page + 1, Math.max(1, Math.ceil(totalCount / pageSize)))} of{' '}
            {Math.max(1, Math.ceil(totalCount / pageSize))}
          </span>
          <div className="pagination-actions">
            <button
              type="button"
              className="directory-page-btn"
              disabled={page === 0}
              onClick={() => setPage((prev) => Math.max(0, prev - 1))}
            >
              <DirectoryActionIcon type="previous" />
              <span>Previous</span>
            </button>
            <button
              type="button"
              className="directory-page-btn next"
              disabled={!hasNextPage}
              onClick={() => setPage((prev) => prev + 1)}
            >
              <span>Next</span>
              <DirectoryActionIcon type="next" />
            </button>
          </div>
        </div>
      </div>

      {toastMessage && <div className="toast">{toastMessage}</div>}

      {selectedProfile && (
        <div className="profile-backdrop" onClick={() => setSelectedProfile(null)}>
          <aside className="risk-profile-drawer" onClick={(event) => event.stopPropagation()} aria-label="User risk profile">
            <div className="profile-drawer-header">
              <div>
                <span className="profile-eyebrow">Learning and risk profile</span>
                <h2>{selectedProfile.full_name || selectedProfile.email}</h2>
                <p>{selectedProfile.email}</p>
              </div>
              <button className="icon-btn" aria-label="Close profile" onClick={() => setSelectedProfile(null)}>✕</button>
            </div>

            {isProfileLoading ? (
              <div className="profile-loading">Loading profile...</div>
            ) : profileError ? (
              <div className="profile-error">{profileError}</div>
            ) : (
              <div className="profile-drawer-body">
                <div className="profile-meta">
                  <span>Department</span>
                  <strong>{selectedProfile.department || 'Not assigned'}</strong>
                  <span>Last simulation activity</span>
                  <strong>{formatTimestamp(selectedProfile.last_activity)}</strong>
                </div>

                <section className="risk-summary">
                  <div className="awareness-score">
                    <span>Awareness score</span>
                    <strong>{selectedProfile.awareness_score}<small>/100</small></strong>
                  </div>
                  <div className="risk-labels">
                    <div>
                      <span>Computed risk</span>
                      <b className={`badge ${riskBadgeClass(selectedProfile.computed_risk)}`}>{selectedProfile.computed_risk}</b>
                    </div>
                    <div>
                      <span>Recorded risk</span>
                      <b className={`badge ${riskBadgeClass(selectedProfile.recorded_risk)}`}>{selectedProfile.recorded_risk || 'Low'}</b>
                    </div>
                  </div>
                </section>

                <section className="profile-metrics" aria-label="Simulation metrics">
                  <div><span>Simulations</span><strong>{selectedProfile.exposures}</strong></div>
                  <div><span>Clicks</span><strong>{selectedProfile.clicks}</strong></div>
                  <div><span>Reports</span><strong>{selectedProfile.reports}</strong></div>
                </section>

                <section className="risk-trend-section">
                  <div className="training-section-heading">
                    <div>
                      <h3>Awareness trend</h3>
                      <p>Cumulative simulation behavior over time.</p>
                    </div>
                  </div>
                  {riskTrend.length ? (
                    <div className="risk-trend-list">
                      {riskTrend.map((point) => (
                        <div className="risk-trend-row" key={point.date}>
                          <span>{point.date}</span>
                          <div className="risk-trend-score" style={{ '--trend-score': `${point.awareness_score}%` }}>
                            <i />
                          </div>
                          <strong>{point.awareness_score}</strong>
                          <b className={`badge ${riskBadgeClass(point.computed_risk)}`}>{point.computed_risk}</b>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="training-empty">Trend data appears after click or report activity.</p>
                  )}
                </section>

                <section className="profile-activity">
                  <h3>Recent activity</h3>
                  {selectedProfile.recent_activity?.length ? (
                    <ul>
                      {selectedProfile.recent_activity.map((activity) => (
                        <li key={activity.id}>
                          <span>{activity.action.replaceAll('.', ' ')}</span>
                          <time>{formatTimestamp(activity.created_at)}</time>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p>No simulation activity recorded yet.</p>
                  )}
                </section>

                <section className="training-section">
                  <div className="training-section-heading">
                    <div>
                      <h3>Training assignments</h3>
                      <p>Targeted follow-up for this user.</p>
                    </div>
                  </div>
                  <div className="assignment-composer">
                    <select
                      value={selectedModuleId}
                      onChange={(event) => setSelectedModuleId(event.target.value)}
                    >
                      <option value="">Custom training assignment</option>
                      {trainingModules.map((module) => (
                        <option value={module.id} key={module.id}>{module.title} · {module.estimated_minutes} min</option>
                      ))}
                    </select>
                    <input
                      value={assignmentTitle}
                      placeholder="Training module title"
                      disabled={Boolean(selectedModuleId)}
                      onChange={(event) => setAssignmentTitle(event.target.value)}
                    />
                    <select value={assignmentType} onChange={(event) => setAssignmentType(event.target.value)}>
                      <option>Micro-learning</option>
                      <option>Policy review</option>
                      <option>Workshop</option>
                    </select>
                    <button
                      className="action-btn primary-btn"
                      disabled={(!selectedModuleId && !assignmentTitle.trim()) || isAssignmentSaving}
                      onClick={handleCreateAssignment}
                    >
                      {isAssignmentSaving ? 'Assigning...' : 'Assign training'}
                    </button>
                  </div>
                  {assignmentError && <p className="assignment-error">{assignmentError}</p>}
                  {trainingAssignments.length ? (
                    <div className="assignment-list">
                      {trainingAssignments.map((assignment) => (
                        <div className="assignment-item" key={assignment.id}>
                          <div>
                            <strong>{assignment.title}</strong>
                            <span>{assignment.assignment_type} · Assigned {formatTimestamp(assignment.created_at)}</span>
                          </div>
                          <select
                            aria-label={`Status for ${assignment.title}`}
                            value={assignment.status}
                            onChange={(event) => handleAssignmentStatusChange(assignment.id, event.target.value)}
                          >
                            <option>Assigned</option>
                            <option>In progress</option>
                            <option>Completed</option>
                          </select>
                          {assignment.status === 'Completed' && (
                            <input
                              className="completion-score"
                              type="number"
                              min="0"
                              max="100"
                              defaultValue={assignment.completion_score ?? ''}
                              placeholder="Score"
                              aria-label={`Completion score for ${assignment.title}`}
                              onBlur={(event) => {
                                const score = event.target.value === '' ? null : Number(event.target.value)
                                if (score !== assignment.completion_score) {
                                  axios.patch(`${apiBase}/users/training-assignments/${assignment.id}`, { status: 'Completed', completion_score: score })
                                    .then((response) => setTrainingAssignments((current) => current.map((item) => item.id === assignment.id ? response.data : item)))
                                    .catch(() => setAssignmentError('Failed to save completion score.'))
                                }
                              }}
                            />
                          )}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="training-empty">No training assigned yet.</p>
                  )}
                </section>
              </div>
            )}
          </aside>
        </div>
      )}

      {isModalOpen && (
        <div className="modal-backdrop" onClick={() => setIsModalOpen(false)}>
          <div className="modal" onClick={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <h3>{activeUser ? 'Edit User' : 'Add User'}</h3>
              <button className="icon-btn" onClick={() => setIsModalOpen(false)}>✕</button>
            </div>
            <div className="modal-body">
              <label className="field">
                Full name
                <input
                  type="text"
                  placeholder="Full name"
                  value={formData.name}
                  onChange={(event) => setFormData({ ...formData, name: event.target.value })}
                />
              </label>
              <label className="field">
                Email address
                <input
                  type="email"
                  placeholder="user@company.com"
                  value={formData.email}
                  onChange={(event) => setFormData({ ...formData, email: event.target.value })}
                />
              </label>
              <label className="field">
                Role
                <select
                  value={formData.role}
                  onChange={(event) => setFormData({ ...formData, role: event.target.value })}
                >
                  <option>Admin</option>
                  <option>Analyst</option>
                  <option>Viewer</option>
                </select>
              </label>
              <label className="field">
                Temporary password
                <input
                  type="password"
                  minLength={8}
                  maxLength={128}
                  required={!activeUser}
                  placeholder={activeUser ? "Leave blank to keep current password" : "Minimum 8 characters"}
                  value={formData.password}
                  onChange={(event) => setFormData({ ...formData, password: event.target.value })}
                />
              </label>
            </div>
            <div className="modal-footer">
              <button className="action-btn secondary-btn" onClick={() => setIsModalOpen(false)}>
                Cancel
              </button>
              {activeUser ? (
                <button className="action-btn primary-btn" onClick={handleUpdateUser}>
                  Save Changes
                </button>
              ) : (
                <button className="action-btn primary-btn" onClick={handleCreateUser}>
                  Add User
                </button>
              )}
            </div>
          </div>
        </div>
      )}

    </div>
  )
}

export default Users
