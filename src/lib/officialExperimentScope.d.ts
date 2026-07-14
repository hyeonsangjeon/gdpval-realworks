export const OFFICIAL_TASK_COUNT: 220
export const HIDDEN_DIAGNOSTIC_EXPERIMENT_IDS: ReadonlySet<string>
export function isHiddenDiagnosticExperimentId(value: string | null | undefined): boolean
export function isSmokeExperimentId(value: string | null | undefined): boolean

interface DashboardExperimentScope {
	short_id: string
	experiment_name: string
	total_tasks: number
	report_scope: string
}

interface DashboardReportScope {
	short_id: string
}

export function isHiddenOfficialExperiment(
	experiment: Pick<DashboardExperimentScope, 'short_id' | 'experiment_name' | 'total_tasks'>,
): boolean
export function filterDashboardExperiments<T extends DashboardExperimentScope>(
	experiments: T[],
	options?: { debug?: boolean; demoMode?: boolean },
): T[]
export function filterDashboardReports<T extends DashboardReportScope>(
	reports: T[],
	visibleExperimentIds: string[],
): T[]
export function getDashboardDisplayData<
	E extends DashboardExperimentScope,
	R extends DashboardReportScope,
>(
	experiments: E[],
	reports: R[],
	options?: { debug?: boolean; demoMode?: boolean },
): { experiments: E[]; reports: R[] }
