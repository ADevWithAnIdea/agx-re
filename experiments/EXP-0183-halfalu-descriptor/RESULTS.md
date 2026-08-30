# EXP-0183 — RESULTS

**Status: COMPLETE. `tools/agx-isa/db.json` is STABLE** (sha256
`2412eac1cad4449eb385702062abd03e5c926d04f7d384e6bf3684c9c4c7c6c4`).

**PURE ANALYSIS — no device, no SSH, no GPU.** Every observation is re-read from committed
raw. Everything below is a **G17P** claim except where a row is explicitly M4.

## 0. The gate, before and after

| tree | clean | leftover | tokens | roundtrip | anchor-decode |
|---|---|---|---|---|---|
| `work/base_head` — git HEAD **at dispatch time** | 833/1080 | 388,604 | 25,419 | ALL PASS | — |
| `work/base_live` — HEAD after EXP-0182 landed (my baseline) | 840/1080 | 387,496 | 25,587 | ALL PASS 302/0/0 | 249/255, MUST-PASS `cvt_bf16` **FAIL** |
| **live, after this experiment** | **841/1080** | **387,214** | **25,634** | **ALL PASS 302/0/0** | **250/255, ALL PASS, 5 FIXED, 0 REGRESSED** |

**No regression on any axis; every axis improved.** The dispatch's baseline (833 / 388,604 /
25,419) was one uncommitted tree stale — it is git HEAD's, not the working tree's. Both are
recorded so the number is reconciled rather than contradicted.

`validate_labels.py` exits 0 with the WARN and the 18 enumerated violations listed in §6;
those are the rows I orphan and create, and `analysis/validation_updates.json` closes every
one of them — proven, not asserted: applying that file to a scratch copy and recomputing
coverage with the orchestrator's own `work/merge_verdicts.py` yields a `validation.json` that
passes `validate_labels.py` with **zero FAILs and zero WARNs** (`work/validation_simulated.json`).

---

## 1. Per defect: what db.json said, what the hardware says, did MY re-derivation confirm it

### DEF-0180-1 — the destination is byte0's HIGH NIBBLE  → **CONFIRMED, and strengthened**

**db.json said:** `half_alu`, `half_alu_ext8` and `half_alu_fma12` all carried
`match [[0,8,16]]`, pinning the whole of byte0 to `0x10`, with `dst` at bits 8..15.
**An emitter following that descriptor could only ever write `r1`, and the field it called
`dst` is a source.**

**My re-derivation — three independent routes, none of which imports EXP-0180's analysis:**

1. **DSTNIB deltas, recomputed from `pre`/`post`.** `byte0 = n<<4`, n = 0..15, two carriers,
   both gated runs. The result lands in `r[n]`'s LOW 16 bits with `r[n]`'s HIGH 16 bits
   preserved. **16 of 16 per-value records identical across the two runs on both carriers.**
   Category counts (`analysis/defects_rederived.json → H1_dstnib`):

   | carrier | confirmed | low-half only | masked | refuted |
   |---|---|---|---|---|
   | C_HI | 0,1,2,3,4,5,6,7,8,9,11,12,13,14 | 10 | 15 | **none** |
   | C_LO | 0..12 | — | 13, 14, 15 | **none** |

   **A correction to EXP-0180's own write-up, which I am obliged to report:** it says "two
   exceptions, both harness artefacts" and names `n=15` and, on C_LO, `n=13`. There is a
   **third**: C_LO `n=14`. It is explained by the same authored harness (`R_ZERO = 14` is the
   pad/zero register, `build_program(pad_reg=R_ZERO)`, `slack() = mov_imm(R_ZERO,0)*4`), and
   C_HI — which has no post-block padding — confirms `n=14` cleanly. The defect is unaffected;
   the exception count in EXP-0180's RESULTS.md is one short.
   **`n=15` is UNOBSERVABLE on both carriers** (`R_IDX = 15` is re-seeded to 0 before every
   store) — a carrier limit, not a hardware property, and exactly the limit EXP-0168 recorded
   for `falu2.dst`.

2. **An independent control that makes the masking a measurement rather than a story:**
   across the whole of `g17p_run02`, **r15 is never non-zero in any of the 16,335 observed
   cases**, and **r14 is non-zero in exactly ONE of 11,115 C_HI cases — the DSTNIB `n=14`
   case itself.** The only thing in the entire run that ever put a value in r14 was
   `byte0 = 0xe0`.

3. **H1b2, the strongest check, and it lands on the SIX-BYTE `half_alu` rather than the
   8-byte sibling the DSTNIB arm used.** EXP-0180's seed program emits fourteen six-byte
   half-adds, `[j<<4] [h_B] [(opflags<<3)|4] [h_A] [0x00] [0xC0]`, and **nothing but byte0
   names register j**. Every gated case dumps all 16 GPRs before the block, so each case
   re-proves where those fourteen writes landed. The per-case identity
   `pre[j].lo == fp16(h[byte+1] + h[byte+3])` for j = 0..13 holds in
   **228,690 checks per run, ZERO mismatches, in both runs** (457,380 total).

4. **H1c, arithmetic.** `r[byte0>>4].lo = fp16(h[byte+1] × h[byte+3] + h[byte+5])` reproduces
   the observed result on **both** carriers in **both** runs (C_HI 1.625 × 2.59375 + 2.84375 =
   7.0586 = `0x470f`; C_LO −0.0625 × 5.5 + 0.46875 = 0.125 = `0x3000`), with the anchor's own
   operand triple recovered by brute force over all 32 half-registers as a control. db's `dst`
   appears as a **source**; **byte+4 does not appear at all**.

**Beyond the defect as filed — three things my re-derivation establishes that EXP-0180 did
not claim:**

* **byte+5 is the fma's THIRD OPERAND**, not the "largely inert" `b5` the descriptor called
  it. Corroborated twice: the identity above, and the `mul_suppress` observation in §1c.
* **byte+1 and byte+3 are the two sources of the 6-byte form**, from the seed identity.
* **`half_alu.srcB` at byte+4 is REFUTED as an operand.** The seed instructions all carry
  byte+4 = `0x00` = h0 = **r0's LOW half, which is non-zero in all 32,670 observed
  pre-vectors**, and it does not enter the sum. That retires EXP-M4-14's byte+4-is-srcB
  reading for this form — and EXP-M4-14 has no committed raw tree at all (EXP-0164).

**What I changed.** `match [[0,8,16]] → [[0,4,0]]` on all three; `dst` added at bits 4..7;
bits 8..15 renamed `dst → srcA`; bits 24..31 `srcA → srcB`; `half_alu` bits 32..39
`srcB → ctrl`; `half_alu_ext8` bits 40..47 `b5 → srcC`. The naming follows the low-nibble-8
sibling `h_alu_hi`, which db.json already models exactly this way.

**One place the round trip earned its keep, recorded because §3(b) of the protocol says it
usually does not.** Relaxing the `match` *without* adding the `dst` field
(`work/cand_half_match`) improves the corpus by exactly as much as the full change
(841 / 387,214 / 25,634) and **fails the round trip**: the fixture `10 85 24 84 00 c0`
re-assembles as `00 85 24 84 00 c0`, because bits 4..7 became unmodelled — pinned by nothing
and named by no field. The corpus alone would have accepted that. It is a narrow win (it
catches *unmodelled* bits, not wrong ones) but it is a real one, and it is why the match
relaxation and the `dst` field must land together.

**Before/after, on the bytes our own GPU EXECUTED** (`analysis/halfdst_decode_check.py`, the
32 distinct DSTNIB byte strings):

| | decodes | as `half_alu_ext8` | `dst` field == byte0 high nibble |
|---|---|---|---|
| before | 7 of 32 | **2** | **0** |
| after | 26 of 32 | **21** | **21** |

The residue is bounded and is not mine: destinations 0, 3, 9 and 11 (byte0 `0x00/0x30/0x90/0xb0`)
are excluded by `isadb.instr_length` on purpose — 0x30/0x90/0xb0 are the texture SAMPLER
leaders and byte0 alone cannot separate them from a half ALU writing r3/r9/r11 (EXP-0182's
documented residue). Three further cases decode as the 2-byte `pad_operand`, **identically
before and after** — a pre-existing length decision, not a regression.

### DEF-0180-2 — the length rule  → **CONFIRMED EXACTLY, and DELIBERATELY NOT APPLIED AS CODE**

**db.json said:** `length_rule.byte0_table["0x10"] = "6, or 8 if (byte+2 & 0x02)"`.

**My re-derivation.** Length read off the four-marker chain at byte +6
(`length = 14 − 2 × hw_markers`), keyed on (opsel = byte+2 & 7, m = byte+4 & 3):

```
opsel          m=0   m=1   m=2   m=3
0,1,2,3,7       10    10    10     8
4  (hadd)        6     8    10     6
5  (hmul)        6     8    10     8
6  (hfma)        6     8    10    12
```

**32 of 32 cells covered, ZERO cells with more than one observed length, ZERO cross-run
disagreements.** Byte-identical to EXP-0180's table. **db.json's stated rule is wrong in 25
of 32 cells** — recomputed, matching EXP-0180's figure. (128 further LEN cases faulted and
carry no length observation; they are the `opflags` wall, kept and counted separately.)

**What I changed, and what I did NOT.** The coordinator's instruction stands and the
measurement does not override it: EXP-0182 measured that applying this table verbatim to the
tokenizer costs **17 clean files and 3,220 leftover bytes**, killing `half_compact4` 8→0 and
`half_alu_fma12` 7→0, because the G17P measurement and the M4 own-shader corpus genuinely
disagree on the compact forms — **exactly where EXP-0180 bounded itself** ("bytes +6.. carry
the marker chain, so a dependence on byte +6 or later is UNTESTED"). So:

* `db.json`'s `length_rule.byte0_table` entry is **documentation** — `isadb.instr_length` is
  Python and is not driven by it. I replaced the one-line guess with the measured 32-cell
  table, the bound, **and an explicit statement that the tokenizer implements only the nine
  cells where both sources agree**, so neither source is silently preferred. Corpus effect:
  **zero**, by construction and by measurement.
* No code change. `isadb.py` is EXP-0182's and was never touched.

### DEF-0180-8 — the six semantic withdrawals → **ALL SIX CONFIRMED**

Moved counts recomputed per case as `digest(post, sentinels, stray) != digest(anchor)`,
against the arm's own once-captured anchor.

| # | committed text | my re-derivation | verdict |
|---|---|---|---|
| a | `rsv6` "fully INERT/reserved" | moves on **252/256** (C_HI), **248/256** (C_LO), 252/256 on the lifted anchor, both runs | **REFUTED** |
| b | `op_valid_marker` "byte+7 bit7 clear nulls the op" | **0 of 2 moved**, two carriers, three arms, both runs; byte+7 `0x40` and `0xc0` both write. The nulling control is **`b7_mid` bit 2 = instruction bit 60**: all sixteen values with that bit set leave the destination untouched, all sixteen without it write — **16/16 both ways**, exact predicate verified | **REFUTED; replaced** |
| c | `saturate` "clamps to [0,1]" | with the bit set the result is **exactly the third operand h[byte+5]**: 2.84375 on C_HI (unmodified 7.0586) and **0.46875 on C_LO, where the unmodified result is 0.125 — a clamp to [0,1] cannot touch 0.125** | **REFUTED at value level** |
| d | `srcB_desc` encodable range 256 | from the measured length map: at opsel 4 and 6 only **64** of 256 keep the 8-byte framing (at opsel 5, **128** — both m=1 and m=3 give 8 bytes, a nuance worth recording) | **CONFIRMED, with a nuance** |
| e | `fma12.opsel` one legal value | **exactly one** of 8 op-selects reaches 12 bytes (6, at m=3) | **CONFIRMED** |
| f | `fma12.ext` is 64 bits, not a field | structural: width 64, 2^64 space, 2,048 dispatched / 2,041 distinct | **CONFIRMED** |

**What I changed.** `saturate → mul_suppress` and `op_valid_marker → b7_hi`, both with their
refuted **enums deleted** — a name is documentation, and leaving `saturate` on a bit that is
not a clamp would keep the refuted claim in the file. `srcB_desc → b4`. `rsv6`, `b7_lo`,
`b7_mid` keep their names; their notes carry the withdrawals and the bit-60 rule.

**One thing I did NOT apply, and it is a measured refusal.** Folding `fma12.opsel` into
`match` — which the one-legal-value rule (falu2_uni.uni_mode, EXP-0175) would normally
require — **regresses the corpus**: 841 → **835** clean files, **+748** leftover bytes,
`half_alu_fma12` firings **7 → 0**. That is the same measurement-versus-corpus disagreement as
the length rule, inside the same bound. The folded variant is committed as
`work/cand_final_plus_fold` with its numbers; **the decision is the db owner's, not mine.**

### DEF-0180-4 / -5 / -6 — three citation defects → **ALL THREE CONFIRMED**

Each row's committed `range` text names a byte outside the field's own span
(`H4_citation_defects`): `half_alu_fma12.srcA` (bits 24..31 = byte+3) cites **byte+4**;
`half_alu_ext8.srcA` (byte+3) cites **byte+6** — and that one sentence is the *entire*
evidence `rsv6`'s row rested on; `half_alu_ext8.srcB_desc` (byte+4) cites **byte+7**. All
three texts are withdrawn in `analysis/validation_updates.json`.

### DEF-0180-3 — **stays withdrawn.** EXP-0180 refuted its own over-consumption claim, and my
length map agrees: at (opsel 6, m 3) twelve bytes is correct. The descriptor's semantics now
say so, and `emit_unsafe` stays because bits 34..95 are unmodelled.

### cvt_bf16 `match [32,8,1] → [32,1,1]` (coordinator-approved) → **CONFIRMED, then landed**

**db.json said** byte+4 must equal `0x01`. **EXP-0162's dense 256-value byte+4 sweep on the
HW-validated carrier accepts 52 values, and `0x01` is NOT among them — it is `wrong_value`.**
Every one of the 52 accepted values has bit 0 set; none of the bit-0-clear values is accepted.
So the descriptor pinned a byte to a value **the hardware rejects**, and the anchor our own
GPU executed correctly (`01 01 14 81 05 02 40 00`, byte+4 = `0x05`) did not decode as
`cvt_bf16` at all — it fell through to the least-specific `bf_alu8_var`.

Narrowed to bit 32; bits 33..39 recovered as the field `fmt` (32..39, 7 free bits, encodable
range 128) with the measured accept set. **Corpus effect: zero** (840→840, 387,496→387,496).
Anchor decode: `cvt_bf16` **FAIL → PASS**. That is the fifth of five unreachable anchors.

### EXP-0181's pending re-scores → **BOTH CONFIRMED from raw**

* `iter_at.grp`: rclean07/08/09, **identical in all three** — grp=1 (`0xaf`) `ok` on both
  carriers; grp=0 (`0x2f`) `wrong_value` on r_i8 (1 sample) and `ok` on r_i8s (4 samples).
  A dense **2-of-2** sweep against the field's real range. `0x00`/`0x01` hang on both carriers
  in all three runs. Recommended `isolated-byte-diff`, **not** `hardware-run` — only one of
  the two carriers has a valid host oracle.
* `reg_move_cb.form`: restricted to the 16 legal bytes (`match` pins byte+2's low nibble to
  `0xb`), **identical in both carriers and both runs**: form 0..3 `ok`, form 4..15
  `wrong_value`. Honest counts **16/16/16**; the old row's 256/256/256 counted 240 values that
  encode a different instruction.
* `shift_amt_move.kind` is carried through **flagged as NOT re-derived by me** — it was
  outside the dispatch's named scope. Its current row has no `start`/`width`, so
  `merge_verdicts`' span guard **cannot** protect it; that is called out in the handover.

### H6 — two `dst` rulings that were deferred and then never made

EXP-0169 filed `falu2_uni.dst` and `reg_move_cb.dst` as `untested` with the note "another
experiment owns this field's verdict → EXP-0168". **EXP-0168's committed
`field_verdicts.json` contains neither row.** The ruling was never made, and it is what keeps
two of the 22 one-field-away instructions blocked. Re-derived from EXP-0169's raw directly:

| row | values | carriers | cross-run | moved |
|---|---|---|---|---|
| `falu2_uni.dst` | 16/16 dense | 1 (C3_uni) | 16/16 identical | 15 |
| `reg_move_cb.dst` | 16/16 dense | **2** (C1_alu, C3_uni — which differ in the kernel buffer signature, the dimension EXP-0087 showed this instruction depends on) | 16/16 identical in all four | 14 each |

Both recommended `hardware-run`, with the caveat recorded that EXP-0169's
`__falsifier_byte0` step changes the opcode nibble as well as the field and is therefore a
weak falsifier — the same weakness DEF-0180-B found for the half family.

---

## 2. What this unblocks, and what stays blocked

Simulated with the orchestrator's own rule (`work/merge_verdicts.py::recompute_coverage`) in
`analysis/simulate_merge.py`; the simulated `validation.json` passes `validate_labels.py`
clean.

**Emittable instructions 50 → 53.** Emitter-grade field rows **628 → 636**.

**Of the 22 one-field-away instructions, THREE are unblocked:**

| instruction | why it is now emittable |
|---|---|
| **`half_alu`** | `dst` was `untested` at the **wrong bits**. It now exists at bits 4..7 with 457,380 per-case confirmations behind it, and the old row's evidence moves to `srcA`, where it belongs. |
| **`falu2_uni`** | `dst` was a deferral nobody executed; the raw is a dense 16/16, two gated runs, 100% agreement. |
| **`reg_move_cb`** | same, on **two** carriers; plus EXP-0181's `form` re-span, re-derived here. |

`cvt_bf16` and `half_alu_ext8` are **retained** (both drop out transiently while the new
fields have no rows, and return when the handover is merged).

**The other 19 stay blocked, each for a named reason** (`analysis/emittability_simulation.json`):

* **`iter_at` is no longer one FIELD away — it is one _instruction LABEL away.** With the
  `grp` re-score merged, **every field row is emitter-grade**; the only thing left is its
  descriptor-level label (`corpus-correlation`), which the DEF-0173-1 gate requires to be
  emitter-grade and which is a `validation.json` decision, not a `db.json` one. That is the
  cheapest remaining row on the board and it is the orchestrator's to make.
* **`half_alu_fma12`** stays blocked by `ext` — correctly. It is `untested` because it is
  **not a field** (64 bits, 2^64), and the descriptor keeps `emit_unsafe`.
* `rt_query_traverse.dst`, `if_push.scope`, `cvt_f2i.b9`, `copysign.operands` — `untested`,
  need a sweep.
* `frag_color_store.store_mode`, `iadd2.b2_fmt`, `imageblock_store.b4`, `iter.b9`,
  `simd_ballot.cache`, `simd_shuffle.cache`, `vtx_out_pos.slot` — `single-template-inference`.
* `dev_scoreboard_fence.scope_flag`, `ret.scoreboard` — `corpus-correlation`.
* `cubearray_coord_const.b3`, `mesh_out_src.sel`, `n4_cf_word.b3`, `n4_rt_word.dst` —
  `tokenization-only`; three of these four also have a `tokenization-only` **descriptor**
  label, so they are two decisions away, not one.

**Treat that enumeration as a LOWER BOUND.** The coordinator's own note applies here: a scope
estimate has widened under scrutiny four times tonight, and this one already widened once —
`iter_at` turned out to be blocked by a different thing than the worklist says.

---

## 3. Observed vs interpreted

**Directly observed (all re-computed here from committed raw, all G17P):** the DSTNIB
register deltas and their cross-run identity; the r14/r15 non-zero census; the 457,380 seed
identities; the two anchor fma identities; the 32-cell length map; every moved/values count in
§1c; the byte+7 nulling partition; EXP-0162's byte+4 accept set; EXP-0168's and EXP-0169's
outcome maps.

**Interpretation:** that byte+1/+3/+5 are *operands* rather than descriptors of something else
— the identity is consistent with, but does not uniquely prove, an operand reading; that
`mul_suppress` suppresses "the multiply term" rather than, say, selecting a passthrough mode
that happens to return the third operand; that byte+4's upper six bits have *no* role rather
than a role this carrier cannot see.

**Not excluded.** The fma-form results come from one op-select (6). `mul_suppress`, `b7_hi`
and the bit-60 rule are measured on the fma instance only; hadd/hmul are untested there,
because the `E8_ADD` arm has no detection power at all. The length map is exact within bytes
0..5; a dependence on byte +6 or later is untested, and that bound is exactly where the
measurement and the corpus disagree. `dst = 15` is unobserved on both carriers.

**Safe driver fallback.** Emit `dst` in byte0's high nibble and treat r15 as unverified for
this family; take the length from the nine agreeing (opsel, m) cells; do not rely on byte+4's
upper bits, on `rsv6`, or on any byte+7 bit other than bit 60 (nulls) and bit 57 (returns the
addend); do not emit `half_alu_fma12`.

---

## 4. Limitations

* No new hardware evidence. If EXP-0180's raw is wrong, this is wrong with it — which is why
  every claim was recomputed rather than inherited, and why the one place EXP-0180's prose and
  its own raw disagree (the C_LO `n=14` exception) is reported above.
* `shift_amt_move.kind` is handed over **unverified by me**.
* `analysis/rederive.py` imports EXP-0180's `harness/isa_helpers.py` — our own authored probe
  source, not an observation. Declared in `raw/README.md`.
* `tools/agx-isa/match_overlap.json` is **stale** with respect to the new db.json. I do not
  own it and restored it to HEAD; the regenerated copy is kept as
  `analysis/match_overlap_regenerated.json`. One command fixes it:
  `python3 tools/agx-isa/match_overlap_report.py`. It reports **0 zero-free-bit fields and 0
  vacuous emitter-grade claims** after the change, and `cvt_bf16.fmt` at 7 free bits / 128
  legal values, matching the row I hand over.

---

## 5. Files changed

**Owned and edited: `tools/agx-isa/db.json` only.** `isadb.py` (EXP-0182), `validation.json`,
`docs/` and `PROVENANCE.md` were not touched. No `git commit`.

## 6. The `validate_labels.py` violations I create, and their closure

18 violations, all expected and all closed by `analysis/validation_updates.json`:

* **MISSING rows** (db field with no label): `half_alu.ctrl`, `half_alu_ext8.{srcB,b4,srcC,mul_suppress,b7_hi}`, `half_alu_fma12.srcB`, `cvt_bf16.fmt`.
* **STALE rows** (label with no db field): `half_alu_ext8.{srcB_desc,b5,saturate,op_valid_marker}` — these must be **deleted by hand**; `merge_verdicts.py` does not delete.
* **Coverage counts** — recomputed automatically by `merge_verdicts.py`.

**And the one that no tool can see.** Seven field NAMES survive at a **different span**:
`half_alu.{dst,srcA,srcB}`, `half_alu_ext8.{dst,srcA}`, `half_alu_fma12.{dst,srcA}`.
`validate_labels.py` only checks that the name exists, so if those `replace` rows are not
applied, `validation.json` will keep describing the wrong bits under a name that still
resolves — DEF-0166-2, the defect that caught EXP-0161's `carry_gen` rename.
`analysis/validation_updates.json` lists all seven under `span_reuse_hazard` and every row
carries `start`/`width` so `merge_verdicts.py`'s guard can check it. **Apply the whole file or
none of it.**

## Clean-room provenance

```
Clean-room provenance: OWN-SHADER + HW-PROBE (re-read offline; no new run)
Inputs inspected: the committed raw/ trees of EXP-0180, EXP-0169, EXP-0168, EXP-0162 --
  records of AGX machine code compiled by the PUBLIC runtime API from MSL authored in this
  project, and byte splices of that same code; EXP-0180's authored harness/isa_helpers.py;
  tools/agx-isa/db.json.
Apple binary introspection: NONE. No Apple binary was disassembled, decompiled,
  symbol-dumped, strings-scanned or debugged. No shader bytes were inspected that were not
  compiled from MSL authored in this project.
Reproduction: README.md
Evidence: analysis/{defects_rederived,ab_metrics,validation_updates,emittability_simulation,
  halfdst_decode_before,halfdst_decode_after,match_overlap_regenerated}.json,
  work/{base_head,base_live,cand_half_match,cand_bf16_match,cand_half,cand_final,
  cand_final_plus_fold,validation_simulated.json,inputs_sha256.json}
```
