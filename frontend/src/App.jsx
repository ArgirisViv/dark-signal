import React from 'react'
import { BrowserRouter as Router, Routes, Route, useLocation } from './router'
import { ThemeProvider } from './context/ThemeContext'
import { AuthProvider, useAuth } from './context/AuthContext'
import Header from './components/Header'
import ProtectedRoute from './components/ProtectedRoute'
import Dashboard from './pages/Dashboard'
import Scenarios from './pages/Scenarios'
import Users from './pages/Users'
import Analytics from './pages/Analytics'
import Templates from './pages/Templates'
import Settings from './pages/Settings'
import Login from './pages/Login'
import ResetPassword from './pages/ResetPassword'
import './App.css'

class AppErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false }
  }

  static getDerivedStateFromError() {
    return { hasError: true }
  }

  componentDidCatch(error) {
    console.error('App render failed', error)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="container error">
          Something went wrong. Try refreshing the page.
        </div>
      )
    }
    return this.props.children
  }
}

function AppContent() {
  const location = useLocation()
  const { isAuthenticated } = useAuth()
  const hideHeader = location.pathname === '/login' || location.pathname === '/reset-password'

  return (
    <div className="app">
      <div className="cyber-background" aria-hidden="true">
        <span className="cyber-background-network" />
        <span className="cyber-background-beam" />
        <span className="cyber-background-node node-one" />
        <span className="cyber-background-node node-two" />
        <span className="cyber-background-node node-three" />
      </div>
      {!hideHeader && isAuthenticated && <Header />}
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/reset-password" element={<ResetPassword />} />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <Dashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/templates"
          element={
            <ProtectedRoute allowedRoles={['admin', 'analyst', 'viewer']}>
              <Templates />
            </ProtectedRoute>
          }
        />
        <Route
          path="/scenarios"
          element={
            <ProtectedRoute allowedRoles={['admin', 'analyst', 'viewer']}>
              <Scenarios />
            </ProtectedRoute>
          }
        />
        <Route
          path="/users"
          element={
            <ProtectedRoute allowedRoles={['admin']}>
              <Users />
            </ProtectedRoute>
          }
        />
        <Route
          path="/analytics"
          element={
            <ProtectedRoute allowedRoles={['admin', 'analyst', 'viewer']}>
              <Analytics />
            </ProtectedRoute>
          }
        />
        <Route
          path="/settings"
          element={
            <ProtectedRoute allowedRoles={['admin']}>
              <Settings />
            </ProtectedRoute>
          }
        />
        <Route path="*" element={<Login />} />
      </Routes>
    </div>
  )
}

function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <Router>
          <AppErrorBoundary>
            <AppContent />
          </AppErrorBoundary>
        </Router>
      </AuthProvider>
    </ThemeProvider>
  )
}

export default App
