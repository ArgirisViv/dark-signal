import React, { useEffect, useState } from 'react'
import axios from 'axios'
import { API_BASE_URL } from '../config'
import { useAuth } from '../context/AuthContext'
import ProfessionalMetricRing from '../components/ProfessionalMetricRing'
import './Analytics.css'

const GeoMap = React.lazy(() => import('../components/GeoMap'))

class MapErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false }
  }

  static getDerivedStateFromError() {
    return { hasError: true }
  }

  componentDidCatch(error) {
    console.error('Geo map failed to render', error)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="geo-fallback">
          <div>Map failed to load.</div>
          <div className="muted">Check internet or reload the page.</div>
        </div>
      )
    }
    return this.props.children
  }
}

function Analytics() {
  const { userRole, isAuthenticated } = useAuth()
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [dashboardData, setDashboardData] = useState(null)
  const [breakdowns, setBreakdowns] = useState({ departments: [], risks: [] })
  const [trends, setTrends] = useState([])
  const [geoData, setGeoData] = useState({ points: [], samples: [] })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [toastMessage, setToastMessage] = useState('')
  const [exportFormat, setExportFormat] = useState('pdf')
  const [dateRange, setDateRange] = useState('30')
  const [includeUsers, setIncludeUsers] = useState(true)
  const [includeScenarios, setIncludeScenarios] = useState(true)
  const [includeEvents, setIncludeEvents] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [campaigns, setCampaigns] = useState([])
  const [selectedCampaignId, setSelectedCampaignId] = useState('')

  const apiBase = API_BASE_URL
  const canViewAnalytics = userRole === 'admin' || userRole === 'analyst' || userRole === 'viewer'

  const showToast = (message) => {
    setToastMessage(message)
    window.setTimeout(() => setToastMessage(''), 2000)
  }

  useEffect(() => {
    const fetchAnalytics = async () => {
      try {
        const params = selectedCampaignId ? { campaign_id: selectedCampaignId } : {}
        const [dashboardResponse, breakdownsResponse, trendsResponse, geoResponse, campaignsResponse] = await Promise.all([
          axios.get(`${apiBase}/stats/dashboard`, { params }),
          axios.get(`${apiBase}/stats/breakdowns`, { params }),
          axios.get(`${apiBase}/stats/trends`, { params: { ...params, days: 30 } }),
          axios.get(`${apiBase}/stats/geo`, { params: { ...params, limit: 60 } }),
          axios.get(`${apiBase}/campaigns/`, { params: { include_scenarios: false, limit: 1000 } }),
        ])
        setDashboardData(dashboardResponse.data)
        setBreakdowns(breakdownsResponse.data || { departments: [], risks: [] })
        setTrends(trendsResponse.data?.points || [])
        setGeoData(geoResponse.data || { points: [], samples: [] })
        setCampaigns(campaignsResponse.data?.items || [])
      } catch (err) {
        const message = err?.response?.data?.detail || err.message
        setError(message || 'Failed to load analytics.')
      } finally {
        setLoading(false)
      }
    }

    if (!isAuthenticated) {
      setLoading(false)
      return
    }

    if (!userRole) {
      setLoading(true)
      return
    }

    if (canViewAnalytics) {
      fetchAnalytics()
    } else {
      setLoading(false)
      setError('You do not have access to analytics.')
    }
  }, [canViewAnalytics, isAuthenticated, userRole, selectedCampaignId])


  if (loading) {
    return <div className="container loading"><div className="spinner"></div></div>
  }

  if (error) {
    return <div className="container error">Error: {error}</div>
  }

  const summary = dashboardData?.summary || {}
  const topScenarios = dashboardData?.top_scenarios || []

  const riskCounts = breakdowns.risks.reduce(
    (acc, item) => {
      const risk = (item.risk || 'low').toLowerCase()
      const users = item.users || 0
      if (risk === 'high') acc.high += users
      else if (risk === 'medium') acc.medium += users
      else acc.low += users
      return acc
    },
    { high: 0, medium: 0, low: 0 }
  )
  const riskTotal = riskCounts.high + riskCounts.medium + riskCounts.low
  const highRiskPercent = riskTotal ? Math.round((riskCounts.high / riskTotal) * 100) : 0
  const highRiskShare = riskTotal ? (riskCounts.high / riskTotal) * 100 : 0
  const mediumRiskShare = riskTotal ? (riskCounts.medium / riskTotal) * 100 : 0
  const lowRiskShare = riskTotal ? (riskCounts.low / riskTotal) * 100 : 0

  const topDepartments = [...breakdowns.departments]
    .sort((a, b) => (b.click_rate || 0) - (a.click_rate || 0))
    .slice(0, 3)

  const formatPercent = (value) => (Number.isFinite(value) ? value.toFixed(1) : '0.0')
  const formatScore = (value) => (Number.isFinite(value) ? value.toFixed(1) : '0.0')
  const geoPoints = geoData.points || []
  const geoSamples = geoData.samples || []
  const mapCenter = [20, 0]
  const mapZoom = 1.6
  const overviewMetrics = [
    { label: 'Email recipients', value: summary.email_recipients || 0, detail: 'Imported recipients with recorded deliveries', tone: 'primary', progress: 100, icon: 'recipients' },
    { label: 'Campaigns', value: summary.total_campaigns || 0, detail: `${summary.total_scenarios || 0} scenarios configured`, tone: 'success', progress: 100, icon: 'campaigns' },
    { label: 'Clicked Links', value: `${formatPercent(summary.average_click_rate)}%`, detail: `${summary.clicked_count || 0}/${summary.email_recipients || 0} recipients`, tone: 'warning', progress: Math.min(summary.average_click_rate || 0, 100), icon: 'clicks', percentage: true },
    { label: 'Reported Emails', value: `${formatPercent(summary.average_report_rate)}%`, detail: `${summary.reported_count || 0}/${summary.email_recipients || 0} recipients`, tone: 'danger', progress: Math.min(summary.average_report_rate || 0, 100), icon: 'reports', percentage: true },
  ]
  const timelinePoints = trends.slice(-5)

  const handleExport = async () => {
    try {
      setExporting(true)
      const now = new Date()
      let dateFrom = null
      if (dateRange !== 'all') {
        const days = Number(dateRange)
        const from = new Date(now.getTime() - days * 24 * 60 * 60 * 1000)
        dateFrom = from.toISOString()
      }

      const payload = {
        format: exportFormat,
        include_users: includeUsers,
        include_scenarios: includeScenarios,
        include_events: includeEvents,
        date_from: dateFrom,
        date_to: dateRange === 'all' ? null : now.toISOString(),
        campaign_id: selectedCampaignId ? Number(selectedCampaignId) : null,
      }

      const isJson = exportFormat === 'json'
      const response = await axios.post(`${apiBase}/stats/export`, payload, {
        responseType: isJson ? 'json' : 'blob',
      })

      const blob = isJson
        ? new Blob([JSON.stringify(response.data, null, 2)], { type: 'application/json' })
        : response.data

      const extension = exportFormat
      const fileName = `dark-signal-analytics.${extension}`
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', fileName)
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
      showToast('Export completed.')
      setIsModalOpen(false)
    } catch (err) {
      const message = err?.response?.data?.detail || err.message
      showToast(message ? `Export failed: ${message}` : 'Export failed.')
    } finally {
      setExporting(false)
    }
  }

  return (
    <div className="container">
      <div className="page-header">
        <div>
          <h1 className="page-title">Advanced Analytics</h1>
          <p className="page-subtitle">Deep insights across campaigns, users, and outcomes.</p>
        </div>
        <div className="analytics-header-actions">
          <label>
            <span className="sr-only">Filter analytics by campaign</span>
            <select value={selectedCampaignId} onChange={(event) => setSelectedCampaignId(event.target.value)}>
              <option value="">All campaigns</option>
              {campaigns.map((campaign) => (
                <option key={campaign.id} value={campaign.id}>{campaign.name}</option>
              ))}
            </select>
          </label>
          <button className="action-btn secondary-btn" onClick={() => setIsModalOpen(true)}>
            Export Report
          </button>
        </div>
      </div>

      <section className="analytics-overview" aria-labelledby="analytics-overview-title">
        <div className="analytics-overview-header">
          <div>
            <span className="analytics-overview-eyebrow">Campaign analytics</span>
            <h2 id="analytics-overview-title">Performance overview</h2>
          </div>
          <div className="analytics-overview-facts" aria-label="Campaign totals">
            <span>{summary.email_recipients || 0} recipients</span>
            <span>{summary.total_campaigns || 0} campaigns</span>
            <span>{summary.total_scenarios || 0} scenarios</span>
            <span>{summary.total_events || 0} events</span>
          </div>
        </div>

        <div className="analytics-timeline" aria-label="Recent campaign trends">
          <div className="analytics-timeline-label">Campaign timeline</div>
          <div className="analytics-timeline-track">
            {timelinePoints.length ? timelinePoints.map((point, index) => (
              <div
                className="analytics-timeline-event"
                key={point.date}
                style={{ '--timeline-position': `${timelinePoints.length === 1 ? 50 : (index / (timelinePoints.length - 1)) * 100}%` }}
                title={`${point.date}: ${formatPercent(point.click_rate)}% click, ${formatPercent(point.report_rate)}% report`}
              >
                <span className="analytics-timeline-dot" />
                <span className="analytics-timeline-event-label">{point.date}</span>
              </div>
            )) : <span className="analytics-timeline-empty">Campaign trend data will appear here.</span>}
          </div>
        </div>

        <div className="analytics-overview-metrics">
          {overviewMetrics.map((metric) => (
            <ProfessionalMetricRing key={metric.label} {...metric} />
          ))}
        </div>
      </section>

      <div className="analytics-grid">
        <div className="card chart-card risk-breakdown-card">
          <div className="chart-header">
            <h2>Campaign Performance</h2>
            <span className="badge neutral">Last 30 days</span>
          </div>
          <div className="bar-chart">
            {topScenarios.slice(0, 5).map((scenario) => (
              <div
                key={scenario.scenario_id}
                className="bar"
                style={{ '--value': `${Math.min(100, Math.round(scenario.click_rate || 0))}%` }}
              >
                <span>{scenario.scenario_name || 'Scenario'}</span>
              </div>
            ))}
            {topScenarios.length === 0 && (
              <div className="empty-state">No scenario performance data yet. Run a simulation to populate this view.</div>
            )}
          </div>
        </div>
        <div className="card chart-card">
          <div className="chart-header">
            <h2>Risk Breakdown</h2>
            <span className="badge warning">This quarter</span>
          </div>
          <div className="donut">
            <svg className="risk-ring-progress" viewBox="0 0 120 120" aria-hidden="true">
              <circle className="risk-ring-track" cx="60" cy="60" r="52" pathLength="100" />
              <circle
                className="risk-ring-segment high"
                cx="60"
                cy="60"
                r="52"
                pathLength="100"
                style={{
                  '--risk-dasharray': `${highRiskShare} ${100 - highRiskShare}`,
                  '--risk-dashoffset': 0,
                  '--risk-delay': '120ms',
                }}
              />
              <circle
                className="risk-ring-segment medium"
                cx="60"
                cy="60"
                r="52"
                pathLength="100"
                style={{
                  '--risk-dasharray': `${mediumRiskShare} ${100 - mediumRiskShare}`,
                  '--risk-dashoffset': -highRiskShare,
                  '--risk-delay': '300ms',
                }}
              />
              <circle
                className="risk-ring-segment low"
                cx="60"
                cy="60"
                r="52"
                pathLength="100"
                style={{
                  '--risk-dasharray': `${lowRiskShare} ${100 - lowRiskShare}`,
                  '--risk-dashoffset': -(highRiskShare + mediumRiskShare),
                  '--risk-delay': '480ms',
                }}
              />
            </svg>
            <span className="risk-ring-orbit" aria-hidden="true" />
            <div className="donut-center">
              <strong>{highRiskPercent}%</strong>
              <span>High risk</span>
            </div>
          </div>
          <div className="legend">
            <div><span className="dot danger"></span> High ({riskCounts.high})</div>
            <div><span className="dot warning"></span> Medium ({riskCounts.medium})</div>
            <div><span className="dot success"></span> Low ({riskCounts.low})</div>
          </div>
        </div>
        <div className="card chart-card">
          <div className="chart-header">
            <h2>Engagement Trends</h2>
            <span className="badge neutral">Last 30 days</span>
          </div>
          <div className="trend-list">
            {trends.slice(-7).map((point) => (
              <div key={point.date} className="trend-row">
                <span>{point.date}</span>
                <strong>{formatPercent(point.click_rate)}% click</strong>
                <strong>{formatPercent(point.report_rate)}% report</strong>
              </div>
            ))}
            {trends.length === 0 && (
              <div className="empty-state">No trend data yet.</div>
            )}
          </div>
        </div>
        <div className="card chart-card geo-card">
          <div className="chart-header">
            <h2>Geo Map</h2>
            <span className="badge neutral">Live view</span>
          </div>
          <div className="geo-map">
            <MapErrorBoundary>
              <React.Suspense
                fallback={
                  <div className="geo-fallback">
                    <div>Loading map…</div>
                    <div className="muted">Please wait</div>
                  </div>
                }
              >
                <GeoMap points={geoPoints} />
              </React.Suspense>
            </MapErrorBoundary>
            {geoPoints.length === 0 && <div className="empty-state">No geo activity recorded yet.</div>}
          </div>
          <div className="geo-list">
            {geoSamples.slice(0, 5).map((sample) => (
              <div key={sample.event_id} className="geo-row">
                <span>{sample.ip}</span>
                <strong>{sample.city}, {sample.country}</strong>
              </div>
            ))}
            {geoSamples.length === 0 && (
              <div className="geo-row">
                <span>—</span>
                <strong>No click events yet.</strong>
              </div>
            )}
          </div>
        </div>
      </div>

      <section className="department-reporting" aria-labelledby="department-reporting-title">
        <div className="department-reporting-header">
          <div>
            <span className="analytics-overview-eyebrow">Department reporting</span>
            <h2 id="department-reporting-title">Risk and learning performance</h2>
          </div>
          <span className="badge neutral">{breakdowns.departments.length} departments</span>
        </div>
        <div className="department-table-wrap">
          <table className="department-table">
            <thead>
              <tr>
                <th>Department</th>
                <th>Users</th>
                <th>Click rate</th>
                <th>Report rate</th>
                <th>High risk</th>
                <th>Training complete</th>
              </tr>
            </thead>
            <tbody>
              {breakdowns.departments.length ? (
                breakdowns.departments.map((department) => (
                  <tr key={department.name}>
                    <td><strong>{department.name}</strong></td>
                    <td>{department.users}</td>
                    <td>{formatPercent(department.click_rate)}%</td>
                    <td>{formatPercent(department.report_rate)}%</td>
                    <td>
                      <span className={`badge ${department.high_risk_users ? 'danger' : 'success'}`}>
                        {department.high_risk_users}
                      </span>
                    </td>
                    <td>
                      {department.training_assignments
                        ? `${department.completed_training_assignments}/${department.training_assignments} (${formatPercent(department.training_completion_rate)}%)`
                        : 'No assignments'}
                    </td>
                  </tr>
                ))
              ) : (
                <tr><td colSpan={6}>No department data is available yet.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      {isModalOpen && (
        <div className="modal-backdrop" onClick={() => setIsModalOpen(false)}>
          <div className="modal" onClick={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <h3>Export Report</h3>
              <button className="icon-btn" onClick={() => setIsModalOpen(false)}>✕</button>
            </div>
            <div className="modal-body">
              <label className="field">
                Format
                <select value={exportFormat} onChange={(event) => setExportFormat(event.target.value)}>
                  <option value="pdf">PDF</option>
                  <option value="csv">CSV</option>
                  <option value="json">JSON</option>
                </select>
              </label>
              <label className="field">
                Date range
                <select value={dateRange} onChange={(event) => setDateRange(event.target.value)}>
                  <option value="7">Last 7 days</option>
                  <option value="30">Last 30 days</option>
                  <option value="90">Last 90 days</option>
                  <option value="all">All time</option>
                </select>
              </label>
              <label className="field">
                Include users
                <select value={includeUsers ? 'yes' : 'no'} onChange={(event) => setIncludeUsers(event.target.value === 'yes')}>
                  <option value="yes">Yes</option>
                  <option value="no">No</option>
                </select>
              </label>
              <label className="field">
                Include scenarios
                <select value={includeScenarios ? 'yes' : 'no'} onChange={(event) => setIncludeScenarios(event.target.value === 'yes')}>
                  <option value="yes">Yes</option>
                  <option value="no">No</option>
                </select>
              </label>
              <label className="field">
                Include events
                <select value={includeEvents ? 'yes' : 'no'} onChange={(event) => setIncludeEvents(event.target.value === 'yes')}>
                  <option value="yes">Yes</option>
                  <option value="no">No</option>
                </select>
              </label>
            </div>
            <div className="modal-footer">
              <button className="action-btn secondary-btn" onClick={() => setIsModalOpen(false)}>
                Cancel
              </button>
              <button className="action-btn primary-btn" onClick={handleExport} disabled={exporting}>
                {exporting ? 'Exporting...' : 'Export'}
              </button>
            </div>
          </div>
        </div>
      )}

      {toastMessage && <div className="toast">{toastMessage}</div>}
    </div>
  )
}

export default Analytics
