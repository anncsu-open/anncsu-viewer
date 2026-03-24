<script setup lang="ts">
import { appConfig } from '@/config'
import { useAppStore } from '@/store/app.store'
import { storeToRefs } from 'pinia'

const store = useAppStore()
const { sidebarOpen } = storeToRefs(store)
</script>

<template>
  <nav class="flex h-16 items-center bg-[#0066CC] px-4 py-3 md:px-6">
    <button
      data-testid="open-panel"
      @click="store.toggleSidebar()"
      class="mr-3 rounded p-1.5 text-white transition-colors hover:bg-white/20"
      :title="sidebarOpen ? 'Close panel' : 'Open panel'"
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
    <span class="text-base font-bold text-white md:text-2xl">Indirizzi ANNCSU {{ appConfig.comuneName }}</span>
  </nav>
</template>
