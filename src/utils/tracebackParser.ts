/**
 * Parse Python traceback strings to extract the final exception type and message.
 *
 * Handles:
 *   - Standard tracebacks: "Traceback ...\nKeyError: 'Branch'\n"
 *   - Chained exceptions: "The above exception ...\nKeyError: ..."
 *   - Exit-code wrappers: "Code execution failed (exit code 1):\n..."
 */

export interface ParsedError {
  type: string      // e.g. "KeyError"
  message: string   // e.g. "'Branch'"
  raw: string       // original full error string
}

/**
 * Extract the last exception line from a Python traceback.
 * Returns { type, message } or a fallback for unparseable strings.
 */
export function parseTraceback(error: string): ParsedError {
  if (!error) return { type: 'Unknown', message: '', raw: error }

  const lines = error.trim().split('\n')

  // Walk backwards to find the last line matching "ExceptionType: message"
  for (let i = lines.length - 1; i >= 0; i--) {
    const line = lines[i].trim()
    // Match "SomeError: message" or "SomeError" (no message)
    const match = line.match(/^([A-Z]\w*(?:Error|Exception|Warning))\s*:\s*(.*)$/i)
      || line.match(/^(SyntaxError)\s*:\s*(.*)$/i)
      || line.match(/^(AssertionError|AssertionError)\s*(.*)$/i)
    if (match) {
      return {
        type: match[1],
        message: match[2]?.trim() || '',
        raw: error,
      }
    }
  }

  // Fallback: check for common patterns
  if (error.includes('exit code')) {
    return { type: 'ExecutionError', message: 'Non-zero exit code', raw: error }
  }
  if (error.includes('timeout') || error.includes('Timeout')) {
    return { type: 'TimeoutError', message: 'Execution timed out', raw: error }
  }

  return { type: 'Unknown', message: lines[lines.length - 1]?.trim() || '', raw: error }
}

/**
 * Aggregate an array of error strings into a frequency map of exception types.
 * Returns sorted by count (descending).
 */
export function aggregateExceptionTypes(errors: string[]): { type: string; count: number }[] {
  const counts = new Map<string, number>()
  for (const err of errors) {
    const { type } = parseTraceback(err)
    counts.set(type, (counts.get(type) || 0) + 1)
  }
  return Array.from(counts.entries())
    .map(([type, count]) => ({ type, count }))
    .sort((a, b) => b.count - a.count)
}
