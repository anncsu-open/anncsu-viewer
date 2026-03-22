import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import Header from '@/components/Header.vue'
import { appConfig } from '@/config'

describe('Header', () => {
  it('does not render the Geobeyond logo in header', () => {
    const wrapper = mount(Header)
    expect(wrapper.find('img[alt="Geobeyond"]').exists()).toBe(false)
  })

  it('renders the title using comuneName from config', () => {
    const wrapper = mount(Header)
    expect(wrapper.text()).toContain('Indirizzi ANNCSU')
    expect(wrapper.text()).toContain(appConfig.comuneName)
  })

  it('renders as a nav element', () => {
    const wrapper = mount(Header)
    expect(wrapper.find('nav').exists()).toBe(true)
  })
})
