# EXP-0148 — classification of the 23 "decode scaffolding" descriptors

**Target:** Apple M4 / G16G (own-MSL corpus, compile-only). **Date:** 2026-08-28.
**Method:** desk analysis over `tools/agx-isa/db.json` + a full tokenization of the
1080-file own-MSL corpus (`experiments/EXP-M4-13-full-corpus/hex`, 587 586 bytes), plus a
*continuation test* that searches, for every observed predecessor `P` of a candidate `X`,
for a bit of `P`'s own bytes that predicts whether `X` follows.
**No hardware was run.** Every verdict below is `STRUCTURAL` or weaker; none is `HW-VALIDATED`.

## 0. Verdict summary

| bucket | n | descriptors |
|---|---:|---|
| **(a)** continuation word of a longer parent | **3** | `frame_marker_compact`, `n2_compact2`, `b_alu14_prep2` |
| **(b)** genuine instruction, under-characterized | **13** | `b_alu10_lo7`, `b_alu10_loe`, `b_alu10_lof`, `b_alu14_c83`, `falu_compact4`, `frame_marker`, `n1_word`, `n3_addr_prep`, `n3_word`, `n4_cf_word`, `n4_rt_word`, `spill_frame_marker`, `tg_atomic_prep` |
| **(c)** decoder artifact / not an instruction | **7** | `pad_operand`, `operand_word`, `operand_word_a2_01`, `operand_word_x2_h5`, `operand_word_x2_h6`, `operand_word_x2_h7`, `cubearray_coord_const` |

Of the three Task-2 over-consumers (not part of the 23): `falu2_ext8b` is **(c)** — a pure
length-rule artifact that drops to **zero firings** once the rule is corrected;
`half_alu_fma12` is **(b) with an over-broad match**; `op04_len8` remains **OPEN**.

## 1. The two metrics used, and why

The strict walk stops at the first undecodable byte (so a file is *clean* only if it tokenizes
end-to-end). The resync walk continues past a bad byte by one 2-byte parcel. **Resync statistics
are secondary**: a token whose predecessor is `<gap>` is manufactured, not observed. Every
number below is from the strict walk unless marked otherwise.

Firing counts, baseline vs. the corrected length rule of §4 (`variant_final4`):

| descriptor | strict (baseline) | strict (corrected) | files | distinct byte patterns |
|---|---:|---:|---:|---:|
| `b_alu10_lo7` | 435 | 442 | 116 | 220 |
| `b_alu10_loe` | 52 | 52 | 38 | 31 |
| `b_alu10_lof` | 182 | 182 | 58 | 87 |
| `b_alu14_c83` | 168 | 167 | 48 | 46 |
| `b_alu14_prep2` | 61 | 62 | 49 | 8 |
| `cubearray_coord_const` | **0** | **0** | 0 | 0 |
| `falu_compact4` | 54 | **182** | 92 | 122 |
| `frame_marker` | 120 | 121 | 86 | 25 |
| `frame_marker_compact` | 26 | **14** | 14 | 1 |
| `n1_word` | 80 | 79 | 44 | 1 |
| `n2_compact2` | 16 | 13 | 10 | 1 |
| `n3_addr_prep` | 9 | 10 | 9 | 10 |
| `n3_word` | 50 | 53 | 33 | 1 |
| `n4_cf_word` | 4 | 4 | 3 | 1 |
| `n4_rt_word` | 19 | 19 | 19 | 3 |
| `operand_word` | 251 | 244 | 160 | 120 |
| `operand_word_a2_01` | **0** | **0** | 0 | 0 |
| `operand_word_x2_h5` | 14 | 14 | 10 | 4 |
| `operand_word_x2_h6` | 11 | 11 | 11 | 4 |
| `operand_word_x2_h7` | 6 | 6 | 6 | 2 |
| `pad_operand` | 1163 | 1166 | 350 | 80 |
| `spill_frame_marker` | 2 | 2 | 2 | 1 |
| `tg_atomic_prep` | 34 | 0 (→ `tg_atomic_prep10`, 34) | 34 | 2 |

## 2. (a) — continuation words of a longer parent

The signature of a continuation word is **`P(X follows ‖ P)` ≈ 1 on a bit-selected subset of
the parent, and ≈ 0 on its complement**. A high `P(prev = P ‖ X)` alone is *not* enough: it only
says "X is usually preceded by P", which any scheduling word would satisfy.

### a1. `frame_marker_compact` → parent **`tg_atomic_prep`** (length 8 → 10)

`tg_atomic_prep` has exactly **two** byte patterns in the whole corpus, and **34 / 34** of its
firings are immediately followed by a two-byte word — a perfect partition on `byte+4 bit5`:

| `tg_atomic_prep` bytes | n | `byte+4` | follower |
|---|---:|---|---|
| `0b 00 06 00 20 00 00 14` | 18 | `0x20` (bit5 set) | `pad_operand` `00 00` |
| `0b 00 06 00 00 00 00 00` | 16 | `0x00` (bit5 clear) | `frame_marker_compact` `60 00` |

Separation = **1.000**, n = 34 (`analysis/continuation_final3.json`). The parent is *never*
observed without its trailing parcel, so the trailing parcel is part of the parent. The 8-byte
length is short by exactly 2.

**Independent second derivation.** The `0x?b` group's 10-byte class rule derived in §4
(`(byte+2 & 0x06) == 0x06`) assigns `0b 00 06 …` a length of **10** on op-select grounds alone,
with no reference to the successor statistic. Two unrelated lines of evidence agree.
Applying it absorbs 16 `frame_marker_compact` + 18 `pad_operand` tokens with **zero** change to
any tokenization metric (`raw/ab/variant_final4/`).

The residual 14 `frame_marker_compact` firings are **not** explained: 10 sit in the
`dec2_n8__g_*` intersection-query getters, a region that is visibly desynchronised (see §5), and
4 follow an `n2_compact2` in the `memory_ptr` kernels. `frame_marker_compact` is therefore
classified **(a) for the tg_atomic_prep-adjacent majority, residual UNKNOWN**.

### a2. `n2_compact2` → parent **`simd_shuffle`** (extra-operand form)

Of 127 `simd_shuffle` firings, exactly 7 have `byte+9 bit7` set, and **all 7** are followed by
`02 00`; **0 of 120** with the bit clear are. Separation = **1.000**, n = 127.

```
c7 06 56 00 02 00 02 00 14 a2 | 02 00    sh_rotdown_u32
47 06 56 00 02 00 02 00 14 a2 | 02 00    sh_rotup_u32
47 06 56 04 02 00 04 08 14 91 | 02 00    sg_shuffle_and_fill_u32
c7 06 54 00 02 00 04 08 14 a2 | 02 00    sg_shuffle_and_fill_u32
c7 06 56 04 02 00 02 00 14 91 | 02 00    x_sg_rotate
47 06 54 00 02 00 02 00 14 a2 | 02 00    x_sg_rotate
c7 06 56 00 02 00 06 00 14 a2 | 02 00    sh_rotd
```

The seven carriers are exactly the MSL forms that take a **second value operand**
(`simd_shuffle_and_fill`, `simd_rotate`) — a longer encoding is what the semantics predict.

**Not proposed as a change.** A 12-byte variant was built and measured
(`raw/ab/variant_final5/`) and it **regressed**: round-trip 300/302 (my candidate descriptor's
match out-specified `ibfe`/`lshr_i`) and 2 files broken. The classification evidence stands; the
encoding of the 12-byte form does not. Recorded as an open lead, not a proposal.

The other 6 `n2_compact2` firings have no parent signature and stay UNKNOWN.

### a3. `b_alu14_prep2` → probable **leading** parcel of `b_alu14_c83`

`b_alu14_prep2` is a 2-byte word with 8 distinct patterns, all obeying
`byte0 = (dst<<4)|2`, `byte+1 = (dst<<1)|1`. **61 of 62** firings are immediately followed by
`b_alu14_c83`; the single exception falls inside a region re-tokenized by the newly proposed
`b_alu10_lo6`. 97 % are preceded by a `falu2`.

This is a *prefix*, not a suffix: `prep2` never appears except in front of `b_alu14_c83`.
But the converse fails — only 37 % of `b_alu14_c83` firings are preceded by a `prep2` — so
`prep2` is **not mandatory**, and the corpus cannot distinguish

* **(a)** a 16-byte `b_alu14` form whose first parcel is `prep2`, from
* **(b)** a genuine 2-byte operand-declaration op the compiler always emits before this ALU op.

**This is the one place in the 23 where a splice genuinely decides (a) vs (b)**, and it is
handed over as the designed probe in `RESULTS.md` §7 rather than run under the concurrent-sweep
contamination hazard (`FIELD-SWEEP-PROTOCOL.md` §7). Verdict: **(a)-probable, parent
`b_alu14_c83`, UNRESOLVED pending that splice.**

## 3. (c) — descriptors that model no hardware instruction

### c1–c2. `pad_operand`, `operand_word` — established negative results, correctly modelled

`db.json` already says it plainly: *"NOT A STANDALONE HARDWARE OPCODE … trailing operand /
immediate / SFU-coefficient / inter-op PAD WORD"*, and for `pad_operand`, *"NEGATIVE RESULT —
0x00 is not an opcode"*. They exist so the tokenizer can account for **data** bytes that sit
between instructions. They are real *bytes* but not real *instructions*.

**Recommendation (metric bug, not an ISA bug).** These two, plus `operand_word_a2_01` and the
three `operand_word_x2_h*`, are by construction not emittable and must be **excluded from the
emittability denominator** rather than counted against it. An emitter never "emits a pad word";
it emits an instruction whose encoding happens to include those bytes. Counting them as
un-emittable instructions understates coverage and, worse, invites someone to "fix" them.

### c3–c5. `operand_word_x2_h5` / `_h6` / `_h7` — match arbitration, not instructions

All three carry identical semantics text and exist for exactly one reason: `b_alu14_prep2`'s
match (`byte0` low-nibble 2 **+** `byte+1` bit0) is looser than its own documented invariant
`byte+1 == (dst<<1)|1`. The `match` language is a list of `(start, width, value)` triples and
**cannot express a cross-field constraint**, so the R10 pass encoded the complement as three
separate "out-specifying" descriptors on `byte+1` bits 5/6/7.

They are therefore **(c) artifacts of the match language** — but **load-bearing** ones. Deleting
them without first giving `match` a way to express `byte+1 == (dst<<1)|1` would let genuine data
words decode as `b_alu14_prep2`. Flagged as such in `proposed_db_changes.json`; **no deletion
proposed.**

### c6. `operand_word_a2_01` — dead descriptor

Zero firings in the strict walk, zero in the resync walk, over 1080 files. It is pinned on the
full 16-bit signature `a2 01`. Its provenance cites a 7519-file corpus that includes
permissively-licensed third-party shaders **not committed to this repository**, so I cannot
confirm or refute that it once fired; on the evidence that *is* in-repo it models nothing.
Verdict **(c)**, with that caveat explicit. No deletion proposed (it is inert and its removal
would be unverifiable from committed evidence).

### c7. `cubearray_coord_const` — over-fitted, and unreachable in its own naming kernel

Zero firings in either walk. Its byte signature `f0 c0 04` occurs in exactly 3 corpus files. In
`k_tex_array_cube.hex` — the kernel it is *named after* — the signature sits at byte offset 48,
which is **interior to the 12-byte `tex_addr_setup` token that starts at offset 40**:

```
@40  tex_addr_setup  (12 bytes, spans 40..52)
     ^                        ^ f0 c0 04 signature at 48 — inside it
@52  fspecial
```

So under the committed DB it can never fire. Its length provenance is an EXP-M4-01 *lenprobe
resync* anchor, not hardware, and `DOC-02` already labelled it `tokenization-only`. Its only
exercise is the literal 4-byte string in `roundtrip_test.py`, and that resolution is fragile: it
depends on the `_r9_succ_safe` lookahead guard seeing the *following* bytes fail to decode, so
two unrelated `op04_len8` length experiments in this run silently broke it (`raw/ab/
variant_h5_op04_2/roundtrip.txt`). Verdict **(c) over-fitted match**; it is the textbook case of
the dispatch's third bucket.

## 4. (b) — genuine instructions that merely lack characterization

| descriptor | family it belongs to | why it is real |
|---|---|---|
| `b_alu10_lo7` | **`b_alu10`** — the `0x?b` 10-byte modifier/logic/convert ALU class, keyed by `(byte+2 & 0x06) == 0x06` | 442 firings / 116 files / 220 distinct byte patterns; dst and src register positions located by a reg-sweep (EXP-M4-13 R6) |
| `b_alu10_loe` | same class (`byte+2` low-nibble `e`) | 52 firings / 38 files; the sibling the external engineer's *released* XOR example decodes into |
| `b_alu10_lof` | same class (`byte+2` low-nibble `f`) | 182 firings / 58 files / 87 patterns |
| `b_alu14_c83` | `b_alu14` (14-byte int/simd ALU, `byte+2 == 0x83`) | 167 firings / 48 files / 46 patterns; register operands isolated by a realloc byte-diff |
| `falu_compact4` | float-ALU **compact 4-byte** class, sibling of the HW-VALIDATED `falu_acc` (EXP-0025) | 182 firings after the §5 rule fix (was 54); the op-select-{0,1} class is now coherent |
| `frame_marker` | `n3_mov` compact-move family, `dst = r4` | 121 firings / 86 files; `db.json` establishes it as the dst-r4 instance of an HW-corroborated family, plus the call-site marker role |
| `n3_addr_prep` | texture/image address prep (10-byte low-nibble-3, `byte+2 == 0x27`) | 10 firings, all 10 distinct; `op_variant` co-varies exactly with the image op it feeds (EXP-M4-14 own-MSL) |
| `spill_frame_marker` | `0x60` frame/scope | **length is HW-VALIDATED** (`0x60`→4; `byte+3 = 0xff` faults, others inert); `validation.json` labels it `hardware-run`. Real op, role unresolved |
| `tg_atomic_prep` | `0x?b` 10-byte class (see a1) | 34 firings; real, but its **length is wrong** — see §5 |
| `n1_word` (`01 00`) | compact control/scheduling words | 79 firings / 44 files, byte-invariant; no predecessor separator above 0.05 → not a continuation |
| `n3_word` (`03 02`) | compact control/scheduling words | 53 firings / 33 files, byte-invariant; the one strong-looking separator (`device_load byte+5 bit6`, 10/10) is **refuted** in §5.1 |
| `n4_cf_word` (`04 01 00 00`) | `byte0 == 0x04` group | 4 firings; carve-out from the unresolved `op04` group — real but its length shares that group's open question |
| `n4_rt_word` (`04 XX 20 80`) | `byte0 == 0x04` group | 19 firings / 19 files; same caveat |

For the four byte-invariant words (`n1_word`, `n3_word`, `n4_cf_word`, `n4_rt_word`) the
continuation test found **no** separating bit in any predecessor (best separations 0.05, 0.14,
0.09, 0.31). A word that (i) is byte-invariant, (ii) has no dominant parent, and (iii) has no
parent bit predicting it, is best modelled as a standalone compact op of unknown semantics —
which is exactly what `db.json` already claims. They stay **(b)**, `tokenization-only`, and each
needs a splice, not a re-model.

### 4.1 A refuted continuation candidate, recorded because it looked strong

`n3_word` after `device_load` produced separation 0.994 on `byte+5 bit6` (10/10 with the bit set
are followed by `03 02`). It is **not** a continuation signature. All 10 carriers are in the
`dec2_n8__g_*` intersection-query getters, and their bytes are visibly desynchronised —
`67 81 22 6c 03 42 20 6a 22 c3 a7 81 22 6c` is not a `device_load`, it is a mis-lengthed window
in which the `03 02` word appears *inside* the token. There are also 11 counterexamples with the
bit clear. Reported so the next reader does not re-derive it.

## 5. What changed the numbers: the length-rule corrections

Full derivation, metrics and per-file diffs are in `RESULTS.md` §3–§5. In brief, four rules were
tested against a **copy** of the DB and accepted only when round-trip stayed 302/302 **and**
every tokenization metric improved or held:

1. **`byte0` low-nibble 9** — op-select (`byte+2` bits[2:0]) ∈ {0,1} selects the **4-byte
   compact** form. Must be tested *before* the `6 + 2*(byte+4 & 3)` extension, because for a
   4-byte op `byte+4` **is the next instruction's leader**.
2. **`byte+2` ∈ {0x26, 0x2e}** — use the same uniform `6 + 2*(byte+4 & 3)`; this reproduces both
   hand-patches it replaces.
3. **`byte0 == 0x10`** — the fp16 sibling of rule 1, restricted to the same `byte+2` value set.
4. **`byte0` low-nibble `b`** — the 10-byte class is `(byte+2 & 0x06) == 0x06`, with **no**
   `tg_atomic_prep` carve-out.

Combined result: round-trip **302/302**, clean files **803 → 832**, strict leftover bytes
**395 390 → 389 368**, resync gap bytes **4 902 → 4 548**. **30 files fixed, 1 broken** (and that
one file's alignment is chained off an `op04_len8` token, itself the flagged over-consumer).

Rule 4 also closes a documented open gap: the external compiler engineer's 10-byte "retain
source 0" XOR example `4b 85 16 07 02 08 00 00 00 00`, which `EXP-0099` §6.1 reported as
decodable under **no** family, now decodes as a 10-byte `b_alu10_lo6` — the low-nibble-6 sibling
of the very family its counterpart already decoded into. Its counterpart still decodes
identically.

## 6. Limitations

1. **Everything here is compile-only.** The corpus is our own MSL compiled on the M4; nothing
   was dispatched. Per `docs/evidence-classification.md` no verdict above may exceed
   `corpus-correlation`, and the length rules are `STRUCTURAL`.
2. **A better tokenization is not proof of a length rule.** It is strong evidence that the old
   rule was wrong (30 files that previously could not be tokenized end-to-end now can, with no
   new failures), but the hardware has not been asked. Round-trip is blind to over-consumption
   by construction and is used here only as a non-regression gate.
3. **Absence from the corpus is not absence from the hardware.** The compiler may never emit a
   legal encoding. `cubearray_coord_const`'s 0 firings bound what *this* corpus shows, not what
   the silicon accepts.
4. **The third-party corpus cited by `EXP-M4-13`'s provenance is not in the repository**, so the
   `operand_word_*` counts (n = 7519 files there vs. 1080 here) cannot be reconciled.
5. `b_alu14_prep2` (a3) and the `simd_shuffle` 12-byte form (a2) are the two verdicts that a
   single splice each would settle; both are handed over undone.
