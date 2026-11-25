import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import Header from '@/components/Header.vue'
import { appConfig } from '@/config'
import { useAppStore } from '@/store/app.store'

describe('Header', () => {
  it('does not render the Geobeyond logo in header', () => {
    const wrapper = mount(Header, { global: { plugins: [createPinia()] } })
    expect(wrapper.find('img[alt="Geobeyond"]').exists()).toBe(false)
  })

  it('renders the title using comuneName from config', () => {
    const wrapper = mount(Header, { global: { plugins: [createPinia()] } })
    expect(wrapper.text()).toContain('Indirizzi ANNCSU')
    expect(wrapper.text()).toContain(appConfig.comuneName)
  })

  it('renders as a nav element', () => {
    const wrapper = mount(Header, { global: { plugins: [createPinia()] } })
    expect(wrapper.find('nav').exists()).toBe(true)
  })

  it('contains the sidebar toggle button', () => {
    const wrapper = mount(Header, { global: { plugins: [createPinia()] } })
    const btn = wrapper.find('[data-testid="open-panel"]')
    expect(btn.exists()).toBe(true)
  })

  it('shows the configured logo', () => {
    const wrapper = mount(Header, { global: { plugins: [createPinia()] } })
    const logo = wrapper.find('[data-testid="site-logo"]')
    expect(logo.element.tagName).toBe('IMG')
    expect(logo.attributes('src')).toBe(appConfig.logoUrl)
    // The name sits next to it, so the logo is decorative.
    expect(logo.attributes('alt')).toBe('')
  })

  it('keeps any logo inside its box', () => {
    const wrapper = mount(Header, { global: { plugins: [createPinia()] } })
    const classes = wrapper.find('[data-testid="site-logo"]').classes()
    expect(classes).toContain('object-contain')
    expect(classes.some((c) => c.startsWith('max-w-'))).toBe(true)
  })

  it('labels the panel button in Italian', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useAppStore()
    const wrapper = mount(Header, { global: { plugins: [pinia] } })
    const button = wrapper.find('[data-testid="open-panel"]')

    store.sidebarOpen = true
    await wrapper.vm.$nextTick()
    expect(button.attributes('title')).toBe('Chiudi pannello')
    store.sidebarOpen = false
    await wrapper.vm.$nextTick()
    expect(button.attributes('title')).toBe('Apri pannello')
  })
})
