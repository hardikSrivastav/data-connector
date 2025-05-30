/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE: string
  readonly VITE_AGENT_BASE_URL: string
  readonly VITE_EDITION: 'enterprise' | 'zero-sync'
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
