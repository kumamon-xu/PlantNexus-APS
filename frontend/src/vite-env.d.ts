/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_PLANTNEXUS_API_BASE_URL?: string;
  readonly VITE_PLANTNEXUS_DATA_PLANE?: "SIMULATION" | "PRODUCTION";
  readonly VITE_PLANTNEXUS_ENVIRONMENT?:
    | "DEVELOPMENT"
    | "TEST"
    | "BENCHMARK"
    | "PRODUCTION";
  readonly VITE_PLANTNEXUS_E2E_SIMULATION?: "true" | "false";
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

interface ImportMetaEnv {
  readonly VITE_PLANTNEXUS_API_BASE_URL?: string;
  readonly VITE_PLANTNEXUS_DATA_PLANE?: "SIMULATION" | "PRODUCTION";
  readonly VITE_PLANTNEXUS_ENVIRONMENT?:
    | "DEVELOPMENT"
    | "TEST"
    | "BENCHMARK"
    | "PRODUCTION";
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
