# EXP-0005: Stand up the ISA database & characterize the float ALU family

- **Date:** 2026-07-06
- **Clean-room category:** OWN-SHADER + HW-PROBE (+ PUBLIC for the applegpu *shape*)
- **Phase / question:** Phase 1 — build the A18 instruction database; determine the
  instruction-length rule; hardware-validate the float ALU op map.
- **Device state:** Apple A18 Pro / G17P, SoC T8140, macOS 26.6 (25G5043d),
  Metal 4 / Apple9, CLT only. No boot-arg/nvram changes.

## Hypotheses
1. G17P instructions are built from 2-byte parcels; a length rule keyed on the
   leading bytes tokenizes a whole `_agc.main` cleanly (do **not** assume the G13
   first-parcel length bit).
2. The float 2-source ALU op-select validated in EXP-0003 (bit 0 of the byte at
   `_agc.main` offset `0x22`) is one bit of a **wider** op-select field.
3. A persistent runner can sweep a 256-value field in one process, surviving the
   contained ALU-op faults EXP-0003 observed.

## Method (all clean-room legal)
- **OWN-SHADER:** compile MSL **we wrote** (`kernels/*.metal`) with runtime
  `newLibraryWithSource:`, extract `_agc.main` with our own parser
  (`tools/shdump/agxparse.py`), and byte-diff / segment those bytes. No Apple
  binary is disassembled.
- **HW-PROBE:** splice bytes into our own compiled archive and run them on the
  real GPU via our own runner, reading back outputs (the EXP-0003 testbed method,
  itself the public MIT applegpu hwtestbed technique reimplemented as our tools).
- The instruction **database's shape** reuses the public applegpu design; its
  contents are ours, populated from our own hardware/byte evidence.

## Procedure
Tools built here / used:
- `tools/agx-isa/` — the DB (`isadb.py`), CLI (`agxisa.py`), round-trip test.
- `tools/agxtest/agxrun_persist.m` — **persistent runner** (one live `MTLDevice`,
  loops over `(spliced-archive, inputs) → outputs` requests on stdin, logs-and-
  continues past faults).
- `tools/agxtest/persistrun.py` — host/device driver with a per-request watchdog
  that restarts the child on a true wedge.
- `opsweep.py` (here) — the 256-value op-select sweep.

Reproduce on the device (`~/cleanroom_work/exp0005/`):
```sh
# build (CLT only)
clang -fobjc-arc -framework Metal -framework Foundation -o shdump shdump.m
clang -fobjc-arc -framework Metal -framework Foundation -o agxrun_persist agxrun_persist.m
# op-select sweep of the canonical  out[gid]=a[gid]+b[gid]  kernel
python3 opsweep.py --offset 0x22 --rebuild --timeout 6      # -> raw/opmap.txt
```
Length rule / round-trip (host, no device needed):
```sh
cd tools/agx-isa && python3 roundtrip_test.py               # ALL PASS
python3 agxisa.py tokenize <_agc.main hex>                  # CLEAN, 0 leftover
```

## Raw results
- `raw/opmap.txt` — every op-byte value 0x00..0xff → status + identified op.
- `raw/opsweep_0x22.log` — sweep run log (progress + summary).
- `raw/length_rule.txt` — clean tokenization of 7 real `_agc.main` programs.
- `raw/roundtrip.txt` — full round-trip test output (ALL PASS).
- `raw/kernel_main_hex.txt` — extracted `_agc.main` hex of the kernels used.

## Analysis
See `RESULTS.md`. Headlines:
- **Length rule** determined and proven to tokenize all our float shaders with
  zero leftover bytes; first parcel is **not** sufficient on G17P (fsub/fma
  counter-example).
- **Op-select field** = low 3 bits of byte `+2` (instruction bits [16:19]);
  `0b100`=fadd, `0b101`=fmul, both **HW-validated** by the full sweep.
- **Persistent runner works and survives contained faults** — 256 dispatches
  (incl. 32 GPU-hang faults) in **one process, zero reboots**.

## Established facts → docs (orchestrator applies)
- Instruction-length rule → `docs/isa/` + `PROVENANCE.md`.
- Float ALU op-select field (bits [16:19], fadd/fmul HW-validated) → `docs/isa/`.
- DB schema + seeded table → `tools/agx-isa/`.

## Follow-ups
- Register/operand field bit-layout (dst/srcA/srcB widths) — next priority.
- Integer ALU family (byte0 `0x9f`) length + op map.
- 3-source / fma field decode; the `srcmode` (byte+2 bits 6-7) passthrough mode.
- Float immediate (packed, non-IEEE) encoding; source modifiers (neg/abs) width.
