# EXP-0208 — RESULTS: the label erased liveness on 183 rows, and 89 notes are contradicted by the raw they cite

**PURE OFFLINE ANALYSIS. No device was contacted** — nine hardware experiments held the A18
Pro for the whole run. No Apple binary was read or introspected. **No label was changed.**

```
Clean-room provenance: derived analysis of already-committed evidence
Inputs inspected: experiments/**/raw/**/*.jsonl (860 files, 5,251,950 records),
                  17,087 committed .json/.txt/.log/.md files, tools/agx-isa/{db,validation}.json,
                  52 committed revisions of validation.json via git
Apple binary introspection: NONE. No shader compiled, no device contacted.
Reproduction: see README.md
Output: analysis/axes.json (496 proposed `axes` records, for the orchestrator to merge)
```

---

## THE HEADLINE

**274 of the 496 rows have dispatched hardware raw. 183 of them show the field LIVE.**
134 of those 183 currently read `label: untested`.

The dispatch's premise holds and then some: the withdrawal did not delete the observations,
it deleted the *ability to see them*. Restated on the seven dashboards §9 asks for:

| Axis | Result over the 496 target rows |
|---|---:|
| **geometry** | 202 `geometry-mapped` · 44 `ledger-verified` (3 with encoding collapse) · 250 `unverified` |
| **liveness** | **183 `live`** · 72 `inert` (with a working detection control) · 12 `accepted-inert` · 7 `carrier-undecidable` · 222 `not-dispatched` |
| **semantics** | 4 `bounded-map` · 22 `hypothesis` · **470 `unknown`** |
| **recipe** | **496 `not-generated`** — not one of these rows has a committed generated recipe |
| **target** | 89 G17P-direct · 75 G16G-direct · 115 both · 217 nothing direct |
| **reproducibility** | 119 `independently-confirmed` (≥2 experiments) · 135 `auditable` · 242 `incomplete` |
| **frozen gate** | **212 rows PASSED their own pre-registered gate** — they held `hardware-run` or `isolated-byte-diff` in a committed revision and were later withdrawn |

The two numbers that matter most are on different axes and must not be collapsed again:
**183 rows have demonstrated liveness** and **470 rows have unknown semantics**. Both were
being carried by the single word `untested`.

---

## 1. What the label erased

### 1.1 Liveness

`isel_reg8.cmp_mode` is the cleanest case. `label: untested`. The raw
(`EXP-0139-m4-emit-ialu`, 2 runs, 512 records): **256 of 256 encodable values dispatched, 256
distinct actual encodings, 17 distinct valid observed payloads, 0 faults, 0 hangs, 128 values
returning a silent zero.** That is a densely-swept, geometry-mapped, demonstrably live 8-bit
field whose *semantics* nobody could explain — the row's own note says so ("no ≤4-bit rule
explains the partition"). Unexplained semantics is `semantics: unknown`. It is not
`liveness: untested`, and it is certainly not "no evidence".

66 of the 212 once-promoted rows do read `inert` or `accepted-inert` from their raw. That is
the withdrawal being *right* — and it survives as a bounded fact with its exact envelope,
rather than as an absence.

### 1.2 Reproducible hazard maps — 130 rows, 22 with an exact predicate

§6 asks for "behaviour at the last valid entry and first invalid/excess entry". 130 rows
carry a hard-outcome or no-effect fact that the label hid. Every predicate below is computed
**per value per carrier** — a value counts as a reproducible fault only when *every run that
dispatched it* faulted on it:

| Predicate | Target rows carrying it |
|---|---|
| `v >= 0xC0` (contiguous wall) | `ibfe.b2_bit0`, `ibfe.sign_ext`, `ibitcount.dst`, `irotate.operands` |
| `(v & 0x03) == 0x03` | `ilogic.{dst,z6,z8,z9,lut_a_sel,lut_a_free}`, `imad.srcC_desc` |
| `(v & 0x06) == 0x04` | `n4_rt_word.dst` — in **two** experiments (EXP-0200, EXP-0187), three carriers each |
| `(v & 0x18) == 0x10` | `ray_move_copy6.optype` — 64 of 255, 100 % cross-run |
| `(v & 0xF3) == 0x03` | `ibfins.b7` |
| `(v & 0x01) == 0x00` | `h_coord_hi_ext.ext` — 128 of 255 |
| `v >= 0xF6` | `imageblock_store.src` |
| `v >= 0x07` | `falu2_srcmod10.opsel` |
| `{0x00-0x06, 0x08-0x19, 0x1B-0xFF}` | `cubearray_coord_const.b3` — only 0x07 and 0x1A are legal |

**The `0xC0` destination wall is not a `frag_color_pack` quirk.** The dispatch named it for
`frag_color_pack.dst`; the same exact wall appears independently on `ibitcount.dst`,
`irotate.operands` and both `ibfe` byte-2 fields, in three different experiments. `dst[7:6] ==
0b11` looks like an ISA-wide illegal encoding, not a per-instruction accident. Encodable range
192, not 256, wherever it holds. **This generalisation is new and is the single most
implementer-relevant thing recovered here.**

`ray_move_copy6.optype` also corrects the record: the existing `axes` note says *"128 of 191
legal values FAULT"*. The raw says **64 distinct values fault** (128 *records* over two runs)
and 191 values are legal. Values, not records.

### 1.3 Instrument validation

`analysis/wall_check.py` points the same predicate finder at the four walls the dispatch
already documents — three of them on rows outside this experiment's target set, so it is a
pure instrument test. It rediscovers all of them verbatim from raw:

```
device_store.extmode    v >= 0xFC          (EXP-0141 synth, EXP-0169 C1_alu, C4_store)
device_store.index_reg  (v & 0x60) == 0x60 (EXP-0169 C1_alu, C4_store)
n4_rt_word.dst          (v & 0x06) == 0x04 (EXP-0200 x3 carriers, EXP-0187)
frag_color_pack.dst     v >= 0xC0          (EXP-0155 fcp@pack0; EXP-0168 r_fcp1 gives
                                            {0xC0-0xC5, 0xC9-0xFF} = 62 of the 64)
```

The EXP-0168 gap (0xC6–0xC8) is the budgeted runs stopping early — exactly the failure
`FIELD-SWEEP-PROTOCOL` §3(c) documents. The dedicated hang-tolerant mapping pass
(`raw/g17p_20260830_MAPPING_fcpdst_hangtolerant/sweep.jsonl`) has all 64: `0xC0..0xFF`
contiguous, 68 hang records, 0 exceptions.

---

## 2. Where the raw CONTRADICTS the current note — 89 rows

`analysis/contradictions.json`. Three shapes, all verified by hand on samples:

**(a) "0 values dispatched / UNVERIFIABLE" against a full dense sweep — 71 rows.** e.g.
`atomic_rmw.amode`, whose note reads *"EXP-0189 withheld (UNVERIFIABLE): 0 values dispatched
over 0 arm(s)"*. Hand-verified: `EXP-0141-m4-emit-mem/raw/m4-20260828-run2{1,2}/sweep.jsonl`
carry **512 records, 256 distinct values, every one `ok`**. Same for `device_load.{addr_mode,
access_desc,reserved7,reserved13}`, `jump.{branch_ctrl,link}`, `jump_cond.{cf_scope,reserved}`,
`imad.b11`, `ishift.pad9`, `iunary.{b1,opsel}`, `simd_reduce.{op,dtype}`, all of
`atomic_rmw.*`. **This is EXP-0197's finding, quantified: the clause is a restatement of
EXP-0189's collector input filter, not a fact about the evidence.**

**(b) "nothing moved / fully inert" against a moving observable — 5 rows.**
`falu3_ext.op`, `iadd2.addsub`, `ilogic.{z6,z8,z9}`. Under EXP-0191's validity rule (which
this corpus wrote and then did not apply here) the observable does move.

**(c) "no raw" against 4,707 records — 1 row.** `stop.reserved`; hand-verified at 1,030
records under the exact `(instr, field)` key alone, in `EXP-0206` and `EXP-0168`.

**None of these is a hardware contradiction.** In every case the *observation* stands and the
*prose about the observation* is wrong. Per §9 that downgrades auditability of the note, not
the fact.

---

## 3. What was genuinely recovered from pre-EXP-0138 raw

`EXP-0189`'s collector admits nothing from before EXP-0138. Reading those files directly:

* **`funary.mod` (`corpus-correlation`, `range: none`)** — `EXP-0013/raw/val_unary_minmax.log`
  is a splice-and-observe transcript with **host-computed expectations and PASS verdicts**:
  `b5 0x0a->0x02` gives `abs`, `->0x00` gives `mov`, `->0x08` gives negate-only. **bit1 =
  absolute value, bit3 = negate.** That is `liveness: live` and `semantics: bounded-map` at 4
  points on the A18 — for a row whose committed `range` says `none`.
* **`matrix_mac.{a_reg,b_reg,acc_en}`** — `RT-5/raw/matrix_test.log` and
  `RT-10/raw/part3_matrix.log` independently substitute the A and B operand registers and
  clear the accumulate bit, each against a **pre-stated host prediction**, and each matches
  exactly (`B*B+C` row-independent; `A*A+C` column-independent; `B*A+C = 704` everywhere;
  `A*B` alone `= 8(i+1)(j+1)`, `D77 = 512`). Two experiments, same result:
  `reproducibility: independently-confirmed`, `semantics: bounded-map`.
* **`EXP-M4-14/splice_results.json`** — 26 rows recovered. `tex_addr_setup.op_mode`: bit 2
  gates the operand (10 values). `tex_addr_setup.rsv11`: **11 values spliced, all inert** —
  a bounded accepted-inert, not an absence. `rt_query_traverse.opB`: **`0x02/0x06/0x40/0x07`
  HANG** (traversal non-termination). `frame_prologue.subop`: every passing value shares
  `bits[1:0] == 0b11`, the rest fault. `link_save_restore.scope`: `0xff` page-faults, and on
  the RESTORE side `0x00/0x80/0x01` all hang.

**EXP-M4-14 marks its own non-dispatched rows and this experiment honours that.** Five rows
(`n3_addr_prep.*`) carry `provenance: own-MSL byte-diff … NOT HW-splice`; they stay
`not-dispatched`. An earlier revision of the classifier had promoted them, and had also
reported a GPU hang for `tex_addr_setup.rsv11` because `"hang" in "unchanged"` is true. Both
were found by reading the output against the raw and are fixed; the substring trap is called
out in the code.

---

## 4. Where the honest answer is "no"

**222 rows have no dispatched raw for the field, in any format or keying searched.** The
`no_raw_statement` on each names all twelve keyings. The breakdown is not arbitrary:

| Cited evidence | Rows | Why "no raw" is correct |
|---|---:|---|
| `EXP-0036`+`EXP-M4-12`+`EXP-M4-13` | 109 | byte0-group census / residue closure / full-corpus convergence — **compile-only, no dispatch**, exactly as `validation.json`'s own `_conventions` says |
| `EXP-M4-13` alone | 22 | same |
| `EXP-0148` | 18 | token-resync framing census, 2.9 M records, **no field values** |
| `EXP-0171` | 18 | `b_alu10_loe`/`b_alu10_lof`. EXP-0171 swept **`ilogic`**. Same byte0 group, same `(start,width)`, **different descriptor** — reported as `sibling_descriptor_evidence` and explicitly NOT counted |
| no citation at all | 32 | `rt_as_load.*`, `rt_ray_mem.*`, `h_alu_hi_ext.*`, `bf_mul_dst.*`, `falu_compact4.*`, `ray_move_zinit.*` … |
| `EXP-M4-14` (non-splice) | 9 | the experiment's own `NOT HW-splice` provenance |
| `EXP-O2C`/`EXP-O2D`/`EXP-0023`/`EXP-0115` | 9 | corpus census + one end-to-end functional test; no per-field splice |

Five rows (`int_alu_ehi.*`) return **zero hits in every one of the six primary lookups** —
no jsonl record, no structural JSON record, not even a textual mention of the mnemonic
anywhere in the corpus.

### 4.1 The debt this exposes in the other direction

**25 rows held an emitter-grade label in a committed revision and have no per-field
dispatched raw I can find.** `jump.offset`, `matrix_mac.{dtype,mode,a_desc,pad4,op_enable}`,
`imageblock_{store,load}.slice_off`, `spill_frame_marker.{b1,b2,b3}`,
`rt_query_traverse.opA` and 13 more. Hand-checked: `spill_frame_marker` and `imageblock_load`
have only instruction-level framing records; `rt_query_traverse` has `dst` and `opB` but no
`opA`; `jump` has `branch_ctrl` and `link` but no `offset`. These were promoted on something
that is not in the raw tree. That is a real auditability gap and it points the other way from
everything else in this report.

---

## 5. Exact numerators and denominators (§5: never a percentage alone)

Every row in `analysis/axes.json` carries a `counts` block:

```
encodable · dispatched_distinct_values · distinct_actual_encodings_best_single_arm ·
distinct_instruction_byte_strings_all_arms · records · legal_values_ok ·
values_producing_a_valid_observation · silent_or_no_effect_records · hard_records ·
fault_values · hang_values · collapsed_encodings · untested_values ·
distinct_valid_payloads_max_single_carrier · distinct_ok_only_payloads_max_single_carrier ·
semantic_checks · distinct_oracle_payloads_max_single_carrier · carriers · outcomes{}
```

`analysis/axes_table.tsv` is the same 496 rows flat, for review.

**Encoding collapse** (distinct requested values → fewer distinct actual encodings) shows on
exactly 3 rows: `n3_sample_read.tail` (14), `tile_read.tail` (13), `vtx_coord_xform.operand`
(4). **None of the three is match-bit aliasing.** Read directly from
`EXP-0147/raw/m4_20260828_run0{1,2}/sweep.jsonl`, the 4 collisions on
`vtx_coord_xform.operand` are five per-byte cases (`byte0=0x00`, `byte1=0x20`, `byte2=0x04`,
`byte3=0x22`, `byte4=0x82`) that each write a byte's **already-present baseline value**, so
all five produce the identical baseline encoding `1722a2b00b00200422822182`. Baseline-identical
no-op mutations, not aliases. The existing `axes` note on that row says *"no match-bit
aliasing found"* — correct conclusion; the collapse is real and has a different cause, and the
record now says which.

---

## 6. Corrections to the six `axes` records already in `validation.json`

| Row | Existing record | This experiment |
|---|---|---|
| `ray_move_copy6.optype` | `hazard: 128 of 191 legal values FAULT` | **64 distinct values fault** (128 records over 2 runs); 191 legal; predicate `(v & 0x18) == 0x10` |
| `vtx_coord_xform.operand` | `geometry: … (no match-bit aliasing found)` | agreed on aliasing, but **4 requested values do collapse** onto the baseline encoding; cause identified as no-op mutation, quoted from raw |
| `frag_color_pack.fmt_class` | `liveness: accepted-inert … (512 records, ONE identical observed payload)` | **confirmed** — and the detection-power basis is now explicit: siblings `val` (10 payloads), `dst` (7), `comp_off` (5) move on the *same* `fcp@pack0` carrier, so the arm demonstrably had detection power. Also confirmed: 255 legal values, 2 `undecodable` cells |
| `jump_cond.offset` | `counts.legal: 36`, `hazard: see note` | agreed; hazard now exact — carrier `cf0` (EXP-0156, 2 runs): **26 of 56 dispatched values fault in every run**, 1 more only intermittently. The union across 4 carrier/arm combinations is 27 and is *not* a per-field fault map |
| `n3_sample_read.tail` | `counts.legal: 1522` | agreed; adds **14 collapsed encodings** and `target: G16G-direct` |
| `ret_luse.linkmode` | `counts.legal: 32` | agreed; hazard now exact and **carrier-dependent**: `cfN` (EXP-0156, 3 runs) **212 of 256 values fault in every run**; the four `EXP-0206` carriers fault on all 8 values they dispatch. A single per-field fault map would be wrong |

---

## 7. Limitations — how this method could still have said "no" when the answer is yes

Stated plainly, because §7 requires it:

1. **Twelve keyings is not proof of twelve.** Each one was found by *listing what did not
   match* and reading it. A thirteenth encoding of "which field is this record about" would
   be invisible to exactly the same procedure that found the first twelve. The 271 distinct
   non-matching raw field names are enumerated in the index; the ones I could not attribute
   are attributed to nothing.
2. **The pre-EXP-0138 `.log` era is hand-read, not parsed.** I read `RT-5`, `RT-10`,
   `EXP-0013`, `EXP-0016`, `EXP-0023`, `EXP-O2C`, `EXP-O2D`, `EXP-0115` and curated **10
   rows**. Those directories contain more splice transcripts than 10 rows' worth. Rows whose
   evidence sits in a log I did not open are reported `not-dispatched`, and that verdict is
   weaker than the ones backed by the index.
3. **Prose parsing is a heuristic.** The `EXP-M4-14` liveness verdicts come from counting
   distinct `->` targets in an English sentence. It already produced two wrong answers before
   being corrected. The verbatim evidence string is stored on every such row so a reader can
   overrule it.
4. **Detection power is approximated.** EXP-0191's frozen gate covers 79 fields; for the rest
   I use its `PASS_SIB` form only (some group in the same `(experiment, file, carrier)`
   produced ≥2 distinct valid payloads). That is weaker than the full role table, and it is
   *not* the same-dimension control §7 requires — a carrier can be live in one dimension and
   blind in the one the field controls. `tex_sample.samp_extra` (inert on nine arms, live on
   the tenth) is the standing proof.
5. **`live` is not `hardware-run`.** Every one of the 183 stays `semantics: unknown` unless a
   committed independent predictor exists. Nothing here promotes a label, and nothing here
   licenses an emitter to choose a value.
6. **One target-set boundary is arbitrary.** Rows already labelled `hardware-run` /
   `isolated-byte-diff` were not scored, so the axis dashboards cover 496 of 1,040 fields.
7. **Three of the source experiments were running while this ran** (`EXP-0200`, `EXP-0204`,
   `EXP-0206`, `EXP-0207`). Their raw is git-tracked and was admitted; if they amend it, the
   affected rows must be re-derived. Untracked working-tree raw was excluded.

---

## 8. Verdict

§10.2 is discharged for the 496 rows: **274 have dispatched raw, 183 show a live field, 130
carry a hazard or no-effect fact, 22 carry an exact hazard predicate, 4 carry a bounded
semantic map, and 212 passed their own pre-registered gate before being withdrawn.** None of
that was visible in `label`, and none of it required the device.

**No dashboard moves on the strength of this experiment alone.** `recipe` is
`not-generated` on all 496; `semantics` is `unknown` on 470. What changes is that the next
experiment can now be aimed: the rerun list §10.3 asks for is the 66 rows that read `inert`
with a working control (they need a same-dimension carrier), the 25 rows promoted without
locatable raw (they need re-running or retracting), and the 89 contradicted notes (they need
prose repair, not hardware).
