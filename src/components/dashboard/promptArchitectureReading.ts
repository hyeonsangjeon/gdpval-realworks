/**
 * Why the Prompt Architecture panel has nothing in it, said out loud.
 *
 * Kept apart from the panel that renders it, and deliberately free of imports,
 * so `scripts/__tests__/a-prompt-architecture-that-never-loaded-is-not-an-empty-panel.test.mjs`
 * can execute the decision itself rather than pattern-match the JSX around it.
 *
 * `ExperimentDetail.tsx` gated the whole panel body on `showPromptArch &&
 * promptArch`. With no architecture to show, pressing "View Prompt
 * Architecture" turned the chevron down, changed the label to "Hide", and drew
 * nothing at all — the same blank an experiment with no system message, no user
 * prompt, no Self-QA and no execution config would draw. Three of the twenty-six
 * routable experiments were in that state (exp026c, exp030, exp031), and a
 * failed fetch of `prompt-architecture.json` puts all twenty-six there.
 *
 * `useExperimentPrompt` already separates the reasons — it tracks `loading` and
 * sets `error` from the failed request — so the four states below are read off
 * what the hook measured, not guessed.
 */

/**
 * `recorded`     — an entry for this experiment was published and can be drawn.
 * `loading`      — the index has not come back yet; nothing is known.
 * `unreadable`   — the request for the index failed; nothing is known.
 * `not_recorded` — the index loaded and carries no entry for this experiment.
 */
export type PromptArchitectureState = 'recorded' | 'loading' | 'unreadable' | 'not_recorded'

export interface PromptArchitectureReading {
  state: PromptArchitectureState
  /** Heading for the panel. Empty only when there is an architecture to draw. */
  title: string
  /** What is, and is not, being claimed. Empty only in the `recorded` state. */
  detail: string
}

/** Where an entry would have come from, named so a reader can go and look. */
export const PROMPT_ARCHITECTURE_SOURCE = 'scripts/aggregate-experiments.mjs'

/**
 * Decide what the panel says when it cannot show an architecture.
 *
 * An index that never arrived is not an experiment that ran without prompts.
 * Neither is an index that arrived without this experiment in it: that means
 * the settings were not read, which is a fact about the aggregator's file
 * discovery rather than about the run. Both are stated as such.
 */
export function readPromptArchitecture(input: {
  hasPrompt: boolean
  loading: boolean
  error: string | null | undefined
  shortId: string | null | undefined
}): PromptArchitectureReading {
  if (input.hasPrompt) return { state: 'recorded', title: '', detail: '' }

  const named = input.shortId?.trim() ? input.shortId.trim() : 'this experiment'

  if (input.error) {
    return {
      state: 'unreadable',
      title: 'Prompt architecture could not be read',
      detail:
        `generated/prompt-architecture.json did not load (${input.error}). ` +
        `This is not a record that ${named} ran without prompt settings — ` +
        'the settings were not read.',
    }
  }
  if (input.loading) {
    return {
      state: 'loading',
      title: 'Loading prompt architecture…',
      detail: 'The index has not come back yet, so nothing is known either way.',
    }
  }
  return {
    state: 'not_recorded',
    title: 'Prompt architecture not recorded',
    detail:
      `The index loaded and carries no entry for ${named}, so ${PROMPT_ARCHITECTURE_SOURCE} ` +
      'did not read this experiment’s settings. That is not the same as this run ' +
      'having had none.',
  }
}
