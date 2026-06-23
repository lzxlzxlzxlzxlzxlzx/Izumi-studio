/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_STATIC_PAGES?: string;
  readonly VITE_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
