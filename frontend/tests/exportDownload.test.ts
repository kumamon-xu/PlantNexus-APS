import { sha256BytesFingerprint } from "../src/api/canonical";
import {
  createPlanningWorkspaceClient,
  WorkspaceClientError,
} from "../src/api/client";
import type { RuntimeConfig } from "../src/api/runtime";

const runtime: RuntimeConfig = {
  apiBaseUrl: "https://aps.test/api/v1",
  dataPlane: "SIMULATION",
  environment: "TEST",
  synthetic: true,
};
const exportJobId = `export-job-${"1".repeat(64)}`;
const packageId = `export-package-${"2".repeat(64)}`;
const manifestFingerprint = `sha256:${"3".repeat(64)}`;

async function downloadResponse(
  init: RequestInit | undefined,
  overrides: Record<string, string> = {},
  bytes = new TextEncoder().encode("verified deterministic zip fixture"),
) {
  const requestHeaders = new Headers(init?.headers);
  const archiveFingerprint = await sha256BytesFingerprint(bytes);
  return new Response(bytes, {
    status: 200,
    headers: {
      "Content-Type": "application/zip",
      "Content-Length": String(bytes.byteLength),
      "Content-Disposition": `attachment; filename="${packageId}.zip"`,
      "X-PlantNexus-Package-Id": packageId,
      "X-PlantNexus-Manifest-Fingerprint": manifestFingerprint,
      "X-PlantNexus-Archive-Fingerprint": archiveFingerprint,
      "X-PlantNexus-Completion-Audit-Event-Id": "audit-export-completed-001",
      "X-Correlation-Id": requestHeaders.get("X-Correlation-Id") ?? "missing",
      ...overrides,
    },
  });
}

describe("verified export package client", () => {
  it("binds the binary response, hashes bytes, and never persists credentials", async () => {
    let capturedInput: RequestInfo | URL | undefined;
    let capturedInit: RequestInit | undefined;
    const client = createPlanningWorkspaceClient(
      runtime,
      { async getAccessToken() { return "ephemeral-export-token"; } },
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        capturedInput = input;
        capturedInit = init;
        return downloadResponse(init);
      }) as typeof fetch,
    );
    const result = await client.downloadExportPackage(exportJobId);
    expect(String(capturedInput)).toBe(
      `https://aps.test/api/v1/export-jobs/${exportJobId}/download`,
    );
    expect(capturedInit?.credentials).toBe("omit");
    expect(new Headers(capturedInit?.headers).get("Authorization")).toBe(
      "Bearer ephemeral-export-token",
    );
    expect(result).toMatchObject({ packageId, manifestFingerprint });
    expect(result.blob.type).toBe("application/zip");
  });

  it.each([
    ["X-PlantNexus-Package-Id", `export-package-${"4".repeat(64)}`],
    ["X-PlantNexus-Manifest-Fingerprint", "invalid"],
    ["X-Correlation-Id", "correlation-wrong"],
    ["Content-Type", "application/json"],
  ])("rejects drift in %s", async (header, value) => {
    const client = createPlanningWorkspaceClient(
      runtime,
      { async getAccessToken() { return null; } },
      vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) =>
        downloadResponse(init, { [header]: value }),
      ) as typeof fetch,
    );
    await expect(client.downloadExportPackage(exportJobId)).rejects.toBeInstanceOf(
      WorkspaceClientError,
    );
  });

  it("rejects archive-byte tampering against the advertised fingerprint", async () => {
    const client = createPlanningWorkspaceClient(
      runtime,
      { async getAccessToken() { return null; } },
      vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) =>
        downloadResponse(init, {
          "X-PlantNexus-Archive-Fingerprint": `sha256:${"f".repeat(64)}`,
        }),
      ) as typeof fetch,
    );
    await expect(client.downloadExportPackage(exportJobId)).rejects.toThrow(
      /archive fingerprint/u,
    );
  });
});
