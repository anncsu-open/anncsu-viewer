import defaultLogo from '@/assets/logo.svg'

export const appConfig = {
  comuneName: import.meta.env.VITE_COMUNE_NAME || 'del territorio nazionale',
  dataBaseUrl:
    import.meta.env.VITE_DATA_BASE_URL ||
    'https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev',
  appMode:
    (import.meta.env.VITE_APP_MODE as 'nazionale' | 'comunale') || 'nazionale',
  logoUrl: import.meta.env.VITE_LOGO_URL || defaultLogo,
  // Only an administration publishing its own copy sets this, and only the
  // exact value "true" counts: anything else keeps the notice.
  istituzionale: import.meta.env.VITE_ISTITUZIONALE === 'true',
  gestore: import.meta.env.VITE_GESTORE || 'anncsu-open',
  get isNazionale() {
    return this.appMode === 'nazionale'
  },
}
