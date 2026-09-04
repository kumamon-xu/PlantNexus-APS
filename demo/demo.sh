#!/usr/bin/env sh
set -eu

demo_root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repository_root=$(dirname -- "$demo_root")
cd "$repository_root"
if [ "$#" -eq 0 ]; then
  set -- start
fi
exec uv run python "$demo_root/scripts/democtl.py" "$@"
