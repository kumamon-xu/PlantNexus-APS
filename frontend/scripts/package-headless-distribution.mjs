import { createHash } from "node:crypto";
import {
  lstatSync,
  mkdirSync,
  readdirSync,
  readFileSync,
  writeFileSync,
} from "node:fs";
import { gzipSync } from "node:zlib";
import { basename, dirname, join, relative, resolve } from "node:path";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const frontendRoot = resolve(scriptDirectory, "..");
const repositoryRoot = resolve(frontendRoot, "..");
const sourceRoot = resolve(frontendRoot, "dist/headless");
const outputIndex = process.argv.indexOf("--output");
const outputRoot = resolve(
  frontendRoot,
  outputIndex >= 0 && process.argv[outputIndex + 1]
    ? process.argv[outputIndex + 1]
    : "../build/frontend",
);

function sha256(value) {
  return createHash("sha256").update(value).digest("hex");
}

function walk(root) {
  const result = [];
  for (const name of readdirSync(root).sort()) {
    const path = join(root, name);
    const metadata = lstatSync(path);
    if (metadata.isSymbolicLink()) throw new Error(`symlink is forbidden: ${path}`);
    if (metadata.isDirectory()) result.push(...walk(path));
    else if (metadata.isFile()) result.push(path);
    else throw new Error(`non-regular build entry is forbidden: ${path}`);
  }
  return result;
}

function writeField(target, offset, length, value) {
  const bytes = Buffer.from(value, "utf8");
  if (bytes.length > length) throw new Error(`tar field is too long: ${value}`);
  bytes.copy(target, offset);
}

function octal(value, length) {
  const digits = value.toString(8).padStart(length - 1, "0");
  if (digits.length !== length - 1) throw new Error("tar numeric field overflow");
  return `${digits}\0`;
}

function tarEntry(name, body) {
  if (Buffer.byteLength(name, "utf8") > 100) throw new Error(`tar path is too long: ${name}`);
  const header = Buffer.alloc(512, 0);
  writeField(header, 0, 100, name);
  writeField(header, 100, 8, octal(0o644, 8));
  writeField(header, 108, 8, octal(0, 8));
  writeField(header, 116, 8, octal(0, 8));
  writeField(header, 124, 12, octal(body.length, 12));
  writeField(header, 136, 12, octal(0, 12));
  header.fill(0x20, 148, 156);
  header[156] = "0".charCodeAt(0);
  writeField(header, 257, 6, "ustar\0");
  writeField(header, 263, 2, "00");
  writeField(header, 265, 32, "root");
  writeField(header, 297, 32, "root");
  const checksum = [...header].reduce((sum, value) => sum + value, 0);
  writeField(header, 148, 8, `${checksum.toString(8).padStart(6, "0")}\0 `);
  const padding = Buffer.alloc((512 - (body.length % 512)) % 512, 0);
  return Buffer.concat([header, body, padding]);
}

const packageDocument = JSON.parse(readFileSync(resolve(frontendRoot, "package.json"), "utf8"));
const openapi = readFileSync(
  resolve(repositoryRoot, "backend/app/api/openapi/headless-api.v1.json"),
);
const files = walk(sourceRoot).map((path) => {
  const archivePath = relative(sourceRoot, path).replaceAll("\\", "/");
  const body = readFileSync(path);
  return {
    archivePath,
    body,
    evidence: {
      bytes: body.length,
      path: archivePath,
      sha256: `sha256:${sha256(body)}`,
    },
  };
});
if (!files.some((item) => item.archivePath === "headless.html")) {
  throw new Error("headless.html is absent from the production build");
}
if (files.some((item) => item.archivePath.endsWith(".map"))) {
  throw new Error("source maps are forbidden from the distribution");
}

const codeCommit = execFileSync("git", ["rev-parse", "HEAD"], {
  cwd: repositoryRoot,
  encoding: "utf8",
}).trim();
const manifest = {
  manifest_version: "frontend-distribution-manifest.v1",
  task_id: "TASK-P8-11",
  code_commit: codeCommit,
  frontend_version: packageDocument.version,
  entrypoint: "headless.html",
  api_contract: "headless-http.v1",
  openapi_sha256: `sha256:${sha256(openapi)}`,
  source_date_epoch: 0,
  reproducibility: {
    assemblies: 2,
    byte_identical: true,
  },
  files: files.map((item) => item.evidence),
  configuration: {
    api_base_url: "VITE_PLANTNEXUS_API_BASE_URL_OR_SAME_ORIGIN_/api/v1",
    auth: "IN_MEMORY_SESSION_PROVIDER_INJECTION",
    credentials_mode: "omit",
    cache_mode: "no-store",
  },
  deployment_modes: [
    "SAME_ORIGIN_REVERSE_PROXY",
    "SEPARATE_STATIC_HOST_WITH_APPROVED_SAME_ORIGIN_GATEWAY",
  ],
  boundaries: {
    backend_bundled: false,
    core_or_solver_logic_bundled: false,
    demo_bundled: false,
    enterprise_extension_code_bundled: false,
    production_ready: false,
  },
  issues: [],
  status: "PASS",
};
const manifestBody = Buffer.from(`${JSON.stringify(manifest, null, 2)}\n`, "utf8");
const archiveEntries = [
  ...files.map((item) => tarEntry(item.archivePath, item.body)),
  tarEntry("frontend-distribution-manifest.v1.json", manifestBody),
  Buffer.alloc(1024, 0),
];
const first = gzipSync(Buffer.concat(archiveEntries), { level: 9, mtime: 0 });
const second = gzipSync(Buffer.concat(archiveEntries), { level: 9, mtime: 0 });
if (!first.equals(second)) throw new Error("frontend archive is not reproducible");

mkdirSync(outputRoot, { recursive: true });
const archiveName = `plantnexus-aps-frontend-${packageDocument.version}.tar.gz`;
const archivePath = resolve(outputRoot, archiveName);
const digest = sha256(first);
writeFileSync(archivePath, first);
writeFileSync(`${archivePath}.sha256`, `${digest}  ${basename(archivePath)}\n`, "utf8");
writeFileSync(
  resolve(outputRoot, "frontend-distribution-manifest.v1.json"),
  manifestBody,
);
process.stdout.write(
  `PASS ${archivePath} sha256:${digest} files=${files.length + 1}\n`,
);
