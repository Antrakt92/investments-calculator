import { useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import Upload from './pages/Upload'
import Portfolio from './pages/Portfolio'
import TaxCalculator from './pages/TaxCalculator'

function App() {
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    const saved = localStorage.getItem('theme')
    return (saved as 'light' | 'dark') || 'light'
  })

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('theme', theme)
  }, [theme])

  const toggleTheme = () => {
    setTheme(prev => prev === 'light' ? 'dark' : 'light')
  }

  return (
    <BrowserRouter>
      <nav className="nav">
        <div className="nav-inner">
          <div className="nav-brand">Irish Tax Calculator</div>
          <div className="nav-links">
            <NavLink to="/" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
              Dashboard
            </NavLink>
            <NavLink to="/upload" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
              Upload
            </NavLink>
            <NavLink to="/portfolio" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
              Portfolio
            </NavLink>
            <NavLink to="/tax" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
              Tax Calculator
            </NavLink>
          </div>
          <button
            className="theme-toggle"
            onClick={toggleTheme}
            title={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
          >
            {theme === 'light' ? '🌙' : '☀️'} {theme === 'light' ? 'Dark' : 'Light'}
          </button>
        </div>
      </nav>

      <div className="container">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/upload" element={<Upload />} />
          <Route path="/portfolio" element={<Portfolio />} />
          <Route path="/tax" element={<TaxCalculator />} />
        </Routes>
      </div>
    </BrowserRouter>
  )
}

export default App
