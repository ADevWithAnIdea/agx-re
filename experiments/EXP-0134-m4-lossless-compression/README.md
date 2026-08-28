# EXP-0134 — M4 lossless compression (DRV-P2-01)

**Pushes the 8×4 lossless-compression codec as far as black-box probing allows** on the
local Apple M4 (G16G): eligibility (usage/dims/storage/type), aux geometry (the
`numTexels/32` formula, the MSAA ratio, finite-resource allocation floors), state-byte ↔
data-pattern correlation, CPU access (`replaceRegion:`/`getBytes:`/blit) and render-target
(PBE) interaction, and the row's own escape-clause question ("can compression stay
disabled"). Extends — does not redo — EXP-0017 (A18 first pass) and EXP-M4-07 (M4 tiling
coverage, `docs/tiling/README.md` §4).

## Question

`APPLE9_RE_IMPLEMENTATION_GAPS.md` DRV-P2-01: "Decode the 8x4 codec, exact state meanings,
MSAA auxiliary ratio, eligibility, placement, size, CPU access, and interaction with PBE.
It may remain disabled if every correctness path can do so." Full falsifiable hypotheses:
`PRE_REGISTRATION.md` (H-E1..H-E5, H-A1..H-A5, H-S1..H-S4, H-C1..H-C5).

**Clean-room boundary (read first):** we document the state **encoding** and **geometry**,
never the compressed-block **bitstream** — see PRE_REGISTRATION.md's "Clean-room boundary"
section for exactly where this experiment stops and why.

## Method

Public Metal API (`newLibraryWithSource:` runtime MSL compilation, `replaceRegion:`,
`getBytes:`, blit encoder) + HW-PROBE (known patterns in, hardware behavior out) +
DATA-TRACE (our own process's GPU buffer objects, captured by the **read-only, unmodified**
`tools/iotrace` interposer). One ObjC harness binary, `harness/cprobe.m` (kinds `probe` and
`replicate`), one case per process. Every compression-candidate texture is written **only
via the render pipeline** (never `access::write`/ShaderWrite image-store, since ShaderWrite
itself disables compression). `harness/auxdecode.py` locates the 32-byte sampled texture
descriptor in an iotrace dump (generalizing EXP-0017's `twiddle.py` / EXP-M4-07's
`solve3d.py` — our own prior authored technique) and decodes the compression flags +
secondary VA + measured aux bytes. `harness/casematrix.py` freezes an 83-case matrix across
4 families (`elig`/`aux`/`state`/`cpu`). `harness/run.py` drives one subprocess per case
under a hard timeout; `harness/verify.py` implements the five standing gates.

## Reproduction

```sh
# Build (device, Command Line Tools only).
clang -dynamiclib -o work/iotrace.dylib ../../tools/iotrace/iotrace.c -framework IOKit -framework CoreFoundation
clang -fobjc-arc -framework Metal -framework Foundation -o work/bin/cprobe harness/cprobe.m

# Standing gates.
python3 harness/verify.py --selftest
python3 harness/verify.py --seqtest

# Inspect the frozen matrix.
python3 harness/run.py --list

# One official capture run (writes raw/<run_id>/; refuses to overwrite an existing dir).
python3 harness/run.py --run <run_id> --out raw/<run_id>

# Cross-run gate (after two runs exist).
python3 harness/verify.py --captured m4_20260828_run01 m4_20260828_run02
```

## Files

```text
PRE_REGISTRATION.md      hypotheses H-E1..H-C5, clean-room boundary, frozen before official runs
CAPTURE_CONTRACT.json    frozen authored-file hashes, pinned revision, gate descriptions
PROGRESS.md              milestone log incl. the shared-heap and aux-floor discoveries
RESULTS.md               OBSERVED vs INTERPRETED, eligibility matrix, aux geometry,
                          state-correlation table, CPU/PBE findings, escape-clause verdict
manifest.json            experiment metadata
harness/
  cprobe.m               the probe binary (STATUS/CONFIG/*_OK/DEVICE stdout protocol)
  auxdecode.py            descriptor + compression-aux decoder (host-side)
  casematrix.py           the frozen 83-case matrix + nondeterministic_observed_keys()
  schema.py               gated/nongated record schema (gate (d) realized structurally)
  run.py                  driver: one subprocess per case, smoke gate, append+fflush, decode
  verify.py               the five standing gates
fixtures/
  recorded_reality.json   5 real M4 captures backing verify.py --selftest (gate (e))
work/
  bin/cprobe, iotrace.dylib   built binaries (rebuild from harness/*.m + tools/iotrace/iotrace.c)
  dumps/<run_id>/<case_id>/  per-case iotrace BO dumps (large; not all committed, see .gitignore)
raw/
  m4_20260828_run01/     official capture 1 (00_inputs/02_gated/03_nongated/04_manifest)
  m4_20260828_run02/     official capture 2 (same shape)
  state_and_cpu_aux_excerpts.txt   full aux byte arrays behind §3/§4's findings
  DUMPS_MANIFEST.md      retention/reproduction note for the ~2.3GiB work/dumps/ tree
                          (too large to commit; kept on-host only, per CODEX's
                          oversized-raw-artifact rule)
.gitignore               work/ (scratch: built binaries, per-case iotrace BO dumps)
```

## Clean-room provenance

See `RESULTS.md`'s attestation block. Summary: `HW-PROBE + OWN-SHADER + DATA-TRACE`. No
Apple binary was introspected anywhere in this experiment; `tools/iotrace/iotrace.c` was
used strictly read-only (built unmodified into `work/iotrace.dylib`).
