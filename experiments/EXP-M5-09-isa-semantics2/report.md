# EXP-M5-09 — M5 ISA semantics II: matrix/neural, ray tracing, texture, atomics, subgroup

**Device:** Apple M5 / Apple10 / G17g / T8142 / macOS 27.0. Every encoding fact is HW-evidenced by a
byte-diff of OUR OWN compiled MSL (one op varied per kernel) and/or a splice-and-observe dispatch
(`agxtest.py --run-timeout 12`). 55 own-MSL functions compiled. No Apple binary disassembled.

## MARQUEE: the M5 matrix path SPLITS — and there is NO new dedicated "neural" ISA leader
On **A18**, both `simdgroup_matrix` MAC and MPP `tensor_ops::matmul2d` lowered to the **identical `0xcf`**.
**On M5 they DIVERGE:**
- **`simdgroup_matrix` MAC (fp16/fp32/bf16): ZERO `0xcf`.** Lowers to a low-nibble-`0xf` **tile family**
  (`?f ..07..`, leaders 0x0f/2f/4f/6f = tile load/store) + a distinct **MAC op `2f 00 05 …`** (byte+2=0x05).
- **MPP `tensor_ops::matmul2d`: `0xcf` STILL PRESENT** (A18 leader survives; body re-laid-out).

**Verdict:** the Apple10 "Neural Accelerator per GPU core" is **NOT a new standalone opcode** on any
MSL-reachable path — matrix work rides the low-nibble-`0xf` family. On M5, `0xcf` is specifically the
*tiled/MPP* matrix op, not the universal one it was on A18. **Proof:** control ladder `ls_f32`(load+store)→2
`?f..07..` ops, `mul`→3, `mad`→4 ⇒ `?f..07..` = tile load/store; the `2f 00 05` MAC is in mul/mad, absent
in ls ⇒ it is the multiply/accumulate. Splice (mad, A=B=1,C=0): corrupting the MAC leader / MAC byte+2
(`05`→00) / a tile byte+2 (`07`→00) each drives output all-zero (load-bearing); byte+1 = operand selector.
Full 8×8 operand bit-packing = splice-TODO (op identity proven).

## Ray tracing: rt_intersect SURVIVES; AS-load migrated
- **`rt_intersect` (byte0 low-nibble `0x4` + byte+1 `0xea`) transfers UNCHANGED from A18** — twice/kernel
  (traverse byte+2=0x10, result-read 0x11), for both `intersector` and inline `intersection_query`; byte+4 =
  AS-type selector.
- **`rt_as_load`(0xdf) / `rt_ray_mem`(0x5f) do NOT survive as distinct leaders** (0–2/kernel on M5 vs 14–37
  on A18) — per the EXP-M5-07 memory split, AS/ray-data loads migrated into the new M5 memory family.
  **Exact M5 AS-load encoding = OPEN** (needs an AS-aware splice testbed).

## Atomics + subgroup/quad: UNIFIED reduction op-selector at byte+6
Form `2f 00 <scope> 0a 27 80 <OP> 02 <mode>`. **byte+6 = OP:** `a0`=and `a1`=or `a2`=xor `a3`=add `a6`=min
`a7`=max **`ac`=float-add** (byte+3=0x08 fp datapath). **Scope = byte+2** (0x04 simd/device-atomic, 0x00 quad).
**reduce vs scan = byte+9** (0x02 reduce, 0x00 exclusive-scan). Shuffle distinct: `2f 00 21 1a 20 00 <mode>`
(a8 broadcast, a0 quad_shuffle, a1 shuffle_xor). Evidence = 22 single-op own-MSL kernels differing only in
byte+6/+2; splice confirms byte+6 load-bearing. **Closes OBJ-2 backlog #2 (atomics incl. float-add) + #9
(subgroup reduce/scan).**

## Texture sample family: byte0 low-nibble `0xf`, byte+2 op-class
Byte-diff (7 kernels): `sample` `0f 04 12`; `sample(level)` = +LOD imm; `gather` `0f 06 12`; `read`(image-load)
`0f 06 1a` (byte+2=0x1a); `calculate_lod` `1f 06 12`; `sample_compare` `1f 05 12`; `write` = distinct
`24 80 03 0a 27 08 ae …`. So texture = **byte0 low-nibble `0xf` + byte+2 ∈ {0x12 sample-class, 0x1a read}**.
Byte-diff only (sampler/coord/LOD field splices need `agxrender`, deferred). **Addresses OBJ-2 backlog #3.**

## Opens: closed vs still-open
- **CLOSED:** atomics op-selector + float-add; subgroup/quad reduce/scan selector; **12B integer-add confirmed**
  (`2f 00 04 3a` byte+3∈{0x1a,0x3a}→12B; the fork lengths it 10B → desync; length-rule proposed).
- **STILL OPEN:** `0xNe` compact-ALU op-select (half add/mul/mov lower to 0x38/0x2f `38 03 04`=add/`38 03 05`=mul,
  not `0xNe`); call ABI `0xef`/`0xff` (needs whole-`__text` extraction — shdump's single-symbol dump returned a
  stub); `0xb7` (quad/simd lower to `2f 00 21`/`2f 00 0x`, never `0xb7` — recorded negative).

## DB deliverable — validated + integrated
**Merged (this commit):** the vec3/vec4 + half-scalar **STORE naming fix** — new `m5_store` len-6 descriptor,
match `[(0,5,1),(16,8,0x10)]` (13 bits) out-matches inherited `cvt_f2h_dst` (8 bits) for every real 6-byte
store (byte+2==0x10) while excluding real fp32→fp16 convert (byte+2∈{0x1c,0x3c}); purely additive. Verified:
`41/61/01 … 10 …` stores now name `m5_store`; real `41/01 … 1c …` correctly stay `cvt_f2h_dst`. Round-trip
ALL PASS; census unchanged (label-correctness fix — DB 176 descriptors).

**Proposed but NOT merged** (deferred per the per-family integration contract — they live in the overloaded
`0x2f`/`0x0f` leader space and need length disambiguation + a full census pass; encodings in
`hex_extractions.txt`): matrix-MAC `2f 00 05`; reduction `2f 00 <scope> 0a 27 80 <op>` (byte+6 table); shuffle
`2f 00 21`; texture `?f ..12/..1a`; the 12B-iadd length rule. These currently decode as `fspecial`/undecoded —
integrating them is a coverage *improvement* but risks desync if a length is off, so they're the next
integration wave, not shipped unvalidated.

## M5 fault behavior
Zero hangs, zero reboots across ~15 splice dispatches (incl. deliberately-corrupted leaders). Corroborates
EXP-M5-07: M5 faults are contained; splice is low-risk.

## Files
`hex_extractions.txt` (annotated ops + splice log), `kernels/*.metal` (8 files, 55 functions), `hex/*.hex`
(55 dumps), `isadb.py.EXP-M5-09.patch` (store-naming fix, merged).

## Clean-room attestation
All facts are the driver/compiler's response to OUR OWN MSL (compiled on-device via `newLibraryWithSource:`)
or bytes our own `agxrun` read from our own buffers. No Apple binary disassembled; no compiler *sequence*
lifted — only per-op HW encoding facts. Negatives/opens recorded.
