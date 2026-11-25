<script setup lang="ts">
import { appConfig } from '@/config'
import { useAppStore } from '@/store/app.store'
import { storeToRefs } from 'pinia'

const store = useAppStore()
const { sidebarOpen } = storeToRefs(store)
</script>

<template>
  <nav class="flex h-18 items-center bg-primary px-4 md:px-6">
    <button
      data-testid="open-panel"
      @click="store.toggleSidebar()"
      class="mr-3 shrink-0 rounded p-1.5 text-white transition-colors hover:bg-white/20"
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
    <img
      data-testid="site-logo"
      :src="appConfig.logoUrl"
      alt=""
      class="mr-3 h-8 w-auto max-w-16 shrink-0 object-contain md:h-10 md:max-w-40"
    />
    <span data-testid="site-name" class="line-clamp-3 text-[18px] leading-tight font-semibold text-white md:text-2xl">
      Indirizzi ANNCSU {{ appConfig.comuneName }}
    </span>
  </nav>
</template>
