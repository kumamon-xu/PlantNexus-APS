#!/bin/sh
set -eu
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec /bin/sh "$HERE/common.sh" start "$@"
