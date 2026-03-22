import { describe, it, expect } from 'vitest'
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

  it('shows comune selection hint only in nazionale mode', () => {
    const wrapper = mount(QueryForm)
    if (appConfig.isNazionale) {
      expect(wrapper.text()).toContain('Seleziona un comune')
    } else {
      expect(wrapper.text()).not.toContain('Seleziona un comune')
    }
  })
})
