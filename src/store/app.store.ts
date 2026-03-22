import { type Ref, ref } from 'vue'
import { defineStore } from 'pinia'

export const useAppStore = defineStore('app', () => {
  const query: Ref<string> = ref('')
  const queryLoading: Ref<boolean> = ref(false)
  const queryError: Ref<boolean> = ref(false)
  const legend: Ref<(string | number)[]> = ref([])
  const sidebarOpen: Ref<boolean> = ref(true)
  const searchFilter: Ref<string> = ref('')
  const querySubmitted: Ref<boolean> = ref(false)
  const selectedCoordinates: Ref<[number, number] | null> = ref(null)
  const resetView: Ref<boolean> = ref(false)

  function setLegend(value: (string | number)[]) {
    legend.value = value
  }
  function setQuery(value: string) {
    query.value = value
  }
  function setQueryLoading(value: boolean) {
    queryLoading.value = value
  }
  function setQueryError(value: boolean) {
    queryError.value = value
  }
  function toggleSidebar() {
    sidebarOpen.value = !sidebarOpen.value
  }
  function setSearchFilter(value: string) {
    searchFilter.value = value
  }
  function setQuerySubmitted(value: boolean) {
    querySubmitted.value = value
  }
  function setSelectedCoordinates(value: [number, number] | null) {
    selectedCoordinates.value = value
  }
  function triggerResetView() {
    resetView.value = true
  }
  function clearResetView() {
    resetView.value = false
  }
  return {
    legend,
    setLegend,
    query,
    setQuery,
    queryLoading,
    setQueryLoading,
    queryError,
    setQueryError,
    sidebarOpen,
    toggleSidebar,
    searchFilter,
    setSearchFilter,
    querySubmitted,
    setQuerySubmitted,
    selectedCoordinates,
    setSelectedCoordinates,
    resetView,
    triggerResetView,
    clearResetView,
  }
})
