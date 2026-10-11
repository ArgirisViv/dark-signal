import React from 'react'
import './ProfessionalMetricRing.css'

function MetricIcon({ type }) {
  const props = {
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.8,
    strokeLinecap: 'round',
    strokeLinejoin: 'round',
    'aria-hidden': true,
  }
  if (type === 'campaigns') {
    return <svg {...props}><path d="M4 5h10l2 3h4v9H4V5Z" /><path d="M8 12h8" /><path d="M8 15h5" /></svg>
  }
  if (type === 'clicks') {
    return <svg {...props}><path d="m5 3 13 9-6 1-3 6L5 3Z" /><path d="m13 14 4 5" /></svg>
  }
  if (type === 'reports') {
    return <svg {...props}><path d="M12 3 19 6v5c0 4.6-2.8 8-7 10-4.2-2-7-5.4-7-10V6l7-3Z" /><path d="m9 12 2 2 4-4" /></svg>
  }
  return <svg {...props}><rect x="3" y="5" width="18" height="14" rx="2" /><path d="m4 7 8 6 8-6" /></svg>
}

function ProfessionalMetricRing({ label, value, detail, tone, progress, icon, percentage = false }) {
  const safeProgress = Math.max(0, Math.min(Number(progress) || 0, 100))
  const ringOffset = percentage ? 100 - safeProgress : 0

  return (
    <article className={`professional-metric-card ${tone} ${percentage ? 'percentage-metric' : 'count-metric'}`}>
      <div
        className="professional-metric-ring"
        aria-label={`${label}: ${value}`}
      >
        <svg className="professional-ring-progress" viewBox="0 0 120 120" aria-hidden="true">
          <circle className="professional-ring-track" cx="60" cy="60" r="52" pathLength="100" />
          <circle
            className={`professional-ring-value ${percentage ? 'animated-progress' : 'decorative-progress'}`}
            cx="60"
            cy="60"
            r="52"
            pathLength="100"
            style={{ '--metric-ring-offset': ringOffset }}
          />
        </svg>
        <span className="professional-ring-orbit" aria-hidden="true" />
        <div className="professional-ring-center">
          <span className="professional-ring-icon"><MetricIcon type={icon} /></span>
          <strong>{value}</strong>
        </div>
      </div>
      <div className="professional-metric-copy">
        <div className="professional-metric-label">{label}</div>
        <div className="professional-metric-detail">{detail}</div>
      </div>
    </article>
  )
}

export default ProfessionalMetricRing
