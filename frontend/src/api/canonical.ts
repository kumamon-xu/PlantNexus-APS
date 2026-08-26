import type { JsonObject, JsonValue } from "./types";

const queryFingerprintFields = [
  "workspace_query_version",
  "schema_set_version",
  "canonicalization_version",
  "query_kind",
  "data_plane",
  "environment",
  "synthetic",
  "synthetic_provenance",
  "resource",
  "view",
  "schedule_version_precondition",
  "sort",
  "filters",
  "page",
] as const;

const commandFingerprintFields = [
  "workspace_command_version",
  "schema_set_version",
  "canonicalization_version",
  "command_type",
  "source_id",
  "expected_state",
  "expected_content_fingerprint",
  "data_plane",
  "environment",
  "synthetic",
  "synthetic_provenance",
  "target",
  "reason",
  "payload",
] as const;

function compareCodePoints(left: string, right: string): number {
  const leftPoints = Array.from(left, (value) => value.codePointAt(0) ?? 0);
  const rightPoints = Array.from(right, (value) => value.codePointAt(0) ?? 0);
  const length = Math.min(leftPoints.length, rightPoints.length);
  for (let index = 0; index < length; index += 1) {
    const difference = (leftPoints[index] ?? 0) - (rightPoints[index] ?? 0);
    if (difference !== 0) return difference;
  }
  return leftPoints.length - rightPoints.length;
}

export function canonicalJson(value: JsonValue): string {
  if (value === null || typeof value === "boolean" || typeof value === "string") {
    return JSON.stringify(value);
  }
  if (typeof value === "number") {
    if (!Number.isFinite(value)) {
      throw new TypeError("canonical-json.v1 accepts only finite numbers");
    }
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) {
    return `[${value.map(canonicalJson).join(",")}]`;
  }
  const fields = Object.keys(value).sort(compareCodePoints);
  return `{${fields
    .map((field) => `${JSON.stringify(field)}:${canonicalJson(value[field] as JsonValue)}`)
    .join(",")}}`;
}

export async function sha256Fingerprint(value: JsonObject): Promise<string> {
  const bytes = new TextEncoder().encode(canonicalJson(value));
  return sha256BytesFingerprint(bytes);
}

export async function sha256BytesFingerprint(
  value: ArrayBuffer | Uint8Array,
): Promise<string> {
  const bytes =
    value instanceof Uint8Array ? Uint8Array.from(value) : new Uint8Array(value.slice(0));
  const digest = await globalThis.crypto.subtle.digest("SHA-256", bytes.buffer);
  const hex = Array.from(new Uint8Array(digest), (byte) =>
    byte.toString(16).padStart(2, "0"),
  ).join("");
  return `sha256:${hex}`;
}

export async function workspaceCommandFingerprint(
  document: JsonObject,
): Promise<string> {
  const projection: JsonObject = {};
  for (const field of commandFingerprintFields) {
    if (field === "synthetic_provenance" && !(field in document)) continue;
    const value = document[field];
    if (value === undefined) {
      throw new TypeError(`command fingerprint field is absent: ${field}`);
    }
    projection[field] = value;
  }
  return sha256Fingerprint(projection);
}

export async function workspaceQueryFingerprint(
  document: JsonObject,
): Promise<string> {
  const projection: JsonObject = {};
  for (const field of queryFingerprintFields) {
    if (field === "synthetic_provenance" && !(field in document)) {
      continue;
    }
    const value = document[field];
    if (value === undefined) {
      throw new TypeError(`query fingerprint field is absent: ${field}`);
    }
    projection[field] = value;
  }
  return sha256Fingerprint(projection);
}
