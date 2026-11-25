/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_COMUNE_NAME?: string
  readonly VITE_DATA_BASE_URL?: string
  readonly VITE_APP_MODE?: 'nazionale' | 'comunale'
  readonly VITE_LOGO_URL?: string
  readonly VITE_ISTITUZIONALE?: string
  readonly VITE_GESTORE?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
