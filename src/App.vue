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
    <div class="relative flex grow flex-col md:flex-row">
      <!-- Sidebar overlay (mobile) / inline (desktop) -->
      <aside
        v-if="sidebarOpen"
        class="fixed inset-0 top-16 z-30 overflow-y-auto bg-white md:relative md:inset-auto md:z-auto md:w-120"
      >
        <!-- Close button inside panel -->
        <button
          data-testid="close-panel"
          @click="store.toggleSidebar()"
          class="absolute right-4 top-4 z-10 rounded-full bg-white p-2 shadow-md transition-colors hover:bg-gray-100 md:hidden"
          title="Close panel"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            stroke-width="1.5"
            stroke="currentColor"
            class="h-5 w-5"
          >
            <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
        <QueryForm></QueryForm>
      </aside>

      <!-- Backdrop overlay on mobile -->
      <div
        v-if="sidebarOpen"
        class="fixed inset-0 top-16 z-20 bg-black/30 md:hidden"
        @click="store.toggleSidebar()"
      ></div>

      <main class="relative grow">
        <SearchBar />
        <Map></Map>
      </main>
    </div>
  </div>
</template>
