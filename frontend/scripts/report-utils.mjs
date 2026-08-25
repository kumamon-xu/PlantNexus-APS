import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";

export function argument(name) {
  const index = process.argv.indexOf(name);
  if (index < 0 || process.argv[index + 1] === undefined) {
    throw new Error(`missing required argument ${name}`);
  }
  return process.argv[index + 1];
}

export function codeCommit() {
  const value = process.env.PLANTNEXUS_CODE_COMMIT;
  return value && /^[0-9a-f]{40}$/.test(value) ? value : "uncommitted";
}

export function writeReport(path, report) {
  const target = resolve(process.cwd(), path);
  mkdirSync(dirname(target), { recursive: true });
  writeFileSync(target, `${JSON.stringify(report, null, 2)}\n`, "utf8");
  return target;
}

export function completedCheck(id, detail) {
  return { id, status: "PASS", detail };
}
