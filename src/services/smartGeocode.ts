interface ComuneInfo {
  nome: string
  codiceIstat: string
}

export interface QueryDetection {
  type: 'postcode' | 'comune' | 'address' | 'combined' | 'unknown'
  postcode?: string
  comune?: ComuneInfo
  address?: string
}

const STREET_PREFIXES = [
  'VIA', 'VIALE', 'PIAZZA', 'PIAZZALE', 'PIAZZETTA', 'CORSO',
  'LARGO', 'VICOLO', 'STRADA', 'CONTRADA', 'TRAVERSA',
  'LUNGOMARE', 'BORGATA', 'LOCALITÀ', 'LOCALITA',
  'V.', 'V.LE', 'P.ZZA', 'P.LE', 'C.SO', 'L.GO',
]

const ABBREVIATIONS: [RegExp, string][] = [
  [/^V\.LE\b/i, 'VIALE'],
  [/^P\.ZZA\b/i, 'PIAZZA'],
  [/^P\.LE\b/i, 'PIAZZALE'],
  [/^C\.SO\b/i, 'CORSO'],
  [/^L\.GO\b/i, 'LARGO'],
  [/^V\.\s/i, 'VIA '],
]

/**
 * Normalize Italian address abbreviations to full form.
 */
export function normalizeAddress(address: string): string {
  let result = address.trim().toUpperCase()

  for (const [pattern, replacement] of ABBREVIATIONS) {
    if (pattern.test(result)) {
      result = result.replace(pattern, replacement)
      break
    }
  }

  // Collapse multiple spaces
  return result.replace(/\s+/g, ' ').trim()
}

function startsWithStreetPrefix(text: string): boolean {
  const upper = text.toUpperCase()
  return STREET_PREFIXES.some((prefix) => {
    if (prefix.endsWith('.')) {
      return upper.startsWith(prefix)
    }
    return upper.startsWith(prefix + ' ') || upper === prefix
  })
}

function findComune(text: string, comuni: ComuneInfo[]): ComuneInfo | undefined {
  const upper = text.toUpperCase().trim()
  if (upper.length < 2) return undefined

  // Exact match first (case insensitive)
  const exact = comuni.find((c) => c.nome.toUpperCase() === upper)
  if (exact) return exact

  // Partial match (starts with, case insensitive)
  const partial = comuni.find((c) => c.nome.toUpperCase().startsWith(upper))
  return partial
}

function findComuneByComma(
  text: string,
  comuni: ComuneInfo[],
): { comune: ComuneInfo; rest: string } | undefined {
  const commaIndex = text.indexOf(',')
  if (commaIndex < 0) return undefined

  const comunePart = text.slice(0, commaIndex).trim()
  const rest = text.slice(commaIndex + 1).trim()

  if (comunePart.length < 2 || rest.length === 0) return undefined

  const comune = findComune(comunePart, comuni)
  if (comune && startsWithStreetPrefix(rest)) {
    return { comune, rest }
  }

  return undefined
}

function findComunePrefix(
  text: string,
  comuni: ComuneInfo[],
): { comune: ComuneInfo; rest: string } | undefined {
  const upper = text.toUpperCase().trim()
  const words = upper.split(/\s+/)

  // Try matching progressively longer prefixes (longest first for multi-word comuni)
  for (let len = words.length - 1; len >= 1; len--) {
    const prefix = words.slice(0, len).join(' ')
    const comune = comuni.find((c) => c.nome.toUpperCase() === prefix)
    if (comune) {
      const rest = words.slice(len).join(' ')
      // Check that the remainder looks like an address
      if (rest.length > 0) {
        return { comune, rest: text.trim().slice(prefix.length).trim() }
      }
    }
  }

  return undefined
}

/**
 * Detect the type of a search query.
 *
 * - Postcode: 5-digit number
 * - Address: starts with a street prefix (Via, Piazza, etc.)
 * - Comune: matches a known comune name
 * - Combined: comune name followed by an address
 * - Unknown: too short or unrecognized
 */
export function detectQueryType(query: string, comuni: ComuneInfo[]): QueryDetection {
  const trimmed = query.trim()
  if (trimmed.length < 2) return { type: 'unknown' }

  // Check for postcode (5-digit number)
  const postcodeMatch = trimmed.match(/^\d{5}$/)
  if (postcodeMatch) {
    return { type: 'postcode', postcode: postcodeMatch[0] }
  }

  // Check if query starts with a street prefix → address
  if (startsWithStreetPrefix(trimmed)) {
    return { type: 'address', address: trimmed }
  }

  // Check for comma-separated combined query (e.g. "Vacone, Via Roma 15")
  const commaResult = findComuneByComma(trimmed, comuni)
  if (commaResult) {
    return {
      type: 'combined',
      comune: commaResult.comune,
      address: commaResult.rest,
    }
  }

  // Check for space-separated combined query (e.g. "Vacone Via Roma 15")
  const combined = findComunePrefix(trimmed, comuni)
  if (combined && startsWithStreetPrefix(combined.rest)) {
    return {
      type: 'combined',
      comune: combined.comune,
      address: combined.rest,
    }
  }

  // Check if it matches a comune
  const comune = findComune(trimmed, comuni)
  if (comune) {
    return { type: 'comune', comune }
  }

  return { type: 'unknown' }
}
