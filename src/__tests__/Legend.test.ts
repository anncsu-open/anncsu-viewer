import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import Legend from '@/components/Legend.vue'
import { useAppStore } from '@/store/app.store'

describe('Legend', () => {
  it('renders legend steps from store', () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useAppStore()
    store.setLegend([0, '#d3f2a3', 10, '#97e196', 50, '#6cc08b'])

    const wrapper = mount(Legend, { global: { plugins: [pinia] } })

    const steps = wrapper.findAll('.flex.items-center.gap-2')
    expect(steps).toHaveLength(3)
    expect(wrapper.text()).toContain('> 0')
    expect(wrapper.text()).toContain('> 10')
    expect(wrapper.text()).toContain('> 50')
  })

  it('renders color squares with correct background', () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useAppStore()
    store.setLegend([0, '#d3f2a3', 10, '#97e196'])

    const wrapper = mount(Legend, { global: { plugins: [pinia] } })

    const colorSquares = wrapper.findAll('span.h-4.w-4')
    expect(colorSquares[0].attributes('style')).toContain('background-color: #d3f2a3')
    expect(colorSquares[1].attributes('style')).toContain('background-color: #97e196')
  })

  it('renders empty when legend is empty', () => {
    const pinia = createPinia()
    setActivePinia(pinia)

    const wrapper = mount(Legend, { global: { plugins: [pinia] } })

    const steps = wrapper.findAll('.flex.items-center.gap-2')
    expect(steps).toHaveLength(0)
  })

  it('displays the count label', () => {
    const pinia = createPinia()
    setActivePinia(pinia)

    const wrapper = mount(Legend, { global: { plugins: [pinia] } })
    expect(wrapper.text()).toContain('count')
  })
})
