#!/bin/sh
set -eu

expected_sha=69fe416b7294dfec4794217bd11379effd53caff4e86010bb803f1b34bdf5e89
url=https://gitlab.freedesktop.org/mesa/mesa/-/raw/3c4d3e46d19f2f4e951f3ae059543b03592f7944/include/drm-uapi/asahi_drm.h
experiment_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
scratch_dir=$(mktemp -d "${TMPDIR:-/tmp}/agx-uapi-matrix.XXXXXX")
trap 'rm -rf "$scratch_dir"' EXIT HUP INT TERM

curl --fail --location --silent --show-error "$url" --output "$scratch_dir/asahi_drm.h"
actual_sha=$(shasum -a 256 "$scratch_dir/asahi_drm.h" | cut -d ' ' -f 1)
test "$actual_sha" = "$expected_sha"

python3 "$experiment_dir/analysis/verify_matrix.py" \
  "$scratch_dir/asahi_drm.h" \
  "$experiment_dir/raw/expected-fields.txt" \
  "$experiment_dir/field-matrix.tsv" \
  "$experiment_dir/manifest.json"
