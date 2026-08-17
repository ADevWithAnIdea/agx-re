#!/bin/sh
set -eu

experiment_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
scratch_dir=$(mktemp -d "${TMPDIR:-/tmp}/agx-isa-audit.XXXXXX")
trap 'rm -rf "$scratch_dir"' EXIT HUP INT TERM

python3 "$experiment_dir/analysis/audit_synthesis.py" > "$scratch_dir/audit.json"
diff -u "$experiment_dir/raw/audit.json" "$scratch_dir/audit.json"
echo "PASS: ISA synthesis audit reproduces exactly"
