import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'

const RouterContext = createContext(null)

const currentLocation = () => ({
  pathname: window.location.pathname || '/',
  search: window.location.search || '',
})

export function BrowserRouter({ children }) {
  const [location, setLocation] = useState(currentLocation)

  useEffect(() => {
    const handlePopState = () => setLocation(currentLocation())
    window.addEventListener('popstate', handlePopState)
    return () => window.removeEventListener('popstate', handlePopState)
  }, [])

  const navigate = useCallback((target, options = {}) => {
    const nextUrl = new URL(String(target || '/'), window.location.origin)
    const nextPath = `${nextUrl.pathname}${nextUrl.search}${nextUrl.hash}`
    if (options.replace) {
      window.history.replaceState({}, '', nextPath)
    } else {
      window.history.pushState({}, '', nextPath)
    }
    setLocation({ pathname: nextUrl.pathname, search: nextUrl.search })
  }, [])

  const value = useMemo(() => ({ location, navigate }), [location, navigate])
  return <RouterContext.Provider value={value}>{children}</RouterContext.Provider>
}

export function useLocation() {
  const context = useContext(RouterContext)
  if (!context) throw new Error('useLocation must be used inside BrowserRouter')
  return context.location
}

export function useNavigate() {
  const context = useContext(RouterContext)
  if (!context) throw new Error('useNavigate must be used inside BrowserRouter')
  return context.navigate
}

export function useSearchParams() {
  const { search } = useLocation()
  const navigate = useNavigate()
  const params = useMemo(() => new URLSearchParams(search), [search])
  const setParams = useCallback((next, options = {}) => {
    const resolved = typeof next === 'function' ? next(new URLSearchParams(search)) : next
    const query = new URLSearchParams(resolved).toString()
    navigate(`${window.location.pathname}${query ? `?${query}` : ''}`, options)
  }, [navigate, search])
  return [params, setParams]
}

const shouldHandleClick = (event) => (
  !event.defaultPrevented
  && event.button === 0
  && !event.metaKey
  && !event.altKey
  && !event.ctrlKey
  && !event.shiftKey
)

export function Link({ to, children, onClick, ...props }) {
  const navigate = useNavigate()
  const handleClick = (event) => {
    onClick?.(event)
    if (!shouldHandleClick(event)) return
    event.preventDefault()
    navigate(to)
  }
  return <a href={to} onClick={handleClick} {...props}>{children}</a>
}

export function NavLink({ to, end = false, className, children, ...props }) {
  const location = useLocation()
  const isActive = end
    ? location.pathname === to
    : location.pathname === to || location.pathname.startsWith(`${to}/`)
  const resolvedClassName = typeof className === 'function' ? className({ isActive }) : className
  return <Link to={to} className={resolvedClassName} {...props}>{children}</Link>
}

export function Navigate({ to, replace = false }) {
  const navigate = useNavigate()
  useEffect(() => navigate(to, { replace }), [navigate, replace, to])
  return null
}

export function Route() {
  return null
}

export function Routes({ children }) {
  const location = useLocation()
  const routes = React.Children.toArray(children)
  const exactMatch = routes.find((route) => route.props.path === location.pathname)
  const fallback = routes.find((route) => route.props.path === '*')
  return exactMatch?.props.element ?? fallback?.props.element ?? null
}
