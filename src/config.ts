export const appConfig = {
  comuneName: import.meta.env.VITE_COMUNE_NAME || 'del territorio nazionale',
  dataBaseUrl:
    import.meta.env.VITE_DATA_BASE_URL ||
    'https://anncsu-open.github.io/anncsu-viewer',
  dataReleaseUrl:
    import.meta.env.VITE_DATA_RELEASE_URL ||
    'https://github.com/anncsu-open/anncsu-viewer/releases/latest/download',
  appMode:
    (import.meta.env.VITE_APP_MODE as 'nazionale' | 'comunale') || 'nazionale',
  get isNazionale() {
    return this.appMode === 'nazionale'
  },
}
