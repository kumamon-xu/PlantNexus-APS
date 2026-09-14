"""Run clean, offline enterprise candidate acceptance without a consumer checkout."""

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from infra.enterprise.acceptance.runner import execute  # noqa: E402


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--bundle-report", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    p.add_argument("--development", action="store_true")
    args = p.parse_args()
    try:
        execute(args.bundle_report, args.report, args.development)
        print("PASS clean offline acceptance")
        return 0
    except Exception as error:
        print(
            "FAIL " + str(error)
            if isinstance(error, ValueError)
            else "FAIL " + type(error).__name__
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
