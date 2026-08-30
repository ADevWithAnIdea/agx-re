# EXP-0212 — triage of the 42 queued items

Produced **before** any file was changed. Columns: **class** is (a) non-span correction,
(b) span-moving correction, (d) match-bit correction, (c) refused or applied only in part.
"Evidence located" means the cited raw/derived artifact resolved on disk
(`analysis/evidence_check.txt`); every one of them did.

## Summary

| class | count |
|---|---|
| (a) non-span — prose / enum / field note | **28** |
| (b) span-moving — a span narrows, splits, or a field appears | **6** |
| (d) match-bit — tokenization-affecting | **3** |
| (c) refused outright | **6** |
| *of the applied, those applied only IN PART (the stronger half refused)* | *6* |
| **total items triaged** | **42** (31 machine-extracted + 11 prose-tail) |

`half_pack.byte0` is counted once, under (d); it is both a match relaxation and a new field.

## A — non-span corrections (28). Cannot invalidate an existing verdict.

| # | item | experiment | applied as |
|---|---|---|---|
| 1 | `DEF-0201-1` `falu3_srcmod12.opsel` overlaps match `[17,1,1]`; encodable range 4 not 8 | 0201 | field note. **Span NOT changed** — the two free bits (16, 18) are non-contiguous, so no single `(start,width)` expresses them |
| 2 | `DEF-0201-2` `falu3.op` low-3 class 5 is a MULTIPLY BY ZERO; classes 0/1/2 refuted | 0201 | field note |
| 3 | `DEF-0201-3` `copysign` byte+3 is live but does not encode the operand ROLE | 0201 | field note |
| 4 | `OBS-0201-1` `falu3` flushes denormal operand and/or result | 0201 | semantics |
| 5 | `OBS-0201-2` `fspecial_est.subop` enum provenance flag | 0201 | field note. **Enum NOT changed** — the item is explicitly a compiler observation, not a hardware claim |
| 6 | `DEF-0202-2` `ibitcount.dst` bit 0 is not the index; `dst[7:6]==0b11` is illegal | 0202 | field note. **Span NOT narrowed to (25,7)** — a narrower span cannot express the `[7:6]` illegality |
| 7 | `DEF-0202-3` `shift_amt_move` / `b_alu10_lo7` `.src_flag` enum is inherited, not observed | 0202 | field notes on both. Enum kept; the item itself says "NOT a request to remove the enum" |
| 8 | `DEF-0202-4` `ibitcount.form` enum incomplete (21 observed) | 0202 | enum value added with its role explicitly unnamed, plus a note |
| 9 | `half_pack.length_gate` — hardware consumed 4 bytes for all 256 byte+1 values | 0203 | semantics. **`isadb.py` length rule NOT changed** — that is the length-rule owner's file; this is the second independent measurement asking for it |
| 10 | `half_pack.source_release` | 0203 | semantics |
| 11 | `half_pack.write_target` — writes the HIGH 16 bits, preserves the LOW | 0203 | semantics |
| 12 | `simd_ballot.pred` inert over its full range; form selection is elsewhere | 0205 | field note. **Field NOT changed** — the item says "needs its own gated experiment before db.json is changed" |
| 13 | `simd_reduce.dtype` decoded width is context-dependent, at most 6 bits | 0205 | field note. **Span NOT narrowed** — bit 4 is `f16_incl_scan` in the enum and none of the four carriers is fp16, so the inertness observation has no detection power in the dimension bit 4 would control (§7) |
| 14 | `simd_reduce.op` x `dtype` are not independent | 0205 | semantics (field-dependency edge) |
| 15 | `call.b6` bit-1 rule is carrier-dependent, refuted by our own compiled bytes | 0206 | field note |
| 16 | `ret` / `ret_luse` `.linkmode` accepted set is `v & 3 == 2`; 4 and 5 FAULT | 0206 | enum rewritten + field note, on both descriptors |
| 17 | `stop` final word IS executed; a CF leader in byte 0 faults | 0206 | semantics |
| 18 | `dev_scoreboard_fence` "the compiler inserts it..." is unsupported | 0207 | semantics |
| 19 | `frag_color_store` `[[sample_mask]]` form emits nothing and does not tokenize | 0207 | semantics (gap recorded) |
| 20 | `get_sr.dst_hi` is NOT the destination-register extension | 0207 | semantics refutation + field note |
| 21 | `get_sr.form` is a READ-ENABLE conditional on `dp_width` | 0207 | field note |
| 22 | `mesh_out_src.sel` — 129 of 256 values suppress the draw | 0207 | field note (hazard map only; the other 127 are carrier-undecidable, not inert) |
| 23 | `vary_slot` documented slot role REFUTED against a firing control | 0199 | semantics. **Match NOT relaxed** — EXP-0199 itself leaves the wider family unresolved |
| 24 | `tex_sample.mode` is a bitfield, not an enum; `0x10` inert; bit 5 context-dependent | 0204 | enum rewritten + field note |
| 25 | `cubearray_coord_const` is shadowed by `pad_operand`, not absent | 0204 | semantics |
| 26 | `tex_write.rsv10` is the write's mip level | 0204 | field note. **RENAME REFUSED** — see §C |
| 27 | `n4_rt_word` / `rtq_pred` swept sites are byte +6 of 10-byte instructions | 0200 | semantics (site re-attribution on both) |
| 28 | `n4_cf_word` is shadowed by byte +2 of a 6-byte `pop_reconverge` | 0200 | semantics |

## B — span-moving corrections (6 defects → 5 moved spans, 13 new fields)

| # | item | experiment | span move |
|---|---|---|---|
| 29 | `half_alu_fma12.ext` is not one 64-bit field | 0203 | `ext` **(32,64) → (48,48)**; new `lensel` (32,2), `mods` (34,6), `srcC` (40,8) |
| 30 | `half_alu_fma12.byte4_modifiers` | 0203 | folded into the same split as `mods` |
| 31 | `simd_reduce.op` — only bits [2:0] are decoded | 0205 | `op` **(8,8) → (8,3)**; new `op_hi` (11,5) |
| 32 | `DEF-0202-1` `irotate.operands` is five one-byte sub-fields | 0202 | `operands` **(24,40) → (48,8)**; new `rot_dst` (24,8), `op_enable` (32,8), `rot_src` (40,8), `amt_tail` (56,8) |
| 33 | `pop_reconverge.reserved` is two fields | 0206 | `reserved` **(32,16) → (32,8)**; new `reserved_hi` (40,8) |
| 34 | `sfu_marker` byte0 match tightening (listed under D) also moves `b0_hi` | 0199 | `b0_hi` **(3,5) → (5,3)** |

## D — match-bit corrections (3). Tokenization-affecting; each measured A/B.

| # | item | experiment | change | measured corpus effect |
|---|---|---|---|---|
| 35 | `half_pack.byte0` pins all 8 bits, so every db-expressible encoding writes r1 | 0203 | `match [0,8,24] → [0,4,8]`; new `dst` (4,4) | none (strict and resync identical; `half_pack` stays at 21 firings) |
| 36 | `sfu_marker` declared match admits 32 values, 8 are accepted | 0199 | `match [0,3,6] → [0,5,6]` | **31 resync tokens move `sfu_marker` → `operand_word`** (116 → 85 firings). No change to clean files, leftover bytes, boundaries or instruction count |
| 37 | `frag_depth_store` byte+1 needs 2 bits; byte+2's match is not enforced at all | 0199 | `match [0,8,215],[8,8,20],[16,8,84] → [0,8,215],[9,2,2]`; the old pins kept in `match_notes`; freed bits given fields `b1_lo` (8,1), `b1_hi` (11,5), `b2` (16,8) | none |

## C — refused outright (6)

| # | item | experiment | why refused |
|---|---|---|---|
| 38 | `MISSING-DESCRIPTOR-non-leaf-epilogue` — add a descriptor for `ef 02 54 00 00 50` | 0206 | A new mnemonic needs an `_instruction` **label**, which is the orchestrator's call and is out of scope here. The evidence is also a census/corpus observation of where our compiler emits the word — real, but with no semantic model, no length proof by insertion, and no field map. Recorded, not invented. |
| 39 | `harness.anchor_loss` | 0203 | **Not a db defect.** It is a self-reported bug in EXP-0203's own committed harness. Editing a completed experiment's harness retroactively would break its reproduction record, and the item's own impact statement is "NONE on any verdict" (cross-run agreement 2047/2048 on the affected arm). |
| 40 | `get_sr.sr_sel[168]` — 168 is a grid size in threads, not a threadgroup count | 0207 | Its own status line says **one dispatch shape tested**. One shape cannot rewrite an enum. Recorded as a candidate in the field note; the enum is unchanged. |
| 41 | `frame_marker_compact` declared 2-byte length refuted; 4-byte form correct 7/7 | 0199 | A **length** change. Measured A/B (`work/var_L2`): clean files 841 → **838**, strict leftover 387,692 → **388,102** (+410), instructions 25,634 → **25,565** (−69). A REGRESSION, and it lands exactly where EXP-0199 bounded itself: its 7 boundaries were straight-line compute insertion, while the corpus `60 00 <nonzero>` sites are threadgroup-atomic and divergent-CF contexts it did not re-test. Recorded in the descriptor's semantics with the full numbers. |
| 42 | `icmpsel` is 10 bytes, not 14 | 0200 | Blanket change refused: every HW-VALIDATED 14-byte instance (EXP-0013 whole programs `icmp_lt`/`ucmp_lt`/`fcmp_lt`) has byte+2 `0x1d`, and both 10-byte hardware sites have byte+2 `0x2d`. A narrow candidate (`b2==0x2d → 10`) was measured and **improves** the corpus — see RESULTS §6 — but it is a length-rule change and is handed to that owner rather than taken here. |
| 43 | `icmp_pred` at `rq_bbox`+960 is 10 bytes, not 6 | 0200 | **One site.** The 6-byte reading is HW-anchored elsewhere (EXP-0010, in running control-flow programs). Changing `length` would break every 6-byte instance. No discriminator is established. Recorded in semantics. |

*(items 42/43 and the `n4_*` re-targeting are counted once each across A and C: the
re-attribution prose IS applied, the length change is not.)*
