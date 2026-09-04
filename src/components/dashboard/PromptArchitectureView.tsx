import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ChevronDown, ChevronRight, FileText, Code2, Shield, Settings, AlertTriangle } from 'lucide-react'
import type { PromptArchitecture } from '../../hooks/useExperimentPrompt'
import type { PromptArchitectureReading } from './promptArchitectureReading'

/**
 * What the panel shows instead of nothing.
 *
 * The button offering "System · User Prompt · QA · Execution Config" opens
 * whether or not there is an architecture behind it, so the empty case has to
 * say which of the three empties it is rather than draw a blank the reader can
 * only read as "this run had no prompt settings".
 */
export function PromptArchitectureNotice({ reading }: { reading: PromptArchitectureReading }) {
  return (
    <div className="flex items-start gap-2.5 px-1 py-2">
      <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0 text-dash-text-muted" />
      <div className="space-y-1">
        <p className="text-xs font-semibold text-dash-heading">{reading.title}</p>
        <p className="text-[11px] text-dash-text-secondary leading-relaxed max-w-[620px]">{reading.detail}</p>
      </div>
    </div>
  )
}

/** Highlight template variables like {occupation} and {task_prompt} */
function Hl({ text }: { text: string }) {
  return (
    <span>
      {text.split(/(\{[a-z_]+\})/gi).map((p, i) =>
        /^\{[a-z_]+\}$/i.test(p) ? (
          <span key={i} className="text-amber-400 font-semibold bg-amber-400/10 px-0.5 rounded">{p}</span>
        ) : (
          <span key={i}>{p}</span>
        )
      )}
    </span>
  )
}

/** Collapsible prompt block */
function Block({ icon, title, source, content, badge, muted, defaultOpen }: {
  icon: React.ReactNode; title: string; source?: string; content: string | null
  badge?: React.ReactNode; muted?: boolean; defaultOpen?: boolean
}) {
  const [open, setOpen] = useState(defaultOpen ?? true)
  const empty = !content?.trim()
  return (
    <div className={`border border-dash-border rounded-lg overflow-hidden ${muted ? 'opacity-50' : ''}`}>
      <button
        onClick={() => !empty && setOpen(!open)}
        disabled={empty}
        className="w-full flex items-center gap-2 px-3 py-2.5 text-left hover:bg-dash-card-hover transition"
      >
        <span className="text-dash-text-muted">{icon}</span>
        <span className="text-xs font-semibold text-dash-heading flex-1">{title}</span>
        {badge}
        {source && <span className="text-[10px] text-dash-text-faint font-mono hidden md:inline">{source}</span>}
        {empty ? (
          <span className="text-[10px] text-dash-text-faint italic">(none)</span>
        ) : open ? (
          <ChevronDown className="w-3.5 h-3.5 text-dash-text-muted" />
        ) : (
          <ChevronRight className="w-3.5 h-3.5 text-dash-text-muted" />
        )}
      </button>
      <AnimatePresence>
        {open && content && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="px-3 pb-3 border-t border-dash-border">
              <pre className="text-[11px] text-dash-text-secondary font-mono whitespace-pre-wrap break-words leading-relaxed mt-2 max-h-[400px] overflow-y-auto">
                <Hl text={content} />
              </pre>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

export default function PromptArchitectureView({ prompt, shortId: _shortId }: { prompt: PromptArchitecture; shortId: string }) {
  const { system, user_prompt, qa_prompt, execution_config: ec } = prompt

  return (
    <div className="space-y-3">
      {/* System Message */}
      <Block icon={<FileText className="w-3.5 h-3.5" />} title="System Message" source={system.source} content={system.content} defaultOpen={true} />

      {/* User Prompt Assembly */}
      <div className="border border-dash-border rounded-lg overflow-hidden">
        <div className="px-3 py-2.5 flex items-center gap-2">
          <Code2 className="w-3.5 h-3.5 text-dash-text-muted" />
          <span className="text-xs font-semibold text-dash-heading">User Prompt Assembly</span>
          <span className="text-[10px] text-dash-text-faint ml-auto">prefix → body → codegen → suffix</span>
        </div>
        <div className="px-3 pb-3 space-y-2">
          {/* ① prefix / ② body */}
          {(['prefix', 'body'] as const).map((key, i) => (
            <div key={key} className="flex items-center gap-2 text-xs">
              <span className="text-dash-text-faint font-mono w-5 text-right">{i === 0 ? '①' : '②'}</span>
              <span className="text-dash-text-secondary">{key}</span>
              {user_prompt[key] ? (
                <span className="text-dash-text font-mono text-[11px] truncate flex-1">{user_prompt[key]!.slice(0, 80)}…</span>
              ) : (
                <span className="text-dash-text-faint italic">(none)</span>
              )}
            </div>
          ))}
          {/* ③ codegen core */}
          <Block
            icon={<span className="text-dash-text-faint font-mono text-[10px]">③</span>}
            title="codegen core"
            source={user_prompt.codegen_core.source}
            content={user_prompt.codegen_core.content}
            defaultOpen={true}
          />
          {/* ④ suffix */}
          <Block
            icon={<span className="text-dash-text-faint font-mono text-[10px]">④</span>}
            title="suffix"
            source={user_prompt.suffix?.source}
            content={user_prompt.suffix?.content ?? null}
            defaultOpen={true}
            badge={
              user_prompt.suffix ? (
                <span className="text-[10px] bg-emerald-500/10 text-emerald-400 px-1.5 py-0.5 rounded font-mono">
                  {user_prompt.suffix.content.split('\n').length} lines
                </span>
              ) : undefined
            }
          />
        </div>
      </div>

      {/* Self-QA */}
      <Block
        icon={<Shield className="w-3.5 h-3.5" />}
        title={`Self-QA${qa_prompt.enabled ? '' : ' (disabled)'}`}
        content={qa_prompt.content}
        muted={!qa_prompt.enabled}
        defaultOpen={true}
        badge={
          qa_prompt.enabled ? (
            <span className="text-[10px] bg-blue-500/10 text-blue-400 px-1.5 py-0.5 rounded font-mono">
              min:{qa_prompt.min_score ?? '—'} retries:{qa_prompt.max_retries ?? '—'}
            </span>
          ) : undefined
        }
      />

      {/* Execution Config */}
      <div className="border border-dash-border rounded-lg px-3 py-2.5">
        <div className="flex items-center gap-2 mb-2">
          <Settings className="w-3.5 h-3.5 text-dash-text-muted" />
          <span className="text-xs font-semibold text-dash-heading">Execution Config</span>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-x-4 gap-y-1.5 text-xs">
          {[
            { l: 'mode', v: ec.mode },
            { l: 'tokens', v: ec.tokens ? `${ec.tokens.code_generation?.toLocaleString()}` : '—' },
            { l: 'timeout', v: ec.timeout ? `${ec.timeout}s` : '—' },
            { l: 'resume_rounds', v: ec.resume_max_rounds ?? '—' },
            { l: 'max_retries', v: ec.max_retries ?? '—' },
            { l: 'libreoffice', v: ec.install_libreoffice ? '✅' : '—' },
            ...(ec.metrics ? [{ l: 'job_metrics', v: ec.metrics.enabled ? 'enabled' : 'disabled' }] : []),
          ].map(({ l, v }) => (
            <div key={l} className="flex justify-between">
              <span className="text-dash-text-muted">{l}</span>
              <span className="font-mono text-dash-text">{v}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Warning note */}
      <div className="flex items-start gap-2 text-[10px] text-dash-text-faint px-1">
        <AlertTriangle className="w-3 h-3 mt-0.5 shrink-0" />
        <span>
          Codegen template shows <strong>current version</strong>. CONFIDENCE added 2026-03-03 (exp007+).
          Dynamic injections (task_prompt, file previews) are per-task.
        </span>
      </div>
    </div>
  )
}
