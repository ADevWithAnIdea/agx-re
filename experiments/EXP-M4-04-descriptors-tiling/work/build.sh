#!/bin/sh
# Build all harnesses + the iotrace interposer LOCALLY on the M4 (arm64e required so the
# DYLD_INSERT interposer arch matches macOS 26 Metal). Command Line Tools only.
set -e
clang -arch arm64e -dynamiclib -o iotrace.dylib iotrace.c -framework IOKit -framework CoreFoundation
for m in iohello_compute texprobe tvar svar pfv; do
  clang -arch arm64e -fobjc-arc -framework Metal -framework Foundation -o $m $m.m
done
echo "built: iotrace.dylib iohello_compute texprobe tvar svar pfv"
