# RESULTS — EXP-0153: G17P revalidation of seven load-bearing M4 findings

**Target: Apple A18 Pro / G17P only** (`Mac17,5`, `AGXAcceleratorG17P`,
`applegpu_g17p`, 5 GPU cores, macOS 26.6 build 25G5043d, Metal family Apple9,
Apple clang 21.0.0). Everything below is a **G17P** claim. The M4/G16G values
quoted alongside are the committed results being revalidated and keep their own
`M4` label; nothing is promoted in either direction.

```
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: our own MSL (kernels/*.metal), the AGX bytes it compiles to
  on G17P, and the outputs the GPU produced from them; for arm G, the own-MSL
  corpus at experiments/EXP-M4-13-full-corpus/corpus.
Apple binary introspection: NONE
Reproduction: README.md -> "Reproduction"
Evidence: raw/{smoke01, g17p-20260830-run01, g17p-20260830-run02 (PARTIAL,
  retained), g17p-20260830-run03, g17p-20260830-reval02, corpus_build.json}
```

**The headline artifact is `analysis/g17p_vs_g16g.md`** — the full side-by-side
table. This file records observation vs interpretation, the exact ranges tested,
what remains unknown, and the limitations.

---

## 0. Headline

**Six of the seven findings reproduce outright on G17P; the seventh (arm G)
reproduces on byte-identical code with a measured, stated caveat. Zero
refutations.**

Every accepted-set mask rule, every fault boundary, every model-fit count and
every competing-model fit count came out **numerically identical** to the M4
result. Two arms come out **stronger** than the evidence they revalidate. One
open M4 question is answered.

| # | finding | M4 source | G17P verdict |
|---|---|---|---|
| 1 | `device_load` destination rule | EXP-0141 | **REPRODUCED** |
| 2 | `falu2` source class + inline minifloat | EXP-0138 | **REPRODUCED** (10 → 64 dense points) |
| 3 | native single-instruction 64-bit ADD | EXP-0146 | **REPRODUCED** |
| 4 | register-file model / fault bound | EXP-0112 + EXP-0139 | **REPRODUCED** (all three parts) |
| 5 | `ibfe` offset literal vs width mod-32 | EXP-0139 | **REPRODUCED** |
| 6 | `mov_imm` 7-bit / `imm_top` / `imm7 == 12` | EXP-0140 | **REPRODUCED** + one open question answered |
| 7 | instruction-length rule corrections | EXP-0148 | **REPRODUCED** on byte-identical code (caveat §7) |

**Does capacity differ between a 10-core G16G and a 5-core G17P? No.** The
addressable-GPR fault boundary is reg 96 on both, the `device_load` destination
ceiling is r63 on both, `r(R mod 64)` aliasing holds on both, and the 7-bit
register fields are 6-bit-load-bearing on both. GPU **core count** is a
throughput parameter; the per-thread register file the ISA can address is
unchanged.

---

## 1. What was directly observed

### 1.1 Captures

| run | cases | records | health | cascades | lease |
|---|---|---|---|---|---|
| `smoke01` | 40 | 52 | 12/12 ok | 0 | no |
| `g17p-20260830-run01` (gated) | 1958 | 1984 | 26/26 ok | 0 | no (concurrent) |
| `g17p-20260830-run02` | **PARTIAL, 215/258 of one arm** | 1731 | — | — | no |
| `g17p-20260830-run03` (gated) | 1958 | 1984 | 26/26 ok | 0 | no (concurrent) |
| `g17p-20260830-reval02` | 75 × 5 | 389 | 14/14 ok | 0 | **yes** |

**The two gated runs agree case-for-case on all 1958 cases, with 0
disagreements** (`analysis/verdicts.json → cross_run_agreement`), and produce an
identical outcome census: 1104 `ok`, 779 `wrong_value`, 73 `fault`, 2
`silent_zero`. They were captured at different times under different sibling
load (16 vs 67 innocent-victim retries).

### 1.2 The target's own compiler output

All six carriers compiled on G17P and **tokenized end-to-end with zero leftover
bytes** under the committed `db.json` (`raw/*/00_build.json`). Two facts are
worth recording on their own:

* The synthesis carrier's `_agc.main` is **170 bytes on G17P — the same length
  EXP-0141 measured on M4.**
* `k_u64sub.metal` compiles on G17P to `get_sr, device_load, device_load,
  iadd2, device_store, stop` (60 B, 0 leftover), and its `iadd2` is
  `1f015600020800501705` — byte0 `0x1f` and byte+7 `0x50`, **byte-identical to
  EXP-0146's M4 anchor.**

### 1.3 Per-arm observations

Complete tables, with the M4 value beside every G17P value, are in
`analysis/g17p_vs_g16g.md`. In brief:

* **A (`device_load` destination).** `dst_lo` 1/4 accepted (`v & 3 == 1`) at
  both r7 and r20; `dst_ext9` 64/128 (`v & 1 == 1`) at both; the full 512-value
  pair product 64/512 (`v & 0x181 == 0x81`); `extmode` 128/256 (`v & 0x80 ==
  0`), with 64 of the 128 accepted values odd, **0 of the 128 values ≥ 128
  accepted**, and `extmode` 252..255 faulting reproducibly. Both pre-registered
  falsifiers fired.
* **B (`falu2`).** The source-class model scores **64/64**, 8/8 at every
  `mod_lo` value. The inline minifloat scores **64/64 dense** over the whole
  64..127 half, including all ten M4-confirmed k values. The bound
  `constant float4&` is at non-GPR indices 6..9 (101/202/303/404), the same
  indices as M4. EXP-0138's own pre-registered refuter fired.
* **C (64-bit ADD).** One bit (`addsub`, byte0 `0x1f` → `0x9f`) turns the
  compiled 64-bit subtract into an exact 64-bit add, on **12 input rows in 5/5
  repetitions in both gated runs**, including 2⁶³+2⁶³ = 0, 0x7FFF…F + 1,
  0xFFFFFFFF00000000 + 0xFFFFFFFF, 0xFFFF…E + 3, and the lo→hi carry witness
  0x0123456789ABCDEF + 0xFEDCBA98 = 0x0123456888888887.
* **D (register model).** `falu2.srcB_reg` 64..112 aliases `r(R mod 64)`,
  confirmed at 49/49 values including **13 distinct non-zero discriminators**;
  the top bit is inert (128/128). `iadd2.dst` reaches the store's r6 at exactly
  12/13, faults at `dst` ≥ 192 (reg ≥ 96, 64 values), and does **not** alias at
  140/141 — all three identical to M4.
* **E (`ibfe`).** `offset` LITERAL 64/64 vs mod-32 32/64; `width` mod-32 64/64
  vs literal-clamp 37/64. **Both competing models score exactly what they scored
  on M4.** The adversarial second lowering (`a >> b`) shows the field live there
  too (only offsets 4 and 5 inert).
* **F (`mov_imm`).** `imm7` 0..127 all reach the destination against a poisoned
  buffer. `imm_top = 1` **padded** leaves the destination at its previous value
  (7) at all five immediates — a non-write, not a silent zero. `imm7 == 12`
  still fails to tokenize (`rt: false`) but **the hardware writes 12 correctly**.
* **G (corpus).** See §7.

---

## 2. Interpretation

The M4 rules are G17P rules. For the six ISA arms the accepted sets are not
merely "compatible" — they are the same sets, with the same exact mask rules,
the same fault boundaries and the same competing-model fit counts, on identical
stimulus. Where the M4 record was narrower than its claim (EXP-0138's ten
minifloat points; EXP-0112's aliasing measured on one field), the G17P sweep is
denser and the rule still holds.

Two arms are now better evidenced on G17P than on M4:

1. **`falu2`'s inline minifloat** — 64 dense points instead of 10.
2. **`falu2.srcB_reg` aliasing** — 13 non-zero discriminators in a second
   register field, where EXP-0112 used 4 poison controls in one field.

## 3. Alternative explanations not excluded

1. **Arms A, B, D and F are whole-program syntheses in one carrier each.** A
   carrier-specific interaction cannot be excluded from a single carrier; arm A
   mitigates this with two independent target registers (r7, r20) and arm E with
   two independent lowerings, but arms B, D-falu2 and F have one carrier each.
2. **Arm A's sweep co-varies the consumer register with the swept
   destination**, which is intrinsic to testing a destination selector. "R is
   unreachable above 63" is therefore, strictly, "the value did not arrive at
   `r(extmode>>1)` for any of the 128 encodings ≥ 128" — a register-file
   partition that hides the value elsewhere is not excluded.
3. **The non-GPR operand file's identity is not established here.** Arm B shows
   `mod_lo` bits[2:1] = 1 reads *something* indexed by `srcB_reg` that holds our
   bound constants at 6..9. EXP-0138's finding that it is **not** the uniform
   file (index 6 read 0.0 under `mod_lo = 1`) was not independently re-derived.
4. **Arm B's index-10 ≈1.0 reading** is a carrier literal, exactly as EXP-0138
   labelled it `CARRIER_SPECIFIC`. It reproduces, which means it is a property of
   `carrier_uni.metal`, not of the hardware.
5. **Arm C validates the 64-bit add in ONE carrier shape** — the compiler's own
   64-bit subtract with one bit flipped. It was **not synthesized from scratch**,
   and the field that makes the operands 64 bits wide (byte+7 `0x50` vs `0xA8`)
   was located but not isolated. This limitation is inherited verbatim from
   EXP-0146 and is unchanged by this experiment.
6. **Arm G's corpus deltas are confounded by toolchain version** (§7).

## 4. Negative and corrected results (first-class)

1. **4 of 5 `F_imm_top` unpadded cases are NOT faults.** In both unlocked gated
   runs all five were recorded as reproducible `fault`s — each having passed
   majority-of-3 within its run, and the two runs agreeing. Under the GPU lease,
   5 repetitions each, only imm 128 is a fault 5/5; 140, 200 and 255 are
   `wrong_value` 5/5 and 129 is 2 fault / 3 `wrong_value`. **Cross-run agreement
   did not defeat sustained sibling GPU load; only isolation did.**

   The corrected observation is provable from the committed record without
   re-running: the case's `sha_0` is `564e3165d8085121`, and re-hashing "16
   poison words with `out[12]` replaced by `0x41D00000` (26.0f)" reproduces it
   exactly, while all-poison and the three other candidate words do not.
   `out[12]` is the pre-test sentinel. So the program ran, and **neither of the
   two following `device_store`s executed at all** — a total instruction-stream
   desync where M4 saw a store land on the wrong word. Same conclusion, cleaner
   signature.

2. **`mov_imm.imm7 == 12` is a decoder defect only.** `rt: false` in every run
   (a `db.json` property, target-independent), but `outcome: ok` with `out0 ==
   12`. EXP-0140 said explicitly that the hardware was not tested; it is now.
   Recorded as `db_defects → DEF-0153-1`.

3. **`falu2.srcB_reg` 126/127 do not fault.** EXP-0112's "126/127 fault" was
   measured on `device_load`'s destination selector, where it **does** reproduce
   here (`extmode` 252..255). In `falu2.srcB_reg` (GPR class) 126/127 return
   0.0. The fault is a property of that one field, not of every 7-bit register
   field — consistent with M4's own EXP-0099 and EXP-0138.

4. **`tools/agxtest/persistrun.py` can busy-loop forever.** When its
   `agxrun_persist` child exits, `_read_line` returns `""` on EOF, `request()`
   recognises no prefix in it, and the parent spins on an unbounded stream of
   empty strings. Observed live at case 215/258 of `D_iadd2_dst` (parent at
   61.3 % CPU, state `RN`, no child of its own in `ps`). That capture is
   retained as `raw/g17p-20260830-run02/` with a `PARTIAL.md` and was **not**
   reused; the replacement was captured under the new id `…run03`. Worked around
   by **subclassing** (`harness/run.py :: GuardedRunner`), not by editing the
   shared tool. Recorded as `db_defects → DEF-0153-2`.

5. **77 of 659 corpus programs could not be rebuilt on G17P.** All 77 are
   `shdump` pipeline-kind limits, not G17P properties: mesh 15, object 14,
   vertex-only/fragment-only sources that have no `--render` pair 43, two
   imageblock kernels needing a tile pipeline
   (`Encountered unlowered function call to air.load.implicit_imageblock.v4f16`),
   and 3 whose `cat__name__stage` filename has an extra `__` segment.

## 5. Exact parameter ranges tested

| field | range exercised on G17P |
|---|---|
| `device_load.dst_lo` | 0..3 dense, at targets r7 and r20 |
| `device_load.dst_ext9` | 0..127 dense, at targets r7 and r20 |
| `(dst_lo, dst_ext9)` | the full 512-value product, at r7 |
| `device_load.extmode` | 0..255 dense, consumer r(v>>1) |
| `falu2.mod_lo` | 0..7 dense × 4 operand configs × {fadd, fmul} |
| `falu2.srcB_reg` @ `mod_lo=2` | 0..127 dense |
| `falu2.srcB_reg` @ `mod_lo=0` | 0..127 dense |
| `iadd2.dst` | 0..255 dense |
| `iadd2.addsub` | both polarities × 12 input rows × 5 reps × 2 runs |
| `ibfe.offset` | 0..63 dense, two lowerings |
| `ibfe.width` | 0..63 dense |
| `mov_imm.imm7` | 0..127 dense |
| `mov_imm.imm_top` | 1, at imm 128/129/140/200/255, padded and unpadded |

Every field of width ≤ 8 was swept over all 2^w values, as
FIELD-SWEEP-PROTOCOL §3.3 requires. **Nothing outside these ranges is claimed.**

## 6. Concurrency (FIELD-SWEEP-PROTOCOL §7.4)

Both gated runs and the corpus build ran **unlocked, concurrently with sibling
experiments**, per the orchestrator's 2026-08-30 direction. `EXP-0154`,
`EXP-0155` and `EXP-0156` were directly observed holding live `agxrun_persist`
processes on the device during run02/run03, and `EXP-0156` held the GPU lease
throughout. Innocent-victim retries: 16 in run01, 67 in run03, 111 in reval02
— recorded per case in `sweep.jsonl` and never allowed by themselves to make a
case a `fault`.

The revalidation pass (`reval02`) **took the lease**, which is exactly what
turned up the correction in §4.1.

## 7. Arm G — the length-rule corrections on G17P-compiled code

All figures from one tokenizer run of one `db.json` (`f5db942f…`, post-EXP-0148).

| corpus | files | clean | leftover bytes | total |
|---|---|---|---|---|
| M4, full EXP-0148 corpus (reference) | 1080 | **832** | **389 368** | 587 586 |
| M4, the 582-program subset with committed MSL source | 582 | 420 | 211 238 | 319 894 |
| **G17P, the same 582 sources recompiled on the A18 Pro** | 582 | **412** | **224 830** | 331 596 |

The first row **reproduces EXP-0148's published post-patch figures exactly**,
which validates the tokenizer before it is pointed at G17P.

The decisive control is the byte-identity split:

| | files | clean (M4 → G17P) | leftover (M4 → G17P) |
|---|---|---|---|
| byte-identical on both targets | 476 | **371 → 371** | **124 982 → 124 982** |
| bytes differ | 106 | 49 → 41 | 86 256 → 99 848 |

**Every byte of the difference comes from the 106 programs whose compiler output
differs — none from the length rule behaving differently.** On identical bytes
the corrected rules tokenize identically. The corrections are not G16G-specific.

**Caveat, stated rather than resolved.** 476/582 = **81.8 %** of the corpus
compiles byte-identically. The 106 that differ are 42 same-length (13 differ in
only 2 bytes) and 64 length-differing, sometimes wildly
(`controlflow__call_fptr_table`: 192 B on M4 vs 4 B on G17P). **This is not
evidence of an ISA difference and must not be read as one:** the two corpora
were compiled by different toolchains — macOS 26.6.2 build **25G82** on the M4
versus 26.6 build **25G5043d** on the neo. Separating "compiler revision" from
"target" needs the same OS build on both machines and is out of scope here.
Recorded as an open question.

## 8. Limitations

1. **Splice carriers have no independent sentinel path.** `bfe`, `shr` and
   `u64` read back through the very instruction under test, so their integrity
   check is the poisoned buffer plus the periodic health check, not a sentinel.
   The synthesis carriers (`synth`, `uni`, `dag`) all write a pre-test sentinel.
2. **Only 582 of EXP-0148's 1080 corpus programs were rebuildable** (§4.5), so
   arm G's G17P number is a subset metric. The full-1080 M4 reference is quoted
   for continuity, not compared directly.
3. **`imm_top` was tested at five immediates, not all 128.** The padded/unpadded
   pairing, not the density, is what carries the conclusion.
4. **The corpus byte-identity confound (§7) is unresolved.**
5. **No arm re-derives the *semantics* of the non-GPR operand file** (§3.3).
6. **Arm C is a one-bit splice, not a from-scratch synthesis** (§3.5).

## 9. Safe driver fallback

For every field in `analysis/field_verdicts.json`, an emitter targeting Apple9
may use the documented rule **within the stated range**, on either G16G or
G17P — the two now agree by direct measurement rather than by inference. Two
hard prohibitions, both HW-observed on G17P:

* never write `device_load.extmode` ≥ 128 (unreachable), and never 252..255
  (reproducible fault);
* never write `iadd2.dst` ≥ 192 (reg ≥ 96; reproducible fault).

And one decoder-only note: `mov_imm.imm7 = 12` is safe to **emit**; it is our
tokenizer that must be fixed.

## 10. A note for whoever merges `field_verdicts.json`

While this experiment was running, a sibling landed a change to
`tools/agx-isa/db.json`: `falu2`'s 3-bit `mod_lo` (start 40) was **split into
`srcA_class` (start 40, width 1) and `srcB_class` (start 41, width 2)**. Every
capture here was taken against `db.json` = `f5db942f…` (recorded in each
`raw/<run>/00_env.json`), which still had `mod_lo`.

**This does not invalidate anything, and the split is exactly the model arm B
measured.** The encoding is bit-for-bit the same field; map the evidence as
`srcA_class = mod_lo bit 0` and `srcB_class = mod_lo bits[2:1]`. Because the
sweep covered all 8 combinations densely, it establishes **both** new fields
over their full ranges (`srcA_class` 0..1, `srcB_class` 0..3), and
`validation.json` currently carries no label for either.
`analysis/field_verdicts.json` therefore ships all three keys.

`analysis/reproduce.sh` pins the frozen DB from commit `ff99bb52…`, rebuilds the
case matrix, and verifies that **all 1958 recorded instruction byte-strings are
reproduced exactly** — the full offline reproduction, no device needed.

## 11. What this experiment did not touch

`tools/agx-isa/db.json`, `tools/agx-isa/validation.json`, `docs/` and
`PROVENANCE.md` are unmodified, and nothing was committed.
`analysis/field_verdicts.json` (13 field entries + 2 `db_defects`) is a
**proposal** for the orchestrator to merge.
