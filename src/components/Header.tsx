import { motion } from 'framer-motion'
import { FlaskConical, Moon, Sun } from 'lucide-react'
import { Button } from './ui/button'
import { useState, useEffect } from 'react'

function Header() {
  const [isDark, setIsDark] = useState(true)

  useEffect(() => {
    // Check localStorage or system preference
    const savedTheme = localStorage.getItem('theme')
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
    const shouldBeDark = savedTheme ? savedTheme === 'dark' : prefersDark

    setIsDark(shouldBeDark)
    if (shouldBeDark) {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
  }, [])

  const toggleTheme = () => {
    const newIsDark = !isDark
    setIsDark(newIsDark)

    if (newIsDark) {
      document.documentElement.classList.add('dark')
      localStorage.setItem('theme', 'dark')
    } else {
      document.documentElement.classList.remove('dark')
      localStorage.setItem('theme', 'light')
    }
  }

  return (
    <motion.header
      initial={{ opacity: 0, y: -20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60"
    >
      <div className="container mx-auto px-4 py-4">
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <FlaskConical className="h-6 w-6 md:h-8 md:w-8 text-primary flex-shrink-0" />
            <div>
              <h1 className="text-xl md:text-2xl font-bold text-foreground">GDPVal RealWork</h1>
              <p className="text-xs md:text-sm text-muted-foreground hidden sm:block">
                Benchmark LLMs on real expert work, not academic tests
              </p>
            </div>
          </div>

          <Button
            variant="outline"
            size="icon"
            onClick={toggleTheme}
            className="transition-all hover:scale-110"
          >
            {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
          </Button>
        </div>
      </div>
    </motion.header>
  )
}

export default Header
