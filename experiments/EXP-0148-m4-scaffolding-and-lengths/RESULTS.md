# EXP-0148 — RESULTS

**Question.** (1) What are the 23 `db.json` descriptors that look like decode scaffolding rather
than instructions? (2) What is the correct modifier/op-select-aware length rule for the three
descriptors flagged `emit_unsafe` under `length_rule_gaps.doc02_over_consumers_20260828`?

**Target.** Apple M4 / G16G. **Corpus.** 1080 own-MSL `_agc.main` hex files
(`experiments/EXP-M4-13-full-corpus/hex`), 587 586 bytes.
**Hardware dispatched: NONE.** See §6 for why, and §7 for the probe handed over undone.

```
Clean-room provenance: OWN-SHADER (corpus is our own MSL, compiled by us)
Inputs inspected: our own compiled shader bytes; our own tools/agx-isa DB and tokenizer
Apple binary introspection: NONE
Reproduction: analysis/*.py, analysis/ab_run.sh (commands in README.md)
Evidence: raw/baseline_tokens*.jsonl, raw/ab/<variant>/{metrics.json,roundtrip.txt,tokens_*.jsonl}
```

---

## 1. Headline

- **The 23 split 3 / 13 / 7:** 3 are continuation words of a longer parent, 13 are genuine
  instructions that merely lack characterization, 7 model no hardware instruction at all.
  Full per-descriptor reasoning: `analysis/scaffolding_classification.md`.
- **`falu2_ext8b` was never an instruction.** It is 100 % an artifact of a length-rule bug.
  Fixing the rule takes it from 45 firings (strict) / 146 (resync) to **zero in both**.
- **The root cause of the whole over-consumer class is identified and it is one sentence:**
  the low-nibble-9 length rule reads `byte+4` to choose 6/8/10/12, but for the *compact* forms
  `byte+4` **is the next instruction's leader byte** — and AGX op leaders overwhelmingly end in
  low nibble `7`/`f` (`&3 == 3` → 12) or `1`/`5`/`9`/`d` (`&3 == 1` → 8). The form must be
  selected from the **leading parcel** before `byte+4` is consulted.
- **Four length-rule corrections were derived and validated** against a copy of the DB:
  round-trip stays **302/302**, clean files **803 → 832**, strict leftover **395 390 → 389 368
  bytes**, resync gaps **4 902 → 4 548**. **30 files fixed, 1 broken.**
- **A documented open gap closes as a side effect:** the external compiler engineer's 10-byte
  XOR example, which `EXP-0099` §6.1 found decodable under *no* family, now decodes.
- **`op04_len8` stays OPEN**, honestly. Its over-consumption is directly demonstrated, but six
  candidate rules all measured *worse* than the status quo. This confirms `EXP-M4-14`'s
  conservative call rather than overturning it.

## 2. Observed (before interpretation)

| metric | baseline | after the four accepted rules |
|---|---:|---:|
| `roundtrip_test.py` OK / FAIL | 302 / 0 | 302 / 0 |
| corpus files tokenizing end-to-end (of 1080) | 803 | **832** |
| strict-walk leftover bytes (of 587 586) | 395 390 | **389 368** |
| resync-walk gap bytes | 4 902 | **4 548** |
| resync-walk `<gap>` records | 2 451 | 2 274 |
| `falu2_ext8b` firings (strict / resync) | 45 / 146 | **0 / 0** |
| descriptors in `db.json` | 170 | 171 (3 added, 2 deleted) |

Per-file: **30 fixed, 1 broken** (`analysis/ab_diff.py isa_copy variant_final4`). The single
broken file, `dec_n8__h2_multi__compute.hex`, has its alignment chained off an `op04_len8`
token — the one over-consumer still unresolved.

## 3. The length rules (interpretation)

### 3.1 Low-nibble-9 (float ALU): op-select selects the form, *then* byte+4 extends it

`byte+2` bits[2:0] is the op-select. The corpus histogram splits cleanly:

| op-select | meaning | length |
|---|---|---|
| 0, 1 | **compact accumulate/move** (`falu_acc` / `falu_compact4`) | **4** |
| 2, 3 | (fma-family sub-forms; left unchanged, not enough evidence) | — |
| 4, 5, 6, 7 | `fadd` / `fmul` / `fma` / `fmul_interp` | `6 + 2*(byte+4 & 3)` |

The seven `byte+2` values the old rule enumerated as compact — `0x18 0x19 0x21 0x30 0x31 0x38
0x39` — are *exactly* values with op-select ∈ {0,1}. They were a sample of a class, hard-coded
as a list. Everything else in that class fell through to the `byte+4` extension and got a
fabricated 8- or 12-byte length.

**Worked example** (`tessellation__pt_tri_linear__vertex.hex`, 248 bytes). Baseline leaves two
gaps. Under the corrected rule the file tokenizes end-to-end with **zero** leftover:

```
@118  09 13 6d 9d 00 c0              falu2      opsel 5 fmul, byte+4=0x00 -> 6
@124  d9 15 29 9d                    compact    opsel 1                   -> 4
@128  39 19 69 9d                    compact    opsel 1                   -> 4
@132  99 9d 24 9f 00 60              falu2      opsel 4 fadd              -> 6
@138  b9 17 39 1d                    compact    opsel 1                   -> 4
@142  a9 b1 34 13 80 08              falu2i     opsel 4, byte+4=0x80      -> 6
@148  99 0f 2e 9f 81 16 02 20        coord fma  byte+4=0x81 -> 6+2        -> 8   (was 6: GAP)
@156  89 11 2e 9f 80 26              coord fma  byte+4=0x80               -> 6
@174  09 01 2e 95 81 16 42 40        coord fma  byte+4=0x81               -> 8   (was 6: GAP)
@182  19 03 2e 95 82 0a 42 00 00 04  coord fma  byte+4=0x82 -> 6+4        -> 10
@202  39 07 3e 15 82 10 42 00 00 0c  coord fma  byte+4=0x82               -> 10
@212  4 x vary_store (8) ... @244 stop(4) = 248  EXACT
```

Note the old rule needed a hand-written special case for the `byte+4 == 0x82 → 10` shape and
another for a literal `0x2e/0x87/0x23 … → 12` signature. **The uniform `6 + 2*(byte+4 & 3)`
reproduces both** (`0x82 & 3 == 2` → 10; `0x23 & 3 == 3` → 12) *and* fixes `byte+4 == 0x81 → 8`,
which neither special case covered. That single change alone moves clean files 803 → 825.

### 3.2 `byte0 == 0x10` (native fp16): the same compact form, but the byte is overloaded

**Worked example**, `dec2_nf_simd__sp_isum_f16__compute.hex`, 48 bytes total:

```
get_sr(4) + device_load(14) + simd_reduce(8) + `10 02 18 03`(4) + device_store(14) + stop(4) = 48
```

The 14 bytes after the compact word are `e7 00 54 02 00 00 21 00 01 00 00 10 11 00`, which
matches the canonical committed `device_store` shape byte position for byte position
(`byte+2 = 0x54`, `byte+6 = 0x21`, `byte+12 = 0x11`). The fixed 12-byte length swallowed that
store's leader — precisely the DOC-02 symptom.

**But the broad generalisation is REFUTED here.** Applying the full op-select-{0,1} rule (as in
§3.1) broke 7 files. `byte0 == 0x10` is **overloaded**: it is also a legal low-nibble-0 two-byte
operand/pad word. In `tessellation__pt_tri_linear__fragment.hex` @36 the correct parse of
`10 00 49 a1 34 05` is `10 00` (2-byte word) + `49 a1 34 05 80 00` — a real 6-byte `falu2`
with op-select 4 (`fadd`) — not a half-ALU op with the nonsensical op-select 1. So the accepted
rule is restricted to the same `byte+2` value set as the 0x09 group. **Do not widen it without
new evidence**; that negative is recorded in `proposed_db_changes.json` L3.

### 3.3 `byte0` low-nibble `b`: the 10-byte class is `(byte+2 & 0x06) == 0x06`

The dispatch enumerated `byte+2` low nibbles `{7, e, f}` (plus `0x17`). Written as a bit test
that set is `(byte+2 & 0x06) == 0x06`, which additionally admits low nibble **6** — and low
nibble 6 is exactly the case `EXP-0099` §6.1 could not decode:

```
"retain source 0"  4b 85 16 07 02 08 00 00 00 00   baseline: UNDECODABLE (byte0=0x4b)
                                                   corrected: b_alu10_lo6, length 10   ✔
"both released"    4b 05 1e 07 02 08 00 80 00 00   baseline: b_alu10_loe, length 10
                                                   corrected: b_alu10_loe, length 10   (unchanged)
```

The two examples differ only in `byte+2` bit 3 (`0x16` vs `0x1e`), which is why one decoded and
one did not: they are siblings in one class the dispatch had split. `length_rule_gaps.b_alu10`
can be marked RESOLVED — as a **coverage** gap; the class's field semantics remain
`corpus-correlation`.

### 3.4 `tg_atomic_prep` is 10 bytes, derived twice independently

All 34 corpus firings are followed by a two-byte word, on a perfect `byte+4 bit5` partition:

| bytes | n | follower |
|---|---:|---|
| `0b 00 06 00 20 00 00 14` | 18 | `pad_operand` `00 00` |
| `0b 00 06 00 00 00 00 00` | 16 | `frame_marker_compact` `60 00` |

Separation 1.000, n = 34. The parent is never seen without its trailing parcel. Independently,
the §3.3 class rule assigns `0b 00 06 …` length 10 on op-select grounds with no reference to
successors. Two unrelated derivations agree; applying it absorbs 34 phantom tokens with **zero**
change to any tokenization metric.

## 4. `op04_len8` — the over-consumption is real, the rule is not found

Direct structural counterexamples (from `frag_output__mrt8_float__fragment.hex`):

```
04 00 | d9 a1 2c 83 80 00 | c9 a1 2c a1 80 00     a 2-byte word + TWO clean 6-byte falu2i
04 00 | e1 19 1c 81 06 02                          a 2-byte word + a clean 6-byte cvt_f2h
04 00 | 87 02 54 00 06 00                          a 2-byte word + a clean frag_tile_setup
```

So `04 XX` is often 2 bytes — consistent with `byte0` low-3-bits `0b100` being the
`get_sr`/`mov_imm` datapath family, of which `0x0c` (`mov_imm`) is the 2-byte member and `0x04`
its bit-3-clear sibling. **Yet every rule tested measured worse:**

| candidate | clean files | strict gaps | resync gaps | round-trip |
|---|---:|---:|---:|---|
| *(status quo: flat 8)* | **832** | **389 368** | **4 548** | 302/302 |
| flat 2 | 830 | 389 976 | 4 588 | **301/302** |
| flat 4 | 830 | 390 046 | 4 638 | 302/302 |
| `4 if (byte+1 & 2) else 2` | 831 | 389 586 | 4 636 | 301/302 |
| `2 if byte+1==0 else 8` | 832 | 389 410 | 4 586 | 301/302 |
| `2 if byte+1==0 else 4` | 831 | 389 586 | 4 642 | 301/302 |
| `8 if (byte+1 & 2) else 2` | 831 | 389 746 | 4 590 | 301/302 |

`byte+1` is not the discriminator. **Verdict: OPEN, keep length 8, keep `emit_unsafe`.** This
reproduces and confirms `EXP-M4-14`'s conclusion from an independent direction rather than
overturning it.

## 5. Negative and refuted results (kept deliberately)

1. **`byte0 == 0x10` broad op-select rule — REFUTED** (7 files broken). §3.2.
2. **`simd_shuffle` 12-byte form — NOT ACCEPTED.** The *classification* evidence is perfect
   (7/7 with `byte+9 bit7` set are followed by `02 00`; 0/120 without; the 7 carriers are exactly
   the extra-operand `simd_shuffle_and_fill`/`simd_rotate` MSL forms). But the encoding regressed:
   round-trip 300/302 and 2 files broken. Recorded as an open lead, not a proposal.
3. **`n3_word`-after-`device_load` — REFUTED.** Separation 0.994 looked like a strong continuation
   signature; all 10 carriers turn out to be inside a desynchronised region of the
   `dec2_n8__g_*` getters, and 11 counterexamples exist. Reported so it is not re-derived.
4. **`cubearray_coord_const` fires 0 times in 1080 files**, and in its own naming kernel the
   `f0 c0 04` signature sits at offset 48 — *interior* to the 12-byte `tex_addr_setup` token
   spanning 40..52. It cannot fire.
5. **A tooling defect worth more than the descriptor:** `cubearray_coord_const`'s 4-byte length
   comes from the `_r9_succ_safe` guard, i.e. it depends on the *following* bytes failing to
   decode. Two unrelated `op04_len8` experiments here silently flipped it to 2 and dropped
   round-trip to 301/302. **A length that depends on a successor's undecodability is a resync
   heuristic, not a length rule**, and it makes `roundtrip_test.py` a non-local test.

## 6. Why no hardware was run

The dispatch authorises hardware "only where a splice would decide between (a) and (b)". Two
such cases exist (§7). Both were left undone because:

1. Three GPU-contending experiments (EXP-0139, EXP-0141, EXP-0146) were live, and
   `FIELD-SWEEP-PROTOCOL.md` §7 now records that concurrent sweeps contaminate each other
   (EXP-0143 command buffers became "innocent victims"; EXP-0147 hit a fault cascade). A fault
   observed under contention is not attributable, and the Prime Directive prefers **no** result
   to a tainted one.
2. Nothing in Task 2 needed hardware to make progress: the decisive evidence was structural, and
   the accepted rules are gated on a full round-trip plus a 1080-file A/B with a per-file diff.

**The carrier was built and verified** so the successor is cheap. `add.bin`, compiled from our
own `kernels/add.metal`, has `_agc.main` at file offset 7344, 56 bytes, tokenizing as
`get_sr(4) · device_load(14) · device_load(14) · falu2 09 01 1c 05 00 c0 @0x20 · device_store(14) · stop`
— so the splice point is `_agc.main+0x22`. The build outputs and the archive are **not
retained**: they rebuild in seconds and `experiments/**/agxrun*` is not covered by
`.gitignore`, which has leaked harness binaries into commits before. Exact rebuild commands and
the verified layout: `work/hw/README.md`. **No spliced code was dispatched.**

## 7. The two probes handed over undone

### HW-LEN-1 — does the op-select field control instruction length? (decides §3.1 on hardware)

Splice at `_agc.main + 0x22` (the `falu2` op-select byte and the three after it), then read back:

| case | bytes at `+0x22` | resulting stream if op-select selects a 4-byte form | predicted output |
|---|---|---|---|
| baseline | `1c 05 00 c0` | one 6-byte `fadd` | `a + b` |
| **A1** | `20 05 0c 55` | `09 01 20 05` (4) + `0c 55` = `mov_imm r0, 85` | out bits = **85** |
| **A2** | `20 05 0c 33` | same, immediate 0x33 | out bits = **51** |
| **A3** | `29 05 0c 55` | op-select 1 | out bits = **85** |
| **A6** | `21 05 0c 55` | positive control — already 4 under *both* rules | out bits = **85** |
| **F1** | `1c 05 0c 55` | op-select 4: 6 bytes under both rules, `mov_imm` never runs | **≠ 85** |

A1 vs F1 differ in **one byte** (`0x20` vs `0x1c`) and nothing else. If A1 reads 85 and F1 does
not, the op-select field demonstrably controls how many bytes the hardware consumes. A2 is the
causal control (the output must track the immediate, not merely be "not `a+b`"). Extending the
`byte+2` splice over all 256 values makes this a dense `hardware-run` sweep of the op-select /
op-flags byte against the length outcome: the prediction is out == 85 for exactly the 64 values
with `byte+2 & 7 ∈ {0,1}`. `mov_imm` immediates are 0..127 only (EXP-0128).

### HW-PREP2 — is `b_alu14_prep2` a leading parcel of `b_alu14_c83`, or its own op?

Corrupt the `prep2` word in a carrier containing `prep2 · b_alu14_c83` and observe whether the
**following** `b_alu14_c83`'s result changes. If it does, `prep2` is part of that instruction
(bucket **a**); if the effect is confined, it is its own op (bucket **b**).

## 8. Limitations

1. Compile-only. Nothing exceeds `corpus-correlation`; the length rules are `STRUCTURAL`.
   A better tokenization is strong evidence the old rule was *wrong*; it is not proof the new one
   is *right*.
2. Round-trip is blind to over-consumption by construction (the swallowed byte is re-emitted
   verbatim) and is used here **only** as a non-regression gate, never as evidence.
3. Absence from the corpus is not absence from the hardware.
4. Op-selects 2 and 3 in the low-nibble-9 group were left untouched — no evidence either way.
5. The third-party corpus cited by `EXP-M4-13`'s provenance (n = 7519 files) is not committed, so
   its `operand_word_*` counts cannot be reconciled with the 1080 files available here.

## 9. Verdict

**Task 1: COMPLETE** (desk). 3 continuation words / 13 genuine / 7 non-instructions, each with
its evidence — `analysis/scaffolding_classification.md`, `analysis/field_verdicts.json`.

**Task 2: 2 of 3 RESOLVED, 1 OPEN.** `falu2_ext8b` resolved (it was never an instruction);
`half_alu_fma12` partially resolved (compact form recovered, 12-byte arithmetic form confirmed
correct, stays `emit_unsafe`); `op04_len8` **OPEN** with six candidates eliminated.
Bonus: `length_rule_gaps.b_alu10` (the EXP-0099 XOR example) **RESOLVED**.

Proposed changes for the orchestrator to apply mechanically:
`analysis/proposed_db_changes.json` — 4 length-rule patches, 3 descriptor additions,
2 deletions, 5 metadata updates, 6 flagged-not-changed items.
