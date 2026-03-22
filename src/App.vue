<script setup lang="ts">
import Header from '@/components/Header.vue'
import Map from '@/components/Map.vue'
import QueryForm from '@/components/QueryForm.vue'
import Legend from '@/components/Legend.vue'
import SearchBar from '@/components/SearchBar.vue'
import { useAppStore } from '@/store/app.store.ts'
import { storeToRefs } from 'pinia'

const store = useAppStore()
const { legend, sidebarOpen } = storeToRefs(store)
</script>

<template>
  <div class="flex h-screen flex-col">
    <header>
      <Header />
    </header>
    <div class="flex grow flex-col md:flex-row">
      <aside v-if="sidebarOpen" class="md:w-120">
        <QueryForm></QueryForm>
      </aside>
      <main class="relative grow">
        <SearchBar />
        <button
          @click="store.toggleSidebar()"
          class="absolute left-4 top-4 z-20 rounded bg-white px-3 py-2 shadow-lg hover:bg-gray-100"
          :title="sidebarOpen ? 'Chiudi pannello' : 'Apri pannello'"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            stroke-width="1.5"
            stroke="currentColor"
            class="h-6 w-6"
          >
            <path
              v-if="sidebarOpen"
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M6 18L18 6M6 6l12 12"
            />
            <path
              v-else
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5"
            />
          </svg>
        </button>
        <Map></Map>
      </main>
    </div>
  </div>
</template>
