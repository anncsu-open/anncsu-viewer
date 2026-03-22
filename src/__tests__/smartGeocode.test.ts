import { describe, it, expect } from 'vitest'
import { detectQueryType, normalizeAddress } from '@/services/smartGeocode'

const comuni = [
  { nome: 'VACONE', codiceIstat: '057072' },
  { nome: 'ROMA', codiceIstat: '058091' },
  { nome: 'MILANO', codiceIstat: '015146' },
  { nome: 'SAN GIOVANNI ROTONDO', codiceIstat: '071047' },
]

describe('detectQueryType', () => {
  it('detects a postcode (5-digit number)', () => {
    const result = detectQueryType('02040', comuni)
    expect(result.type).toBe('postcode')
    expect(result.postcode).toBe('02040')
  })

  it('detects a comune name', () => {
    const result = detectQueryType('Vacone', comuni)
    expect(result.type).toBe('comune')
    expect(result.comune?.nome).toBe('VACONE')
  })

  it('detects a comune with partial match', () => {
    const result = detectQueryType('Vacon', comuni)
    expect(result.type).toBe('comune')
    expect(result.comune?.nome).toBe('VACONE')
  })

  it('detects an address when query starts with a street prefix', () => {
    const result = detectQueryType('Via Roma 15', comuni)
    expect(result.type).toBe('address')
    expect(result.address).toBe('Via Roma 15')
  })

  it('detects a combined query (comune + address)', () => {
    const result = detectQueryType('Vacone Via Roma 15', comuni)
    expect(result.type).toBe('combined')
    expect(result.comune?.nome).toBe('VACONE')
    expect(result.address).toBe('Via Roma 15')
  })

  it('detects combined query with multi-word comune', () => {
    const result = detectQueryType('San Giovanni Rotondo Via Roma 1', comuni)
    expect(result.type).toBe('combined')
    expect(result.comune?.nome).toBe('SAN GIOVANNI ROTONDO')
    expect(result.address).toBe('Via Roma 1')
  })

  it('detects combined query with comma separator', () => {
    const result = detectQueryType('Vacone, Via Roma 15', comuni)
    expect(result.type).toBe('combined')
    expect(result.comune?.nome).toBe('VACONE')
    expect(result.address).toBe('Via Roma 15')
  })

  it('detects combined query with comma and extra spaces', () => {
    const result = detectQueryType('Vacone ,  Via Roma 1', comuni)
    expect(result.type).toBe('combined')
    expect(result.comune?.nome).toBe('VACONE')
    expect(result.address).toBe('Via Roma 1')
  })

  it('detects combined query with multi-word comune and comma', () => {
    const result = detectQueryType('San Giovanni Rotondo, Via Roma 1', comuni)
    expect(result.type).toBe('combined')
    expect(result.comune?.nome).toBe('SAN GIOVANNI ROTONDO')
    expect(result.address).toBe('Via Roma 1')
  })

  it('returns unknown for very short queries', () => {
    const result = detectQueryType('V', comuni)
    expect(result.type).toBe('unknown')
  })

  it('returns unknown for empty query', () => {
    const result = detectQueryType('', comuni)
    expect(result.type).toBe('unknown')
  })

  it('detects comune name case-insensitively', () => {
    const result = detectQueryType('VACONE', comuni)
    expect(result.type).toBe('comune')
    expect(result.comune?.codiceIstat).toBe('057072')
  })

  it('distinguishes between comune "ROMA" and "Via Roma"', () => {
    const addressResult = detectQueryType('Via Roma', comuni)
    expect(addressResult.type).toBe('address')

    const comuneResult = detectQueryType('Roma', comuni)
    expect(comuneResult.type).toBe('comune')
    expect(comuneResult.comune?.nome).toBe('ROMA')
  })
})

describe('normalizeAddress', () => {
  it('expands V. to VIA', () => {
    expect(normalizeAddress('V. Roma 15')).toBe('VIA ROMA 15')
  })

  it('expands P.zza to PIAZZA', () => {
    expect(normalizeAddress('P.zza Garibaldi 3')).toBe('PIAZZA GARIBALDI 3')
  })

  it('expands V.le to VIALE', () => {
    expect(normalizeAddress('V.le Europa 1')).toBe('VIALE EUROPA 1')
  })

  it('expands C.so to CORSO', () => {
    expect(normalizeAddress('C.so Italia 22')).toBe('CORSO ITALIA 22')
  })

  it('expands L.go to LARGO', () => {
    expect(normalizeAddress('L.go Augusto 5')).toBe('LARGO AUGUSTO 5')
  })

  it('passes through already full names', () => {
    expect(normalizeAddress('VIA ROMA 15')).toBe('VIA ROMA 15')
  })

  it('is case insensitive and returns uppercase', () => {
    expect(normalizeAddress('via roma 15')).toBe('VIA ROMA 15')
  })
})
