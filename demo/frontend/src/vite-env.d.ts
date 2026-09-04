/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_DEMO_PROFILE?: "smoke" | "showcase";
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
