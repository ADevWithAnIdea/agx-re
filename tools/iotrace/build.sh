#!/bin/sh
# Build the iotrace interposer + minimal Metal harnesses on the A18 device.
# Command Line Tools only (no `metal` CLI needed).
set -e
clang -dynamiclib -o iotrace.dylib iotrace.c -framework IOKit -framework CoreFoundation
clang -fobjc-arc -framework Metal -framework Foundation -o iohello_compute iohello_compute.m
clang -fobjc-arc -framework Metal -framework Foundation -o iohello_draw    iohello_draw.m
echo "built: iotrace.dylib iohello_compute iohello_draw"
