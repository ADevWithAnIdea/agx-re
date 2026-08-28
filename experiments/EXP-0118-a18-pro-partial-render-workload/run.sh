#!/bin/sh
# SPDX-License-Identifier: MIT
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
mkdir -p "$root/build"

xcrun -sdk macosx metal -c "$root/partial_render.metal" \
    -o "$root/build/partial_render.air"
xcrun -sdk macosx metallib "$root/build/partial_render.air" \
    -o "$root/build/g17ppartial.metallib"
xcrun -sdk macosx clang -arch arm64 -fobjc-arc -Wall -Wextra -Werror \
    "$root/partial_render.m" -framework Foundation -framework Metal \
    -o "$root/build/partial_render"
codesign -f -s - "$root/build/partial_render"
shasum -a 256 "$root/build/partial_render" \
    "$root/build/g17ppartial.metallib"
