# EXP-0136 — M4 Metal-unreachable descriptor/opcode encodings (DRV-P2-05)

**Date:** 2026-08-28 · **Target:** Apple M4 (G16G), local host only, macOS 26.6.2, Metal 4.
No A18 Pro claim anywhere (A18 hands-off per CLAUDE.md). **Clean-room category:**
HW-PROBE + DATA-TRACE + OWN-SHADER.

## Question

`APPLE9_RE_IMPLEMENTATION_GAPS.md` § DRV-P2-05 asks us to exhaust finite raw sampler/
address/swizzle/border/aniso descriptor values, arbitrary restart and raster modes, native
geometry-shader/stream-output paths, and other Metal-unreachable descriptor/opcode values
— with an explicit promotion rule: "unknown hard resource capacities must be promoted to
P0/P1 even if the performance model remains deferred." This experiment answers the
encoding-envelope half of that row (the performance-model half — occupancy, latency,
cache, tile/parameter-buffer sizing — is explicitly out of scope here).

## Method (full detail: `PRE_REGISTRATION.md`)

1. **Sampler/texture descriptor direct patch** (`harness/descpatch.m`): build a real
   `MTLSamplerState`/`MTLTexture` via the public API, encode one dispatch, then — using
   `tools/iotrace` (read-only, unmodified) purely as a DATA source to locate the live CPU
   address of Metal's own internal descriptor-pool bytes for that object (client GPU memory
   is regular userspace VM registered into the GPU VM, EXP-0009) — overwrite exactly one
   byte of the 8-byte sampler / 32-byte texture descriptor with a value Metal's public API
   can never produce, then commit and read back the result. Validated with a bit-exact
   positive control against a real API-generated encoding (PRE_REGISTRATION.md §2).
2. **Restart/raster** (`harness/gfxprobe.m`): pure public-API probes — no memory patching
   needed since every input (index-buffer bytes, `rasterizationEnabled`) is directly
   settable.
3. **Opcode space** (`tools/agxtest`, read-only): splice `reserved7`/`reserved13` modifier
   bytes of the well-characterized `device_load`/`device_store` instructions, and the
   inert-terminator `stop` word's byte0, in our own compiled copy kernel.

## Commands

```sh
python3 harness/verify.py --selftest && python3 harness/verify.py --seqtest
sh work/bin/build.sh   # or the individual clang lines in PRE_REGISTRATION.md §1
python3 harness/verify.py --preflight
python3 harness/run.py --run m4_20260828_run01 --out raw/m4_20260828_run01
python3 harness/verify.py --between-runs
python3 harness/run.py --run m4_20260828_run02 --out raw/m4_20260828_run02
python3 harness/verify.py --captured m4_20260828_run01 m4_20260828_run02
python3 analysis/summarize.py m4_20260828_run01
```

## Result

See `RESULTS.md`. Headline: sampler anisotropy is natively supported up to at least 128×
(4× Metal's 16× API cap) with a measured, monotonic filtering-quality effect; address-mode
codes 4/6/7 are exact, deterministic aliases (4→clampToEdge, 6/7→clampToBorder); border
code 3 aliases to preset 0 regardless of creation-time preset; texture swizzle codes 6/7
hard-fault the command buffer (GPU-hang class, auto-recovered); primitive restart is a
fixed all-ones sentinel, HW-VALIDATED; `rasterizationEnabled=NO` runs the vertex stage
with fragment output correctly suppressed, consistent with (not a distinct hardware path
from) the ordinary VDM/tiler pipeline; `device_load`/`device_store` `reserved7`/
`reserved13` are confirmed inert padding.

## Clean-room provenance

```
Clean-room provenance: HW-PROBE + DATA-TRACE + OWN-SHADER
Inputs inspected: our own MSL (harness/*.m string templates + harness/kernels/add.metal),
  the public Metal API, tools/iotrace (read-only, unmodified, hash-checked) as a DATA
  source, tools/agxtest (read-only, unmodified, hash-checked).
Apple binary introspection: NONE.
Reproduction: see Commands above.
Evidence: raw/m4_20260828_run01/, raw/m4_20260828_run02/, work/spike/ (non-recorded
  method-validation spike), work/smoke/ (non-recorded smoke gate).
```
