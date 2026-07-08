#!/bin/sh
# Build on the A18 Pro device (Command Line Tools only). arm64e required so the
# DYLD_INSERT interposer arch matches macOS 26 Metal.
set -e
clang -arch arm64e -dynamiclib -o iotrace.dylib iotrace.c -framework IOKit -framework CoreFoundation
clang -arch arm64e -fobjc-arc -framework Metal -framework Foundation -o texprobe texprobe.m
echo "built: iotrace.dylib texprobe"
