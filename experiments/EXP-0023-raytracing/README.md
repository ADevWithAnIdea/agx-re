# EXP-0023: hardware ray tracing — dedicated intersector?

- **Date:** 2026-07-07
- **Clean-room category:** OWN-SHADER + HW-PROBE + DATA-TRACE
- **Phase / question:** Phase 1 ISA — Part B1/B2/B3 of `docs/isa/msl-feature-map.md`.
  Apple9 caps report `supportsRaytracing=YES`. Does `raytracing::` lower to dedicated
  intersect instruction(s) (a novel opcode group) or a software BVH-traversal loop?
- **Device:** Apple A18 Pro / G17P, macOS 26.6 (25G5043d), 5 GPU cores, Metal 4 / Apple9. SIP off.

## Hypothesis
`intersector::intersect` / `intersection_query` either (a) emit a **new opcode group**
unknown to our tokenizer ⟹ dedicated ray-tracing HW, or (b) lower to ordinary ALU/load
BVH-traversal ⟹ software. Decide by diffing against a hand-written software Möller-Trumbore
ray/triangle loop (the exact thing a software lowering produces). If dedicated: decode the
intersect op (opcode/operands/mode), the AS referencing, and the intersection-function /
`ray_data` binding; then HW-validate a known ray vs a known triangle in a real acceleration
structure.

## Method (clean-room)
Compile OUR OWN MSL (`kernels/rt.metal`, `kernels/hand.metal`, `kernels/isectfn.metal`) with
`tools/shdump` (runtime `newLibraryWithSource:`), carve `_agc.main`, tokenize/diff
(`tools/agx-isa` + `rtlen.py`/`rtcount.py`). **HW-validate** by building a real
`MTLAccelerationStructure` and tracing known rays on the GPU (`rtval.m`). **Capture the AS
referencing** by running `rtval` under `tools/iotrace` (read-only) and locating the AS GPU VA
in the argument buffer (`asref.py`). No Apple binary is disassembled — only our own compiled
bytes and the DATA our own process hands the kernel.

## Procedure
```sh
# device: ~/cleanroom_work/exp0023 (tools + kernels copied there)
clang -fobjc-arc -framework Metal -framework Foundation -o rtval rtval.m
# compile + extract each kernel's _agc.main -> raw/mains.txt
for f in rq_trace isect_trace isect_dist isect_dynray isect_anyhit isect_instance; do
  ./shdump -o out/rt_$f.bin -f $f kernels/rt.metal
  python3 agxparse.py out/rt_$f.bin --stage compute --extract-hex --symbol _agc.main; done
# controls:
./shdump -o out/hand.bin -f hand_trace kernels/hand.metal   # + hand_one
# analysis (host):
python3 rtlen.py raw/mains.txt        # length rule incl. RT groups -> clean tokenization
python3 rtcount.py raw/mains.txt      # RT-op counts + traversal-loop (back-edge) detection
# HW validation + AS-descriptor capture (device):
./rtval                                                       # known ray vs known triangle
IOTRACE_LOG=raw/rt_iotrace.log IOTRACE_DUMP_DIR=maps RT_SIGUSR1=1 \
  DYLD_INSERT_LIBRARIES=./iotrace.dylib ./rtval               # capture AS referencing
python3 asref.py                                              # locate AS VA in the arg buffer
```

## Raw results (`raw/`)
- `mains.txt` — `_agc.main` hex of all RT kernels + software controls + fn-table kernel.
- `intersect_diff.txt` — byte-diff of the dedicated intersect op across ray/AS/fn-table variants.
- `rtops.txt` — dedicated-intersect-op counts + traversal-loop (back-edge) counts per kernel.
- `hwval.txt` — HW validation: known ray vs known triangle → correct t / prim / barycentrics.
- `asref.txt` — AS referenced by GPU VA in the Tier-2 argument buffer (offset 0x1620) + BVH header.
- `iotrace_summary.txt` — IOKit call summary for the AS build + trace.
- `tokenize_full.txt` — initial structural tokenization (shows the novel groups blob).

See **`RESULTS.md`** for the full analysis.

## Result (one line)
**HYBRID.** Dedicated ray-tracing HW instructions — a ray-intersect op (byte0 low-nibble `0x4`
+ byte+1 `0xea`, 8 B) and AS-data loads (`0xdf`, 14 B), both **absent** from a hand-written
software triangle loop — drive a **compiler-generated shader BVH-traversal loop** (not one
fire-and-forget instruction). AS build is GPU/firmware-managed; AS referenced by GPU VA in the
argument buffer; intersection functions bind via `intersection_function_table` (function-table
model). End-to-end HW-validated (correct t/prim/barycentrics). `tools/agx-isa` +2 descriptors,
round-trip 188/188 PASS.

## Established facts → tools
- `tools/agx-isa/`: new **`rt_intersect`** + **`rt_as_load`** descriptors, length-rule entries,
  `db.json` regenerated (38 descriptors), `roundtrip_test.py` extended — ALL PASS.

## Follow-ups
Full `rt_intersect` operand bit-decode (needs an AS-aware splice testbed); decode companion RT
groups (`0x5f`, `0x?2/0x27`, `0x?b` ray-moves); the WWDC "reorder/sort stage"; RT-from-render
and motion blur; BVH node format (firmware — kernel team).
