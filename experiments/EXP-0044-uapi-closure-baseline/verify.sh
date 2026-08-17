#!/bin/sh
set -eu

uapi_url='https://gitlab.freedesktop.org/mesa/mesa/-/raw/3c4d3e46d19f2f4e951f3ae059543b03592f7944/include/drm-uapi/asahi_drm.h'
expected_sha='69fe416b7294dfec4794217bd11379effd53caff4e86010bb803f1b34bdf5e89'
work_dir=$(mktemp -d)
trap 'rm -rf "$work_dir"' EXIT HUP INT TERM
header_path="$work_dir/asahi_drm.h"

curl --fail --location --max-time 20 --silent --show-error "$uapi_url" > "$header_path"
actual_sha=$(shasum -a 256 "$header_path" | awk '{print $1}')
test "$actual_sha" = "$expected_sha"
printf 'sha256 %s\n' "$actual_sha"

awk '
  /struct drm_asahi_queue_create/ {show=1}
  /struct drm_asahi_queue_destroy/ {show=0}
  /enum drm_asahi_render_flags/ {show=1}
  /struct drm_asahi_timestamp/ {if (show) show=0}
  /struct drm_asahi_helper_program/ {show=1}
  /struct drm_asahi_get_time/ {if (show) show=0}
  show {print}
' "$header_path"

