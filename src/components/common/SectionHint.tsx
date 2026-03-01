import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Lightbulb } from 'lucide-react'
import { onboarding } from '../../utils/onboarding'

interface SectionHintProps {
  tabId: string
  children: React.ReactNode
}

export default function SectionHint({ tabId, children }: SectionHintProps) {
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    // Show only if not already dismissed (delay to avoid SSR flash)
    setVisible(!onboarding.isHintDismissed(tabId))
  }, [tabId])

  const handleDismiss = () => {
    onboarding.dismissHint(tabId)
    setVisible(false)
  }

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          exit={{ opacity: 0, height: 0 }}
          transition={{ duration: 0.25 }}
          className="overflow-hidden"
        >
          <div className="rounded-lg bg-amber-500/[0.06] border border-amber-500/20 border-l-2 border-l-amber-500/40 px-4 py-3 flex items-start gap-3">
            <Lightbulb className="w-3.5 h-3.5 text-amber-500/70 flex-shrink-0 mt-0.5" />
            <p className="text-xs text-dash-text-secondary leading-relaxed flex-1">
              {children}
            </p>
            <button
              onClick={handleDismiss}
              className="flex-shrink-0 text-dash-text-faint hover:text-amber-400 transition-colors p-0.5 rounded hover:bg-amber-500/10"
              aria-label="Dismiss hint"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
