# `db_defects` backlog — triage, application record, and the deferred (c) worklist

**Scope.** Every `"db_defects"` entry in `experiments/EXP-01*/analysis/field_verdicts.json`
(EXP-0138, 0139, 0140, 0141, 0144, 0146, 0147, 0148 — eight files, **50 entries**), plus the
emittability-metric defect.
**Target of every cited measurement:** Apple M4 / G16G, except where a row says otherwise.
**Nature of this work:** DESK. No GPU, no SSH, no device was touched. Every number below is
either read out of a committed `field_verdicts.json` or produced by re-running committed
analysis over the committed own-MSL corpus.

**Clean-room provenance:** `PUBLIC` (this repository's own committed artifacts only).
**Inputs inspected:** `tools/agx-isa/{db.json,validation.json,isadb.py,roundtrip_test.py}`,
`experiments/EXP-01*/analysis/field_verdicts.json`,
`experiments/EXP-0148-*/analysis/scaffolding_classification.md`, and the own-MSL corpus
`experiments/EXP-M4-13-full-corpus/hex` (1080 files, 587 586 bytes, compiled from MSL we wrote).
**Apple binary introspection:** NONE.
**Reproduction:** `python3 work/dbtriage/apply_ab_defects.py` (idempotent),
`python3 tools/agx-isa/roundtrip_test.py`, `python3 tools/agx-isa/validate_labels.py`,
`python3 work/dbtriage/make_c_variant.py <v> && bash work/dbtriage/ab_run.sh <v>`,
`python3 work/dbtriage/c_functional_check.py`.

---

## 0. Classification key

| class | meaning | disposition |
|---|---|---|
| **(a)** | semantics-only annotation — prose in `semantics`/`provenance` | **applied** |
| **(b)** | field-model change (split / rename / retype / enum) — `match` and `length` untouched, so *which* descriptor fires and *how many bytes* it consumes are bit-for-bit unchanged | **applied** |
| **(c)** | match or length change — **does** alter decoding | **prepared, NOT applied** |
| **(n)** | not a `db.json` defect (testbed gap, harness self-report, cross-experiment label scope) | recorded, no db change |

The (b)/(c) boundary was **verified empirically, not asserted**: after all (a)+(b) edits the
full-corpus strict tokenization is byte-identical to the pre-edit baseline —
**1080 files, 832 clean, 389 368 leftover bytes, 25 382 instructions** before and after
(`work/dbtriage/ab/base_strict.json` vs `.../after_final_strict.json`). That is the same metric
pair EXP-0148 gated on (its move was 803 → 832 files, 395 390 → 389 368 bytes; the live tree
reproduces its endpoint exactly).

---

## 1. Gate results

| gate | before | after |
|---|---|---|
| `python3 tools/agx-isa/roundtrip_test.py` | ALL PASS (302 OK / 0 FAIL) | **ALL PASS (302 OK / 0 FAIL)** |
| `python3 tools/agx-isa/validate_labels.py` | exit 0 | **exit 0** |
| corpus strict clean files | 832 / 1080 | **832 / 1080** |
| corpus strict leftover bytes | 389 368 | **389 368** |
| `docs/isa/encoding-tables.md` | — | regenerated (171 descriptors) |
| `docs/isa/agx3.xml` | — | regenerated, XML parses OK |
| db.json fields | 1036 | 1057 (+21, all from (b) splits) |
| emittable instructions | 38 | **38 — unchanged; no label was promoted** |

`roundtrip_test.py` needed a **field-name-only** edit: its section (B) synthesis table names
fields literally, so a rename breaks it by construction. Every asserted **byte string** in that
file is untouched — see `git diff tools/agx-isa/roundtrip_test.py` (15 insertions, 12 deletions,
all inside field dicts and comments).

`validation.json` was edited **mechanically and only as the gate forces**: `validate_labels.py`
hard-requires an entry per db.json field and forbids entries for fields db.json lacks, so a
field split/rename is impossible without it. Rule followed, encoded in
`work/dbtriage/apply_ab_defects.py`: a **rename** moves the entry verbatim; a **split** copies
the parent's `label`/`target`/`evidence` to each child and narrows only the `range` string to
that child's own bits. **No label was ever strengthened.** `db_sha256` was refreshed, clearing a
pre-existing staleness warning.

---

## 2. Score

**By defect entry** (the per-entry table in §3 is authoritative; each entry is counted once):

| disposition | count |
|---|---|
| defect entries collected across the eight files | **50** |
| **closed by this pass** (an (a) and/or (b) edit landed) | **29** |
| already closed before this pass (EXP-0148 commit `2c93efcb` + earlier orchestrator annotations) | **5** |
| **deferred (c)** — match/length change, prepared and A/B'd, not applied | **11** |
| **(n)** not a `db.json` defect (testbed / harness / label-scope) | **5** |

50 = 29 + 5 + 11 + 5. **34 of the 50 are now closed** (29 this pass + 5 prior). One closed entry —
defect 36, `sfu_marker` — also has a deferred (c) remainder, so the §4 worklist carries **12**
items, not 11.

**By db.json edit operation** (what actually landed, for diff review): **27** (a) semantics
annotations and **43** (b) operations — 12 renames, 11 splits, 7 retypes, 1 enum extension, 6
`emitter_role` marks, 1 `emit_unsafe`, plus the sub-field additions those splits imply — across
**34 descriptors** and **+21 net fields** (1036 → 1057).

---

## 3. The worklist, per experiment

Legend for **status**: `APPLIED` (this pass) · `PRIOR` (already in db.json) ·
`DEFERRED-c` · `NOT-DB`.

### EXP-0138 — float ALU

| # | defect | class | status | what was done / what it rests on |
|---|---|---|---|---|
| 1 | `falu2.mod_lo` is an OPERAND-SOURCE-CLASS field, not a spare 3-bit modifier | **b** | APPLIED | split into `srcA_class` (byte+5 bit0) + `srcB_class` (bits[2:1], enum: 0 GPR / 1 non-GPR file or inline immediate / 2,3 read 0.0). Bit2 dominates bit1. 98 HW cases, run01/05/06 |
| 2 | `falu2.srcB_reg` bit6 is LIVE in uniform mode; 64..127 is an inline 8-bit minifloat immediate | **a** | PRIOR + APPLIED | the orchestrator had annotated it; this pass added the emitter-facing restatement keyed to the new `srcB_class` name (k = v−64, e = k>>3, m = k&7, value = m·2⁻⁵ if e==0 else (8+m)·2^(e−6); HW-confirmed at 10 points) |
| 3 | `sentinel_release` — reading a GPR through falu3/falu3_ext/falu_acc source slots ZEROES it | **n** | NOT-DB | a property of EXP-0138's own MODE-A measurement, and the reason 2–4 cases per field are held at `untested`. A `validation.json` labelling decision, not an encoding defect |
| 4 | `falu3`/`falu3_ext` field NAMES put the destination in a source slot | **b** | APPLIED | renamed `dst_lo`→`dst`, `dst`→`srcA`, `srcA`→`srcB`, `srcB`→`ctrl_len` (retyped reg→mod; its low 2 bits are the 0x09-group length selector), `srcC` unchanged. 1809 + 2321 HW cases; the 28 `srcA`/`srcB` "misses" are bit0-clear values, i.e. 16-bit reads of f32-seeded registers — which *confirms* (reg<<1)\|is32 |
| 5 | `fspecial.src` bit7 (192..255) FAULTS or HANGS the GPU | **a** + **b** | APPLIED | safety note added; `emit_unsafe: true` set. run01: 60 reproducible faults; run05: 192/193/194 each hung 3× under a 12 s watchdog, stopping the arm per FIELD-SWEEP-PROTOCOL §8 |

### EXP-0139 — integer ALU

| # | defect | class | status | what was done / what it rests on |
|---|---|---|---|---|
| 6 | DEF-0139-1 `iunary.operand` is five one-byte sub-fields, not one 40-bit blob | **b** | PRIOR | **verified consistent this pass**: `b1`(+1)/`opsel`(+2)/`dst`(+3)/`op_enable`(+4)/`src`(+5)/`srcdesc`(+6)/`tail`(+7) tile bits 8..64 exactly against `match [0,8,39]`, matching `ibitcount`'s meanings as the defect requires. Round-trip and label checks both clean |
| 7 | DEF-0139-2 `ibfe.width` is taken MOD 32; `offset` is literal — opposite rules | **a** | APPLIED | mod-32 fits 64/64 stable values over dense 0..63; literal/clamp-at-32 fits only 37/64. offset 32..63 shifts the field out (result 0) |
| 8 | DEF-0139-3 `ibitcount.tail`: only bit 2 is load-bearing | **a** | APPLIED | dense 0..255 ×2 gated launches. *The label promotion itself is a `validation.json` decision and is left to the label owner* |
| 9 | DEF-0139-4 EXP-0112's register-aliasing rule does not transfer to `iadd2.dst` | **a** | APPLIED | dst 140/141 (reg 70) does not alias r6; dst ≥ 0xBE (reg ≥ 95) faults reproducibly. Merged with EXP-0146's identical finding |
| 10 | DEF-0139-5 `isel_reg8` is hardware-reachable by construction | **a** | APPLIED | isel8 anchor byte+2 0x0f→0x25 executes deterministically; all 7 fields respond to dense 0..255 |
| 11 | DEF-0139-6 ICMPSEL arm fed the integer vector against a float oracle | **n** | NOT-DB | self-reported harness defect; the captured bytes are sound and scored against the arm's own gated baseline |

### EXP-0140 — mov / control flow

| # | defect | class | status | what was done / what it rests on |
|---|---|---|---|---|
| 12 | `mov_imm` with `imm7 == 12` does not tokenize (byte+1 = 0x0C looks like the 4-byte low-nibble-0xC preamble group) | **c** | DEFERRED-c | annotated; the fix is a **length-rule** change. Only immediate in 0..127 with this property, exhaustive over all 16 dst values |
| 13 | `mov_imm.imm_top` does not write dst and consumes the next 2-byte instruction | **a** | APPLIED | EXP-0128's "silent zero" was a zero-initialised read-back buffer; against a poisoned buffer the register keeps 0xDEADBEEF. The immediate is **7 bits** |
| 14 | `reg_move_c0/c1/c2var/c9/cb` are ONE instruction whose byte+2 is a form selector | **c** | DEFERRED-c | annotated on `reg_move_c1`; collapsing five descriptors is a match change. A/B measured — see §4 C8 |
| 15 | `sel.body` is three located bytes, not one opaque 24-bit field | **b** | APPLIED | split into `b1`(+1) / `b2`(+2) / `selFalse`(+3, bit7 = immediate flag). Per-byte outcome classes recorded from the dense ×2-vector sweep |

### EXP-0141 — memory

| # | defect | class | status | what was done / what it rests on |
|---|---|---|---|---|
| 16 | The atomic RMW **operand register is encoded**, not implicit — DOC-02 ranked it a MISSING field | **b** | APPLIED | on `atomic_mem` **and** `atomic_rmw`: `index_reg` → `index_reg`(7b) + `oper_reg_lo`(byte+5 bit7); `addr_desc` → `oper_reg_hi`(byte+6 bits0-5) + `addr_desc_hi`(bits6-7, don't-care). index = `oper_reg_lo \| (oper_reg_hi << 1)`; all four constructible indices built and read back (7 / 1007 / 2007 / 3007), redirected register consumed each time. Residual unknown (byte+6 = 0x30/0x31) recorded |
| 17 | `device_load.addr_mode` is INERT for a terminal scalar 32-bit indexed load | **a** | APPLIED | 256/256 load correctly, including every enum code. Caveat recorded: only that shape was tested |
| 18 | `device_load.dst_lo`/`dst_ext9` carry NO register information | **a** + **b** | APPLIED | note added; both retyped `reg` → `mod`. 3 constrained bits of 9; identical accepted set at four target registers plus the full 512-value 2-D product. Supersedes EXP-M4-13's dst formula and EXP-0101's copy-verbatim advice |
| 19 | `device_store` byte+2 bit1 selects the DATA SOURCE (context-dependent, not inert) | **a** | APPLIED | inert for ALU-computed data (256/256 — EXP-0119's configuration); with a load-forwarded source only the 128 bit1-set values work |
| 20 | `atomic_mem.rsv10/rsv11`, `atomic_tg.rsv4/rsv6/rsv9` are LIVE, not reserved | **a** | PRIOR | already annotated; `device_load`/`device_store` `reserved7`/`reserved13` confirmed genuinely inert (256/256) |

### EXP-0144 — pack / convert

| # | defect | class | status | what was done / what it rests on |
|---|---|---|---|---|
| 21 | `pack_convert.src` at byte+3 is the **DESTINATION** | **b** | APPLIED | renamed `src` → `dst`; sweeping it redirects the result into 6 distinct registers, an identical map to `cvt_i2f`/`cvt_f2i` `dst` |
| 22 | `pack_convert.fmt_word` is not one 40-bit field | **b** | APPLIED | split into `src_lane0`(+5, reg<<2) / `src_lane1`(+6, reg<<3) / `b7`(+7, rule `(v & 0xfb) == 0x50`) / `cvt_enable`(+8) / `fmt_sel`(+9, enum 0x4x snorm2x16 / 0x8x unorm2x16 / 0xcx unorm8×2). Without it an emitter could choose neither the format nor either source |
| 23 | `unpack_convert.convert_desc` is dst / inert / src / opcode | **b** | APPLIED | split into `dst`(+3) / `inert4`(+4, completely inert over 256) / `src`(+5, reg<<3) / `opdesc`(+6, bits 0,2 == 0,1) |
| 24 | `unpack_convert.reg_sel` is a FORMAT selector, not a register | **b** | APPLIED | renamed `reg_sel` → `fmt_sel`, retyped `reg` → enum with the measured 8-value map. Also annotated: byte+7 **bit3** (top bit of `size`) changes which SOURCE register is read |
| 25 | `unpack_convert` byte+2's real rule is `(byte & 3) != 0` — db.json is **permissive where the hardware is not** | **c** | DEFERRED-c (**inexpressible**) | the `match` language is `(start, width, value)` triples with no OR/mask form, so a 2-bit OR-enable **cannot be written down**. Already documented in `semantics`. Fixing it requires extending the match language — the same blocker as defect 50. Until then it is an **emitter rule, not a decoder constraint** |
| 26 | `cvt_bf16`'s match pins byte+4 == 0x01 but our own compiler emits 0x05 | **c** | DEFERRED-c | A/B measured — see §4 C3 |
| 27 | `cvt_f2h` and `cvt_f2h_dst` are one instruction (identical bit rules on every byte; only byte0's dst nibble differs) | **c** | DEFERRED-c | descriptor merge = match change |
| 28 | Length-rule gaps: `instr_length()` cannot length `byte0 == 0x01` (cvt_f2h_dst with dst nibble 0, emitted by our own compiler) nor `byte0 == 0x18` (packed_half2_hi) | **c** | DEFERRED-c | **this gap subsumes defect 26**: byte0 0x01 has no length at all, so relaxing `cvt_bf16`'s match cannot help until the length rule covers it (proved in §4 C3) |

### EXP-0146 — integer misc

| # | defect | class | status | what was done / what it rests on |
|---|---|---|---|---|
| 29 | `carry_gen.subop` is an OPERAND, not a sub-opcode — the op is a two-operand compare | **b** | APPLIED | byte+1 renamed `subop` → `srcA` and retyped raw → reg; byte+3 `srcA` → `srcB`. Exactly {0x01, 0x81} work — (reg<<1)\|is32 with an inert bit7 |
| 30 | `carry_gen` byte+2's match is over-constrained: real rule `(v & 0xCD) == 0x05` | **c** | DEFERRED-c | annotated; A/B measured — see §4 C2 |
| 31 | A **native 64-bit register-pair ADD exists**; the Apple compiler simply never uses it | **a** | APPLIED | flipping only `addsub` (byte0 0x1f → 0x9f) gives an exact single-instruction 64-bit add, verified on two independent 8-row boundary sets (incl. 2⁶⁴−1 + 1 = 0 and 2⁶³ + 2⁶³ = 0), both gated runs, 5/5 repetitions |
| 32 | `iadd2.dst` faults above register 94 | **a** | APPLIED | merged with defect 9. Corroborates EXP-0020's ~96-entry GPR file from a different family and method |
| 33 | `ilogic` reaches **all 16** two-input boolean functions; `lut_a` is a 2-bit selector | **a** + **b** | APPLIED | `lut_a` split into `lut_a_sel`(bits0-1) / `lut_a_free`(bits2-4, don't-care) / `lut_a_z`(bits5-7, must be clear). `lut_b`'s rule is recorded in prose only, because EXP-0146 warns its 1-D mask is misleading (bit3 *is* function-selecting jointly with lut_a) — **use the joint table**. Labels deliberately **not** promoted by the split |
| 34 | `mov_zext16.src_reg` is inert in the only carrier — UNRESOLVED | **a** | APPLIED | all 128 values + both bit7 values reproduce the zero-extend while `subform` faults on 26 and zeros on 39 — instruction live, field inert. Second-carrier attempt emitted no `mov_zext16`. Contrast recorded: `shift_amt_move`'s byte+1 IS load-bearing (1 of 128) |
| 35 | `n3_mov.srcA_reg` is inert in the only carrier — UNRESOLVED | **a** | APPLIED | same shape; needs a carrier observable at register granularity |
| 36 | `sfu_marker` is NOT a byte-invariant token — both bytes are load-bearing | **a** + **c** | APPLIED (a) / DEFERRED-c | prose refutation applied. Giving it fields requires relaxing the match **and** the length rule — A/B measured, see §4 C7/C7b |
| 37 | `int_alu_ehi` has no own-MSL carrier (second independent attempt) | **n** | NOT-DB | EXP-M4-13's negative result reproduced; all 7 fields stay `untested` |
| 38 | `sr_read_wide` carrier found but not executable | **n** | NOT-DB | **testbed** gap: `agxrun_persist` binds `MTLBuffer`s only and cannot bind an `MTLAccelerationStructure`, so `q.next()` never enters the loop. Concrete next step is in that experiment |

### EXP-0147 — pipeline misc

| # | defect | class | status | what was done / what it rests on |
|---|---|---|---|---|
| 39 | `matrix_mac.b11hi` is typed `raw` but two of its bits are accumulator-SIGN controls | **b** | APPLIED | split into `c_neg_half`(byte+11 bit1, rows 0-3 use −C) / `c_neg_all`(bit2, all rows use −C) / `b11_rsv`(bits3-7). Both set cancels back to +C; correct a·b+c needs both clear (32/128). **The matrix unit computes A·B − C**, a mode Metal never emits |
| 40 | `matrix_mac.dst_desc` is typed `raw` but the rule is simple | **b** | APPLIED | split into `dst_desc_lo`(bits0-5, don't-care) / `dst_en`(bits6-7, enum): correct iff bit6==1 and bit7==0 (64/64) |
| 41 | **`pixel_order` declares `flags` at bits[32:40] AND a match constant pinning those same bits to 0x06** | **c** | DEFERRED-c | the headline defect. Self-contradictory *and* over-constraining: HW accepts 112 (acquire) / 224 (release) values there with the program byte-exactly correct, so every legal encoding with byte+4 ≠ 0x06 is today neither decodable nor emittable. **Two candidate fixes built and measured — both are wrong; see §4 C1/C1b.** This one is genuinely open |
| 42 | `scoreboard_fence.kind` enum incomplete — our own MSL compiles to `07 42 02 00` | **b** | APPLIED | `0x42` added to the enum (role not established). Also recorded: EXP-0147's detection power for this instruction was INSUFFICIENT (general, not ordering-specific, sensitivity), so no field label is raised on it |
| 43 | `tile_read.b6` / `tile_read_mrt.b6` — bit0 is a READ-ENABLE | **b** | APPLIED | split into `read_en`(bit0, enum) / `b6_hi`(bits1-7, don't-care) on **both** descriptors. 128 odd values correct, 128 even values SILENT ZERO. In a BG/EOT program that surfaces as a **black tile**, not a failure |

### EXP-0148 — scaffolding & lengths

| # | defect | class | status | what was done / what it rests on |
|---|---|---|---|---|
| 44 | `falu2_ext8b` models nothing — 100 % length-rule artifact | **c** | PRIOR | descriptor deleted in commit `2c93efcb`; confirmed absent from db.json this pass |
| 45 | `tg_atomic_prep` length 8 should be 10 | **c** | PRIOR | applied as `tg_atomic_prep10`; confirmed present this pass |
| 46 | `half_alu_fma12` match too broad | **c** | PRIOR | `half_compact4` added; `emit_unsafe` retained. Confirmed present |
| 47 | `op04_len8` over-consumes, discriminator NOT FOUND | **c** | DEFERRED-c (**open**) | annotated. Over-consumption directly demonstrated, but six candidate rules all measured **worse** than length 8. byte+1 is not the discriminator. Needs a splice |
| 48 | `cubearray_coord_const` unreachable / over-fitted match | **c** | DEFERRED-c (**open**) | annotated. 0 firings in 1080 files in both walks; its signature sits *interior* to a 12-byte `tex_addr_setup` token in the very kernel it is named after. **Not deleted** without a texture-stage splice |
| 49 | `_r9_succ_safe` makes some lengths depend on the NEXT instruction failing to decode | **n** | NOT-DB | tooling defect, recorded in EXP-0148. A length that depends on a successor's undecodability is a resync heuristic, not a length rule; it makes round-trip a **non-local** test |
| 50 | `operand_word_x2_h5/h6/h7` encode ONE inexpressible constraint | **c** | DEFERRED-c (**blocked**) | annotated on all three. They exist only because `b_alu14_prep2`'s match cannot express its own invariant `byte+1 == (dst<<1)\|1`. **LOAD-BEARING** — deleting them without extending the match language would let genuine data words decode as `b_alu14_prep2`. Same blocker as defect 25 |

---

## 4. The deferred (c) worklist — prepared changes and their A/B results

**Harness.** `work/dbtriage/make_c_variant.py <name>` builds a variant copy of the ISA tree under
`work/dbtriage/cvar/<name>/` with exactly one (c) change applied; `bash work/dbtriage/ab_run.sh
<name>` runs round-trip plus the frozen corpus metrics into `work/dbtriage/ab/<name>/`. The live
`tools/agx-isa/` tree is never touched. This mirrors EXP-0148's `make_variant.py` / `ab_run.sh`.
`work/dbtriage/c_functional_check.py` adds what a corpus A/B cannot supply: does the variant
actually decode the encoding the **hardware** accepts?

All variants: round-trip **302 OK / 0 FAIL**; corpus **832 clean / 389 368 leftover** — i.e.
none of them regresses the frozen metric pair. The interesting signal is in the per-descriptor
firing deltas and in the functional check.

| id | change | round-trip | clean files | leftover bytes | descriptor deltas | verdict |
|---|---|---|---|---|---|---|
| baseline | — | 302/0 | 832 | 389 368 | — | reference |
| **C1** | `pixel_order`: drop match `[32,8,6]` | 302/0 | 832 | 389 368 | none | ❌ **REGRESSES** |
| **C1b** | `pixel_order`: replace the byte+4 pin with a byte+1 discriminator | 302/0 | 832 | 389 368 | `pixel_order` 0→186, `threadgroup_barrier` 280→94 | ❌ **OVER-CLAIMS** |
| **C2** | `carry_gen`: byte+2 match → `(v & 0xCD) == 0x05` | 302/0 | 832 | 389 368 | `carry_gen` 22→25, `n2_op6` 549→546 | ✅ clean gain, **partially blocked** |
| **C3** | `cvt_bf16`: drop the byte+4 pin | 302/0 | 832 | 389 368 | `cvt_bf16` 7→9, `bf_alu` 7→9, `bf_alu8_var` 9→6, `bf_add_dst` 3→2 | ⚠️ mixed; **blocked by defect 28** |
| **C7** | `sfu_marker`: relax the match to the two measured bit rules | 302/0 | 832 | 389 368 | none | ❌ **no effect** (length rule gates first) |
| **C7b** | `sfu_marker`: relax the **length rule** *and* the match on byte+1 | 302/0 | 832 | 389 368 | none | ✅ **strongest candidate** |
| **C8** | collapse the five `reg_move_*` into one `reg_move` | 302/0 | 832 | 389 368 | 497+84+4+93+31 = 709 → `reg_move` 709 (exact conservation) | ✅ **clean** |

### The load-bearing finding: the length rule gates before the match

Four of these are not match changes at all. `instr_length()` is consulted *first*, so a
descriptor's match can never see bytes the length rule rejects:

* **C7** relaxes `sfu_marker`'s match and changes **nothing**, because
  `b0 == 0x06 and b1 == 0x02 → 2` rejects every free-bit encoding before the match runs.
  **C7b** fixes the length rule instead — `(b1 & 0x13) == 0x02 → 2`, placed *below* the
  `rtq_pred` test (0xc2 & 0x13 == 0x02 would otherwise swallow it) — and then `06 ee`, `06 2a`
  and 30 further HW-legal encodings decode, `rtq_pred` is preserved, and no corpus token moves.
  **Not applied only because it is a length change.** It is the cleanest item on this list.
* `sfu_marker`'s byte0 **bit3** (HW-legal `0e 02`) stays **unreachable** either way: byte0 0x0e
  is the stop/end group's own length key. Recorded, not fixed.
* **C2**: byte+2 free bits 1/4/5 also change the *length* verdict for the 0x?2 group
  (`32 01 07 …` lengths to 10, `32 01 27 …` to 8), so the match relaxation reaches only the
  same-length subset. It still buys 3 corpus instructions back from `n2_op6` for free.
* **C3**: `byte0 == 0x01` has **no length rule at all** (defect 28), so the `cvt_bf16` match
  relaxation cannot reach the compiler's own `byte+4 == 0x05` encoding. Defect 28 must land first.

### C1 — `pixel_order`, the headline defect: **both candidate fixes are wrong**

The corpus contains **zero `pixel_order` firings** (it is a raster-order-group fragment op; the
corpus is compute-dominated), so the corpus A/B has **no detection power here at all** — which is
exactly why both variants show identical clean-file and leftover-byte counts while doing very
different things.

* **C1 (drop the pin):** `pixel_order`'s match then *equals* `threadgroup_barrier`'s
  (`[0,8,7] + [16,8,84]`) and loses the most-specific-match tie-break. The compiler's **own**
  `07 14 54 50 06 00` stops decoding as `pixel_order` and becomes `threadgroup_barrier`.
  A strict regression.
* **C1b (byte+1 discriminator):** correct on all four `pixel_order` probes and does not steal
  `mem_fence` — but it moves **186 real corpus `threadgroup_barrier`s** into `pixel_order`,
  because `threadgroup_barrier` also uses byte+1 = 0x04. Byte+1 discriminates the *acquire*
  member (0x14) but **not** the *release* member.

**Handover:** the remaining candidate discriminator is byte+3 (`scope`), whose EXP-0147 legal set
on the release carrier was `0x90-0x9f, 0xb0-0xbf, 0xd0-0xdf, 0xf0-0xff` (64/256) — but the
compiler's own acquire value is 0x50, which is outside that set, so the two arms must be
reconciled before it can be used as a match constraint. This needs a **fragment-stage splice**,
not more corpus fitting. Both variants and their measurements are retained under
`work/dbtriage/cvar/` and `work/dbtriage/ab/` so the next agent starts from the negative results
rather than re-deriving them.

### Prepared but not built as variants

| defect | why no variant |
|---|---|
| 25 `unpack_convert` byte+2 `(b & 3) != 0` | **inexpressible** in the `(start,width,value)` match language (a 2-bit OR-enable). Blocked on a language extension |
| 50 `operand_word_x2_h*` collapse | same blocker: needs a cross-field predicate (`byte+1 == (dst<<1)\|1`) |
| 12 `mov_imm` imm7 == 12 | length-rule change entangled with the low-nibble-0xC preamble group; a candidate hook is stubbed in `make_c_variant.py::c9_mov_imm12` but it needs the group's own dispatch reworked, not a guard bolted on |
| 27 `cvt_f2h` / `cvt_f2h_dst` merge | must land **after** defect 28 (byte0 0x01 has no length rule), and the merged match would then need arbitrating against `cvt_bf16`, which shares byte0's low nibble |
| 28 length-rule gaps (0x01, 0x18) | the prerequisite for 26 and 27; a genuine new length rule, not a relaxation. Needs its own pre-registration |
| 47 `op04_len8` | EXP-0148 already measured six candidate rules, all worse. Needs a splice |
| 48 `cubearray_coord_const` | needs a texture-stage splice; deleting it on corpus evidence alone is unverifiable |

---

## 5. Task 2 — the emittability metric

### The defect

`validate_labels.py` reported **"38 of 171 instructions emittable"**. The denominator was every
descriptor in `db.json`, which mixes two populations:

1. **instructions** an emitter must be able to produce, with operands to choose; and
2. **decode scaffolding** — descriptors that exist only so the tokenizer can account for **data**
   bytes sitting between instructions.

"Emittable" is not *defined* for the second population. Nobody emits a pad word; an emitter emits
an instruction whose encoding happens to include those bytes. Counting them is a **metric
defect, not an ISA gap** — and, as EXP-0148 warned, it "invites someone to *fix* them".

### The correction, and how the exclusion is derived

The excluded set is **not a hand-maintained list in the checker**. Six descriptors already state,
in their own committed `semantics`, the exact phrase **"NOT A STANDALONE HARDWARE OPCODE"** —
and exactly those six do:

`pad_operand`, `operand_word`, `operand_word_a2_01`, `operand_word_x2_h5`,
`operand_word_x2_h6`, `operand_word_x2_h7`.

This pass marks them `"emitter_role": "data-word"` in `db.json` (a key, like `emit_unsafe`, that
no consumer's decode path reads), and `validate_labels.py` gained **hard check 9**: the key and
the phrase must agree in both directions, or the run fails. The exclusion is therefore auditable
per descriptor and cannot silently drift.

### Both numbers

```
EMITTABILITY
  old headline (every db.json descriptor):       38 / 171  (22.2%)
  corrected (emitter-relevant instructions):     38 / 165  (23.0%)
    denominator = 171 descriptors - 6 data words
```

**Derivation:** 171 − 6 = **165**. Numerator **unchanged at 38** — none of the six was ever in
the emittable set, so nothing was added to the top.

**Direction: the number moved UP, by 0.8 percentage points (22.2 % → 23.0 %).** It moved up for
one reason only: six non-instructions left the denominator. No label was promoted, no field was
re-graded, and no descriptor became emittable. **165, not 147** — see below for why the larger
exclusion was rejected.

### What was deliberately NOT excluded, and why

The dispatch floated 147 as a possible honest denominator. I could not get there on the committed
evidence, and I am not going to manufacture it.

* **The 3 continuation-word candidates** (`frame_marker_compact`, `n2_compact2`,
  `b_alu14_prep2`). EXP-0148 records **all three as unresolved**: `frame_marker_compact`'s
  residual 14 firings are unexplained; the `n2_compact2` 12-byte variant was built, measured, and
  **regressed** (round-trip 300/302, 2 files broken), and is filed as "an open lead, not a
  proposal"; `b_alu14_prep2` is explicitly the one place where "a splice genuinely decides (a) vs
  (b)". Excluding them would be claiming a result EXP-0148 declined to claim.
* **`cubearray_coord_const`.** 0 corpus firings, but EXP-0148 refuses to delete it without a
  texture-stage splice, and absence from a corpus is not absence from the hardware.
* **The 13 genuine-but-under-characterized instructions.** These are **real ISA gaps**. Removing
  them would be exactly the inflation the dispatch warns against.

All four of the first two bullets are printed as an explicit **informational lower bound**
(38 / 161 = 23.6 %), clearly labelled *not the headline*.

### A correction to the dispatch's premise

The dispatch said `rtq_pred` and `sfu_marker` "have ZERO fields in db.json". True — but there are
**six** zero-field descriptors, not two:

| descriptor | `_instruction` label | |
|---|---|---|
| `rtq_pred` | tokenization-only | genuinely a fully-pinned 4-byte token |
| `sfu_marker` | tokenization-only | **byte-invariance REFUTED by EXP-0146** — mis-modelled, not un-modelled |
| `n1_word` | tokenization-only | byte-invariant `01 00` |
| `n3_word` | tokenization-only | byte-invariant `03 02` |
| `n2_compact2` | tokenization-only | continuation-word candidate |
| `operand_word_a2_01` | tokenization-only | data word (already excluded) |

I did **not** exclude or promote these. Reasons:

* `sfu_marker` is not "modelling nothing" — it is modelling the **wrong thing**. EXP-0146 proved
  byte0 bit3 and byte+1 bits 2,3,5,6,7 are free. Promoting it to emittable would bake in a
  refuted claim. The fix is C7b, which is a (c) change.
* For a genuinely fully-pinned token like `rtq_pred` there is nothing to synthesize, so the
  `hardware-run` bar ("arbitrary operands executed") is vacuous and arguably it *should* count as
  emittable — but that verdict lives in its `_instruction` **label**, which is a
  `validation.json` decision belonging to the label owner, not a `db.json` one.

All six are now printed as their own bucket by `validate_labels.py`, with `sfu_marker` flagged,
so the label owner can rule on them explicitly rather than having me decide by side effect.

---

## 6. Files changed

| file | change |
|---|---|
| `tools/agx-isa/db.json` | 34 descriptors touched: 27 (a) semantics annotations + 43 (b) operations (renames / splits / retypes / 1 enum extension / 6 `emitter_role` marks / 1 `emit_unsafe`); fields 1036 → 1057 |
| `tools/agx-isa/validation.json` | mechanical mirror of the (b) changes (renames move verbatim, splits inherit the parent label with a narrowed range — **no label strengthened**); coverage block recomputed; `db_sha256` refreshed |
| `tools/agx-isa/validate_labels.py` | corrected emittability metric + hard check 9; both numbers always printed |
| `tools/agx-isa/roundtrip_test.py` | **field names only** in the section-(B) synthesis table; every asserted byte string unchanged |
| `docs/isa/encoding-tables.md`, `docs/isa/agx3.xml` | regenerated by the two `gen_*.py` scripts |
| `work/dbtriage/*` | the idempotent patch script, the (c) variant builder + A/B runner, the functional checker, and all measurements |

Not touched: `docs/` prose, `PROVENANCE.md`, `docs/P0-P1-CLOSURE.md`,
`APPLE9_RE_IMPLEMENTATION_GAPS.md`. Nothing was committed.
(`docs/isa/README.md`, `docs/isa/memory-model.md` and `docs/isa/register-move-and-liveness.md`
show as modified in `git status` — those are **another agent's** edits, not mine; the two `gen_*`
scripts write only `encoding-tables.md` and `agx3.xml`.)

## 7. Limitations

1. **Everything here is desk work.** No hardware was run. Every (a) annotation restates a
   measurement made by the cited experiment on **M4 / G16G**; nothing was promoted to A18/G17P.
2. **A better tokenization is not proof of a length or match rule.** The corpus metric is a
   non-regression gate, and round-trip is blind to over-consumption by construction. Both were
   used here only to show that the applied (b) changes are decode-neutral.
3. **The corpus A/B has zero power for anything the compiler never emits** — proved concretely by
   C1 (`pixel_order`: 0 firings) and C7 (`sfu_marker` free bits: 0 firings). Two variants can post
   identical metrics and do completely different things. Always pair a corpus A/B with a
   functional check.
4. **`validation.json` label decisions were left alone by design.** Several defects (defect 8's
   `ibitcount.tail`, the six zero-field descriptors, `ilogic.lut_a`/`lut_b`'s stale EXP-0013
   labels) imply label changes that belong to the label owner. They are surfaced, not made.
