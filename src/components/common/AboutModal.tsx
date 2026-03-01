import { useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Info } from 'lucide-react'
import { useIsMobile } from '../../hooks/useIsMobile'
import { onboarding } from '../../utils/onboarding'
import { aboutContent } from '../../data/tooltipTexts'

interface AboutModalProps {
  open: boolean
  onClose: () => void
}

export default function AboutModal({ open, onClose }: AboutModalProps) {
  const isMobile = useIsMobile()
  const modalRef = useRef<HTMLDivElement>(null)

  // Mark as seen + close
  const handleClose = () => {
    onboarding.markAboutSeen()
    onClose()
  }

  // ESC key to close
  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') handleClose()
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [open])

  // Focus trap: focus modal on open
  useEffect(() => {
    if (open && modalRef.current) {
      modalRef.current.focus()
    }
  }, [open])

  // Prevent body scroll when modal is open
  useEffect(() => {
    if (open) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => {
      document.body.style.overflow = ''
    }
  }, [open])

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          className="fixed inset-0 z-[100] flex items-center justify-center"
          onClick={handleClose}
        >
          {/* Overlay */}
          <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />

          {/* Modal */}
          <motion.div
            ref={modalRef}
            tabIndex={-1}
            initial={{ opacity: 0, scale: 0.95, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 10 }}
            transition={{ duration: 0.2 }}
            onClick={(e) => e.stopPropagation()}
            className={`relative z-10 bg-dash-card border border-dash-border shadow-2xl outline-none ${
              isMobile
                ? 'fixed inset-0 rounded-none overflow-y-auto'
                : 'rounded-2xl max-w-lg w-full mx-4 max-h-[85vh] overflow-y-auto'
            }`}
          >
            {/* Header */}
            <div className="sticky top-0 bg-dash-card border-b border-dash-border px-5 py-4 flex items-center justify-between z-10">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-blue-500/10 flex items-center justify-center">
                  <Info className="w-4 h-4 text-blue-400" />
                </div>
                <h2 className="text-base font-semibold text-dash-heading">
                  {aboutContent.title}
                </h2>
              </div>
              <button
                onClick={handleClose}
                className="w-8 h-8 rounded-lg flex items-center justify-center text-dash-text-muted hover:text-dash-heading hover:bg-dash-card-hover transition-all"
                aria-label="Close"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Body */}
            <div className="px-5 py-5 space-y-5">
              {aboutContent.sections.map((section, idx) => (
                <div key={idx}>
                  <h3 className="text-sm font-semibold text-dash-text mb-2">{section.heading}</h3>
                  {'body' in section && (
                    <p className="text-xs text-dash-text-secondary leading-relaxed">
                      {section.body}
                    </p>
                  )}
                  {'bullets' in section && section.bullets && (
                    <ul className="space-y-1.5 mt-1">
                      {section.bullets.map((bullet, bIdx) => (
                        <li key={bIdx} className="flex items-start gap-2 text-xs text-dash-text-secondary leading-relaxed">
                          <span className="text-dash-text-muted mt-0.5">•</span>
                          <span>{bullet}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              ))}

              {/* Footer hint */}
              <div className="rounded-lg bg-blue-500/5 border border-blue-500/10 px-4 py-3">
                <p className="text-xs text-dash-text-muted leading-relaxed">
                  ℹ️ {aboutContent.footer}
                </p>
              </div>
            </div>

            {/* Action */}
            <div className="sticky bottom-0 bg-dash-card border-t border-dash-border px-5 py-4">
              <button
                onClick={handleClose}
                className="w-full py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium transition-colors"
              >
                Got it
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
