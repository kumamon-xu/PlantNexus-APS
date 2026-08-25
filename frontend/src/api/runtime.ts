import type { DataPlane, RuntimeEnvironment } from "./types";

export interface RuntimeConfig {
  apiBaseUrl: string;
  dataPlane: DataPlane;
  environment: RuntimeEnvironment;
  synthetic: false;
}

export interface RuntimeEnvInput {
  readonly VITE_PLANTNEXUS_API_BASE_URL?: string;
  readonly VITE_PLANTNEXUS_DATA_PLANE?: "SIMULATION" | "PRODUCTION";
  readonly VITE_PLANTNEXUS_ENVIRONMENT?:
    | "DEVELOPMENT"
    | "TEST"
    | "BENCHMARK"
    | "PRODUCTION";
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
  if (requestedPlane !== "PRODUCTION" || requestedEnvironment !== "PRODUCTION") {
    throw new Error(
      "P3-11 runtime is fail-closed: Simulation fixtures are test-only and have no navigation entry",
    );
  }
  return {
    apiBaseUrl: apiBaseUrl(env.VITE_PLANTNEXUS_API_BASE_URL),
    dataPlane: "PRODUCTION",
    environment: "PRODUCTION",
    synthetic: false,
  };
}
