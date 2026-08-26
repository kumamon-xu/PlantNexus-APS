import {
  e2eSyntheticProvenance,
  loadRuntimeConfig,
} from "../src/api/runtime";

describe("Production / Simulation runtime isolation", () => {
  it("defaults to a same-origin Production read surface", () => {
    expect(loadRuntimeConfig({})).toEqual({
      apiBaseUrl: "/api/v1",
      dataPlane: "PRODUCTION",
      environment: "PRODUCTION",
      synthetic: false,
    });
  });

  it("fails closed when a deploy attempts to expose a Simulation plane", () => {
    expect(() =>
      loadRuntimeConfig({
        VITE_PLANTNEXUS_DATA_PLANE: "SIMULATION",
        VITE_PLANTNEXUS_ENVIRONMENT: "DEVELOPMENT",
      }),
    ).toThrow(/fail-closed/u);
  });

  it("permits Simulation only through the explicit development E2E gate", () => {
    expect(
      loadRuntimeConfig({
        DEV: true,
        VITE_PLANTNEXUS_DATA_PLANE: "SIMULATION",
        VITE_PLANTNEXUS_ENVIRONMENT: "TEST",
        VITE_PLANTNEXUS_E2E_SIMULATION: "true",
      }),
    ).toEqual({
      apiBaseUrl: "/api/v1",
      dataPlane: "SIMULATION",
      environment: "TEST",
      synthetic: true,
      syntheticProvenance: e2eSyntheticProvenance,
    });
    expect(() =>
      loadRuntimeConfig({
        DEV: false,
        VITE_PLANTNEXUS_DATA_PLANE: "SIMULATION",
        VITE_PLANTNEXUS_ENVIRONMENT: "TEST",
        VITE_PLANTNEXUS_E2E_SIMULATION: "true",
      }),
    ).toThrow(/fail-closed/u);
  });

  it("rejects an insecure or credential-bearing API base", () => {
    expect(() =>
      loadRuntimeConfig({ VITE_PLANTNEXUS_API_BASE_URL: "http://aps.example/api/v1" }),
    ).toThrow(/HTTPS/u);
    expect(() =>
      loadRuntimeConfig({
        VITE_PLANTNEXUS_API_BASE_URL: "https://reader:secret@aps.example/api/v1",
      }),
    ).toThrow(/credential-free/u);
  });
});
