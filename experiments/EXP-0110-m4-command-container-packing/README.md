# EXP-0110 -- M4 command-stream relocation, link/chain grammar, state-packet
# fields, and shader-container/metadata split (P0.5 + P0.7)

## Question

`docs/P0-P1-CLOSURE.md` rows P0.5 (`DRV-CMD-01`, relocatable VDM/CDM/PPP/USC
command and state packing) and P0.7 (`DRV-SHADER-01`, shader container /
metadata / resource-spec generation) are both stuck at partial, single-
capture evidence (EXP-0043, EXP-0049, EXP-0042). This experiment pushes both
as far as one experiment reasonably can:

1. **Relocation** -- which command-segment base addresses move under
   controlled allocator/queue perturbation, and by what transform.
2. **Link/chain grammar** -- does the previously-observed single link pair
   generalize to a formula that predicts new targets, and what is the exact
   per-segment record capacity?
3. **State-packet fields** -- does the A18-only VDM bind-pair/FF-state pool
   template (EXP-0019/EXP-0024) reproduce on M4, and can the bind-pair
   control-word "nibble" be tied to a target sub-block?
4. **Container/metadata (P0.7)** -- which `__GPU_METADATA` fields are
   firmware-consumed (reappear in the live command stream) vs Metal-archive
   bookkeeping (consumed only to build the archive/argument table)?

See `PRE_REGISTRATION.md` for the frozen hypotheses/falsifiers/variables and
`CAPTURE_CONTRACT.json` for the gate order and schema hashes.

## Clean-room category

`HW-PROBE` + `DATA-TRACE` + `OWN-SHADER`. Every shader dispatched is authored
MSL compiled at runtime through the public Metal API
(`harness/cmdprobe.m`'s embedded kernels; `kernels/gen_container_kernels.py`-
generated sources for the container sweep). The command/state-stream bytes
analyzed are DATA-TRACE captures of our own process's boundary traffic via
the unmodified, read-only `tools/iotrace` interposer. The shader container
bytes analyzed come from the unmodified, read-only `tools/shdump` +
`tools/shdump/agxparse.py`, run on archives WE compiled from OUR OWN MSL.
No Apple binary, framework, kernel, firmware, or Apple-authored shader is
inspected, disassembled, decompiled, or otherwise introspected.

## Method

- `harness/cmdprobe.m`: one Metal harness, two modes (`cdm`=compute,
  `vdm`=draw), with knobs for dispatch/draw count, prior-queue count
  (optionally each issuing its own draw), client padding count/size, and
  (vdm only) depth-test/stencil-test/blend/cull-mode toggles.
- `harness/containerdispatch.m`: dispatches an arbitrary authored `.metal`
  file/function with N bound buffers, for the P0.7 live cross-check.
- `analysis/scan.py`: locates our own authored CDM/VDM record signatures in
  a BO's bytes, follows the segment link chain from a uniquely-identified
  head, decodes the split-address link transform, and (for VDM) extracts
  the bind-pair table and clusters it to find the FF-state pool base.
- `analysis/metadata.py`: surveys `__GPU_METADATA` FlatBuffer fields from an
  archive `tools/shdump` produced (own authored code).
- `schema.py`: the one frozen GATED-record schema per case kind, with the
  delta-from-baseline / normalized-record design that keeps raw GPU
  addresses out of the cross-run-compared payload (see PRE_REGISTRATION.md
  "Confounders").
- `casematrix.py`: the frozen case list (imported by `run.py`/`verify.py`).
- `run.py`: capture driver -- builds the harnesses, runs the smoke gate,
  then every case in its own process with a hard timeout, appending+
  fsyncing each GATED record and its non-gated address sibling.
- `verify.py`: `--selftest`, `--seqtest`, `--preflight`, `--between-runs`,
  `--captured` gates (see PRE_REGISTRATION.md).

## Reproduction

```sh
cd experiments/EXP-0110-m4-command-container-packing
python3 verify.py --selftest && python3 verify.py --seqtest
python3 verify.py --preflight --run-id m4_20260827_run01
python3 run.py --run-id m4_20260827_run01 --execute
python3 verify.py --between-runs --run01-id m4_20260827_run01 --run02-id m4_20260827_run02
python3 run.py --run-id m4_20260827_run02 --execute
python3 verify.py --captured --run01-id m4_20260827_run01 --run02-id m4_20260827_run02
python3 analysis/report.py   # derives RESULTS.md's tables from raw/
```

All steps run on the local M4 only; no SSH; no A18/M5 contact.

## Layout

```
PRE_REGISTRATION.md, CAPTURE_CONTRACT.json  -- frozen contract
casematrix.py, schema.py                    -- frozen case list + record schema
harness/                                    -- authored Metal/ObjC probes
kernels/gen_container_kernels.py            -- authored MSL generator (P0.7 sweep)
analysis/scan.py, analysis/metadata.py      -- authored decoders (shared)
analysis/report.py                          -- derives RESULTS.md tables from raw/
run.py, verify.py                           -- capture driver + gates
raw/m4_20260827_run01/, raw/m4_20260827_run02/  -- two full captures
manifest.json, PROGRESS.md, RESULTS.md
```
