"""Demo-local pytest path setup; the repository packages remain unmodified."""

from __future__ import annotations

from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEMO_ROOT = REPOSITORY_ROOT / "demo"
sys.path.insert(0, str(REPOSITORY_ROOT / "backend"))
sys.path.insert(0, str(DEMO_ROOT / "backend"))
