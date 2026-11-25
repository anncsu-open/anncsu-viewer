import { afterEach, describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import QueryForm from '@/components/QueryForm.vue'
import { appConfig } from '@/config'

describe('QueryForm (info panel)', () => {
  it('renders the description using comuneName from config', () => {
    const wrapper = mount(QueryForm)
    expect(wrapper.text()).toContain(appConfig.comuneName)
  })

  it('mentions searching addresses with house numbers', () => {
    const wrapper = mount(QueryForm)
    expect(wrapper.text()).toContain('indirizzi con numero civico')
  })

  it('mentions the search bar', () => {
    const wrapper = mount(QueryForm)
    expect(wrapper.text()).toContain('barra di ricerca')
  })

  it('shows combined search hint only in nazionale mode', () => {
    const wrapper = mount(QueryForm)
    if (appConfig.isNazionale) {
      expect(wrapper.text()).toContain('comune e indirizzo')
      expect(wrapper.text()).toContain('separati da virgola')
    } else {
      expect(wrapper.text()).not.toContain('separati da virgola')
    }
  })

  it('mentions clearing search to reset view', () => {
    const wrapper = mount(QueryForm)
    expect(wrapper.text()).toContain('azzerare la ricerca')
    expect(wrapper.text()).toContain('ripristinare la visualizzazione')
  })

  it('does not render any form elements', () => {
    const wrapper = mount(QueryForm)
    expect(wrapper.find('select').exists()).toBe(false)
    expect(wrapper.find('textarea').exists()).toBe(false)
    expect(wrapper.find('button').exists()).toBe(false)
  })

  it('renders as an alert-style card with top border', () => {
    const wrapper = mount(QueryForm)
    const card = wrapper.find('.border-t-4')
    expect(card.exists()).toBe(true)
  })

  it('shows comune search hint only in nazionale mode', () => {
    const wrapper = mount(QueryForm)
    if (appConfig.isNazionale) {
      expect(wrapper.text()).toContain('Digita il nome di un comune')
    } else {
      expect(wrapper.text()).not.toContain('Digita il nome di un comune')
    }
  })
})

describe('QueryForm notice', () => {
  // The notice depends on the build-time variables, so each test reloads
  // the config and the component with its own values.
  async function mountWith(env: Record<string, string>) {
    for (const [name, value] of Object.entries(env)) vi.stubEnv(name, value)
    vi.resetModules()
    const { default: Panel } = await import('@/components/QueryForm.vue')
    return mount(Panel)
  }

  afterEach(() => {
    vi.unstubAllEnvs()
  })

  it('says the site is not institutional', async () => {
    const wrapper = await mountWith({ VITE_ISTITUZIONALE: '', VITE_GESTORE: '' })
    expect(wrapper.find('[data-testid="notice"]').text()).toBe(
      'Non è un sito istituzionale · gestito da anncsu-open',
    )
  })

  it('names the configured operator', async () => {
    const wrapper = await mountWith({ VITE_GESTORE: 'Comune di Test' })
    expect(wrapper.find('[data-testid="notice"]').text()).toMatch(/gestito da Comune di Test$/)
  })

  it('hides the notice on an institutional site', async () => {
    const wrapper = await mountWith({ VITE_ISTITUZIONALE: 'true' })
    expect(wrapper.find('[data-testid="notice"]').exists()).toBe(false)
  })
})
