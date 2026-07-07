# EXP-0040 RESULTS — objective-2 descriptor merge + byte0-census re-run

## Part A — descriptor merge (host)

Merged the two staged objective-2 descriptor files (EXP-O2C + EXP-O2D) into
`tools/agx-isa/isadb.py` and regenerated `db.json`.

- **Descriptor count: 68 → 75** (+7 new; `matrix_mac` and `rt_intersect` were **updated in
  place**, not added). New descriptors:
  - **EXP-O2C (RT tail + tensor):** `rt_ray_mem` (`0x5f`, 14B — ray-data / traversal-stack
    memory op, the store/spill sibling of the `0xdf` AS-load; carries the ray_data payload
    copy-in/out), `rt_transform_test` (`0x?2`, 10B — ray-vs-node transform / AABB box-test,
    full `27 81 22` signature), `ray_move` (`0x?b`, 4B — ray register-marshalling move; also
    the MPP matmul2d TRANSPOSE data-move).
  - **EXP-O2D (compute/fragment tail):** `bf_alu` (`0x11` byte+1==0x02, 8B — native bfloat
    add/mul), `imageblock_store` (`0xe7` byte+1==0x16, 12B — explicit `imageblock<T>.write`
    from a tile shader, byte+5 = field byte-offset>>1), `imageblock_load` (`0x67` byte+1==0x16,
    12B — explicit `imageblock<T>.read`), `mem_fence` (`0x07 54 84 0a`, 6B —
    `atomic_thread_fence(mem_device, seq_cst)`, no execution barrier).
- **`matrix_mac` (0xcf) fully operand-decoded** (was "partially decoded"): byte+5 = A (LEFT)
  operand, byte+6 = B (RIGHT), byte+7 = C accumulator src, byte+8 = dst, byte+3 = A
  sub-descriptor (load-bearing), byte+10 = op-enable 0x24, byte+1 = dtype, byte+2 = mode
  (0x56 standalone / 0x54 tiled — SEMANTIC, not a hint), byte+11 bit0 = accumulate-enable —
  all HW-splice-validated in EXP-O2C.
- **`rt_intersect` (0x?4/0xea) motion + AS-select** decoded: byte+2 mode 0x10 =
  dynamic-origin OR primitive-motion; byte+4 as_type 0x8b primitive / 0x1b instance /
  0xbb primitive-motion; byte+3 carries the motion time (0x46 device / 0x26 const).
- **Refinements:** `simd_reduce` (float `simd_product` = byte+1==0x06 bit7=1; float
  exclusive-scan byte+7==0x32; fmin 0x05 / fmax 0x07), `simd_shuffle`
  (shuffle_and_fill_up/down = byte+1==0x06), `get_sr` (SR 0x84 = `simd_is_helper_thread`).
- **Length-rule additions/fixes** in `instr_length()`:
  - **`0x11` bfloat (LOAD-BEARING FIX):** the old flat `8 if byte+2&0x02 else 6` mis-lengthed
    every bfloat op (bf_add 0x1c → 6, bf_fma 0x1e → 8) and desynced bfloat kernels. New rule is
    length-polymorphic on **byte+1**: 0x03 → 6 (cvt_f2h), 0x02/0x04 → 8 (add/mul) or 10 (fma,
    byte+2&0x02). Disambiguate on byte+1 because cvt_f2h and bf_add SHARE opsel byte+2==0x1c.
  - `0x5f` (byte+2∈{0x54,0x56}) → 14 (rt_ray_mem); `0x?2` `27 81 22` → 10 (rt_transform_test,
    placed BEFORE the unconditional 0x02/0x32 handlers); `0x?b` byte+2∈{0x80,0x81} → 4
    (ray_move); `0xe7` byte+1∈{0x06,0x16} → 12 and `0x67` byte+1∈{0x06,0x0e,0x16} → 12
    (frag_color_store/tile_read + imageblock tile variants).

- **Round-trip: PASS.** `roundtrip_test.py` extended with 15 new real single-op vectors
  (matrix_mac ×4, rt_intersect motion, rt_ray_mem, rt_transform_test, ray_move, bf_add/bf_mul,
  imageblock_store/load, mem_fence, get_sr helper) + 2 new synth combos + 4 new whole-program
  tokenizations (`bfaddu`, `bfmulu`, `ib_tile`, `rt_ops`). All four sections (real asm↔disasm,
  synth field round-trip, whole-program tokenize-to-0-leftover, packed-immediate codec) report
  **ALL PASS** (275 OK vectors).

- **Nothing skipped.** All requested descriptors merged. The only deviations from the raw
  `new_descriptors.json` were the two **collision resolutions** below (byte+N signature
  tightening), which the task explicitly sanctions.

## Part B — encoding tables (host)

`gen_encoding_tables.py` re-rendered `docs/isa/encoding-tables.md`: **75 descriptors, all 75
tabulated, 0 in "Other"** (the 7 new descriptors slotted into Float-ALU / Ray-tracing /
Barrier-ordering / Fragment-stage families; the byte-0 length-rule appendix extended with the
EXP-O2C/O2D rows).

## Part C — byte0-group census (host)

Corpus = the **reused EXP-0036 hex set** (57 unique stage `_agc.main`, 10,110 instruction bytes)
**plus** the **new objective-2 families** (36 unique: 10 tensor + 7 MPP-matrix + 14 RT +
2 bfloat + 3 imageblock-tile, 82,510 bytes). Full output in `raw/census.txt`.

### Headline

| view | streams | byte coverage | cleanly tokenized | named |
|---|---|---|---|---|
| **A. EXP-0036 subcorpus** (vs EXP-0039) | 57 | **8886/10110 = 87.9%** | 1067/1246 = 85.6% | 940 |
| **B. NEW objective-2 families only** | 36 | **67730/82510 = 82.1%** | 6803/8333 = 81.6% | 6094 |
| **C. COMBINED** | 93 | **76616/92620 = 82.7%** | 7870/9579 = 82.2% | 7034 |

**The EXP-0036 subcorpus is byte-identical to EXP-0039 (87.9%, 940 named, 0 stream regressed,
0 spuriously inflated)** — the merge added RT/tensor/bfloat/imageblock decode without disturbing
the original compute/fragment/vertex corpus (per-stream diff vs the committed EXP-0039 census:
**0 regressed, 0 improved, 57 unchanged**). The combined 82.7% is heavily weighted by the MPP
matrix kernels (matrix/tensor = 53,458 of 92,620 bytes = 58% of the corpus), so the **per-category
numbers are the real signal**.

### Byte coverage by category (COMBINED)

| category | coverage | note |
|---|---|---|
| objective2:bfloat | **100.0%** (124/124) | fully decoded (bf_alu + 0x11 length fix) |
| render:vertex | 97.9% | unchanged vs EXP-0039 |
| render:fragment | 95.4% | unchanged |
| compute:function-table | 90.1% | unchanged |
| compute:core | 89.6% | unchanged |
| objective2:matrix/tensor | **86.7%** (46350/53458) | 0xcf matrix_mac + ray_move transpose + memory |
| objective2:imageblock-tile | **85.0%** (294/346) | imageblock_store/load; residue = slice-addr ALU |
| compute:texture | 80.0% | unchanged |
| objective2:raytracing | **73.3%** (20962/28582) | residue = traversal-loop address ALU + 0x0f masks |
| mesh | 65.4% | unchanged |

New top-named mnemonics from the merge: **matrix_mac (1439)**, **rt_ray_mem (323)**,
**rt_as_load (253)**, **ray_move (67)**, plus bf_alu / imageblock_store / imageblock_load /
mem_fence.

### Final still-undecoded byte0 groups (the honest residue)

181 distinct byte0 leaders seen; the residue is **operand sub-fields and previously-flagged
follow-ups, NOT whole undecoded instruction families**:

- **RT-traversal inner-loop address ALU** — `0x42`/`0x92`/`0x52`/`0xb2`/`0xd2`… the
  `Xx 81 27/35 …` coordinate / texel-address arithmetic. This is the SAME family EXP-0039
  flagged as the densest compute residual (`k_tex_atomic`), and it dominates the RT traversal
  loop; it is deliberately left undecoded (a full bit-decode of the address-generation ALU is
  the standing follow-up — NOT force-lengthed, see §"Regression resolved").
- **Execution-mask sub-ops** — `0x0f` (byte+1 ≠ the decoded jump/call/return forms;
  push/pop/reconverge, EXP-0010 follow-up). Abundant in the RT traversal loops (419 length-only
  + 53 undecoded) — the software BVH traversal is mask-heavy.
- **Uncharacterized `0x07` sub-op** — `07 22 02 00` (byte+2==0x02), distinct from the
  barrier/link/pixel-order/mem-fence forms (EXP-0039 follow-up).
- **VS-select / value-compute** — `0x1a`/`0x2a`/`0x21` (the `vid==k ? A : B` select chain that
  feeds the `0x57` varying stores; EXP-0037 follow-up).
- **`0x18 84 24` high-register half_pack sibling** (EXP-0039 follow-up, deliberately not
  force-lengthed).
- The remaining count-1/2 leaders (`0x00`/`0x54`/`0x03`/`0x24`/`0x06`/`0x80`/…) are resync
  landings on operand bytes after a genuinely-undecodable op desyncs the walk — not real opcodes.

**Judgment:** the merge closed every objective-2 instruction FAMILY the census was missing —
the dedicated matrix-MAC operand model, the RT ray-data / transform / ray-move ops, native
bfloat ALU (bfloat now 100%), explicit imageblock read/write, and the device memory fence. Every
remaining gap is an **operand-level sub-field, a mask sub-op, or a resync artifact** — the same
frontier EXP-0037/0038/0039 identified, now including the RT traversal-loop address ALU. No new
whole opcode group is undecoded.

## Regression / collision resolved

The first census run showed 5 compute kernels (`k_int_arith`, `k_cf_switch`, `k_cf_if`,
`k_int64`, `k_uint_arith`) "improving" +1–3% — a **false positive**: `rt_transform_test`'s
initial loose gate (`low-nibble-2` + `byte+2==0x27`) collided with the compute **texel-address /
coordinate ALU** (`Xx 81 27 …`, byte+3==0x80 / byte+4≠0x22), spuriously length-fitting and
naming that op as an RT transform test. Resolution: gate `rt_transform_test` on the **full
`27 81 22` signature** (byte+2==0x27 AND byte+3==0x81 AND byte+4==0x22) in both the length rule
and the descriptor match — the real RT transform test always carries it, the compute texel ALU
never does. Result: the compute texel ALU returns to being honestly undecoded (the flagged
follow-up), the EXP-0036 subcorpus is **byte-identical to EXP-0039** (0 regressed, 0 spurious
gain), and round-trip stays green. This mirrors the EXP-0039 `half_pack` blanket-vs-gated lesson:
prefer honest undecoded residue over spuriously-inflated coverage.

Other collisions resolved cleanly by byte+N signature (no regression):
- `imageblock_store`/`imageblock_load` match the **tile first-access variant byte+1==0x16**;
  byte+1==0x06 stays `frag_color_store`/`tile_read`, byte+1==0x0e stays `tile_read`.
- `mem_fence` match (byte+3==0x84, sum 24) is strictly more specific than `threadgroup_barrier`
  (byte+2==0x54, sum 16), so device-fence bytes pick `mem_fence` while the barrier's
  0x61/0x85 scope bytes stay `threadgroup_barrier`.
- `bf_alu` (byte0 0x11, byte+1==0x02, len 8) and `cvt_f2h` (0x11, byte+1==0x03, len 6) never
  collide — different byte+1 AND different length.

## Established facts → docs
- `docs/isa/encoding-tables.md` — refreshed authoritative encoding table (all 75 descriptors).
- (The prose ISA facts these descriptors encode were established in EXP-O2C/O2D; the orchestrator
  owns any `docs/isa/README.md` prose updates.)

## Follow-ups (the frontier, now smaller)
1. Bit-decode the RT-traversal / compute texel-address coordinate ALU (`0x42`/`0x92` `Xx 81 27`
   family) — the densest residual (worst on RT at 73% and `k_tex_atomic`).
2. Length the `0x0f` execution-mask push/pop/reconverge sub-ops (abundant in RT traversal) and
   the `0x07 byte+2==0x02` sub-op.
3. Decode the VS-select value-compute family (`0x1a`/`0x2a`/`0x21`) that feeds the `0x57` stores,
   and the `0x18 84 24` high-register half_pack sibling.
4. Splice-validate the RT operand register bit-packing (rt_intersect ray operands, rt_ray_mem
   addressing) — needs an AS-aware splice testbed.

## Clean-room status
Clean. Only our own OWN-SHADER-derived encoding data was merged; only our own compiled bytes
(the EXP-0036 corpus + the EXP-O2C/O2D-extracted RT/tensor/bfloat/imageblock `_agc.main`) were
tokenized with the read-only DB. No Apple binary was disassembled. No `tools/iotrace/`, other
`docs/*`, `PROVENANCE`, `ROADMAP`, or `reviews/` were edited; nothing was committed.
