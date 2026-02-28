import { BrowserRouter as Router, Routes, Route, useLocation } from 'react-router-dom'
import { AnimatePresence } from 'framer-motion'
import { ThemeProvider } from './contexts/ThemeContext'
import Dashboard from './pages/Dashboard'
import ExperimentDetail from './pages/ExperimentDetail'
import GradeDetail from './pages/GradeDetail'

function AnimatedRoutes() {
  const location = useLocation()

  return (
    <AnimatePresence mode="wait">
      <Routes location={location} key={location.pathname}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/experiments" element={<Dashboard />} />
        <Route path="/experiments/:id" element={<ExperimentDetail />} />
        <Route path="/grades/:gradeId" element={<GradeDetail />} />
      </Routes>
    </AnimatePresence>
  )
}

function App() {
  return (
    <ThemeProvider>
      <Router basename="/gdpval-realworks">
        <AnimatedRoutes />
      </Router>
    </ThemeProvider>
  )
}

export default App
