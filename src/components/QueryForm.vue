<script setup lang="ts">
import { appConfig } from '@/config'
</script>

<template>
  <div class="flex flex-col gap-4 p-6 font-['Titillium_Web',sans-serif] text-[#19191a]">
    <div class="flex flex-col gap-2 rounded-lg border-t-4 border-[#0066CC] bg-white p-5 shadow-lg">
      <div class="mb-3 flex items-center gap-2 text-lg font-bold text-[#0066CC]">
        <svg class="h-6 w-6 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
          <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd" />
        </svg>
        Questo applicativo permette di esplorare i dati ANNCSU {{ appConfig.comuneName }}
      </div>
      <ul class="list-disc text-base leading-relaxed text-[#17324d]">
        <li class="mb-2 ml-5">
          Cerca e visualizza sulla mappa gli <span class="font-bold">indirizzi con numero civico</span> del territorio comunale.
        </li>
        <li v-if="appConfig.isNazionale" class="mb-2 ml-5">
          Seleziona un <span class="font-bold">comune</span> per caricare gli indirizzi disponibili sul territorio.
        </li>
        <li class="mb-2 ml-5">
          Usa la <span class="font-bold">barra di ricerca</span> sopra la mappa per cercare un indirizzo
          specifico con autocompletamento.
        </li>
        <li class="mb-2 ml-5">
          Passa il mouse sui punti della mappa per visualizzare i dettagli di ogni indirizzo o luogo.
        </li>
        <li class="mb-2 ml-5">
          Clicca sulla <span class="font-bold">X</span> nel campo di ricerca per azzerare la ricerca e
          ripristinare la visualizzazione di tutti gli indirizzi.
        </li>
      </ul>
      <div class="mt-4 flex flex-col gap-3 rounded-md bg-[#f2f7fc] p-4 text-sm leading-relaxed text-[#17324d]">
        <div class="flex items-start gap-2">
          <svg class="mt-0.5 h-5 w-5 flex-shrink-0 text-[#0066CC]" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M6.267 3.455a3.066 3.066 0 001.745-.723 3.066 3.066 0 013.976 0 3.066 3.066 0 001.745.723 3.066 3.066 0 012.812 2.812c.051.643.304 1.254.723 1.745a3.066 3.066 0 010 3.976 3.066 3.066 0 00-.723 1.745 3.066 3.066 0 01-2.812 2.812 3.066 3.066 0 00-1.745.723 3.066 3.066 0 01-3.976 0 3.066 3.066 0 00-1.745-.723 3.066 3.066 0 01-2.812-2.812 3.066 3.066 0 00-.723-1.745 3.066 3.066 0 010-3.976 3.066 3.066 0 00.723-1.745 3.066 3.066 0 012.812-2.812zm7.44 5.252a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
          </svg>
          <span>
            Progetto finanziato nell'ambito del
            <a href="https://www.italiadomani.gov.it/" target="_blank" rel="noopener noreferrer" class="font-bold text-[#0066CC] underline hover:text-[#004d99]">PNRR</a>
            — Missione 1, Componente 1, Investimento 1.3 "Dati e interoperabilità" —
            <a href="https://padigitale2026.gov.it/" target="_blank" rel="noopener noreferrer" class="font-bold text-[#0066CC] underline hover:text-[#004d99]">Misura 1.3.1</a>
            per la digitalizzazione dell'<a href="https://www.anncsu.gov.it/" target="_blank" rel="noopener noreferrer" class="font-bold text-[#0066CC] underline hover:text-[#004d99]">Archivio Nazionale dei Numeri Civici e delle Strade Urbane (ANNCSU)</a>.
          </span>
        </div>
        <div class="flex items-start gap-2">
          <svg class="mt-0.5 h-5 w-5 flex-shrink-0 text-[#17324d]" fill="currentColor" viewBox="0 0 16 16">
            <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
          </svg>
          <span>
            Codice rilasciato in <span class="font-bold">open source</span> con
            <span class="font-bold">licenza MIT</span> su
            <a
              href="https://github.com/anncsu-open/anncsu-viewer"
              target="_blank"
              rel="noopener noreferrer"
              class="font-semibold text-[#0066CC] underline hover:text-[#004d99]"
            >GitHub</a>.
          </span>
        </div>
      </div>
      <div class="mt-3 flex flex-col items-center gap-1 text-sm text-[#17324d]">
        <span>Progetto sviluppato da</span>
        <a href="https://geobeyond.it/" target="_blank" rel="noopener noreferrer" class="inline-flex items-center gap-2">
          <img class="h-8" src="../assets/geobeyond.png" alt="Geobeyond" />
          <span class="text-lg font-bold">Geobeyond</span>
          <span class="text-xs italic text-[#5b6f82]">Making Geospatial Happen</span>
        </a>
      </div>
    </div>
  </div>
</template>

<style scoped></style>
