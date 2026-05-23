export const TASK_TOTAL_PLACEHOLDER = '{TASK_TOTAL}'

export const tooltipTexts = {
  kpi: {
    bestSuccessRate:
      "Highest task-completion rate based on the LLM's self-QA check during inference. This is the model judging its own deliverable — NOT the same as the LLM-judge grade (rubric-based, run via grade-run.yml). Both signals are independent.",
    experiments:
      `Total number of experiment runs. Each experiment tests a different prompt strategy or token configuration against the same ${TASK_TOTAL_PLACEHOLDER} tasks.`,
    tasksEvaluated:
      'Number of real-world professional tasks per experiment. Covers 9 industry sectors and 44 occupations from the GDPVal Gold Subset.',
    bestQaScore:
      'Highest average Self-QA score (0–10): the LLM rates its own output right after generation. Useful for runtime quality signal but does NOT imply rubric correctness — for that see the LLM-judge grade (Grading Analysis tab).',
  },
  leaderboard: {
    experiment:
      `Unique experiment identifier (e.g., exp003). Click a row to see all ${TASK_TOTAL_PLACEHOLDER} task results.`,
    model:
      'The LLM model used. Currently all experiments run on the same model for controlled comparison.',
    strategy:
      'Prompt strategy used for each experiment. Each experiment tests a different approach to task execution — strategies vary in prompting technique, reasoning steps, and token budget. See each row for the specific strategy applied.',
    progress:
      `Fraction of tasks completed out of ${TASK_TOTAL_PLACEHOLDER} total. Bar color matches the experiment\u2019s assigned color, not completion status.`,
    successRate:
      "Percentage of tasks that passed the LLM's self-QA check. Self-assessed (model judging itself) — separate from the LLM-judge grade. Colors: ≥96% green, ≥90% amber, <90% red.",
    deltaBest:
      "Difference from the best experiment's success rate. 0% means this is the top performer.",
    qaScore:
      'Average self-QA score (0–10), model rates its own output. Independent from the LLM-judge grade (see Grading Analysis tab).',
    tasks: 'Completed tasks / total tasks.',
  },
  errors: {
    errors:
      'Tasks that encountered runtime exceptions (timeouts, code errors, etc.) during execution.',
    retried:
      'Tasks that were re-attempted after an initial failure. Includes both recovered and still-failed tasks.',
    recovered:
      'Percentage of retried tasks that succeeded on retry. 100% = all retries eventually succeeded.',
  },
  grading: {
    perfect:
      'Tasks scored 100% by the LLM-judge (rubric-based, automated). The LLM output fully met all rubric criteria.',
    partial:
      'Tasks scored between 1–99% by the LLM-judge. The output met some but not all rubric criteria.',
    zero:
      'Tasks scored 0% by the LLM-judge. The output failed to meet any rubric criteria or was completely off-target.',
    graderDisagreement:
      'Cases where multiple judges scored the same task differently. Visible only in multi-judge mode (Phase B). High rates may indicate ambiguous rubric criteria.',
    ci:
      '95% confidence interval for the overall score, calculated via bootstrap sampling.',
    judgeVsInference:
      'LLM-judge model evaluates outputs against the rubric. Distinct from the inference model that produced them.',
  },
  health: {
    row:
      'Run-quality diagnostics: judge call success rate, pass rates by decision type, and cost/latency totals. Distinct from the score itself.',
    judgeErrorRate:
      'Percentage of judge calls that failed (timeout, parse error, or hit token limit). Alert threshold > 5% — unreliable run.',
    judgePassRate:
      'Pass rate among LLM-judge-decided rubric items (content-quality criteria). Distinct from precheck (deterministic structural checks).',
    precheckPassRate:
      'Pass rate among deterministically checked items (filename, sheet name, format).',
    judgeCalls:
      'Total number of LLM-judge API calls used during grading. Per-experiment cost proxy.',
    judgeLatency:
      'Total wall-clock seconds spent inside the judge LLM during this grading run.',
  },
  badge: {
    selfAssessed:
      "This experiment has no LLM-judge grade yet. Numbers shown come from the model's own self-QA check during inference (independent signal). Run grade-run.yml to generate rubric-based grades.",
  },
  wow: {
    rubricCoverage:
      "Average pass rate across rubric items per task. OpenAI exposed only task-level 0/1; we expose item-level partial credit derived from the full rubric.",
    criticalItems:
      "Pass rate on rubric items with weight ≥ 3 — the highest-stakes 'must-have' requirements. Distinguishes decisive criteria from small formatting items.",
    structureVsReasoning:
      "Splits deterministic verification (file format, sheet names, etc.) from LLM judgement (content correctness). Large gap = strong structure but weak reasoning, or vice versa.",
    sectorHeatmap:
      "Visualizes per-sector pass rates so weak sector + weak category combinations stand out. Color: 0% red → 100% green.",
    scoreDensity:
      "OpenAI's hosted grader produced only 4 task-level scores (0/33/67/100). Our item-level partials roll up to 10 buckets across the full 0–100% range.",
    rubricSeverity:
      "Groups rubric items by weight and plots pass rate per weight. A sharp drop signals the difficulty threshold where the model breaks down.",
  },
} as const

export const sectionHintTexts = {
  leaderboard:
    `Each row is one experiment — same ${TASK_TOTAL_PLACEHOLDER} real-world tasks, different prompt strategies. Numbers here reflect inference-time self-QA. For rubric-based grades, switch to the Grading Analysis tab.`,
  trend:
    'Track how success rates, QA scores, and error counts evolve across experiments. X-axis is ordered by experiment date.',
  errors:
    'Runtime failures during task execution. "Recovered" means the task succeeded after automatic retry. AI Failure Insights are LLM-generated analysis of error patterns.',
  grading:
    'LLM-judge (rubric-based, automated). Scores: Perfect (100%), Partial (1-99%), Zero (0%). Grading runs separately from inference via grade-run.yml.',
} as const

export const aboutContent = {
  title: 'About GDPVal RealWorks Dashboard',
  sections: [
    {
      heading: 'What is this?',
      body: `This dashboard visualizes results from GDPVal RealWorks — a benchmark that tests LLMs on ${TASK_TOTAL_PLACEHOLDER} real-world professional tasks across 9 industry sectors and 44 occupations.`,
    },
    {
      heading: 'How to read the data',
      body: `Each "experiment" runs the same ${TASK_TOTAL_PLACEHOLDER} tasks with a different configuration (prompt strategy, token budget, etc.). Compare experiments on the Leaderboard tab, track progress in Trends, and investigate failures in Error Analysis.`,
    },
    {
      heading: 'Key Metrics',
      bullets: [
        'Success Rate — Did inference complete with a deliverable that passed self-QA?',
        "Self-QA Score (0-10) — Model's own rating of its output (runtime signal)",
        'LLM-Judge Grade — Independent rubric-based scoring run via grade-run.yml (Grading Analysis tab)',
        'Note: Self-QA and LLM-judge grade are independent signals — high self-QA does not guarantee high rubric grade.',
      ],
    },
  ],
  footer: 'Hover ⓘ icons on any label for detailed explanations.',
} as const
