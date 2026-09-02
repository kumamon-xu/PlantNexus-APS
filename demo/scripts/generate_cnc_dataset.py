"""Export one deterministic CNC demo batch at the Raw Staging boundary."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


DEMO_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = DEMO_ROOT.parent
sys.path.insert(0, str(REPOSITORY_ROOT / "backend"))
sys.path.insert(0, str(DEMO_ROOT / "backend"))

from plantnexus_demo.generator import DemoPackageGenerator, source_record_counts  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("smoke", "showcase", "upper"), default="showcase")
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    generated = DemoPackageGenerator().prepare_batch(arguments.profile)
    provenance = generated.batch.synthetic_provenance
    if provenance is None:
        raise RuntimeError("a Demo batch must retain synthetic provenance")
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_bytes(b"\n".join(row.raw_payload for row in generated.batch.rows) + b"\n")
    manifest_path = arguments.output.with_suffix(arguments.output.suffix + ".manifest.json")
    manifest = {
        "manifest_version": "cnc-demo-staged-batch-manifest.v1",
        "profile": arguments.profile,
        "assets_digest": generated.assets_digest,
        "batch_id": generated.batch.batch_id,
        "request_fingerprint": generated.batch.request_fingerprint,
        "content_sha256": generated.batch.content_sha256,
        "row_count": len(generated.batch.rows),
        "record_counts": source_record_counts(generated),
        "data_plane": generated.batch.data_plane.value,
        "synthetic_provenance": provenance.fingerprint_projection(),
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": "PASS", "dataset": str(arguments.output.resolve()), "manifest": str(manifest_path.resolve())}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
