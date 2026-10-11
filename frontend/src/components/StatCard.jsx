import React from 'react'
import './Stats.css'

function StatCard({ label, value, change, icon, iconType, color = 'primary' }) {
  const renderIcon = () => {
    switch (iconType) {
      case 'users':
        return (
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <circle cx="8" cy="8" r="3" />
            <circle cx="17" cy="9" r="2.5" />
            <path d="M3 20c0-3 2.5-5 5-5s5 2 5 5" />
            <path d="M13.5 20c0-2 1.6-3.5 3.5-3.5s3.5 1.5 3.5 3.5" />
          </svg>
        )
      case 'target':
        return (
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <circle cx="12" cy="12" r="8" />
            <circle cx="12" cy="12" r="4" />
            <circle cx="12" cy="12" r="1.5" />
          </svg>
        )
      case 'click':
        return (
          <svg viewBox="0 0 24 24" aria-hidden="true" className="icon-click">
            <path d="M3 2l10 14-4-1.2 1.8 5.2-2.2 0.8-1.8-5-3.8 2z" />
          </svg>
        )
      case 'report':
        return (
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <rect x="5" y="3" width="14" height="18" rx="2" />
            <path d="M8 8h8" />
            <path d="M8 12h8" />
            <path d="M8 16h5" />
          </svg>
        )
      default:
        return icon
    }
  }

  return (
    <div className={`stat-card stat-card-${color}`}>
      <div className="stat-icon">
        {iconType ? renderIcon() : icon}
      </div>
      <div className="stat-content">
        <div className="stat-label">{label}</div>
        <div className="stat-value">{value}</div>
        {change && <div className={`stat-change ${change.positive ? 'positive' : 'negative'}`}>
          {change.positive ? '↑' : '↓'} {change.value}
        </div>}
      </div>
    </div>
  )
}

export default StatCard
