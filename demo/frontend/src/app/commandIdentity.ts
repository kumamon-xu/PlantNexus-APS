import type {
  BaselineActivationRequest,
  JobAccepted,
  UrgentOrderCommand,
} from "../api/types";

interface StorageLike {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

export interface StoredActivation {
  readonly idempotencyKey: string;
  readonly request: BaselineActivationRequest;
}

export interface StoredUrgentOrder {
  readonly idempotencyKey: string;
  readonly request: UrgentOrderCommand;
}

export type StoredPendingJob = Pick<
  JobAccepted,
  "job_id" | "job_kind" | "run_id"
>;

const memory = new Map<string, string>();

const memoryStorage: StorageLike = {
  getItem: (key) => memory.get(key) ?? null,
  setItem: (key, value) => memory.set(key, value),
  removeItem: (key) => memory.delete(key),
};

function browserStorage(): StorageLike {
  try {
    const storage = globalThis.localStorage;
    const probe = "plantnexus-demo-storage-probe";
    storage.setItem(probe, "1");
    storage.removeItem(probe);
    return storage;
  } catch {
    return memoryStorage;
  }
}

function newKey(kind: string): string {
  const suffix = globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`;
  return `demo-ui-${kind}-${suffix}`;
}

function isActivation(value: unknown): value is StoredActivation {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  const item = value as Record<string, unknown>;
  const request = item.request;
  if (
    typeof item.idempotencyKey !== "string" ||
    typeof request !== "object" ||
    request === null ||
    Array.isArray(request)
  ) {
    return false;
  }
  const command = request as Record<string, unknown>;
  return (
    command.command_version === "cnc-demo-baseline-activation.v1" &&
    typeof command.expected_run_id === "string" &&
    typeof command.schedule_version_id === "string" &&
    typeof command.content_fingerprint === "string" &&
    Number.isInteger(command.expected_state_revision) &&
    command.confirmation === "ACTIVATE_SIMULATION_BASELINE"
  );
}

function isUrgentOrder(value: unknown): value is StoredUrgentOrder {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  const item = value as Record<string, unknown>;
  const request = item.request;
  if (
    typeof item.idempotencyKey !== "string" ||
    item.idempotencyKey.length < 16 ||
    item.idempotencyKey.length > 128 ||
    typeof request !== "object" ||
    request === null ||
    Array.isArray(request)
  ) {
    return false;
  }
  const command = request as Record<string, unknown>;
  return (
    command.command_version === "cnc-demo-urgent-order-command.v1" &&
    typeof command.expected_run_id === "string" &&
    typeof command.expected_base_version_id === "string" &&
    typeof command.route_template_id === "string" &&
    Number.isInteger(command.quantity) &&
    Number(command.quantity) >= 1 &&
    Number(command.quantity) <= 50 &&
    typeof command.due_at_local === "string" &&
    ["NORMAL", "KEY", "URGENT"].includes(String(command.priority_class)) &&
    (command.note === null || typeof command.note === "string")
  );
}

function isPendingJob(value: unknown): value is StoredPendingJob {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return false;
  }
  const item = value as Record<string, unknown>;
  return (
    typeof item.job_id === "string" &&
    item.job_id.length > 0 &&
    ["RESET", "INITIAL_PLAN", "URGENT_REPLAN"].includes(
      String(item.job_kind),
    ) &&
    (item.run_id === null || typeof item.run_id === "string")
  );
}

export class CommandIdentityStore {
  constructor(private readonly storage: StorageLike = browserStorage()) {}

  getOrCreate(kind: string, scope: string): string {
    const storageKey = `plantnexus-demo:command:${kind}:${scope}`;
    const existing = this.storage.getItem(storageKey);
    if (existing !== null && existing.length >= 16 && existing.length <= 128) {
      return existing;
    }
    const created = newKey(kind);
    this.storage.setItem(storageKey, created);
    return created;
  }

  activation(versionId: string): StoredActivation | null {
    const value = this.storage.getItem(
      `plantnexus-demo:activation:${versionId}`,
    );
    if (value === null) return null;
    try {
      const parsed = JSON.parse(value) as unknown;
      return isActivation(parsed) ? parsed : null;
    } catch {
      return null;
    }
  }

  saveActivation(value: StoredActivation): void {
    this.storage.setItem(
      `plantnexus-demo:activation:${value.request.schedule_version_id}`,
      JSON.stringify(value),
    );
  }

  clearActivation(versionId: string): void {
    this.storage.removeItem(`plantnexus-demo:activation:${versionId}`);
  }

  urgentOrder(runId: string): StoredUrgentOrder | null {
    const value = this.storage.getItem(`plantnexus-demo:urgent:${runId}`);
    if (value === null) return null;
    try {
      const parsed = JSON.parse(value) as unknown;
      return isUrgentOrder(parsed) ? parsed : null;
    } catch {
      return null;
    }
  }

  saveUrgentOrder(value: StoredUrgentOrder): void {
    this.storage.setItem(
      `plantnexus-demo:urgent:${value.request.expected_run_id}`,
      JSON.stringify(value),
    );
  }

  clearUrgentOrder(runId: string): void {
    this.storage.removeItem(`plantnexus-demo:urgent:${runId}`);
  }

  pendingJob(): StoredPendingJob | null {
    const storageKey = "plantnexus-demo:pending-job";
    const value = this.storage.getItem(storageKey);
    if (value === null) return null;
    try {
      const parsed = JSON.parse(value) as unknown;
      if (isPendingJob(parsed)) return parsed;
    } catch {
      // Invalid browser state is discarded below instead of being trusted.
    }
    this.storage.removeItem(storageKey);
    return null;
  }

  savePendingJob(value: StoredPendingJob): void {
    this.storage.setItem(
      "plantnexus-demo:pending-job",
      JSON.stringify({
        job_id: value.job_id,
        job_kind: value.job_kind,
        run_id: value.run_id,
      }),
    );
  }

  clearPendingJob(expectedJobId?: string): void {
    if (expectedJobId !== undefined) {
      const current = this.pendingJob();
      if (current !== null && current.job_id !== expectedJobId) return;
    }
    this.storage.removeItem("plantnexus-demo:pending-job");
  }
}

export function createMemoryCommandIdentityStore(): CommandIdentityStore {
  const values = new Map<string, string>();
  return new CommandIdentityStore({
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: (key) => values.delete(key),
  });
}
