import React, { useEffect, useState } from 'react'
import { useNavigate } from '../router'
import axios from 'axios'
import { useAuth } from '../context/AuthContext'
import { API_BASE_URL } from '../config'
import ProfessionalMetricRing from '../components/ProfessionalMetricRing'
import './Dashboard.css'

function Dashboard() {
  const [dashboardData, setDashboardData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [recentEvents, setRecentEvents] = useState([])
  const [operationalAlerts, setOperationalAlerts] = useState([])
  const [dashboardRefreshSignal, setDashboardRefreshSignal] = useState(0)
  const [auditFilters, setAuditFilters] = useState({ action_type: '', user: '', campaign: '', date_from: '', date_to: '' })
  const [isAuditLogOpen, setIsAuditLogOpen] = useState(false)
  const [exporting, setExporting] = useState(false)
  const navigate = useNavigate()
  const { token, userRole } = useAuth()
  const apiBase = API_BASE_URL

  useEffect(() => {
    const fetchDashboard = async () => {
      setError(null)
      try {
        const dashboardResponse = await axios.get(`${apiBase}/stats/dashboard`)
        setDashboardData(dashboardResponse.data)

        if (userRole === 'admin') {
          try {
            const alertsResponse = await axios.get(`${apiBase}/stats/operational-alerts`)
            setOperationalAlerts(alertsResponse.data?.alerts || [])
          } catch (alertsError) {
            setOperationalAlerts([])
          }
        } else {
          setOperationalAlerts([])
        }

      } catch (err) {
        const message = err?.response?.status === 403
          ? 'Access denied.'
          : err?.response?.data?.detail || 'Dashboard data could not be loaded.'
        setError(message)
      } finally {
        setLoading(false)
      }
    }

    fetchDashboard()
    const interval = setInterval(fetchDashboard, 30000) // Refresh every 30 seconds
    return () => clearInterval(interval)
  }, [userRole, dashboardRefreshSignal])

  useEffect(() => {
    const canReceiveUpdates = (userRole === 'admin' || userRole === 'analyst' || userRole === 'viewer') && token
    if (!canReceiveUpdates) return undefined

    const websocketBase = apiBase.replace(/^http/, 'ws')
    const socket = new WebSocket(`${websocketBase}/ws/notifications?topic=analytics&token=${encodeURIComponent(token)}`)
    socket.onmessage = (message) => {
      try {
        if (JSON.parse(message.data).type === 'analytics_update') {
          setDashboardRefreshSignal((signal) => signal + 1)
        }
      } catch {
        // Ignore malformed messages and continue using periodic refresh.
      }
    }
    return () => socket.close()
  }, [apiBase, token, userRole])

  useEffect(() => {
    const canViewEvents = userRole === 'admin' || userRole === 'analyst' || userRole === 'viewer'
    if (!canViewEvents) {
      setRecentEvents([])
      return undefined
    }
    const fetchEvents = async () => {
      const params = { limit: 50 }
      Object.entries(auditFilters).forEach(([key, value]) => {
        if (value) params[key] = value
      })
      try {
        const eventsResponse = await axios.get(`${apiBase}/events/`, { params })
        setRecentEvents(eventsResponse.data || [])
      } catch (eventsError) {
        setRecentEvents([])
      }
    }
    const timer = window.setTimeout(fetchEvents, 250)
    return () => window.clearTimeout(timer)
  }, [userRole, auditFilters, dashboardRefreshSignal])

  const handleExport = async (format = 'csv') => {
    setExporting(true)
    try {
      const response = await axios.post(
        `${apiBase}/stats/export`,
        {
          format,
          include_users: true,
          include_scenarios: true,
          include_events: false,
        },
        { responseType: 'blob' }
      )

      const contentDisposition = response.headers['content-disposition'] || ''
      const filenameMatch = /filename="?([^"]+)"?/.exec(contentDisposition)
      const filename = filenameMatch ? filenameMatch[1] : `phishing-dashboard-export.${format}`

      const url = window.URL.createObjectURL(
        new Blob([response.data], { type: response.headers['content-type'] || 'text/csv' })
      )
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = filename
      document.body.appendChild(anchor)
      anchor.click()
      anchor.remove()
      window.URL.revokeObjectURL(url)
    } catch (err) {
      setError('Failed to download export. Please try again.')
    } finally {
      setExporting(false)
    }
  }

  const handleAcknowledgeAlert = async (alertId) => {
    try {
      await axios.post(`${apiBase}/stats/operational-alerts/${alertId}/acknowledge`)
      setOperationalAlerts((current) => current.filter((alert) => alert.id !== alertId))
    } catch (acknowledgementError) {
      setError('Failed to acknowledge the alert. Please try again.')
    }
  }

  const handleExportAuditLog = () => {
    const escapeCsv = (value) => `"${String(value ?? '').replaceAll('"', '""')}"`
    const rows = [
      ['User', 'Campaign', 'Action', 'Time'],
      ...recentEvents.map((event) => [
        event.user_email || `User #${event.user_id || 'unknown'}`,
        event.scenario_title || '',
        formatAction(event.action),
        formatTimestamp(event.created_at),
      ]),
    ]
    const blob = new Blob([rows.map((row) => row.map(escapeCsv).join(',')).join('\n')], { type: 'text/csv;charset=utf-8' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'dark-signal-audit-log.csv'
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)
  }

  const formatAction = (action) => {
    if (!action) return 'Unknown event'

    const actions = {
      'click': 'Clicked phishing link',
      'report': 'Reported phishing',
      'opened': 'Opened email',
      'scenario.created': 'Scenario created',
      'scenario.updated': 'Scenario updated',
      'scenario.deleted': 'Scenario deleted',
      'user.created': 'User created',
      'user.updated': 'User updated',
      'user.deleted': 'User deleted',
    }

    if (actions[action]) return actions[action]
    if (action.startsWith('scenario.')) return action.replace('scenario.', 'Scenario ')
    if (action.startsWith('user.')) return action.replace('user.', 'User ')
    return action.replace(/[:.]/g, ' ')
  }

  const getEventStatus = (action) => {
    if (!action) return { label: 'Unknown', type: 'neutral' }
    if (action.includes('click')) return { label: 'Clicked', type: 'danger' }
    if (action.includes('report')) return { label: 'Reported', type: 'success' }
    if (action.includes('open') || action.includes('view')) return { label: 'Opened', type: 'warning' }
    if (action.startsWith('scenario.')) return { label: 'Scenario update', type: 'neutral' }
    if (action.startsWith('user.')) return { label: 'User update', type: 'neutral' }
    return { label: action.replace(/[:.]/g, ' '), type: 'neutral' }
  }

  const formatTime = (value) => {
    if (!value) return '—'
    const date = new Date(value)
    return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString()
  }

  const formatTimestamp = (value) => {
    if (!value) return '—'
    const date = new Date(value)
    return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString()
  }

  const data = dashboardData || {}
  const summary = data.summary || {}
  const totalEvents = summary.total_events || 0
  const topCampaign = data.top_campaigns?.find((campaign) => campaign.total_recipients > 0)
  const recipientRankings = data.recipient_rankings || []
  const topRecipient = recipientRankings[0]
  const lastUpdated = data.last_updated || summary.updated_at
  const metrics = [
    { label: 'Email recipients', value: summary.email_recipients || 0, detail: 'Imported recipients with recorded deliveries', tone: 'primary', progress: 100, icon: 'recipients' },
    { label: 'Campaigns', value: summary.total_campaigns || 0, detail: `${summary.total_scenarios || 0} scenarios configured`, tone: 'success', progress: 100, icon: 'campaigns' },
    { label: 'Clicked Links', value: `${(summary.average_click_rate || 0).toFixed(1)}%`, detail: `${summary.clicked_count || 0}/${summary.email_recipients || 0} recipients`, tone: 'warning', progress: Math.min(summary.average_click_rate || 0, 100), icon: 'clicks', percentage: true },
    { label: 'Reported Emails', value: `${(summary.average_report_rate || 0).toFixed(1)}%`, detail: `${summary.reported_count || 0}/${summary.email_recipients || 0} recipients`, tone: 'danger', progress: Math.min(summary.average_report_rate || 0, 100), icon: 'reports', percentage: true },
  ]
  const timelineEvents = recentEvents.slice(0, 5)

  if (loading && !dashboardData) {
    return (
      <div className="dashboard">
        <div className="container">
          <div className="card dashboard-state" role="status">Loading dashboard data…</div>
        </div>
      </div>
    )
  }

  if (error && !dashboardData) {
    return (
      <div className="dashboard">
        <div className="container">
          <div className="card dashboard-state dashboard-state-error" role="alert">
            <h2>Dashboard unavailable</h2>
            <p>{error}</p>
            <button
              type="button"
              className="action-btn primary-btn"
              onClick={() => {
                setLoading(true)
                setDashboardRefreshSignal((signal) => signal + 1)
              }}
            >
              Try again
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="dashboard">
      <div className="container">
        <div className="dashboard-header">
          <div>
            <h1 className="page-title">Dashboard</h1>
            <p className="page-subtitle">Live campaign overview, user performance and recent activity.</p>
          </div>
          <div className="dashboard-meta">
            <span className="badge neutral">Updated</span>
            <span>{formatTimestamp(lastUpdated)}</span>
          </div>
        </div>

        {error && (
          <div className="dashboard-error-banner" role="alert">
            <span>{error}</span>
            <button type="button" onClick={() => setError(null)} aria-label="Dismiss message">×</button>
          </div>
        )}

        <section className="dashboard-section dashboard-quick-actions" aria-labelledby="quick-actions-title">
          <div className="quick-actions-heading">
            <div>
              <span className="overview-eyebrow">Workspace shortcuts</span>
              <h2 id="quick-actions-title">Quick Actions</h2>
            </div>
            <span className="quick-actions-hint">Frequent tasks, one click away</span>
          </div>
          <div className="actions-grid">
            {(userRole === 'admin' || userRole === 'analyst') && (
              <button className="action-btn primary-btn" onClick={() => navigate('/scenarios')}>
                <span className="quick-action-icon" aria-hidden="true">+</span>
                <span>Create Campaign</span>
              </button>
            )}
            {userRole === 'admin' && (
              <button className="action-btn secondary-btn" onClick={() => navigate('/users')}>
                <span className="quick-action-icon" aria-hidden="true">U</span>
                <span>Manage Users</span>
              </button>
            )}
            <button className="action-btn secondary-btn" onClick={() => navigate('/analytics')}>
              <span className="quick-action-icon" aria-hidden="true">↗</span>
              <span>View Reports</span>
            </button>
            <button className="action-btn secondary-btn" onClick={() => setIsAuditLogOpen(true)}>
              <span className="quick-action-icon" aria-hidden="true">≡</span>
              <span>Open Audit Log</span>
            </button>
            <button
              className="action-btn secondary-btn export-btn"
              onClick={() => handleExport('csv')}
              disabled={exporting}
            >
              <span className="quick-action-icon" aria-hidden="true">↓</span>
              <span>{exporting ? 'Exporting...' : 'Export CSV'}</span>
            </button>
          </div>
        </section>

        <section className="campaign-overview" aria-labelledby="campaign-overview-title">
          <div className="campaign-overview-header">
            <div>
              <span className="overview-eyebrow">Campaign analytics</span>
              <h2 id="campaign-overview-title">Current performance</h2>
            </div>
            <div className="campaign-facts" aria-label="Campaign totals">
              <span>{summary.email_recipients || 0} email recipients</span>
              <span>{summary.total_campaigns || 0} campaigns</span>
              <span>{summary.total_scenarios || 0} scenarios</span>
              <span>{totalEvents} events</span>
            </div>
          </div>

          <div className="campaign-timeline" aria-label="Latest campaign activity">
            <div className="timeline-label">Campaign timeline</div>
            <div className="timeline-track">
              {timelineEvents.length ? timelineEvents.map((event, index) => {
                const status = getEventStatus(event.action)
                return (
                  <div
                    className={`timeline-event ${status.type}`}
                    key={event.id}
                    style={{ '--timeline-position': `${timelineEvents.length === 1 ? 50 : (index / (timelineEvents.length - 1)) * 100}%` }}
                    title={`${formatAction(event.action)} - ${formatTime(event.created_at)}`}
                  >
                    <span className="timeline-dot" />
                    <span className="timeline-event-label">{status.label}</span>
                  </div>
                )
              }) : <span className="timeline-empty">New campaign activity will appear here.</span>}
            </div>
          </div>

          <div className="campaign-metrics">
            {metrics.map((metric) => (
              <ProfessionalMetricRing key={metric.label} {...metric} />
            ))}
          </div>
        </section>

        <div className="dashboard-highlights">
          <div className="card highlight-card">
            <div className="highlight-title">Best campaign</div>
            <div className="highlight-value">{topCampaign?.campaign_name || 'No campaign results yet'}</div>
            <div className="highlight-meta">
              {topCampaign
                ? `Awareness score ${topCampaign.awareness_score.toFixed(1)}/100 (60% click avoidance + 40% reporting) · ${topCampaign.score_explanation}`
                : 'Send campaign emails to compare campaign performance.'}
            </div>
          </div>
          <div className="card highlight-card">
            <div className="highlight-title">Best awareness email recipient</div>
            <div className="highlight-value">{topRecipient?.recipient_email || 'No recipient performance data yet'}</div>
            <div className="highlight-meta">
              {topRecipient
                ? `Awareness score ${topRecipient.training_score.toFixed(1)}/100 (60% click avoidance + 40% reporting) · ${topRecipient.score_explanation}`
                : 'Import email recipients and send a campaign to start tracking awareness scores.'}
            </div>
          </div>
          <div className="card highlight-card">
            <div className="highlight-title">Platform health</div>
            <div className="highlight-value">{totalEvents ? `${totalEvents} events` : 'No events yet'}</div>
            <div className="highlight-meta">
              {lastUpdated ? `Last refreshed ${formatTimestamp(lastUpdated)}` : 'Waiting for data...'}
            </div>
          </div>
        </div>

        {userRole === 'admin' && (
          <section className="operational-alerts" aria-labelledby="operational-alerts-title">
            <div className="operational-alerts-header">
              <div>
                <span className="overview-eyebrow">Operational queue</span>
                <h2 id="operational-alerts-title">Needs attention</h2>
              </div>
              <span className="badge neutral">{operationalAlerts.length} open</span>
            </div>
            {operationalAlerts.length ? (
              <div className="operational-alert-list">
                {operationalAlerts.map((alert) => (
                  <article className={`operational-alert ${alert.severity}`} key={alert.id}>
                    <div>
                      <strong>{alert.title}</strong>
                      <p>{alert.description}</p>
                    </div>
                    <div className="operational-alert-actions">
                      <button className="link-btn" onClick={() => navigate(alert.action_path)}>
                        {alert.action_label}
                      </button>
                      <button className="link-btn muted-link" onClick={() => handleAcknowledgeAlert(alert.id)}>
                        Acknowledge
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <p className="operational-alert-empty">No immediate follow-up is required.</p>
            )}
          </section>
        )}

        <section className="dashboard-section">
          <h2>Performance Insights</h2>
          <div className="insights-grid dashboard-insights-grid">
              <div className="card top-list">
                <h3>Top scenarios</h3>
                <ul>
                  {data.top_scenarios?.length ? (
                    data.top_scenarios.slice(0, 5).map((scenario) => (
                      <li key={scenario.scenario_id}>
                        <strong>{scenario.scenario_name}</strong>
                        <span>
                          {scenario.click_rate.toFixed(1)}% click · {scenario.click_count}/{scenario.total_recipients} clicked · {scenario.total_recipients} recipients
                        </span>
                      </li>
                    ))
                  ) : (
                    <li className="empty-state">No scenario insights available.</li>
                  )}
                </ul>
              </div>
              <div className="card top-list">
                <h3>Top email recipients</h3>
                <ul>
                  {recipientRankings.length ? (
                    recipientRankings.slice(0, 5).map((recipient) => (
                      <li key={recipient.recipient_id}>
                        <strong>{recipient.recipient_email}</strong>
                        <span>Score {recipient.training_score.toFixed(1)} · {recipient.total_scenarios_exposed} delivered scenarios</span>
                      </li>
                    ))
                  ) : (
                    <li className="empty-state">No email recipient rankings available.</li>
                  )}
                </ul>
              </div>
          </div>
        </section>
      </div>

      {isAuditLogOpen && (
        <div className="audit-modal-backdrop" role="presentation" onMouseDown={() => setIsAuditLogOpen(false)}>
          <section
            className="audit-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="audit-modal-title"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <div className="audit-modal-header">
              <div>
                <span className="overview-eyebrow">Activity center</span>
                <h2 id="audit-modal-title">Audit Log</h2>
                <p>Review, filter and export recorded application activity.</p>
              </div>
              <div className="audit-header-actions">
                <span className="badge neutral">{recentEvents.length} events</span>
                <button className="link-btn" disabled={!recentEvents.length} onClick={handleExportAuditLog}>Export CSV</button>
                <button className="audit-modal-close" type="button" onClick={() => setIsAuditLogOpen(false)} aria-label="Close audit log">×</button>
              </div>
            </div>
            <div className="audit-filters">
              <select aria-label="Filter by action type" value={auditFilters.action_type} onChange={(event) => setAuditFilters({ ...auditFilters, action_type: event.target.value })}>
                <option value="">All activity</option>
                <option value="simulation">Simulation behavior</option>
                <option value="scenario">Campaign changes</option>
                <option value="user">User changes</option>
                <option value="training">Training follow-up</option>
              </select>
              <input aria-label="Filter by user" placeholder="User" value={auditFilters.user} onChange={(event) => setAuditFilters({ ...auditFilters, user: event.target.value })} />
              <input aria-label="Filter by campaign" placeholder="Campaign" value={auditFilters.campaign} onChange={(event) => setAuditFilters({ ...auditFilters, campaign: event.target.value })} />
              <input aria-label="Filter from date" type="date" value={auditFilters.date_from} onChange={(event) => setAuditFilters({ ...auditFilters, date_from: event.target.value })} />
              <input aria-label="Filter to date" type="date" value={auditFilters.date_to} onChange={(event) => setAuditFilters({ ...auditFilters, date_to: event.target.value })} />
              <button className="link-btn" onClick={() => setAuditFilters({ action_type: '', user: '', campaign: '', date_from: '', date_to: '' })}>Clear</button>
            </div>
            <div className="audit-table-viewport" tabIndex="0" aria-label="Scrollable audit activity">
              <table className="activity-table">
                <thead>
                  <tr><th>User</th><th>Campaign</th><th>Action</th><th>Time</th><th>Status</th></tr>
                </thead>
                <tbody>
                  {recentEvents.length === 0 && <tr><td colSpan={5}>No audit activity matches the selected filters.</td></tr>}
                  {recentEvents.map((event) => {
                    const status = getEventStatus(event.action)
                    return (
                      <tr key={event.id}>
                        <td>{event.user_email || `User #${event.user_id}`}</td>
                        <td>{event.scenario_title || '—'}</td>
                        <td>{formatAction(event.action)}</td>
                        <td>{formatTime(event.created_at)}</td>
                        <td><span className={`badge ${status.type}`}>{status.label}</span></td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </section>
        </div>
      )}
    </div>
  )
}

export default Dashboard
