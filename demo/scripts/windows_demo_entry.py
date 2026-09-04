"""PyInstaller/source entry point for the Windows CNC Demo package."""

from __future__ import annotations

from pathlib import Path
import sys


if not getattr(sys, "frozen", False):
    DEMO_ROOT = Path(__file__).resolve().parents[1]
    REPOSITORY_ROOT = DEMO_ROOT.parent
    sys.path.insert(0, str(REPOSITORY_ROOT / "backend"))
    sys.path.insert(0, str(DEMO_ROOT / "backend"))

from plantnexus_demo.windows_launcher import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
