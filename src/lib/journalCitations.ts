import type { JournalArticle, JournalSection } from '../data/journal'

const CITATION_ID_PATTERN = /^[a-z0-9]+(?:-[a-z0-9]+)*$/

type CitationArticle = Pick<JournalArticle, 'slug' | 'thesisCitations' | 'evidence'>

export function validateJournalCitations(
  article: CitationArticle,
  sections: JournalSection[],
): string | null {
  const evidenceIds = new Set<string>()
  const renderedEvidenceIds = new Set<string>()

  for (const [sourceIndex, source] of article.evidence.entries()) {
    const renderedId = source.id ?? `source-${sourceIndex + 1}`
    if (!CITATION_ID_PATTERN.test(renderedId)) {
      return `${article.slug}: invalid evidence ID ${renderedId}`
    }
    if (renderedEvidenceIds.has(renderedId)) {
      return `${article.slug}: duplicate rendered evidence ID ${renderedId}`
    }
    renderedEvidenceIds.add(renderedId)
    if (source.id) evidenceIds.add(source.id)
  }

  const usedEvidenceIds = new Set<string>()
  const validateLocation = (ids: string[] | undefined, location: string) => {
    if (!ids) return null
    const localIds = new Set<string>()
    for (const evidenceId of ids) {
      if (localIds.has(evidenceId)) {
        return `${article.slug}: duplicate citation ${evidenceId} at ${location}`
      }
      if (!evidenceIds.has(evidenceId)) {
        return `${article.slug}: unknown citation ${evidenceId} at ${location}`
      }
      localIds.add(evidenceId)
      usedEvidenceIds.add(evidenceId)
    }
    return null
  }

  let error = validateLocation(article.thesisCitations, 'thesis')
  if (error) return error
  for (const [sectionIndex, section] of sections.entries()) {
    if (
      section.paragraphCitations
      && section.paragraphCitations.length !== section.paragraphs.length
    ) {
      return `${article.slug}: paragraph citation slots differ at section ${sectionIndex + 1}`
    }
    for (const [paragraphIndex, ids] of (section.paragraphCitations ?? []).entries()) {
      error = validateLocation(
        ids,
        `section ${sectionIndex + 1} paragraph ${paragraphIndex + 1}`,
      )
      if (error) return error
    }
    if (section.calloutCitations && !section.callout) {
      return `${article.slug}: callout citations lack a callout at section ${sectionIndex + 1}`
    }
    error = validateLocation(
      section.calloutCitations,
      `section ${sectionIndex + 1} callout`,
    )
    if (error) return error
  }

  for (const evidenceId of evidenceIds) {
    if (!usedEvidenceIds.has(evidenceId)) {
      return `${article.slug}: unused citation evidence ${evidenceId}`
    }
  }
  return null
}