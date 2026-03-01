import { useState, useRef, useEffect, useId, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Info } from 'lucide-react'
import { useIsMobile } from '../../hooks/useIsMobile'

interface InfoTooltipProps {
  content: string
  position?: 'top' | 'bottom' | 'left' | 'right'
  className?: string
}

const GAP = 8 // px between icon and tooltip
const VIEWPORT_PAD = 16 // px padding from viewport edges

export default function InfoTooltip({ content, position = 'top', className = '' }: InfoTooltipProps) {
  const [visible, setVisible] = useState(false)
  const [coords, setCoords] = useState<{ top: number; left: number } | null>(null)
  const triggerRef = useRef<HTMLSpanElement>(null)
  const tooltipRef = useRef<HTMLDivElement>(null)
  const isMobile = useIsMobile()
  const tooltipId = useId()

  // Compute fixed position relative to viewport
  const computePosition = useCallback(() => {
    if (!triggerRef.current || !tooltipRef.current) return
    const iconRect = triggerRef.current.getBoundingClientRect()
    const tipRect = tooltipRef.current.getBoundingClientRect()
    const vw = window.innerWidth
    const vh = window.innerHeight

    const iconCenterX = iconRect.left + iconRect.width / 2
    const iconCenterY = iconRect.top + iconRect.height / 2

    let top: number
    let left: number

    // Decide vertical direction: prefer requested, fallback if no space
    let dir = position
    if (dir === 'top' && iconRect.top - tipRect.height - GAP < 0) dir = 'bottom'
    if (dir === 'bottom' && iconRect.bottom + tipRect.height + GAP > vh) dir = 'top'
    if (dir === 'left' && iconRect.left - tipRect.width - GAP < 0) dir = 'right'
    if (dir === 'right' && iconRect.right + tipRect.width + GAP > vw) dir = 'left'

    switch (dir) {
      case 'top':
        top = iconRect.top - tipRect.height - GAP
        left = iconCenterX - tipRect.width / 2
        break
      case 'bottom':
        top = iconRect.bottom + GAP
        left = iconCenterX - tipRect.width / 2
        break
      case 'left':
        top = iconCenterY - tipRect.height / 2
        left = iconRect.left - tipRect.width - GAP
        break
      case 'right':
        top = iconCenterY - tipRect.height / 2
        left = iconRect.right + GAP
        break
    }

    // Clamp horizontal to viewport bounds
    left = Math.max(VIEWPORT_PAD, Math.min(left, vw - tipRect.width - VIEWPORT_PAD))
    // Clamp vertical to viewport bounds
    top = Math.max(VIEWPORT_PAD, Math.min(top, vh - tipRect.height - VIEWPORT_PAD))

    setCoords({ top, left })
  }, [position])

  // Recompute on visible / scroll / resize
  useEffect(() => {
    if (!visible) {
      setCoords(null)
      return
    }
    // Use rAF so the tooltip is rendered (invisible) first, then we measure
    const frame = requestAnimationFrame(() => computePosition())
    window.addEventListener('scroll', computePosition, true)
    window.addEventListener('resize', computePosition)
    return () => {
      cancelAnimationFrame(frame)
      window.removeEventListener('scroll', computePosition, true)
      window.removeEventListener('resize', computePosition)
    }
  }, [visible, computePosition])

  // Close on outside tap (mobile) or click (desktop fallback)
  useEffect(() => {
    if (!visible) return
    const handler = (e: Event) => {
      if (
        triggerRef.current &&
        !triggerRef.current.contains(e.target as Node) &&
        tooltipRef.current &&
        !tooltipRef.current.contains(e.target as Node)
      ) {
        setVisible(false)
      }
    }
    if (isMobile) {
      document.addEventListener('touchstart', handler)
      return () => document.removeEventListener('touchstart', handler)
    }
    return undefined
  }, [isMobile, visible])

  return (
    <span
      ref={triggerRef}
      className={`relative inline-flex items-center ${className}`}
      onMouseEnter={() => !isMobile && setVisible(true)}
      onMouseLeave={() => !isMobile && setVisible(false)}
      onClick={(e) => {
        if (isMobile) {
          e.stopPropagation()
          setVisible((v) => !v)
        }
      }}
      aria-describedby={visible ? tooltipId : undefined}
    >
      <Info className="w-3.5 h-3.5 text-dash-text-muted hover:text-dash-text-secondary transition-colors cursor-help flex-shrink-0" />
      <AnimatePresence>
        {visible && (
          <motion.div
            ref={tooltipRef}
            id={tooltipId}
            role="tooltip"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: coords ? 1 : 0, scale: coords ? 1 : 0.95 }}
            exit={{ opacity: 0, scale: 0.95 }}
            transition={{ duration: 0.15 }}
            className="fixed z-50"
            style={{
              top: coords?.top ?? -9999,
              left: coords?.left ?? -9999,
              // Bug 1 fix: reset inherited text-transform & letter-spacing
              textTransform: 'none',
              letterSpacing: 'normal',
            }}
          >
            <div
              className="bg-dash-card border border-dash-border rounded-lg shadow-lg px-3 py-2 text-xs text-dash-text leading-relaxed whitespace-normal"
              style={{
                minWidth: 200,
                maxWidth: isMobile ? 'calc(100vw - 32px)' : 280,
                overflowWrap: 'break-word',
              }}
            >
              {content}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </span>
  )
}
