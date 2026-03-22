export const appConfig = {
  comuneName: import.meta.env.VITE_COMUNE_NAME || 'del territorio nazionale',
  dataBaseUrl:
    import.meta.env.VITE_DATA_BASE_URL ||
    'https://anncsu-open.github.io/anncsu-viewer',
  appMode:
    (import.meta.env.VITE_APP_MODE as 'nazionale' | 'comunale') || 'nazionale',
  get isNazionale() {
    return this.appMode === 'nazionale'
  },
}
