import {
  HeadlessContractError,
  parseCanonicalIngressRequestText,
  parseCanonicalIngressResult,
  parsePlanningRun,
} from "../src/headless/contracts";
import { loadHeadlessRuntimeConfig } from "../src/headless/runtime";
import { resolveHeadlessSessionProvider } from "../src/headless/session";
import {
  cloneFixture,
  p8AcceptedResult,
  p8CanonicalRequestText,
  p8CompletedRun,
  p8CreatedRun,
} from "./p8HeadlessFixtures";

describe("TEST-P8-FRONTEND-DISTRIBUTION-001 strict Headless contracts", () => {
  it("preserves the submitted canonical JSON bytes and binds the accepted result", () => {
    const request = parseCanonicalIngressRequestText(p8CanonicalRequestText);
    expect(request.raw).toBe(p8CanonicalRequestText);
    expect(request.requestId).toBe("REQUEST-P8-SYNTHETIC-001");
    expect(parseCanonicalIngressResult(p8AcceptedResult, request)).toMatchObject({
      disposition: "ACCEPTED",
      correlation_id: "CORRELATION-P8-SYNTHETIC-001",
    });
  });

  it("accepts the published created and completed PlanningRun samples", () => {
    expect(parsePlanningRun(p8CreatedRun)).toMatchObject({
      state: "CREATED",
      terminal: false,
      allowed_actions: ["READ", "CANCEL"],
    });
    expect(parsePlanningRun(p8CompletedRun)).toMatchObject({
      state: "COMPLETED",
      terminal: true,
      allowed_actions: ["READ"],
    });
  });

  it("fails closed for unknown versions, fields, state authority and fingerprints", () => {
    const version = cloneFixture(p8CompletedRun) as Record<string, unknown>;
    version.planning_run_version = "planning-run.v2";
    expect(() => parsePlanningRun(version)).toThrowError(HeadlessContractError);

    const extra = cloneFixture(p8AcceptedResult) as Record<string, unknown>;
    extra.frontend_private_result = true;
    expect(() => parseCanonicalIngressResult(extra)).toThrow(/unknown fields/u);

    const state = cloneFixture(p8CreatedRun) as Record<string, unknown>;
    state.allowed_actions = ["READ"];
    expect(() => parsePlanningRun(state)).toThrow(/allowed actions/u);

    const resolution = cloneFixture(p8CompletedRun) as Record<string, unknown>;
    const runtime = resolution.runtime_resolution as Record<string, unknown>;
    const extension = runtime.extension_set as Record<string, unknown>;
    extension.extension_set_fingerprint = "not-a-fingerprint";
    expect(() => parsePlanningRun(resolution)).toThrow(/SHA-256/u);
  });

  it("allows packaged synthetic data only in the exact e2e build mode", () => {
    expect(
      loadHeadlessRuntimeConfig({
        MODE: "e2e",
        DEV: false,
        VITE_PLANTNEXUS_DATA_PLANE: "SIMULATION",
        VITE_PLANTNEXUS_ENVIRONMENT: "TEST",
        VITE_PLANTNEXUS_E2E_SIMULATION: "true",
      }),
    ).toMatchObject({ dataPlane: "SIMULATION", environment: "TEST", synthetic: true });
    expect(() =>
      loadHeadlessRuntimeConfig({
        MODE: "production",
        DEV: false,
        VITE_PLANTNEXUS_DATA_PLANE: "SIMULATION",
        VITE_PLANTNEXUS_ENVIRONMENT: "TEST",
        VITE_PLANTNEXUS_E2E_SIMULATION: "true",
      }),
    ).toThrow(/fail-closed/u);
  });

  it("uses only an explicitly injected in-memory session provider", async () => {
    const fallback = resolveHeadlessSessionProvider({});
    expect(await fallback.getAccessToken()).toBeNull();

    const injected = { async getAccessToken() { return "opaque-session-token"; } };
    expect(
      resolveHeadlessSessionProvider({
        __PLANTNEXUS_APS_SESSION_PROVIDER__: injected,
      }),
    ).toBe(injected);
  });
});
