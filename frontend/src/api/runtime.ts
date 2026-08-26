import type { DataPlane, JsonObject, RuntimeEnvironment } from "./types";

export const e2eSyntheticProvenance: JsonObject = {
  scenario_id: "SIM-P3-HUMAN-CONTROL-001",
  scenario_version: "1.0.0",
  seed: 20260826,
  factory_profile_id: "PROFILE-P3-UI-E2E-001",
  profile_version: "1.0.0",
  generator_id: "PLANTNEXUS-P3-PLAYWRIGHT",
  generator_version: "1.0.0",
};

export interface RuntimeConfig {
  apiBaseUrl: string;
  dataPlane: DataPlane;
  environment: RuntimeEnvironment;
  synthetic: boolean;
  syntheticProvenance?: JsonObject;
}

export interface RuntimeEnvInput {
  readonly DEV?: boolean;
  readonly VITE_PLANTNEXUS_API_BASE_URL?: string;
  readonly VITE_PLANTNEXUS_DATA_PLANE?: "SIMULATION" | "PRODUCTION";
  readonly VITE_PLANTNEXUS_ENVIRONMENT?:
    | "DEVELOPMENT"
    | "TEST"
    | "BENCHMARK"
    | "PRODUCTION";
  readonly VITE_PLANTNEXUS_E2E_SIMULATION?: "true" | "false";
}

function apiBaseUrl(value: string | undefined): string {
  const candidate = value?.trim() || "/api/v1";
  const normalized = candidate.endsWith("/") ? candidate.slice(0, -1) : candidate;
  if (normalized.startsWith("/") && !normalized.startsWith("//")) {
    return normalized;
  }
  let url: URL;
  try {
    url = new URL(normalized);
  } catch {
    throw new Error("Frontend API base URL must be same-origin or absolute HTTPS");
  }
  if (
    url.protocol !== "https:" ||
    url.username !== "" ||
    url.password !== "" ||
    url.search !== "" ||
    url.hash !== ""
  ) {
    throw new Error("Frontend API base URL must be credential-free absolute HTTPS");
  }
  return normalized;
}

export function loadRuntimeConfig(env: RuntimeEnvInput = import.meta.env): RuntimeConfig {
  const requestedPlane = env.VITE_PLANTNEXUS_DATA_PLANE ?? "PRODUCTION";
  const requestedEnvironment =
    env.VITE_PLANTNEXUS_ENVIRONMENT ?? "PRODUCTION";
  const isolatedE2e =
    env.DEV === true &&
    env.VITE_PLANTNEXUS_E2E_SIMULATION === "true" &&
    requestedPlane === "SIMULATION" &&
    requestedEnvironment === "TEST";
  if (isolatedE2e) {
    return {
      apiBaseUrl: apiBaseUrl(env.VITE_PLANTNEXUS_API_BASE_URL),
      dataPlane: "SIMULATION",
      environment: "TEST",
      synthetic: true,
      syntheticProvenance: e2eSyntheticProvenance,
    };
  }
  if (requestedPlane !== "PRODUCTION" || requestedEnvironment !== "PRODUCTION") {
    throw new Error(
      "P3 runtime is fail-closed: Simulation controls require the isolated development E2E gate",
    );
  }
  return {
    apiBaseUrl: apiBaseUrl(env.VITE_PLANTNEXUS_API_BASE_URL),
    dataPlane: "PRODUCTION",
    environment: "PRODUCTION",
    synthetic: false,
  };
}
