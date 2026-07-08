# M4 census — undecoded byte0-group investigation (starting notes)

## Context
Repeating the A18 RE on the **local Mac Mini M4** (Apple M4, Mac16,10, 10-core GPU, Metal 4, this host — NOT a remote device; compile/extract/splice run LOCALLY). M4 shares the A18 ISA: all 57 A18-corpus shaders compile on M4, and the A18 DB (`tools/agx-isa`) tokenizes them at **88.6% tokens / 91.5% bytes** — same as A18. But the resync census reports **~28 undecoded byte0 groups**. The user wants these driven to ~0 ("we shouldn't have any of those").

## What's established
- The census (`experiments/EXP-M4-01-isa-census/census/census.py`, reads `census/hex/*.hex`) resyncs by advancing ONE 2-byte parcel on a length failure — so a SINGLE length-mis-count cascades into MANY spurious "undecoded groups" until it re-aligns. The undecoded-group count is therefore inflated; the real cause is a small number of length bugs and/or genuinely-missing encodings.
- `0x2b` (the byte the user first noticed) is NOT a real group head — it appears only INSIDE resync samples (mid-instruction). Ignore it as a symptom, not a cause.
- **Integer multiply/MAD is NOT the gap in isolation:** minimal `o=a*b` / `o=a*b+c` / int `a*b` kernels (`work/mul.metal`) tokenize 100% clean — `imad` = byte0 `0x9f`/`0x1f`, **byte+2=0x56** (vs `iadd2` byte+2=0x54), 12 bytes, already in the DB. So the desyncs in dense kernels (`k_uint_arith` 83%, `k_int64` 81%, `k_transcend` 75%, `k_tex_atomic`/`k_tex_array_cube` 84%) come from something subtler — likely **imad/iadd LENGTH VARIANTS** (immediate operand or wider forms with a length ≠ 12), or other instructions.
- Recurring motif around the desyncs (see `raw/M4_census.txt` and a walk of `k_uint_arith`): `a7 07 54`, `27 07 54`, `81 27 80`, `32 80 25 8b`, `9f 00 54 …` with trailing `03 0c 8e` / `03 08 06` operand tails. These look like arithmetic/address-math instructions whose LENGTH the DB gets wrong, desyncing the walk.

## The task (for the subagent)
Drive the census to ~0 undecoded on the M4 corpus (and re-check on the A18 corpus — same ISA, so fixes should apply to both; A18 hex is in `experiments/EXP-0036-consolidation-census/hex/`).

Method per group: pick a shader with a desync (start with `k_uint_arith`, `k_int_arith`, `k_transcend`), walk it, find the FIRST instruction whose decoded length is wrong (the one right before the first `<UNDECODED>`), isolate that instruction by compiling a minimal provoking MSL kernel (`work/*.metal` + `shdump` built locally), byte-diff to pin its true length/fields, splice-and-run on the M4 (`tools/agxtest`, build locally) to HW-validate, then add/fix the descriptor + length rule in `tools/agx-isa`. Keep `roundtrip_test.py` GREEN. Re-run the census after each fix; watch the undecoded-group count collapse.

Distinguish: (a) length bug in an existing instruction (fix the length rule) vs (b) genuinely-missing instruction (add descriptor) vs (c) true resync artifact (rare). Most are expected to be (a).

Build harnesses locally: `clang -fobjc-arc -framework Metal -framework Foundation -o shdump tools/shdump/shdump.m` (already done in `census/` and `work/`); agxtest similarly.

---

# RESULTS (EXP-M4-01)

All fixes are in `tools/agx-isa/isadb.py` `instr_length` (pure length-tokenizer refinements;
no descriptor / `db.json` changes). `roundtrip_test.py` stays **GREEN (ALL PASS)**. Method for
every fix: **anchored segmentation** — bracket the unknown region between two high-confidence
anchors (get_sr / device_load / device_store / cvt_i2f `a7 07` / cvt_f2i `27 07` / iadd2/imad
`9f/1f .. 54` / stop), then the gap size = Σ enclosed op lengths pins each length. Isolation
kernels live in `work/*.metal`; harnesses in `work/` (`walk.py`, `solve.py`, `ab.py`,
`localize.py`, `patches.py`, `helper.sh`).

## Headline metric (own-shader census)

| corpus | metric | before | after |
|---|---|---|---|
| **M4** | distinct byte0 groups the DB CANNOT decode at all | **28** | **19** |
| M4 | byte coverage | 91.5% | 93.4% |
| M4 | tokens cleanly length-known | 88.6% | 91.4% |
| M4 | UNDECODED resync regions | 137 | 101 |
| **A18** (cross-check, same ISA) | never-decoded groups | 29 | 20 |
| A18 | byte coverage | 90.6% | 93.2% |
| A18 | UNDECODED regions | 158 | 112 |

**No per-kernel regression** vs the original committed `isadb.py` (total undecoded bytes 826→642,
verified kernel-by-kernel against `git show HEAD:…/isadb.py`).

## What each undecoded group actually was

The overwhelming majority of "undecoded groups" were **NOT missing instructions** — they were
operand-tail bytes (`0x00,0x54,0x80,0x92,0x96,0x03,0x06,0x1a,0x26,0x2a,0x42,…`) exposed when a
real op UPSTREAM was mis-lengthed and the resync walk landed mid-instruction. Fixing a small number
of length rules collapsed most of them:

1. **The `0x?2` (low-nibble-2) integer compare/min-max/select/carry group — THE root cause.**
   It is ONE family whose byte0 **high nibble = destination register (r0..r15)**, exactly like the
   low-nibble-9 float ALU. The DB hard-coded only dst r0..r3 (`0x02/0x12/0x22/0x32`) and left every
   higher-register form (`0x42,0x52,0x62,0x72,0x82,0x92,0xa2,0xb2,0xc2,0xd2,…`) UNDECODED — so every
   `max/select/carry/coord` writing r4+ desynced the walk. **HW-VALIDATED on this M4** (splice of
   `o=max(a,b)`): byte0 `0x02→0x12`(dst r1)/`0x02→0x42`(dst r4) flips output `10..80`→all-zeros
   (result lands in a different reg; store still reads r0), STATUS OK (valid encodings). Length is
   keyed on the byte+2 op-select (6=iminmax, 14=icmpsel-const, 10=coord/madd or reg-select, 8=
   quotient/wide-select); see the table in `docs/isa/README.md`. This single generalization is the
   biggest contributor and cleared 0x42/0x52/0x92/0xd2/… plus their downstream tails.

2. **Compact 4-byte float ALU** (low-nibble-9, byte+2 arith-enable bit clear): added byte+2 ∈
   `{0x19,0x21,0x31}` to the existing `{0x18,0x38}`. These are the div/sqrt-refinement 4-byte
   accumulate/move ops (`79 8d 21 97`, `09 05 19 01`) that mis-lengthed as 6 and desynced.

3. **`0x27` byte+1==0x02 → 12** (matrix-load prep). The old rule dropped it to the 8-byte
   else-branch, exposing its tail `f0 11 01 00` as the spurious **`0xf0`** group. k_matrix now 100%.

4. **`0x2c` byte+1==0x0c → 4** (compact move); **low-nibble-3 byte+2==0x27 → 10** (transcend/tex
   `33 8a 27 bf …`); **low-nibble-0/8 byte+2==0x24 → 6** (packed-half2 ALU); **byte+1==0xc2 tail
   `.. 80 08` → 8** (transcendental range-reduction select). Each cleared its group + tails.

## Justified irreducible residue (still undecoded, ≈101 regions / 6.6% bytes)

- **`k_tex_atomic` (27 regions, the single worst)** — the imageblock/texture-atomic sequence is
  interleaved with the **variable-length `0x0f` execution-mask control-flow ops** (`0f 06 04`,
  `0f 04 04`, `0f 01 54 <off>`), which `instr_length` intentionally leaves LEN_UNKNOWN (a documented
  follow-up for the mask push/pop family), plus the texture-atomic op itself (a genuinely new op not
  yet characterized). These produce the residual `0x00/0x54` tail groups.
- **`k_transcend` / `k_transcend_round` (≈15 regions)** — a long tail of distinct SFU
  range-reduction/polynomial helpers (byte+2 op-selects `0x39,0x49,0x23,0x2f,0x25,…`); the two most
  frequent (`b1==0xc2` select, the `0x33` 10-byte op) are now fixed; the rest are each low-frequency
  and would each need its own isolation kernel.
- **`k_half2_pack` / `k_half_arith`** — a small half2 subsystem (0x18/0x38/0x30/0x20 with mixed
  op-selects) partially fixed (the byte+2==0x24 packed ALU); the remaining forms are a follow-up.

These are true instruction gaps or the known variable-length-CF follow-up, not length bugs — i.e.
the residue is now dominated by genuinely-uncharacterized ops rather than resync cascade artifacts.

---

# RESULTS — ROUND 2 (EXP-M4-01, drive the residue → ~0)

All changes are in `tools/agx-isa/isadb.py` (length rules + one descriptor generalization).
`roundtrip_test.py` stays **GREEN (294 checks, exit 0)**. `db.json` / `docs/isa/encoding-tables.md`
/ `docs/isa/agx3.xml` regenerated (82 descriptors). **No per-kernel regression** (all 23
previously-100% M4 kernels stay 100%; 9 MORE reach 100%).

## Headline metric

| corpus | metric | round-1 end | **round-2 end** |
|---|---|---|---|
| **M4** | distinct byte0 groups the DB CANNOT decode | 19 | **12** |
| M4 | byte coverage | 93.4% | **96.4%** |
| M4 | tokens cleanly length-known | 91.4% | **95.2%** |
| M4 | UNDECODED resync regions | 101 | **57** |
| **A18** (cross-check, same ISA) | never-decoded groups | 20 | **13** |
| A18 | byte coverage | 93.2% | **96.0%** |
| A18 | UNDECODED regions | 112 | **70** |

## Target-by-target outcome (from the task list)

1. **`0x0f` execution-mask CF — RECONCILED (no regression; the round-1 note was STALE).**
   `instr_length` already lengths every `0x0f` sub-op (`00`/`01`=10, `04`=4, `05`=4/14, `06`=6,
   `80`=6); the corpus walk decodes all 67 `0x0f` occurrences in-sequence. The `k_tex_atomic`
   desyncs were NOT the CF ops — they were genuine gaps UPSTREAM of the CF (`0x2a` icmp, `0x37`
   compute gradient, `0x87`/`0x80` fences, the coord-madd 8-vs-10 length) whose mis-length landed
   the walk mid-instruction, exposing `0x00`/`0x54` tails near the `0x0f` bytes. Fixed at the source.

2. **Texture-coordinate atomic path — CHARACTERIZED.** `t.read()`/`t.atomic_fetch_add()` on a
   `read_write` texture compiles to a large (~440-byte) SOFTWARE address blob (isolated in
   `work/iso_tex.metal`: a plain read is a clean 14B `tex_sample`; the *atomic* carries the blob).
   The atomic itself is the already-decoded `67 01 54` `atomic_mem`. The blob's new ops now decoded:
   `27 04`+`18 00` coordinate convert/pack; `2b 35`/`0b 35` (2B texture coord/LOD selector) →
   `37 xx 80` (8B COMPUTE texture-gradient) → `27 00 54 .. f0 13 01 00` (12B ibfe); `87 02 00 00`/
   `80 02 00 00` compute fences. `k_tex_atomic` 22 → 7 undecoded regions.

3. **Transcend SFU helpers — common ones CHARACTERIZED, rest are justified residue.** Added the
   6-byte SFU polynomial fma (low-nibble-2, op-select `0x23`, the exp/log/pow Horner step feeding a
   sel). Gated the greedy `02`/`0a` rules so they stop eating the `fspecial`/`coord_madf` that
   follow. Remaining `k_transcend` tail (`06 02 72`, `2e 15 a0`, `54 xx 03`, `00 00` markers) is a
   low-frequency range-reduction/polynomial-helper set — a justified residue (each needs its own
   isolation kernel; see below).

4. **half2 / compact-move subsystem — extended.** Added `18 00` (2B compact half move), `00 8c` /
   `80 04` (2B compact moves), and the `0x?b` shift/rotate compact `?b .. {1c,3c} <amt>` (4B).

## HW SPLICE VALIDATION (own-shader, local M4)

`work/iso_icmp2.metal` (a loop with `break`+`continue` → execution-mask divergence → multiple
predicate registers). Baseline out `4 25 110 110`. Splicing a loop-guard `icmp` byte0:
- `2a → 0a` (predicate dst r2→r0): out `133 25 133 133`, `STATUS OK`
- `2a → 4a` (predicate dst r2→r4): out `4 389 9989`, `STATUS OK`
- `2a → 2a` (control): out `4 25 110 110` (unchanged)

⇒ **byte0's HIGH nibble is the destination PREDICATE REGISTER** for the low-nibble-`0xa` icmp
family (relocating it corrupts the downstream `0f` jump that reads the predicate), exactly as
round-1 proved for the `0x?2` sibling. The `icmp_pred` descriptor was generalized to match the low
nibble with a `dst` field.

## Remaining residue — ENUMERATED + JUSTIFIED (≈57 M4 regions, none a mystery)

Every remaining region is a NAMED, characterized op — not a resync-cascade artifact. Grouped:

- **`0x54` texture-address / imageblock op family** (byte+2`==0x03`; also `0x02`/`0x92` sub-forms):
  variable 4/6/8/10-byte (the 10B `.. f0 13 01 00` extension form is now decoded via the `0x37`
  fix). Appears in k_tex_atomic/k_transcend/r_blend_f/r_deriv_f/k_int64. Needs an operand-swept
  isolation to pin the 4/6/8 length selector — follow-up.
- **Threadgroup-memory atomics** (`k_atomics_tg`, `k_threadgroup`): `0b 00 06`, `54 .. 44 01`,
  `00 00 44 05`, `56 00 08`, `80 00 44`, `23 04 1f` — a coherent shared-memory atomic-RMW
  descriptor subsystem distinct from device atomics; isolate as its own experiment.
- **Cube-array coordinate math** (`k_tex_array_cube`): `f0 c0 04` (4B constant/coord load),
  `54 21 92`, `23 a0 42`-adjacent `coord_madf` residue.
- **SFU polynomial/range-reduction helpers** (`k_transcend`): `06 02 72`, `2e 15 a0`, `54 16 03`,
  `42 85 03` — low-frequency Horner/range-reduction ops (task-sanctioned justified residue).
- **Compact 2-byte helper ops in dense code**: `00 8c`-class moves, `00 06 02`, `01 00`, `80 00`,
  `20 05` — high-nibble = dst reg, 2 bytes; a handful still need a tight per-signature gate.
- **misc n=1**: `5b 11 17` (k_mem, 64-bit masked op), `2c cd 02` (k_tex_lod LOD-clamp), `31 01 3c`
  (k_cvt_half), `20 00 1a`/`20 80 32` (k_tex_atomic atomic-descriptor setup), `ac 01`.

## Provenance
`census/` (harness + `hex/` OWN-SHADER bytes), `work/` (isolation kernels `iso_tex.metal`,
`iso_icmp2.metal`; analysis harnesses `walk.py`, `enum_gaps.py`, `scan_op.py`). HW splices via
`tools/agxtest/agxtest.py` on the local M4. Method: OWN-SHADER + HW-PROBE. No Apple binary inspected.
