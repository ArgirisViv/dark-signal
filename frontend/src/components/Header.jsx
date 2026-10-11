import React, { useEffect, useMemo, useState } from 'react'
import { Link, NavLink, useLocation, useNavigate } from '../router'
import { useAuth } from '../context/AuthContext'
import logoEye from '../assets/dark-signal-logo-eye.svg'
import './Header.css'

function Header() {
  const { logout, userEmail, userRole } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [menuOpen, setMenuOpen] = useState(false)
  const canAnalyze = userRole === 'admin' || userRole === 'analyst' || userRole === 'viewer'
  const canManage = userRole === 'admin'
  const displayRole = userRole ? `${userRole.charAt(0).toUpperCase()}${userRole.slice(1)}` : 'Account'
  const accountInitial = (userEmail || displayRole).trim().charAt(0).toUpperCase()

  const navigationItems = useMemo(() => [
    { to: '/', label: 'Dashboard', visible: true, end: true },
    { to: '/scenarios', label: 'Campaigns', visible: canAnalyze },
    { to: '/users', label: 'Users', visible: canManage },
    { to: '/analytics', label: 'Analytics', visible: canAnalyze },
    { to: '/templates', label: 'Templates', visible: canAnalyze },
    { to: '/settings', label: 'Settings', visible: canManage },
  ].filter((item) => item.visible), [canAnalyze, canManage])

  useEffect(() => {
    setMenuOpen(false)
  }, [location.pathname])

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <header className={`header ${menuOpen ? 'menu-is-open' : ''}`}>
      <div className="header-content">
        <Link to="/" className="logo">
          <span className="logo-mark-shell">
            <img className="logo-mark" src={logoEye} alt="Dark Signal" />
            <span className="logo-signal" aria-hidden="true" />
          </span>
          <div className="logo-text">
            <span className="logo-title">Dark Signal</span>
            <span className="logo-tagline">Cyber Training Platform</span>
          </div>
        </Link>

        <button
          className="menu-toggle"
          type="button"
          aria-label={menuOpen ? 'Close navigation menu' : 'Open navigation menu'}
          aria-expanded={menuOpen}
          aria-controls="primary-navigation-panel"
          onClick={() => setMenuOpen((open) => !open)}
        >
          <span />
          <span />
          <span />
        </button>

        <div id="primary-navigation-panel" className={`header-panel ${menuOpen ? 'open' : ''}`}>
          <nav className="nav" aria-label="Primary navigation">
            {navigationItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
              >
                <span className="nav-link-signal" aria-hidden="true" />
                <span>{item.label}</span>
              </NavLink>
            ))}
          </nav>

          <div className="nav-account">
            <span className="nav-avatar" aria-hidden="true">{accountInitial}</span>
            <span className="nav-identity">
              <span className="nav-user" title={userEmail || displayRole}>{userEmail || displayRole}</span>
              <span className="nav-role">{displayRole}</span>
            </span>
            <span className="nav-account-divider" aria-hidden="true" />
            <button
              className="nav-logout"
              type="button"
              onClick={handleLogout}
              title="Sign out"
              aria-label="Logout"
            >
              <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="M10 5H6.8A1.8 1.8 0 0 0 5 6.8v10.4A1.8 1.8 0 0 0 6.8 19H10" />
                <path d="m15 8 4 4-4 4M9 12h10" />
              </svg>
              <span>Logout</span>
            </button>
          </div>
        </div>
      </div>
      {menuOpen && (
        <button
          className="mobile-nav-backdrop"
          type="button"
          aria-label="Close navigation menu"
          onClick={() => setMenuOpen(false)}
        />
      )}
    </header>
  )
}

export default Header
