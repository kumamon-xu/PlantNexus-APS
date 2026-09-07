import canonicalIngressRequest from "../../schemas/samples/canonical-ingress-request.v1.synthetic.json";
import canonicalIngressAccepted from "../../schemas/samples/canonical-ingress-result.v1.accepted.synthetic.json";
import planningRunCompleted from "../../schemas/samples/planning-run.v1.completed.synthetic.json";
import planningRunCreated from "../../schemas/samples/planning-run.v1.created.synthetic.json";

import type { RuntimeConfig } from "../src/api/runtime";
import type { EffectiveScope } from "../src/headless/types";

export function cloneFixture<T>(value: T): T {
  return structuredClone(value);
}

export const p8CanonicalRequest = canonicalIngressRequest;
export const p8CanonicalRequestText = `${JSON.stringify(canonicalIngressRequest, null, 2)}\n`;
export const p8AcceptedResult = canonicalIngressAccepted;
export const p8CreatedRun = planningRunCreated;
export const p8CompletedRun = planningRunCompleted;

export const p8Runtime: RuntimeConfig = {
  apiBaseUrl: "/api/v1",
  dataPlane: "SIMULATION",
  environment: "TEST",
  synthetic: true,
};

export const p8Scope = canonicalIngressAccepted.effective_scope as EffectiveScope;

export function jsonResponse(
  payload: unknown,
  status: number,
  correlationId: string,
): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "Cache-Control": "no-store",
      "Content-Type": "application/json",
      "X-Correlation-Id": correlationId,
    },
  });
}
