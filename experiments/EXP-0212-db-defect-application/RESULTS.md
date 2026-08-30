# EXP-0212 — RESULTS

**Target of the underlying observations:** G17P (all of EXP-0199…EXP-0207).
**This experiment:** desk work on the M4 host. No device contacted, no shader compiled.

---

## 1. Headline

The queue is drained. **42 items triaged, 36 applied (28 non-span + 6 span-moving + 3
match; `half_pack.byte0` counted once), 6 refused outright, and 6 more applied only in
part** with the stronger half explicitly withheld.

**Five field spans moved. Five `validation.json` rows were measured against those old spans.
None of them was silently kept:** every one now carries a DEF-0166-2 notice recording the
old span, the new span, and a re-derivation status established from the committed raw — not
from the PENDING file's prose.

Every gate passes on the live tree:

| check | before | after |
|---|---|---|
| `validate_labels.py` | rc 0, 1040 fields | **rc 0, 1053 fields** |
| `roundtrip_test.py` | 302 OK / 0 FAIL | **302 OK / 0 FAIL** |
| corpus decode, strict (1080 own-MSL files) | 841 clean / 387,692 leftover / 25,634 instrs | **841 / 387,692 / 25,634 — identical** |
| corpus decode, resync | 841 clean / 4,440 gap / 78,838 instrs | **841 / 4,440 / 78,838 — identical** |
| descriptor firing mix, strict | — | **no delta at all** |
| descriptor firing mix, resync | — | **one delta: `sfu_marker` 116 → 85, `operand_word` 2102 → 2133** |
| `match_overlap_report.py` | rc 0 | rc 0 |
| whole-db field overlap / overrun sweep | — | **0 problems** |

`db.json` `2412eac1…` → `02a47fc6…`; `validation.json` → `2e2125b8…`.

---

## 2. What the numbers moved, and why the emittable count went DOWN

| metric | before | after |
|---|---|---|
| fields in the sidecar | 1040 | **1053** (+13) |
| emitter-grade (`hardware-run` + `isolated-byte-diff`) | 559 | **559 — unchanged** |
| `untested` | 244 | **257** (+13) |
| emittable instructions | 40 / 166 | **37 / 166** |

**No label changed. Not one.** The +13 are the fields the span splits and the match
relaxation created; each is a *new* row, at `untested`, with the evidence pointer and a note
that states with exact numerators what the evidence shows and what label it may support.
EXP-0212 sets no labels — that is the orchestrator's call, and `untested` is the placeholder
that asserts nothing.

**`half_pack`, `irotate` and `simd_reduce` drop out of the emittable list.** That is the
gate working, not a regression: each gained a field nobody has ruled on. Per
`RE_EXPERIMENT_PROCESS_CORRECTIONS` §9 this is a precisely scoped downgrade with a named
reason, and §8 says the emittability headline must not be derived from field labels anyway.
The three instructions are one orchestrator ruling away from returning — and the evidence
for `half_alu_fma12.srcC` in particular (256/256 full-vector host-oracle match on three arms
in two runs) reads on its face like `hardware-run`.

---

## 3. The five moved spans, and what happened to the rows measured against them

Four of the five rows record `start`/`width`. Those four are exactly the rows
`work/merge_verdicts.py`'s DEF-0166-2 guard would now reject if their verdicts were
re-submitted — which is the guard doing its job. **`start`/`width` were deliberately NOT
re-pointed at the new span:** they record the bits that were actually measured, and a
name-keyed re-point is the silent mis-attachment the guard exists to prevent.

| row | old span | new span | re-derivation status, established from the raw |
|---|---|---|---|
| `half_alu_fma12.ext` (`untested`) | 32, 64 | 48, 48 | **NOT NEEDED for the label.** `untested` is equally correct for the residue that remains, and the raw *does* cover the new span densely (`analysis/ext_bytes.json`, bytes +6…+11 at 256 values each, 3 arms × 2 runs). What moved out from under the name now has its own rows. |
| `simd_reduce.op` (`hardware-run`) | 8, 8 | 8, 3 | **SUPPORTED, ruling needed.** Re-derived from raw: 8,312 recorded cases, **256 distinct byte+1 values** over 4 carriers × 2 runs, so all 8 values of the new 3-bit field were dispatched ~32× each; and the semantic check that earned the label (4 values → 4 distinct predicted 32-lane vectors → 4 matches, 0 mismatches on `sr_sum`) lies entirely inside the new span. The label is not weakened by the move. |
| `irotate.operands` (`isolated-byte-diff`) | 24, 40 | 48, 8 | **SUPPORTED, and the raw supports a STRONGER label than the row carries.** The `isolated-byte-diff` was assigned because only 1 of the old field's 5 bytes was mapped — byte+6, which *is* the new span. Re-derived from raw: arm `ROT/rot_alu#0/operands_b6` dispatched **256 values**, and `byte+6 = 4·(32−K)` matched an exact host rotate vector at 33/33 modelled values on 4 carriers in 2 runs (264 exact vector matches, 0 misses). EXP-0202's own RESULTS says "byte+6 bits[6:2] alone meets the `hardware-run` bar". |
| `pop_reconverge.reserved` (`untested`) | 32, 16 | 32, 8 | **NOT NEEDED for the label; a future promotion needs NEW RAW.** Re-derived from `sweep.jsonl`: the sweep is **52 distinct 16-bit values covering only 33 of 256 distinct LOW bytes** — sampled, not dense. That is exactly EXP-0206's own next-experiment recommendation 2. The "low byte must be zero" model is post-hoc; no pre-registered model survived. |
| `sfu_marker.b0_hi` (`hardware-run`) | 3, 5 | 5, 3 | **SUPPORTED, ruling needed.** EXP-0199 swept byte0 densely 0…255 at each site (5,943 recorded cases), so all 8 values of the new 3-bit span are exhaustively covered and all 8 accepted — that measurement is what *defined* the new span. |

### The finding the guard could not have made

`sfu_marker.b0_hi` **records no `start`/`width` at all.** A verdict that omits the bits it
measured is *invisible* to the DEF-0166-2 guard: `merge_verdicts.py` skips the check when
`got == (None, None)`. So the guard is only as strong as the verdicts' own honesty about
which bits they measured, and this span move would have passed it silently. That is recorded
in the row's note because no tool could catch it.

---

## 4. The refusals, in the order they matter

1. **`icmpsel` 14 → 10 (blanket): REFUSED.** Every HW-VALIDATED 14-byte instance
   (EXP-0013's `icmp_lt`/`ucmp_lt`/`fcmp_lt`, which *run* on hardware and tokenize with zero
   leftover) has byte+2 `0x1d`; both 10-byte hardware sites have byte+2 `0x2d`. The length is
   context-dependent and a single integer cannot express it. See §6 for the narrow candidate.
2. **`icmp_pred` 6 → 10: REFUSED.** One site. The 6-byte reading is HW-anchored elsewhere.
   No discriminator established.
3. **`frame_marker_compact` 2 → 4: REFUSED, and measured to be a regression.** See §6.
4. **The missing non-leaf-epilogue descriptor: REFUSED.** A new mnemonic requires an
   `_instruction` label, and the evidence is a census observation with no semantic model,
   no length proof, and no field map. Recorded rather than invented.
5. **`get_sr.sr_sel[168]`: enum NOT changed.** Its own status line says one dispatch shape.
6. **`tex_write.rsv10` → `level`: RENAME REFUSED.** DEF-0204-4 is a **three-point compiler
   differential** (three explicit-level writes differing only at byte+10, `0x00`/`0x10`/`0x20`),
   i.e. OWN-SHADER-DIFF, not a swept or spliced result. That row's label is `hardware-run`,
   earned on a different question. Renaming would carry that label onto a role that was never
   dispatched — precisely the name-reuse hazard DEF-0166-2 names. The finding is in the note;
   the rename needs one splice.
7. **`harness.anchor_loss`: not a db defect.** A bug in EXP-0203's own committed harness, with
   its own impact statement of "NONE on any verdict". Retro-editing a finished experiment's
   harness would break its reproduction record.

Six further items were applied only in part — `falu3_srcmod12.opsel`, `ibitcount.dst` and
`simd_reduce.dtype` all keep their spans, `fspecial_est.subop` keeps its enum,
`simd_ballot.pred` keeps its field, and `half_pack`'s length gate stays with the length-rule
owner. Each refusal is stated in the descriptor itself, with the reason, so the next reader
sees why the obvious edit was not made.

The most instructive of these is **`simd_reduce.dtype`**. The defect proposes narrowing it
because bits 4, 6 and 7 are inert on all four carriers. Bit 4 is `f16_incl_scan` in that
enum, and **none of the four carriers is fp16** — so the carriers have no detection power in
the dimension bit 4 would control. Narrowing on that observation is exactly the §7 trap.
`simd_reduce.op` was narrowed and `dtype` was not, from the same experiment, for that reason.

---

## 5. The one tokenization change: `sfu_marker`

The match tightening `(b0 & 0x07) == 6` → `(b0 & 0x1f) == 6` re-attributes **31 corpus
tokens** from `sfu_marker` to `operand_word` in the resync walk. Their bytes are
`1e 0a` ×22, `1e 02` ×8, `4e 0e` ×1 — byte0 values with bits 3–4 set, exactly the ones
EXP-0199 measured as **not accepted** (of the 32 values the old match admitted, exactly 8 are
accepted, and `0x0e` satisfies the old match but is `stop`).

Read both ways, honestly:

* **As a correction** — and this is the reading the evidence supports: 31 tokens that the
  over-broad match was claiming are data words, and now decode as data words. `sfu_marker`
  keeps 85 real firings, so the descriptor is not zeroed out (contrast DB-DEFECT-TRIAGE's
  C1, where a `pixel_order` variant looked identical on the metric while doing something
  very different).
* **As a cost** — the corpus is our own compiler's output, so those 31 tokens were emitted by
  a working compiler; if any of them really is this instruction, the tightening loses it.
  Nothing structural moved: clean files, leftover bytes, instruction boundaries and total
  instruction count are all **bit-identical** before and after.

Both readings are recorded in the descriptor.

---

## 6. The two refused length candidates, measured

Retained as isolated trees so the next agent starts from the measurement.

| candidate | change | clean files | strict leftover | instructions | resync gap |
|---|---|---:|---:|---:|---:|
| baseline | — | 841 | 387,692 | 25,634 | 4,440 |
| **L1** `work/var_L1` | `icmpsel`: byte+2 `0x2d` → 10 (was: only when byte+3 == `0x80`) | 841 | **387,686** (−6) | **25,637** (+3) | **4,416** (−24) |
| **L2** `work/var_L2` | `frame_marker_compact`: byte0 `0x60` → always 4 | **838** (−3) | **388,102** (+410) | **25,565** (−69) | 4,454 (+14) |

Round-trip is 302 OK / 0 FAIL for both.

**L1 is a positive result and is handed on, not taken.** It is backed by hardware (EXP-0200's
stop-scan: two independent sites in two carriers, 10-byte enclosing spans, 905 shared offsets
at 99.56 % cross-run agreement), it is narrow (it fires only on the byte+2 value both hardware
sites carry, and never on the `0x1d` value every HW-validated 14-byte instance carries), and it
*improves* every corpus number. It is not applied here because it is an `isadb.py` length-rule
change — a separate ownership domain in this repo, and one whose db-side counterpart
(`icmpsel.length`) cannot express a context-dependent length as a single integer. This is the
same disposition DB-DEFECT-TRIAGE gave C7b ("Not applied only because it is a length change").

**L2 is a measured regression** and confirms EXP-0199's own scope caveat. Its 7 boundaries were
insertions into straight-line compute carriers; the corpus `60 00 <nonzero>` sites are
threadgroup-atomic and divergent-control-flow contexts it explicitly did not re-test. The
2-byte reading is refuted *in the tested envelope*, and the corpus says the envelope matters.

---

## 7. Two things found on the way that nobody asked for

1. **`tools/agx-isa/match_overlap.json` was already stale at HEAD.** Regenerating it from
   HEAD's *own* `db.json` + `validation.json` produces 5 rows that differ from the committed
   file (e.g. `falu3_srcmod12.opsel` recorded as `untested` when `validation.json` at the
   same commit says `isolated-byte-diff`). **This application's own delta to that file is
   exactly ONE row** — `irotate.b2`'s `instruction_emittable` flag, a direct consequence of
   `irotate` leaving the emittable list. A generated artifact that drifts from its inputs and
   is still committed is a small audit hole worth closing.
2. **`tools/agx-isa/promotion_check.py` rewrites another experiment's committed reports as a
   side effect.** Running it regenerated eight files under
   `experiments/EXP-0209-dashboards/reports/` (2,485 insertions / 1,269 deletions — i.e. they
   were badly stale too). They were reverted with `git checkout` and are untouched in the
   final tree. A checker that mutates a finished experiment's evidence directory when you run
   it read-only is worth flagging.

---

## 8. How this process could have applied a defect that was not actually supported

The honest answer, because it nearly happened three times.

**The failure mode is that `PENDING_DB_DEFECTS.md` flattens evidence strength.** It is
generated by a script from `db_defects` blocks, so a three-point compiler differential
(`tex_write.rsv10`), a single-dispatch-shape observation (`get_sr.sr_sel[168]`), a
hypothesis-grade ungated probe (`simd_ballot.pred`'s adversarial arm) and a
2048-case-×-3-arm-×-2-run host-oracle match (`half_alu_fma12.srcC`) all appear as bullet
points of the same size, under a heading that says "hardware-confirmed". **Reading the
PENDING file alone, all four look equally applicable.** The dispatch that sent me here
reinforced it: it named `tex_write.rsv10` as "is the write's mip level, not reserved", which
is exactly true and exactly not a licence to rename a `hardware-run` row.

Three concrete ways I could have got it wrong, and what actually stopped each:

1. **Renaming `tex_write.rsv10` → `level`.** The rename is *correct as prose* and would have
   been *wrong as an edit*: the row is `hardware-run` from a different question, and a rename
   carries a label onto a new name as well as new bits. What stopped it was going back to
   EXP-0204's RESULTS, where the finding is labelled in its own words as "a three-point
   compiler differential, not a swept result". **The PENDING entry does not carry that
   sentence.**
2. **Narrowing `simd_reduce.dtype` to 6 bits.** The defect proposes it, the observation
   (bits 4/6/7 inert on all four carriers) is real, and the enum still fits. Applying it would
   have asserted geometry from a liveness result on carriers with no detection power in the
   dimension the bit controls — §7's named trap. What stopped it was noticing that bit 4 is
   `f16_incl_scan` and that no carrier was fp16. **Nothing in the defect text says that**; it
   took reading the enum next to the carrier list.
3. **`icmpsel` 14 → 10.** The PENDING tail states it flatly, in bold, as a "hardware-measured
   LENGTH correction". Applying it verbatim would have broken three HW-validated whole
   programs. What stopped it was checking what `roundtrip_test.py` actually contains before
   editing, and noticing that every 14-byte instance carries byte+2 `0x1d` while both 10-byte
   hardware sites carry `0x2d`.

**The common structure: in each case the PENDING file was true and the *edit* it implied was
not, and the difference was only visible in the source experiment's own hedging.** So the
process that would have failed is exactly the efficient one — apply the queue from the queue.

The two things that made the difference, and which I would make mandatory:

* **Never apply from the summary. Open the source experiment's RESULTS and find the sentence
  where it bounds itself.** Every one of the six refusals came from that sentence, and in
  four of the six the sentence had been dropped in generation. `PENDING_DB_DEFECTS.md` should
  carry each defect's **evidence class and its stated bound** as required fields, so an
  applier cannot see the claim without seeing its limit.
* **Re-derive coverage from the raw before believing a span move is safe.** The
  `pop_reconverge.reserved` row looked like a clean 16→8 narrowing; counting the actual sweep
  showed 52 sampled values covering 33 of 256 low bytes, which is what turns "re-derived" into
  "needs new raw". That count is not in any summary — it came from `sweep.jsonl`.

One residual risk this experiment does **not** close: `half_pack.dst` was added with only
**2 of 16 destination nibbles ever dispatched** (the compiler's own 1, and nibble 7 on arms
HP_C/HP_D). `range` is free prose, so no tool can read that bound out — the same gap
DEF-0166-1 and `merge_verdicts.py`'s own comment describe. It is stated in the row's note as
a coverage bound rather than left for a reader to infer, but a field whose `range` says
"2 of 16" and whose label is set by a human is still one careless promotion away from
claiming a mapped 4-bit register field.
