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

const version = "canonical-json.v1";
// JSON.parse erases the Python int/float distinction. Keep it on immutable
// parsed containers, never on a global numeric-value lookup (1 and 1.0 differ).
const numberForms = new WeakMap<object, ReadonlyMap<string, string>>();

function quoted(value: string): string {
  for (let index = 0; index < value.length; index += 1) {
    const point = value.charCodeAt(index);
    if (point >= 0xd800 && point <= 0xdbff) {
      const next = value.charCodeAt(++index);
      if (!(next >= 0xdc00 && next <= 0xdfff)) throw new TypeError("Unpaired surrogate");
    } else if (point >= 0xdc00 && point <= 0xdfff) {
      throw new TypeError("Unpaired surrogate");
    }
  }
  return JSON.stringify(value);
}

// Python binary64 repr: shortest round-tripping decimal, closest to the exact
// binary value, ties to even. BigInt avoids a second floating-point rounding
// when choosing digits. Formatting thresholds are Python's, not ECMAScript's.
function pythonFloat(value: number): string {
  if (!Number.isFinite(value)) throw new TypeError(`${version} requires finite numbers`);
  if (value === 0) return Object.is(value, -0) ? "-0.0" : "0.0";
  const magnitude = Math.abs(value);
  const view = new DataView(new ArrayBuffer(8));
  view.setFloat64(0, magnitude);
  const bits = view.getBigUint64(0);
  const exponent = Number((bits >> 52n) & 0x7ffn);
  const mantissa = bits & ((1n << 52n) - 1n);
  const significand = exponent === 0 ? mantissa : mantissa + (1n << 52n);
  const power = exponent === 0 ? -1074 : exponent - 1075;
  const numerator = power >= 0 ? significand << BigInt(power) : significand;
  const denominator = power < 0 ? 1n << BigInt(-power) : 1n;
  const decimalExponent = Number(magnitude.toExponential().split("e")[1]);
  for (let digits = 1; digits <= 17; digits += 1) {
    const scale = decimalExponent - digits + 1;
    const top = scale < 0 ? numerator * 10n ** BigInt(-scale) : numerator;
    const bottom = scale > 0 ? denominator * 10n ** BigInt(scale) : denominator;
    const floor = top / bottom;
    // One of the two adjacent decimal values is the nearest representable
    // candidate at this precision. Search both for asymmetric binary intervals.
    const candidates = [floor, floor + 1n].filter(
      (candidate) => candidate > 0n && Number(`${candidate}e${scale}`) === magnitude,
    );
    candidates.sort((left, right) => {
      const distance = (candidate: bigint) => {
        const difference = candidate * bottom - top;
        return difference < 0n ? -difference : difference;
      };
      const delta = distance(left) - distance(right);
      return delta < 0n ? -1 : delta > 0n ? 1 : Number((left & 1n) - (right & 1n));
    });
    const selected = candidates[0];
    if (selected === undefined) continue;
    let text = selected.toString();
    const scientificExponent = text.length - 1 + scale;
    text = text.replace(/0+$/u, "");
    const sign = value < 0 ? "-" : "";
    if (scientificExponent < -4 || scientificExponent >= 16) {
      const fraction = text.length > 1 ? `.${text.slice(1)}` : "";
      const expSign = scientificExponent < 0 ? "-" : "+";
      return `${sign}${text[0]}${fraction}e${expSign}${Math.abs(scientificExponent).toString().padStart(2, "0")}`;
    }
    const point = scientificExponent + 1;
    if (point <= 0) return `${sign}0.${"0".repeat(-point)}${text}`;
    if (point >= text.length) return `${sign}${text}${"0".repeat(point - text.length)}.0`;
    return `${sign}${text.slice(0, point)}.${text.slice(point)}`;
  }
  throw new TypeError("Unable to represent binary64 number");
}

function nativeNumber(value: number): string {
  if (Object.is(value, -0) || !Number.isInteger(value)) return pythonFloat(value);
  if (!Number.isSafeInteger(value)) {
    throw new TypeError("Ambiguous JavaScript integer; use explicit canonical JSON text");
  }
  return String(value);
}

/** Strict v1 object parser. Does not coerce timestamps, null, versions or fields.
 * Integers outside the JS safe range are explicitly unsupported by this consumer;
 * Python's legacy arbitrary integers remain valid and are never rehashed here.
 */
export function parseCanonicalJson(raw: string, canonicalizationVersion = version): JsonObject {
  if (canonicalizationVersion !== version) throw new TypeError("Unsupported canonicalization version");
  let position = 0;
  const whitespace = () => {
    while (position < raw.length && /[ \t\n\r]/u.test(raw[position] as string)) position += 1;
  };
  const fail = (): never => { throw new TypeError("Invalid canonical JSON"); };
  const string = (): string => {
    const start = position++;
    while (position < raw.length) {
      const character = raw[position++];
      if (character === "\\") position += 1;
      else if (character === '"') {
        const result: unknown = JSON.parse(raw.slice(start, position));
        if (typeof result !== "string") return fail();
        quoted(result);
        return result;
      }
    }
    return fail();
  };
  const parse = (forms: Map<string, string>, key: string): JsonValue => {
    whitespace();
    const character = raw[position];
    if (character === '"') return string();
    if (character === "{" || character === "[") {
      const array = character === "[";
      const closing = array ? "]" : "}";
      const value: JsonObject | JsonValue[] = array ? [] : {};
      const ownForms = new Map<string, string>();
      position += 1;
      whitespace();
      if (raw[position] !== closing) {
        for (;;) {
          whitespace();
          let member = Array.isArray(value) ? String(value.length) : "";
          if (!array) {
            if (raw[position] !== '"') return fail();
            member = string();
            if (Object.hasOwn(value, member)) throw new TypeError("Duplicate JSON key");
            whitespace();
            if (raw[position++] !== ":") return fail();
          }
          const item = parse(ownForms, member);
          // defineProperty treats __proto__ as an ordinary JSON key.
          Object.defineProperty(value, member, { value: item, enumerable: true });
          whitespace();
          if (raw[position] !== ",") break;
          position += 1;
        }
      }
      if (raw[position++] !== closing) return fail();
      numberForms.set(value, ownForms);
      Object.freeze(value);
      return value;
    }
    for (const [literal, value] of [["true", true], ["false", false], ["null", null]] as const) {
      if (raw.startsWith(literal, position)) {
        position += literal.length;
        return value;
      }
    }
    const token = /^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?/u.exec(raw.slice(position))?.[0];
    if (token === undefined) return fail();
    position += token.length;
    let value = Number(token);
    if (!Number.isFinite(value)) throw new TypeError("Non-finite JSON number");
    if (/[.eE]/u.test(token)) forms.set(key, pythonFloat(value));
    else {
      if (!Number.isSafeInteger(value)) throw new TypeError("Integer outside JavaScript safe range");
      if (value === 0) value = 0; // Python int(-0) is 0, unlike float(-0.0).
      forms.set(key, String(value));
    }
    return value;
  };
  try {
    const result = parse(new Map(), "");
    whitespace();
    if (position !== raw.length || result === null || typeof result !== "object" || Array.isArray(result)) return fail();
    return result;
  } catch (error) {
    if (error instanceof TypeError) throw error;
    throw new TypeError("Invalid canonical JSON");
  }
}

export async function readCanonicalResponse(response: Response): Promise<JsonObject> {
  const bytes = await response.arrayBuffer();
  // Keep BOM visible to the JSON parser and reject malformed UTF-8 rather than
  // allowing Response.text()/json() to replace invalid bytes before hashing.
  return parseCanonicalJson(new TextDecoder("utf-8", { fatal: true, ignoreBOM: true }).decode(bytes));
}

/** Preserve primitive number provenance when selecting a fingerprint projection. */
export function canonicalProjection(document: JsonObject, fields: readonly string[]): JsonObject {
  const result: JsonObject = {};
  const forms = new Map<string, string>();
  for (const field of fields) {
    if (!Object.hasOwn(document, field)) throw new TypeError(`Fingerprint field is absent: ${field}`);
    Object.defineProperty(result, field, { value: document[field], enumerable: true });
    const form = numberForms.get(document)?.get(field);
    if (form !== undefined) forms.set(field, form);
  }
  numberForms.set(result, forms);
  return Object.freeze(result);
}

export function canonicalJson(value: JsonValue, canonicalizationVersion = version): string {
  if (canonicalizationVersion !== version) throw new TypeError("Unsupported canonicalization version");
  if (value === null || typeof value === "boolean") return JSON.stringify(value);
  if (typeof value === "string") return quoted(value);
  if (typeof value === "number") return nativeNumber(value);
  if (typeof value !== "object") throw new TypeError("Not a JSON value");
  const member = (key: string, item: JsonValue) => numberForms.get(value)?.get(key) ?? canonicalJson(item);
  if (Array.isArray(value)) {
    return `[${Array.from(value, (item, index) => member(String(index), item)).join(",")}]`;
  }
  const prototype: unknown = Object.getPrototypeOf(value);
  if (prototype !== Object.prototype && prototype !== null) throw new TypeError("Not a JSON object");
  return `{${Object.keys(value).sort(compareCodePoints)
    .map((field) => `${quoted(field)}:${member(field, value[field] as JsonValue)}`).join(",")}}`;
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
  if (document.canonicalization_version !== version) throw new TypeError("Unsupported canonicalization version");
  return sha256Fingerprint(canonicalProjection(document, commandFingerprintFields.filter(
    (field) => field !== "synthetic_provenance" || Object.hasOwn(document, field),
  )));
}

export async function workspaceQueryFingerprint(document: JsonObject): Promise<string> {
  if (document.canonicalization_version !== version) throw new TypeError("Unsupported canonicalization version");
  return sha256Fingerprint(canonicalProjection(document, queryFingerprintFields.filter(
    (field) => field !== "synthetic_provenance" || Object.hasOwn(document, field),
  )));
}
