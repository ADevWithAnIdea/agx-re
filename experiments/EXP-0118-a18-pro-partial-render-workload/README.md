# EXP-0118: A18 Pro partial-render workload

- **Date:** 2026-08-28
- **Clean-room category:** OWN-SHADER / HW-PROBE
- **Phase / question:** Generate a deterministic Metal render whose tile-memory pressure forces partial rendering.
- **Device state:** Tested with Apple M4 and A18 Pro-class G17P hardware.

## Hypothesis

A sufficiently large number of concentrated triangles, eight color attachments, and additive blending exhausts the tile-side parameter storage and forces the GPU to split one logical render into partial-render segments.

## Method

`partial_render.m` and `partial_render.metal` are project-authored sources. The workload draws 48,217 concentrated triangles into eight 128×128 R32F attachments. Every triangle adds a known fraction, so successful framebuffer reloads converge to approximately 1 through 8. A broken reload retains only the final segment and produces much smaller values.

## Procedure

```sh
./run.sh
./build/partial_render 128 128 accumulate 48217 1
```

To exercise multiple Metal command queues:

```sh
env G17P_ENQUEUE_ALL=1 G17P_COMMAND_QUEUE_COUNT=2 \
  ./build/partial_render 128 128 accumulate 48217 2
```

The executable prints the maximum value in each attachment and an `exact=1` semantic result. Small floating-point error is expected because the additions are performed in different segment groupings.

## Raw results

This source-only copy intentionally contains no GPU captures or compiled Apple artifacts.

## Analysis

The workload is both a partial-render trigger and a semantic oracle: command retirement alone is insufficient, while the eight accumulated outputs directly test whether tile contents were reloaded between partial segments.

## Established facts → docs

- Eight-attachment additive accumulation detects partial-render reload failures.
- 48,217 concentrated triangles reliably triggers the path on the tested G17P hardware.

## Follow-ups

Use the workload as the first application render in a single-user guest, capture the pre-kick UAT state, allow the original kick to execute, and replay the captured state after a clean reboot.
