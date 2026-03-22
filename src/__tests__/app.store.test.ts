import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAppStore } from '@/store/app.store'

describe('useAppStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('has correct initial state', () => {
    const store = useAppStore()
    expect(store.query).toBe('')
    expect(store.queryLoading).toBe(false)
    expect(store.queryError).toBe(false)
    expect(store.legend).toEqual([])
    expect(store.sidebarOpen).toBe(true)
    expect(store.searchFilter).toBe('')
    expect(store.querySubmitted).toBe(false)
    expect(store.selectedCoordinates).toBeNull()
    expect(store.resetView).toBe(false)
  })

  it('setQuery updates query', () => {
    const store = useAppStore()
    store.setQuery('SELECT * FROM places')
    expect(store.query).toBe('SELECT * FROM places')
  })

  it('setQueryLoading updates queryLoading', () => {
    const store = useAppStore()
    store.setQueryLoading(true)
    expect(store.queryLoading).toBe(true)
    store.setQueryLoading(false)
    expect(store.queryLoading).toBe(false)
  })

  it('setQueryError updates queryError', () => {
    const store = useAppStore()
    store.setQueryError(true)
    expect(store.queryError).toBe(true)
  })

  it('setLegend updates legend', () => {
    const store = useAppStore()
    const legendData = [0, '#d3f2a3', 10, '#97e196']
    store.setLegend(legendData)
    expect(store.legend).toEqual(legendData)
  })

  it('toggleSidebar toggles sidebarOpen', () => {
    const store = useAppStore()
    expect(store.sidebarOpen).toBe(true)
    store.toggleSidebar()
    expect(store.sidebarOpen).toBe(false)
    store.toggleSidebar()
    expect(store.sidebarOpen).toBe(true)
  })

  it('setSearchFilter updates searchFilter', () => {
    const store = useAppStore()
    store.setSearchFilter('VIA ROMA 15')
    expect(store.searchFilter).toBe('VIA ROMA 15')
  })

  it('setQuerySubmitted updates querySubmitted', () => {
    const store = useAppStore()
    store.setQuerySubmitted(true)
    expect(store.querySubmitted).toBe(true)
  })

  it('setSelectedCoordinates updates selectedCoordinates', () => {
    const store = useAppStore()
    store.setSelectedCoordinates([12.641, 42.376])
    expect(store.selectedCoordinates).toEqual([12.641, 42.376])
  })

  it('setSelectedCoordinates can be reset to null', () => {
    const store = useAppStore()
    store.setSelectedCoordinates([12.641, 42.376])
    store.setSelectedCoordinates(null)
    expect(store.selectedCoordinates).toBeNull()
  })

  it('triggerResetView sets resetView to true', () => {
    const store = useAppStore()
    expect(store.resetView).toBe(false)
    store.triggerResetView()
    expect(store.resetView).toBe(true)
  })

  it('clearResetView sets resetView back to false', () => {
    const store = useAppStore()
    store.triggerResetView()
    store.clearResetView()
    expect(store.resetView).toBe(false)
  })
})
