/**
 * gradeProvenance — route-provenance labelling for published grades.
 *
 * A grade carries `source_azure_ai_provenance_status`, which records how the
 * inference run it scored proved which Azure AI routes produced the
 * deliverables. Only `legacy-missing` is a gap: that run predates
 * `inference_provenance.json`, and the sidecar cannot be written after the fact
 * without inventing the prepared fingerprint and the route list.
 *
 * Step 8 still publishes such a run when its config pins the complete corpus,
 * because the judge reads deliverables, rubric, and prompts — never the
 * inference routes. The missing sidecar is a hole in the audit trail, not in
 * what was graded. That is exactly why the dashboard has to say so out loud:
 * a `final` grade with an unverifiable source would otherwise look identical to
 * one whose routes were checked.
 *
 * Every other value renders nothing — `runtime-verified` and
 * `verified-sidecar` are proven, `local-runtime` never involved a remote route,
 * and `null` is what grades produced before the field existed carry.
 */

/** The one status that means the source run's routes cannot be verified. */
export const LEGACY_MISSING_PROVENANCE = 'legacy-missing'

/** Compact badge text, sized for a grade card's badge row. */
export const UNVERIFIED_PROVENANCE_LABEL = 'UNVERIFIED PROVENANCE'

/** Shared copy for the badge tooltip and the detail-page banner. */
export const UNVERIFIED_PROVENANCE_DESCRIPTION =
  'Scores are complete, but the inference run predates the route provenance ' +
  'sidecar — which Azure AI deployments produced these deliverables cannot be ' +
  'verified from the record.'

/** True when the graded source has no verifiable Azure AI route provenance. */
export function hasUnverifiedRouteProvenance(status) {
  return status === LEGACY_MISSING_PROVENANCE
}
