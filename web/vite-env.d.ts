/// <reference types="vite/client" />

declare const __APP_VERSION__: string;

interface ImportMetaEnv {
  readonly VITE_LANDING_URL?: string;
  readonly VITE_PRO_URL?: string;
  readonly VITE_DOWNLOAD_URL?: string;
  readonly VITE_REPO_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
