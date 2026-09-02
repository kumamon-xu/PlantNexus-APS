"""Start the standalone CNC Demo on loopback only."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


DEMO_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = DEMO_ROOT.parent
sys.path.insert(0, str(REPOSITORY_ROOT / "backend"))
sys.path.insert(0, str(DEMO_ROOT / "backend"))

import uvicorn  # noqa: E402

from plantnexus_demo.composition import create_demo_app  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    arguments = parser.parse_args()
    if not 1 <= arguments.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    application = create_demo_app(
        repository_root=REPOSITORY_ROOT,
        runtime_root=DEMO_ROOT / "runtime",
    )
    uvicorn.run(
        application,
        host="127.0.0.1",
        port=arguments.port,
        log_level="info",
        access_log=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
