import React, { useEffect, useMemo, useState } from 'react'
import axios from 'axios'
import { API_BASE_URL } from '../config'
import { useAuth } from '../context/AuthContext'
import './Settings.css'

const defaultDirectory = {
  enabled: false,
  server_url: 'ldap://directory.company.local:389',
  base_dn: 'DC=company,DC=local',
  bind_dn: 'CN=Dark Signal Service,OU=Service Accounts,DC=company,DC=local',
  bind_password: '',
  user_filter: '(&(objectClass=person)(mail=*))',
  group_base_dn: 'OU=Groups,DC=company,DC=local',
  group_filter: '(objectClass=group)',
  email_attribute: 'mail',
  name_attribute: 'displayName',
  department_attribute: 'department',
  use_ssl: false,
  start_tls: true,
  verify_tls_certificate: true,
}

function SettingsIcon({ type }) {
  const props = { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.8, strokeLinecap: 'round', strokeLinejoin: 'round', 'aria-hidden': true }
  if (type === 'directory') return <svg {...props}><circle cx="12" cy="6" r="3" /><path d="M5 21v-2a4 4 0 0 1 4-4h6a4 4 0 0 1 4 4v2M12 9v3M5 12h14M5 12v3M19 12v3" /></svg>
  if (type === 'security') return <svg {...props}><path d="M12 3 19 6v5c0 4.6-2.8 8-7 10-4.2-2-7-5.4-7-10V6l7-3Z" /><path d="m9.2 12 1.8 1.8 3.9-4.1" /></svg>
  if (type === 'email') return <svg {...props}><rect x="3" y="5" width="18" height="14" rx="2" /><path d="m3 7 9 6 9-6" /></svg>
  if (type === 'organization') return <svg {...props}><path d="M3 21h18M5 21V8l7-4 7 4v13M9 21v-5h6v5M9 10h.01M15 10h.01" /></svg>
  if (type === 'notification') return <svg {...props}><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4" /></svg>
  return <svg {...props}><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H3v-4h.1a1.7 1.7 0 0 0 1.5-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1A1.7 1.7 0 0 0 9 4.6 1.7 1.7 0 0 0 10 3V3h4v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z" /></svg>
}

function Settings() {
  const { userRole } = useAuth()
  const [activeSection, setActiveSection] = useState('overview')
  const [toastMessage, setToastMessage] = useState('')
  const [preferences, setPreferences] = useState(() => {
    try {
      return JSON.parse(window.localStorage.getItem('dark-signal-settings')) || {
        campaign_completed: true, high_risk: true, weekly_summary: false,
        risk_threshold: 'High', auto_remediate: 'Enabled', organization_name: '', primary_domain: '',
      }
    } catch { return { campaign_completed: true, high_risk: true, weekly_summary: false, risk_threshold: 'High', auto_remediate: 'Enabled', organization_name: '', primary_domain: '' } }
  })
  const [directory, setDirectory] = useState(defaultDirectory)
  const [directoryMeta, setDirectoryMeta] = useState({ configured: false, status: 'loading', has_password: false })
  const [directoryBusy, setDirectoryBusy] = useState('')
  const [directoryError, setDirectoryError] = useState('')
  const [templateState, setTemplateState] = useState({ subject: '', body_text: '', body_html: '' })
  const [templateStatus, setTemplateStatus] = useState({ loading: false, error: '' })

  const templateHelp = useMemo(() => [
    { token: '{{app_name}}', description: 'Application name' },
    { token: '{{reset_url}}', description: 'Password reset link' },
    { token: '{{expires_minutes}}', description: 'Reset token expiry' },
  ], [])

  const notify = (message) => {
    setToastMessage(message)
    window.setTimeout(() => setToastMessage(''), 2400)
  }

  const fetchTemplate = async () => {
    setTemplateStatus({ loading: true, error: '' })
    try {
      const response = await axios.get(`${API_BASE_URL}/email-templates/password_reset`)
      setTemplateState({ subject: response.data.subject || '', body_text: response.data.body_text || '', body_html: response.data.body_html || '' })
      setTemplateStatus({ loading: false, error: '' })
    } catch { setTemplateStatus({ loading: false, error: 'Failed to load email template.' }) }
  }

  const fetchDirectory = async () => {
    try {
      const { data } = await axios.get(`${API_BASE_URL}/directory-integration/config`)
      setDirectoryMeta(data)
      if (data.configured) {
        setDirectory({ ...defaultDirectory, ...data, bind_password: '' })
      }
    } catch (error) {
      setDirectoryMeta({ configured: false, status: 'unavailable', has_password: false })
      setDirectoryError(error?.response?.data?.detail || 'Directory configuration could not be loaded.')
    }
  }

  useEffect(() => {
    if (userRole === 'admin') {
      fetchTemplate()
      fetchDirectory()
    }
  }, [userRole])

  const savePreferences = () => {
    window.localStorage.setItem('dark-signal-settings', JSON.stringify(preferences))
    notify('Workspace preferences saved.')
  }

  const saveDirectory = async () => {
    setDirectoryBusy('save')
    setDirectoryError('')
    try {
      const { data } = await axios.put(`${API_BASE_URL}/directory-integration/config`, directory)
      setDirectoryMeta(data)
      setDirectory((current) => ({ ...current, bind_password: '' }))
      notify('LDAP directory configuration saved.')
    } catch (error) {
      setDirectoryError(error?.response?.data?.detail || 'Failed to save directory configuration.')
    } finally { setDirectoryBusy('') }
  }

  const testDirectory = async () => {
    setDirectoryBusy('test')
    setDirectoryError('')
    try {
      const { data } = await axios.post(`${API_BASE_URL}/directory-integration/test`)
      setDirectoryMeta(data)
      notify('LDAP connection verified successfully.')
    } catch (error) {
      setDirectoryMeta((current) => ({ ...current, status: 'failed' }))
      setDirectoryError(error?.response?.data?.detail || 'LDAP connection test failed.')
    } finally { setDirectoryBusy('') }
  }

  const saveTemplate = async () => {
    setTemplateStatus({ loading: true, error: '' })
    try {
      await axios.put(`${API_BASE_URL}/email-templates/password_reset`, templateState)
      notify('Email template updated.')
      setTemplateStatus({ loading: false, error: '' })
    } catch { setTemplateStatus({ loading: false, error: 'Failed to save email template.' }) }
  }

  const resetTemplate = async () => {
    setTemplateStatus({ loading: true, error: '' })
    try {
      const { data } = await axios.post(`${API_BASE_URL}/email-templates/password_reset/reset`)
      setTemplateState({ subject: data.subject || '', body_text: data.body_text || '', body_html: data.body_html || '' })
      notify('Email template reset to default.')
      setTemplateStatus({ loading: false, error: '' })
    } catch { setTemplateStatus({ loading: false, error: 'Failed to reset email template.' }) }
  }

  const updateDirectory = (key, value) => setDirectory((current) => ({ ...current, [key]: value }))
  const directoryStatus = directoryMeta.status || 'not_configured'
  const statusLabel = directoryStatus === 'connected' ? 'Connected' : directoryStatus === 'failed' ? 'Connection failed' : directoryMeta.configured ? 'Test required' : 'Not configured'

  return (
    <div className="container settings-page">
      <header className="settings-hero">
        <div>
          <span className="settings-kicker">Control center</span>
          <h1 className="page-title">Settings</h1>
          <p className="page-subtitle">Manage workspace identity, security, communications and enterprise integrations.</p>
        </div>
        <div className="settings-hero-status">
          <span className="settings-status-dot" />
          <div><small>Workspace status</small><strong>Operational</strong></div>
        </div>
      </header>

      <nav className="settings-nav" aria-label="Settings sections">
        {[
          ['overview', 'Overview', 'settings'], ['directory', 'Directory', 'directory'], ['security', 'Security', 'security'], ['notifications', 'Notifications', 'notification'], ['email', 'Email', 'email'],
        ].map(([id, label, icon]) => (
          <button key={id} className={activeSection === id ? 'active' : ''} onClick={() => setActiveSection(id)}>
            <SettingsIcon type={icon} /><span>{label}</span>
          </button>
        ))}
      </nav>

      {activeSection === 'overview' && (
        <section className="settings-content">
          <div className="settings-section-heading"><div><span className="settings-kicker">Workspace overview</span><h2>Configuration health</h2></div><button className="action-btn primary-btn" onClick={savePreferences}>Save workspace changes</button></div>
          <div className="settings-overview-grid">
            <article className="settings-overview-card"><span className="settings-card-icon cyan"><SettingsIcon type="organization" /></span><div><small>Organization profile</small><strong>{preferences.organization_name || 'Setup required'}</strong><p>Brand and domain identity</p></div></article>
            <article className="settings-overview-card"><span className={`settings-card-icon ${directoryStatus === 'connected' ? 'green' : 'amber'}`}><SettingsIcon type="directory" /></span><div><small>LDAP directory</small><strong>{statusLabel}</strong><p>{directoryMeta.last_sync_at ? `Last sync ${new Date(directoryMeta.last_sync_at).toLocaleString()}` : 'No recipient sync yet'}</p></div></article>
            <article className="settings-overview-card"><span className="settings-card-icon green"><SettingsIcon type="security" /></span><div><small>Security policy</small><strong>{preferences.risk_threshold} threshold</strong><p>Auto-remediation {preferences.auto_remediate.toLowerCase()}</p></div></article>
            <article className="settings-overview-card"><span className="settings-card-icon purple"><SettingsIcon type="email" /></span><div><small>Communications</small><strong>Password reset ready</strong><p>Managed email template</p></div></article>
          </div>

          <div className="settings-panel settings-organization-panel">
            <div className="settings-panel-header"><span className="settings-card-icon cyan"><SettingsIcon type="organization" /></span><div><h2>Organization identity</h2><p>Information used across reports, campaigns and workspace communications.</p></div></div>
            <div className="settings-form-grid">
              <label className="settings-field"><span>Organization name</span><input value={preferences.organization_name} onChange={(e) => setPreferences({ ...preferences, organization_name: e.target.value })} placeholder="Your organization name" /></label>
              <label className="settings-field"><span>Primary domain</span><input value={preferences.primary_domain} onChange={(e) => setPreferences({ ...preferences, primary_domain: e.target.value })} placeholder="company.com" /></label>
            </div>
          </div>
        </section>
      )}

      {activeSection === 'directory' && (
        <section className="settings-content">
          <div className="settings-section-heading"><div><span className="settings-kicker">Enterprise integration</span><h2>LDAP Directory Integration</h2><p>Connect Dark Signal to a trusted LDAP or Active Directory source.</p></div><span className={`directory-status-pill ${directoryStatus}`}>{statusLabel}</span></div>
          <div className="directory-security-banner"><SettingsIcon type="security" /><div><strong>Protected directory credentials</strong><p>The bind password is encrypted by the backend, never returned to the browser and is never used to create application login accounts.</p></div></div>
          {userRole !== 'admin' ? <div className="settings-panel"><p className="muted">Only administrators can configure directory integrations.</p></div> : (
            <div className="settings-panel directory-panel">
              <div className="directory-panel-top">
                <label className="premium-switch"><input type="checkbox" checked={directory.enabled} onChange={(e) => updateDirectory('enabled', e.target.checked)} /><span /><div><strong>Enable LDAP integration</strong><small>Allows group browsing and controlled recipient synchronization.</small></div></label>
                <div className="directory-actions"><button className="action-btn secondary-btn" disabled={Boolean(directoryBusy) || !directoryMeta.configured} onClick={testDirectory}>{directoryBusy === 'test' ? 'Testing connection…' : 'Test connection'}</button><button className="action-btn primary-btn" disabled={Boolean(directoryBusy)} onClick={saveDirectory}>{directoryBusy === 'save' ? 'Saving…' : 'Save configuration'}</button></div>
              </div>
              {directoryError && <div className="settings-inline-error">{directoryError}</div>}
              {directoryMeta.last_test_message && !directoryError && <div className={`directory-result ${directoryStatus}`}>{directoryMeta.last_test_message}</div>}
              <div className="settings-form-section"><div><span>01</span><h3>Connection</h3><p>LDAP endpoint and service account used for read-only directory access.</p></div><div className="settings-form-grid">
                <label className="settings-field settings-field-wide"><span>Server URL</span><input value={directory.server_url} onChange={(e) => updateDirectory('server_url', e.target.value)} placeholder="ldaps://directory.company.local:636" /></label>
                <label className="settings-field"><span>Base DN</span><input value={directory.base_dn} onChange={(e) => updateDirectory('base_dn', e.target.value)} /></label>
                <label className="settings-field"><span>Group Base DN</span><input value={directory.group_base_dn || ''} onChange={(e) => updateDirectory('group_base_dn', e.target.value)} /></label>
                <label className="settings-field"><span>Bind DN / service account</span><input value={directory.bind_dn} onChange={(e) => updateDirectory('bind_dn', e.target.value)} /></label>
                <label className="settings-field"><span>Bind password</span><input type="password" value={directory.bind_password} onChange={(e) => updateDirectory('bind_password', e.target.value)} placeholder={directoryMeta.has_password ? 'Stored securely · leave blank to keep' : 'Required on first save'} autoComplete="new-password" /></label>
              </div></div>
              <div className="settings-form-section"><div><span>02</span><h3>Directory mapping</h3><p>Define which objects and attributes become campaign email recipients.</p></div><div className="settings-form-grid">
                <label className="settings-field settings-field-wide"><span>User filter</span><input className="mono-input" value={directory.user_filter} onChange={(e) => updateDirectory('user_filter', e.target.value)} /></label>
                <label className="settings-field settings-field-wide"><span>Group filter</span><input className="mono-input" value={directory.group_filter} onChange={(e) => updateDirectory('group_filter', e.target.value)} /></label>
                <label className="settings-field"><span>Email attribute</span><input value={directory.email_attribute} onChange={(e) => updateDirectory('email_attribute', e.target.value)} /></label>
                <label className="settings-field"><span>Full-name attribute</span><input value={directory.name_attribute} onChange={(e) => updateDirectory('name_attribute', e.target.value)} /></label>
                <label className="settings-field"><span>Department attribute</span><input value={directory.department_attribute} onChange={(e) => updateDirectory('department_attribute', e.target.value)} /></label>
                <div className="directory-transport"><label><input type="checkbox" checked={directory.use_ssl} onChange={(e) => updateDirectory('use_ssl', e.target.checked)} /> LDAPS / SSL</label><label><input type="checkbox" checked={directory.start_tls} onChange={(e) => updateDirectory('start_tls', e.target.checked)} /> STARTTLS</label><label><input type="checkbox" checked={directory.verify_tls_certificate} onChange={(e) => updateDirectory('verify_tls_certificate', e.target.checked)} /> Verify certificate</label></div>
              </div></div>
              <div className="directory-next-step"><div><strong>Next step: recipient synchronization</strong><p>After a successful connection test, open Users and choose “Import from LDAP” to select groups, preview members and synchronize recipients.</p></div><span>Admin only</span></div>
            </div>
          )}
        </section>
      )}

      {activeSection === 'security' && (
        <section className="settings-content"><div className="settings-section-heading"><div><span className="settings-kicker">Protection policy</span><h2>Security controls</h2></div><button className="action-btn primary-btn" onClick={savePreferences}>Save policy</button></div><div className="settings-panel compact-panel"><div className="settings-panel-header"><span className="settings-card-icon green"><SettingsIcon type="security" /></span><div><h2>Awareness enforcement</h2><p>Set the operational threshold used to prioritize recipient follow-up.</p></div></div><div className="settings-form-grid"><label className="settings-field"><span>Risk threshold</span><select value={preferences.risk_threshold} onChange={(e) => setPreferences({ ...preferences, risk_threshold: e.target.value })}><option>High</option><option>Medium</option><option>Low</option></select></label><label className="settings-field"><span>Auto-remediate</span><select value={preferences.auto_remediate} onChange={(e) => setPreferences({ ...preferences, auto_remediate: e.target.value })}><option>Enabled</option><option>Disabled</option></select></label></div></div></section>
      )}

      {activeSection === 'notifications' && (
        <section className="settings-content"><div className="settings-section-heading"><div><span className="settings-kicker">Signal delivery</span><h2>Notification preferences</h2></div><button className="action-btn primary-btn" onClick={savePreferences}>Save preferences</button></div><div className="settings-panel notification-panel">{[['campaign_completed', 'Campaign completed', 'Notify administrators when a campaign finishes.'], ['high_risk', 'High-risk recipient detected', 'Surface urgent awareness follow-up events.'], ['weekly_summary', 'Weekly summary email', 'Send a consolidated workspace performance report.']].map(([key, title, text]) => <label className="premium-switch notification-switch" key={key}><input type="checkbox" checked={preferences[key]} onChange={(e) => setPreferences({ ...preferences, [key]: e.target.checked })} /><span /><div><strong>{title}</strong><small>{text}</small></div></label>)}</div></section>
      )}

      {activeSection === 'email' && (
        <section className="settings-content"><div className="settings-section-heading"><div><span className="settings-kicker">Communications</span><h2>Email templates</h2><p>Edit the password-reset message sent to application accounts.</p></div><div className="settings-actions"><button className="action-btn secondary-btn" onClick={resetTemplate} disabled={templateStatus.loading || userRole !== 'admin'}>Reset default</button><button className="action-btn primary-btn" onClick={saveTemplate} disabled={templateStatus.loading || userRole !== 'admin'}>Save template</button></div></div><div className="settings-panel email-editor-panel">{userRole !== 'admin' ? <p className="muted">Only administrators can edit templates.</p> : <><div className="settings-field"><span>Subject</span><input value={templateState.subject} onChange={(e) => setTemplateState({ ...templateState, subject: e.target.value })} /></div><div className="email-editor-grid"><label className="settings-field"><span>Plain text</span><textarea rows="12" value={templateState.body_text} onChange={(e) => setTemplateState({ ...templateState, body_text: e.target.value })} /></label><label className="settings-field"><span>HTML</span><textarea rows="12" value={templateState.body_html} onChange={(e) => setTemplateState({ ...templateState, body_html: e.target.value })} /></label></div>{templateStatus.error && <p className="error-text">{templateStatus.error}</p>}<div className="template-help"><span>Available variables</span><div className="template-tags">{templateHelp.map((item) => <span key={item.token} className="template-tag">{item.token} · {item.description}</span>)}</div></div></>}</div></section>
      )}

      {toastMessage && <div className="toast">{toastMessage}</div>}
    </div>
  )
}

export default Settings
