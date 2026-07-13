# EXP-M5-19 — M5 ray-tracing AS-load + ray-data encoding (RESOLVED)

**Device:** Apple M5 / Apple10 / G17g / T8142. Every fact HW-evidenced by splice-and-observe against a **real
single-triangle acceleration structure** running our own byte-spliced machine code, or byte-diff of own MSL.
No Apple binary disassembled. 0 GPU faults / 0 reboots across ~180 splice dispatches (RT faults fully contained).

## Result — the A18 migration hypothesis is CONFIRMED; RT loads are NOT a dedicated M5 opcode
- **`rt_intersect` (`?4 ea`) SURVIVES and is now splice-confirmed on M5** (was A18-provenance-inherited). Baseline
  vs real AS: rays 0-4 (dir +z) → t=3.0, ray 5 (dir −z) → miss. Splices: byte+1 `ea`→`00` breaks traverse; byte+2
  `90`→`00` makes the miss-ray HIT (functional mode); byte+4 = per-lane ray/AS operand; op#2 reads a non-distance
  result field.
- **AS handle = index-fixed argument/uniform load.** `as_slot1.hex` ≡ `as_slot3.hex` **byte-for-byte** (AS at
  buffer 1 vs 3) — unlike plain device buffers whose split-memory addr-gen slot is keyed by binding index. Loaded
  by frame-prologue argument loads `?f 48 43/03 00` (byte+1=0x48; `0xff` scan confirms load-bearing).
- **Ray origin/dir ride the `0x?f` split-memory family** (cluster `[0x32,0x54)` before traverse): `m5_addr_gen`
  `5f 0a 03` = origin base; `4f 10 83`/`8f 68 83` = direction / origin loads (byte+2 0x83). Origin vs direction
  separated by ray0-survival splices (t = 3 − origin.z; a corruption leaving ray0 correct broke only per-lane
  origin; one making even ray0 miss broke direction; `@0x31 03→00` flipped only the −z miss-ray = direction sign).
- **Family structure:** byte0 low-nibble `0xf` + byte+2 low-bits `0b11` = signature; byte+2 top-2 bits = mode
  (`0x03` addr-gen, `0x43`/`0x83` load); byte+1 = source (`0x48` argument/uniform index-fixed = AS handle + buffer
  ptrs; `0x10`/`0x68` device pointer = ray data).

## Driver takeaway
A driver emits M5 RT via the **general argument-load (AS handle) + split-memory loads (ray data)** — there is
**no dedicated `0xdf` AS-load op on M5**, so RT lowering reuses the memory paths already specified.

## DB deliverable — SEMANTICS-ONLY update (zero census risk)
Correct action is NOT a new descriptor (AS-load = general argument/uniform load; ray-data = general `0x?f`
split-memory load — a dedicated descriptor in the overloaded `0x?f` space would risk desync). Updated the
`rt_as_load` descriptor's `semantics` in `isadb.py` from CAVEAT→RESOLVED (no match/length/field change).
Round-trip ALL PASS (189 desc); census unchanged.

## Still open (honest)
In-loop BVH-node loads (past the traversal loop back-edge, inferred same `0x?f` family, not per-op spliced);
exact bit-widths of the `0x83`-load dst/addr/elem-size sub-fields (roles assigned, A18 template is the hypothesis);
op#2's result-field layout (needs a `primitive_id`/barycentric-reading kernel).

## Artifacts
`kernels/rtprov.metal` (10 provocations) + `kernels/rtk.metal`; **`rtsplice.m`/`rtsplice2.m` — the real-AS splice
testbed** (agxrun archive technique + AS build) prior reports flagged as missing; `rtsplicerun.py`/`rtscan.py`/
`locate.py`; `hex/*.hex`; `raw/splice_log.txt` (baseline + splice/scan tables).

## Clean-room attestation
Every fact = the compiler/driver's response to our own on-device-compiled MSL, or what our own `rtsplice` harness
observed the GPU compute for our own buffers against an AS we built. No Apple binary disassembled; no compiler
sequence lifted. Negatives/opens recorded.
