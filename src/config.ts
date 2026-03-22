export const appConfig = {
  comuneName: import.meta.env.VITE_COMUNE_NAME || 'del territorio nazionale',
  dataBaseUrl:
    import.meta.env.VITE_DATA_BASE_URL ||
    'https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev',
  appMode:
    (import.meta.env.VITE_APP_MODE as 'nazionale' | 'comunale') || 'nazionale',
  get isNazionale() {
    return this.appMode === 'nazionale'
  },
}
