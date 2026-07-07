# EXP-0012: memory access family (device / threadgroup / constant)

- **Date:** 2026-07-06
- **Clean-room category:** OWN-SHADER + HW-PROBE (+ PUBLIC for the applegpu *shape*)
- **Phase / question:** ISA Phase 1 — fully decode the load/store instructions a
  compiler must emit (device load/store field map, addressing model, access size,
  vector width, sign-extension, threadgroup memory, constant reads).
- **Device state:** Apple A18 Pro / G17P, SoC T8140, macOS 26.6 (25G5043d),
  Metal 4 / Apple9. SIP disabled. No `metal` CLI (runtime `newLibraryWithSource:`).

## Hypothesis
Device `device_load`/`device_store` are byte0 `0x67`/`0xe7` (14B) with a
base-pointer uniform slot at byte+4 (EXP-0010). We expected the remaining fields
to encode: a destination/data register, an offset (register / immediate /
base+index*scale), an access size (8/16/32/64-bit), a vector width (scalar vs
`float2/3/4`), and sign/zero-extension for sub-32 integer loads. Threadgroup
memory was expected to use a *different* opcode group (candidates 0x07/0x87/0x97/
0xa7); constant reads, an unknown encoding vs device.

## Method
Compile OUR OWN MSL kernels (`kernels/*.metal`), extract `_agc.main` with our own
Mach-O parser (`agxparse.py`), and **byte-diff** a family that varies one axis at
a time (offset k, stride, element type, vector width, address space). Then
**splice-and-observe** on the real GPU (`agxrun_persist` via `persistrun.py`,
reusing `IntProbe` from EXP-0007): change a candidate field in our own compiled
bytes, dispatch, read back, and confirm the semantics. Clean-room legal: only our
own MSL is compiled and only our own compiled bytes are inspected/spliced/run; no
Apple binary is disassembled or introspected.

## Procedure
On the device (`~/cleanroom_work/exp0012/`), Command Line Tools only:
```sh
clang -fobjc-arc -framework Metal -framework Foundation -o shdump shdump.m
clang -fobjc-arc -framework Metal -framework Foundation -o agxrun_persist agxrun_persist.m
python3 dump_mem.py       # compile each kernel, tokenize, dump load/store bytes -> raw/
python3 memfields.py      # aligned per-byte field tables across the kernel family
python3 mem_probe.py      # M1..M6 HW splice-and-observe validations
```
- `kernels/` — the MSL family: `copy1/off{1,2,4}/str{2,4}/offn` (offset/stride),
  `ld_{char,uchar,short,ushort,long}` + `st_{char,short}` (access size / sign),
  `copyf/vec{2,3,4}/vec{2,4}i` (vector width), `tg_copy/tg_rot8/tg_shift{,1}`
  (threadgroup), `const_copy/const_idx/scalaru` (constant), `atomic_add` (note).
- `dump_mem.py` / `memfields.py` — compile + tokenize + aligned field tables.
- `mem_probe.py` — the six HW validations (M1 offset, M2 access size, M3 sign,
  M4 vector width, M5 threadgroup, M6 constant), reusing `intprobe.py`.

## Raw results
`raw/` holds text logs only (`dump_mem.log`, `memfields.log`, `mem_probe.log`) and
the extracted `*.main.hex` / `*.cp.hex` for every kernel. The `.bin` archives stay
on the device under `~/cleanroom_work/exp0012/`. See `RESULTS.md` for the analysis.

## Established facts → docs
See `RESULTS.md`. Tool DB updated: `tools/agx-isa/db.json` + `isadb.py`
(`device_load`/`device_store` promoted to HW-VALIDATED with the full field map);
`roundtrip_test.py` extended (memory instrs + programs) and passing.

## Follow-ups
- Full bit-decode of the index/destination register descriptors (bytes +1/+5/+8).
- Atomics (byte0 `0xbf` + a CAS/retry loop) — a later experiment.
- The `0x13` sub-32 unsigned format op and the `+2` addressing-mode byte.
