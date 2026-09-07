import {
  loadRuntimeConfig,
  type RuntimeConfig,
  type RuntimeEnvInput,
} from "../api/runtime";

export interface HeadlessRuntimeEnvInput extends RuntimeEnvInput {
  readonly MODE?: string;
}

/**
 * Production distributions retain the existing fail-closed runtime policy.
 * A separately built `e2e` artifact may run against intercepted synthetic
 * responses so Playwright can verify the packaged files rather than a dev
 * server. The gate is compile-time explicit and cannot be enabled by a
 * runtime query string, browser storage, or cookie.
 */
export function loadHeadlessRuntimeConfig(
  env: HeadlessRuntimeEnvInput = import.meta.env,
): RuntimeConfig {
  const packagedSyntheticEvidence =
    env.MODE === "e2e" &&
    env.VITE_PLANTNEXUS_E2E_SIMULATION === "true" &&
    env.VITE_PLANTNEXUS_DATA_PLANE === "SIMULATION" &&
    env.VITE_PLANTNEXUS_ENVIRONMENT === "TEST";

  return loadRuntimeConfig(
    packagedSyntheticEvidence ? { ...env, DEV: true } : env,
  );
}
