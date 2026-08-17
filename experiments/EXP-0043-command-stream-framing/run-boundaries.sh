#!/bin/sh
set -eu
EXPERIMENT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
RUN_SET=boundaries
export RUN_SET
exec "$EXPERIMENT_DIR/run.sh"
