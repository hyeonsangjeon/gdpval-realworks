import { basename } from 'node:path'

const nonEmptyString = (value) => (
  typeof value === 'string' && value.trim() ? value.trim() : null
)

export function experimentIdFromFilename(filePath) {
  const filename = basename(filePath, '.json')
  const separator = filename.indexOf('__')
  return separator > 0 ? filename.slice(0, separator) : filename
}

export function gradeIdentityFromRaw(filePath, raw) {
  const meta = raw && typeof raw === 'object' && raw._meta && typeof raw._meta === 'object'
    ? raw._meta
    : {}
  return {
    is_dummy: raw?.schema_version === '1.0' || raw?.schema_version === '1.1'
      ? false
      : meta.is_dummy === true,
    experiment_id: nonEmptyString(raw?.experiment_id)
      ?? nonEmptyString(meta.experiment_id)
      ?? experimentIdFromFilename(filePath),
    source_inference_experiment_id: nonEmptyString(raw?.source_inference_experiment_id)
      ?? nonEmptyString(meta.source_inference_experiment_id),
  }
}
