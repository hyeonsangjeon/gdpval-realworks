export const tooltipTexts = {
  kpi: {
    bestSuccessRate:
      'Highest task-completion rate among all experiments. A task is "successful" when the LLM\'s self-assessed QA check passes (pre-grading).',
    experiments:
      'Total number of experiment runs. Each experiment tests a different prompt strategy or token configuration against the same 220 tasks.',
    tasksEvaluated:
      'Number of real-world professional tasks per experiment. Covers 11 industry sectors and 44 occupations from the GDPVal Gold Subset.',
    bestQaScore:
      'Highest average QA score (0–10) across experiments. Self-assessed by the LLM based on completeness, accuracy, and format criteria.',
  },
  leaderboard: {
    experiment:
      'Unique experiment identifier (e.g., exp003). Click a row to see all 220 task results.',
    model:
      'The LLM model used. Currently all experiments run on the same model for controlled comparison.',
    strategy:
      'Prompt strategy used for each experiment. Each experiment tests a different approach to task execution — strategies vary in prompting technique, reasoning steps, and token budget. See each row for the specific strategy applied.',
    progress:
      'Fraction of tasks completed out of 220 total. Bar color matches the experiment\u2019s assigned color, not completion status.',
    successRate:
      'Percentage of tasks that passed self-assessed QA. Higher is better. Color: ≥96% green, ≥90% amber, <90% red.',
    deltaBest:
      "Difference from the best experiment's success rate. 0% means this is the top performer.",
    qaScore:
      'Average quality score (0–10) across completed tasks. Self-assessed by the LLM after each task.',
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
      'Tasks scored 100% by the external grading pipeline. The LLM output fully met all rubric criteria.',
    partial:
      'Tasks scored between 1–99%. The output met some but not all grading criteria.',
    zero:
      'Tasks scored 0%. The output failed to meet any grading criteria or was completely off-target.',
    graderDisagreement:
      'Cases where multiple graders scored the same task differently. High rates may indicate ambiguous rubric criteria.',
    ci:
      '95% confidence interval for the overall score, calculated via bootstrap sampling.',
  },
  badge: {
    selfAssessed:
      "Scores are currently based on the LLM's own QA assessment, not external grading. Amber badge = awaiting external evaluation pipeline.",
  },
} as const

export const sectionHintTexts = {
  leaderboard:
    'Each row is one experiment — same 220 real-world tasks, different prompt strategies. Click a row to drill into individual task results.',
  trend:
    'Track how success rates, QA scores, and error counts evolve across experiments. X-axis is ordered by experiment date.',
  errors:
    'Runtime failures during task execution. "Recovered" means the task succeeded after automatic retry. AI Failure Insights are LLM-generated analysis of error patterns.',
  grading:
    'External evaluation of LLM outputs by an independent grading pipeline. Scores: Perfect (100%), Partial (1-99%), Zero (0%). "Pre-grading" means awaiting external evaluation.',
} as const

export const aboutContent = {
  title: 'About GDPVal RealWorks Dashboard',
  sections: [
    {
      heading: 'What is this?',
      body: 'This dashboard visualizes results from GDPVal RealWorks — a benchmark that tests LLMs on 220 real-world professional tasks across 11 industry sectors and 44 occupations.',
    },
    {
      heading: 'How to read the data',
      body: 'Each "experiment" runs the same 220 tasks with a different configuration (prompt strategy, token budget, etc.). Compare experiments on the Leaderboard tab, track progress in Trends, and investigate failures in Error Analysis.',
    },
    {
      heading: 'Key Metrics',
      bullets: [
        'Success Rate — Did the LLM produce a valid deliverable?',
        'QA Score (0-10) — Self-assessed quality of the output',
        'Grading — External evaluation (when available)',
      ],
    },
  ],
  footer: 'Hover ⓘ icons on any label for detailed explanations.',
} as const
