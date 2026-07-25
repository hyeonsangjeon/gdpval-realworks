export interface BuildProvenanceInput {
  version?: unknown
  sha?: unknown
  repository?: unknown
}

export type BuildProvenance =
  | {
      kind: 'published'
      version: string
      shortSha: string
      fullSha: string
      repository: string
      commitUrl: string
      displayLabel: string
      accessibleLabel: string
    }
  | {
      kind: 'local'
      version: string | null
      shortSha: null
      fullSha: null
      repository: null
      commitUrl: null
      displayLabel: string
      accessibleLabel: string
    }

const VERSION_PATTERN = /^(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$/
const SHA_PATTERN = /^[0-9a-f]{40}$/
const OWNER_PATTERN = /^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$/
const REPOSITORY_NAME_PATTERN = /^[A-Za-z0-9._-]{1,100}$/

function validRepositorySlug(value: string): boolean {
  const segments = value.split('/')
  if (segments.length !== 2) return false
  const [owner, repository] = segments
  return OWNER_PATTERN.test(owner)
    && REPOSITORY_NAME_PATTERN.test(repository)
    && repository !== '.'
    && repository !== '..'
}

export function resolveBuildProvenance(input: BuildProvenanceInput): BuildProvenance {
  const version = typeof input.version === 'string' && VERSION_PATTERN.test(input.version)
    ? input.version
    : null
  const sha = typeof input.sha === 'string' && SHA_PATTERN.test(input.sha)
    ? input.sha
    : null
  const repository = typeof input.repository === 'string' && validRepositorySlug(input.repository)
    ? input.repository
    : null

  if (version && sha && repository) {
    const shortSha = sha.slice(0, 7)
    return {
      kind: 'published',
      version,
      shortSha,
      fullSha: sha,
      repository,
      commitUrl: `https://github.com/${repository}/commit/${sha}`,
      displayLabel: `Dashboard build v${version} · ${shortSha}`,
      accessibleLabel: `Dashboard build version ${version}, source commit ${sha}`,
    }
  }

  const versionLabel = version ? `v${version}` : 'version unavailable'
  return {
    kind: 'local',
    version,
    shortSha: null,
    fullSha: null,
    repository: null,
    commitUrl: null,
    displayLabel: `Dashboard build ${versionLabel} · local build`,
    accessibleLabel: `Dashboard build ${versionLabel}, local build without a source commit link`,
  }
}