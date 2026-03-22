<script setup lang="ts">
import { appConfig } from '@/config'
</script>

<template>
  <nav class="flex h-16 bg-[#0066CC] px-6 py-3">
    <div class="flex grow items-center">
      <span class="text-2xl font-bold text-white">Indirizzi ANNCSU {{ appConfig.comuneName }}</span>
    </div>
  </nav>
</template>

<style scoped></style>
