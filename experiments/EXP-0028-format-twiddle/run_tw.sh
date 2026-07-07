#!/bin/sh
# EXP-0028 part 2 — twiddle/layout probe for the untested texture TYPES.
# Writes a known (x,y,slice) pattern into each texture type, dumps raw backing
# bytes, and solves the byte->(x,y,slice) map. Text artifacts only.
# Clean-room: HW-PROBE + OWN-SHADER + DATA-TRACE.
set -u
cd "$(dirname "$0")"

echo "=== build ==="
clang -dynamiclib -o iotrace.dylib iotrace.c -framework IOKit -framework CoreFoundation || exit 1
clang -fobjc-arc -framework Metal -framework Foundation -o typrobe typrobe.m || exit 1
echo built

DYL=./iotrace.dylib
rm -rf tcaps tanalysis; mkdir -p tcaps tanalysis

cap() { # cap LABEL -- <typrobe args...>
  label="$1"; shift; [ "$1" = "--" ] && shift
  d="tcaps/$label"; rm -rf "$d"; mkdir -p "$d"
  IOTRACE_LOG="tcaps/$label.trace" IOTRACE_DUMP_DIR="$d" \
    DYLD_INSERT_LIBRARIES=$DYL ./typrobe "$@" --dump > "tcaps/$label.stdout" 2>&1 || true
  echo "  cap $label : $* -> $(grep -oE 'WRITE status=[0-9]+|MSRENDER status=[0-9]+|TEX_FAIL|COMPILE_FAIL|CUBE_VIEW_FAIL|RPIPE_FAIL' tcaps/$label.stdout | head -1)"
}

# 3D — 16x16x16 (rich bits to see 3D-Morton vs 2D-slices)
cap tw_3d_16 -- --type 3d --w 16 --h 16 --d 16
cap tw_3d_8  -- --type 3d --w 8  --h 8  --d 8
# 2DArray — 16x16 x 6 layers
cap tw_2darr -- --type 2darray --w 16 --h 16 --arraylen 6
# 1DArray — 16 x 6 layers
cap tw_1darr -- --type 1darray --w 16 --h 1 --arraylen 6
# Cube — 16x16 x 6 faces
cap tw_cube  -- --type cube --w 16 --h 16
# CubeArray — 16x16 x (6*2)
cap tw_cubearr -- --type cubearray --w 16 --h 16 --arraylen 2
# 2DMS — sample interleave (small target, many samples visible)
cap tw_ms4_8 -- --type 2dms --w 8 --h 8 --samples 4
cap tw_ms2_8 -- --type 2dms --w 8 --h 8 --samples 2

echo "=== solve ==="
{
  echo "########## 3D 16x16x16 ##########"; python3 tw3.py tcaps/tw_3d_16 --w 16 --h 16 --slices 16 --label tw_3d_16
  echo; echo "########## 3D 8x8x8 ##########"; python3 tw3.py tcaps/tw_3d_8 --w 8 --h 8 --slices 8 --label tw_3d_8
  echo; echo "########## 2DArray 16x16x6 ##########"; python3 tw3.py tcaps/tw_2darr --w 16 --h 16 --slices 6 --label tw_2darr
  echo; echo "########## 1DArray 16x6 ##########"; python3 tw3.py tcaps/tw_1darr --w 16 --h 1 --slices 6 --label tw_1darr
  echo; echo "########## Cube 16x16x6 ##########"; python3 tw3.py tcaps/tw_cube --w 16 --h 16 --slices 6 --label tw_cube
  echo; echo "########## CubeArray 16x16x12 ##########"; python3 tw3.py tcaps/tw_cubearr --w 16 --h 16 --slices 12 --label tw_cubearr
  echo; echo "########## 2DMS 8x8 s4 ##########"; python3 tw3.py tcaps/tw_ms4_8 --w 8 --h 8 --slices 4 --label tw_ms4_8
  echo; echo "########## 2DMS 8x8 s2 ##########"; python3 tw3.py tcaps/tw_ms2_8 --w 8 --h 8 --slices 2 --label tw_ms2_8
} > tanalysis/twiddle_solved.txt 2>&1
cat tanalysis/twiddle_solved.txt
echo "=== done run_tw ==="
