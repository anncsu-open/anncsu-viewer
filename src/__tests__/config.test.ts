import { describe, it, expect, vi } from 'vitest'

describe('appConfig', () => {
  it('exports a comuneName string', async () => {
    const { appConfig } = await import('@/config')
    expect(appConfig).toHaveProperty('comuneName')
    expect(typeof appConfig.comuneName).toBe('string')
  })

  it('has a non-empty comuneName', async () => {
    const { appConfig } = await import('@/config')
    expect(appConfig.comuneName.length).toBeGreaterThan(0)
  })

  it('reads comuneName from VITE_COMUNE_NAME env var', async () => {
    vi.stubEnv('VITE_COMUNE_NAME', 'Comune di Test')
    vi.resetModules()
    const { appConfig } = await import('@/config')
    expect(appConfig.comuneName).toBe('Comune di Test')
    vi.unstubAllEnvs()
  })

  it('falls back to default when VITE_COMUNE_NAME is not set', async () => {
    vi.stubEnv('VITE_COMUNE_NAME', '')
    vi.resetModules()
    const { appConfig } = await import('@/config')
    expect(appConfig.comuneName).toBe('del territorio nazionale')
    vi.unstubAllEnvs()
  })

  it('exports a dataBaseUrl string', async () => {
    const { appConfig } = await import('@/config')
    expect(appConfig).toHaveProperty('dataBaseUrl')
    expect(typeof appConfig.dataBaseUrl).toBe('string')
  })

  it('reads dataBaseUrl from VITE_DATA_BASE_URL env var', async () => {
    vi.stubEnv('VITE_DATA_BASE_URL', 'https://example.com/data')
    vi.resetModules()
    const { appConfig } = await import('@/config')
    expect(appConfig.dataBaseUrl).toBe('https://example.com/data')
    vi.unstubAllEnvs()
  })

  it('falls back to default dataBaseUrl when VITE_DATA_BASE_URL is not set', async () => {
    vi.stubEnv('VITE_DATA_BASE_URL', '')
    vi.resetModules()
    const { appConfig } = await import('@/config')
    expect(appConfig.dataBaseUrl).toBe('https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev')
    vi.unstubAllEnvs()
  })

  it('exports appMode', async () => {
    const { appConfig } = await import('@/config')
    expect(appConfig).toHaveProperty('appMode')
    expect(['nazionale', 'comunale']).toContain(appConfig.appMode)
  })

  it('reads appMode from VITE_APP_MODE env var', async () => {
    vi.stubEnv('VITE_APP_MODE', 'comunale')
    vi.resetModules()
    const { appConfig } = await import('@/config')
    expect(appConfig.appMode).toBe('comunale')
    vi.unstubAllEnvs()
  })

  it('defaults appMode to nazionale when VITE_APP_MODE is not set', async () => {
    vi.stubEnv('VITE_APP_MODE', '')
    vi.resetModules()
    const { appConfig } = await import('@/config')
    expect(appConfig.appMode).toBe('nazionale')
    vi.unstubAllEnvs()
  })

  it('exports isNazionale helper', async () => {
    vi.stubEnv('VITE_APP_MODE', 'nazionale')
    vi.resetModules()
    const { appConfig } = await import('@/config')
    expect(appConfig.isNazionale).toBe(true)
    vi.unstubAllEnvs()
  })

  it('isNazionale is false when mode is comunale', async () => {
    vi.stubEnv('VITE_APP_MODE', 'comunale')
    vi.resetModules()
    const { appConfig } = await import('@/config')
    expect(appConfig.isNazionale).toBe(false)
    vi.unstubAllEnvs()
  })
})
