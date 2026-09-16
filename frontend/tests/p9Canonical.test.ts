import type { JsonObject } from "../src/api/types";
import { createDynamicReplanningClient } from "../src/features/replanning/client";
import { buildTimelineQuery } from "../src/features/replanning/query";
import { p4Runtime, p4Identity, responseForQuery } from "./replanningFixtures";
import {
  canonicalJson, canonicalProjection, parseCanonicalJson, readCanonicalResponse,
  sha256Fingerprint, workspaceQueryFingerprint,
} from "../src/api/canonical";
import { createPlanningWorkspaceClient } from "../src/api/client";
import { buildWorkspaceQuery } from "../src/api/query";
import { createHeadlessPlanningClient } from "../src/headless/client";
import { parseCanonicalIngressRequestText } from "../src/headless/contracts";
import { p8CanonicalRequestText, p8Runtime, p8Scope } from "./p8HeadlessFixtures";
import { workspaceResponse } from "./fixtures";
import vectors from "./p9CanonicalVectors.json";

describe("TEST-P9-CANONICAL-001 frozen Python/TypeScript v1 parity", () => {
  it.each(vectors.vectors)("$id exact bytes and SHA-256", async ({ raw, canonical, fingerprint }) => {
    const value = parseCanonicalJson(raw);
    expect(canonicalJson(value)).toBe(canonical);
    expect(await sha256Fingerprint(value)).toBe(fingerprint);
    expect(canonicalJson(parseCanonicalJson(canonical))).toBe(canonical);
  });

  it.each([...vectors.rejections, ...vectors.unsupported_in_browser])("rejects %s before hashing", (raw) => {
    expect(() => parseCanonicalJson(raw)).toThrow(TypeError);
  });

  it("keeps parsed numbers immutable and preserves scalar projection provenance", () => {
    const source = parseCanonicalJson('{"n":1.0,"other":2,"array":[-0.0]}');
    expect(canonicalJson(canonicalProjection(source, ["n", "array"]))).toBe('{"array":[-0.0],"n":1.0}');
    expect(() => { source.n = 2; }).toThrow(TypeError);
    expect(() => canonicalProjection(source, ["missing"])).toThrow(TypeError);
    expect(canonicalJson({ n: 1, fraction: 1e-7, zero: -0 })).toBe('{"fraction":1e-07,"n":1,"zero":-0.0}');
  });

  it("rejects ambiguous native numbers, invalid Unicode and unsupported versions", async () => {
    for (const n of [NaN, Infinity, -Infinity, 9007199254740992]) {
      expect(() => canonicalJson({ n })).toThrow(TypeError);
    }
    expect(() => canonicalJson({ text: "\ud800" })).toThrow(TypeError);
    expect(() => parseCanonicalJson("{}", "canonical-json.v2")).toThrow(TypeError);
    expect(() => canonicalJson({}, "canonical-json.v2")).toThrow(TypeError);
    await expect(workspaceQueryFingerprint({ canonicalization_version: "unknown" })).rejects.toThrow(TypeError);
  });

  it("rejects malformed UTF-8 and BOM instead of replacing bytes", async () => {
    for (const bytes of [new Uint8Array([123, 34, 115, 34, 58, 34, 255, 34, 125]), new Uint8Array([239, 187, 191, 123, 125])]) {
      await expect(readCanonicalResponse(new Response(bytes))).rejects.toThrow();
    }
  });

  it("validates a workspace response carrying a Python whole-valued float", async () => {
    const runtime = { apiBaseUrl: "/api/v1", dataPlane: "PRODUCTION", environment: "PRODUCTION", synthetic: false } as const;
    const query = await buildWorkspaceQuery({ authority: runtime, view: "DATA_HEALTH" });
    const payload = parseCanonicalJson('{"status":"HEALTHY","observed_at_utc":"2026-08-25T01:00:00Z","metric":1.0}');
    const body = await workspaceResponse("DATA_HEALTH", { request: query, payloads: [payload] });
    const raw = canonicalJson(body);
    expect(raw).toContain('"metric":1.0');
    const client = createPlanningWorkspaceClient(runtime, { async getAccessToken() { return null; } },
      vi.fn(async () => new Response(raw)) as typeof fetch);
    await expect(client.queryWorkspace(query, "DATA_HEALTH")).resolves.toMatchObject({ items: [{ payload: { metric: 1 } }] });
    // A wire mutation retaining the original fingerprint must fail closed.
    const drifted = createPlanningWorkspaceClient(runtime, { async getAccessToken() { return null; } },
      vi.fn(async () => new Response(raw.replace('"metric":1.0', '"metric":1'))) as typeof fetch);
    await expect(drifted.queryWorkspace(query, "DATA_HEALTH")).rejects.toMatchObject({ kind: "contract_error" });
  });

  it("rejects duplicate request keys before a Headless mutation is sent", async () => {
    const fetcher = vi.fn() as unknown as typeof fetch;
    const client = createHeadlessPlanningClient(p8Runtime, { async getAccessToken() { return null; } }, fetcher);
    const duplicate = p8CanonicalRequestText.replace("{", '{"operation":"SHADOW",');
    expect(() => parseCanonicalIngressRequestText(duplicate)).toThrow();
    await expect(client.create(duplicate)).rejects.toMatchObject({ kind: "contract_error" });
    expect(fetcher).not.toHaveBeenCalled();
    for (const raw of [p8CanonicalRequestText.replace("canonical-json.v1", "canonical-json.v2"), p8CanonicalRequestText.replace("{", '{"unknown":1,')]) {
      expect(() => parseCanonicalIngressRequestText(raw)).toThrow();
    }
  });

  it("preserves top-level float provenance in a dynamic replan projection", async () => {
    const query = await buildTimelineQuery(p4Runtime, p4Identity);
    const raw = canonicalJson({ ...await responseForQuery(query) }).replace('"from_position":1', '"from_position":1.0');
    const result = parseCanonicalJson(raw).result as JsonObject;
    const corrected = await sha256Fingerprint(canonicalProjection(result,
      Object.keys(result).filter((key) => key !== "projection_fingerprint")));
    const wire = raw.replace(String(result.projection_fingerprint), corrected);
    const client = createDynamicReplanningClient(p4Runtime, { async getAccessToken() { return null; } },
      vi.fn(async () => new Response(wire)) as typeof fetch);
    await expect(client.listExecutionEvents(query)).resolves.toMatchObject({ from_position: 1 });
    const duplicate = createDynamicReplanningClient(p4Runtime, { async getAccessToken() { return null; } },
      vi.fn(async () => new Response('{"result":null,"result":{}}')) as typeof fetch);
    await expect(duplicate.listExecutionEvents(query)).rejects.toMatchObject({ kind: "contract_error" });
  });

  it("rejects duplicate response keys in the Headless transport", async () => {
    const client = createHeadlessPlanningClient(p8Runtime, { async getAccessToken() { return null; } },
      vi.fn(async () => new Response('{"state":"FAILED","state":"COMPLETED"}')) as typeof fetch);
    await expect(client.status("run-p9", p8Scope, "correlation-p9")).rejects.toMatchObject({ kind: "contract_error" });
  });
});
