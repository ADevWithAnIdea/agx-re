# RESULTS — EXP-0140 (M4): making the MOV and control-flow families EMITTABLE

**Headline: 11 of the 23 dispatched instructions moved from "decodable" to EMITTABLE
(3 → 14 of 23), and 31 fields reached emitter grade.**

| | |
|---|---|
| Target | **local Apple M4 / G16G only** (macOS 26.6, Metal 4). No A18, no M5, no `macvdmtool`. |
| Gated captures | `raw/m4_20260828_run02` (complete, 7960 cases) gated against `raw/m4_20260828_run03` (partial, 7365 cases) |
| Retained but not promoted | `raw/m4_20260828_run01` — see `QUARANTINE-NOTE-run01.md` |
| Newly emittable | `get_sr` `mov_imm` `psel` `sel` `uniform_mov` `reg_move_c0` `reg_move_c1` `reg_move_c2var` `reg_move_c9` `reg_move_cb` `if_push` |
| Already emittable (untouched) | `frame_prologue` `link_save_restore` `stop` |
| Still blocked | `if_push_pred` `jump` `jump_cond` `pop_reconverge` `ret` `ret_luse` `mask_op` `call` `call_indirect` |
| Falsifiers | 10 of 11 pre-registered `expect_match=False` cases failed exactly as predicted; 1 disclosed surprise (§7) |
| Hangs | 5, all in the CF arm; the per-arm budget stopped exactly two arms; the host never wedged |

**Concurrency (FIELD-SWEEP-PROTOCOL §7.4): this experiment ran in batch 2, concurrently with
EXP-0144 (PACK) and EXP-0147 (pipeline misc).** Both were confirmed live on the GPU during the
captures (their `agxrun_persist` processes were observed alongside this experiment's). The
contamination that produced is quantified in §8; it is not a background remark, it shaped the
result.

---

## 1. What was directly OBSERVED

All numbers below are from the two gated captures. "Executed" means the case ran and produced
an output; "inert" means the swept value reproduced the carrier's own baseline exactly.

### 1.1 `mov_imm.dst` — 16/16
Every value 0..15 wrote **only** r_D (`mov_imm(D,99)` read back as 99, a control register
still holding its poison seed 7), and four independent 12-register aliasing scans confirmed no
second register changed. `imm7`/`imm_top` were **not** re-swept (already `hardware-run`,
EXP-0128).

### 1.2 `get_sr` — `form` 2/2, `dp_width` 256/256, `dp_marker` 32/32
Oracle: with grid=8/tg=8 a working `thread_position_in_grid.x` read makes each lane store its
own index, i.e. `out == [0..7]`; a no-op leaves the poison seed so all eight lanes collide on
one word. Exact acceptance rules (derived by `analysis/masks.py`, verified as set equality
over the full 256/32-value space):

| field | values that still read the SR correctly | rule |
|---|---|---|
| `form` | 0, 1 | **both inert** |
| `dp_width` | 16, 20, 24, 28, 48, 52, 56, 60 | **`(v & 0xD3) == 0x10`** — bits 0,1,6,7 must be clear, bit 4 must be set; bits 2,3,5 are don't-care |
| `dp_marker` | 6, 7, 14, 15, 22, 23, 30, 31 | **`(v & 0xE6) == 0x06`** — bits 1,2 must be set, bits 5,6,7 clear; bits 0,3,4 don't-care |

`dp_width` additionally **faults** on 32 of its 256 values and silently returns the wrong
vector on 216; `dp_marker` returns the wrong vector on the other 24. These are not don't-care
bytes: a driver that fills them arbitrarily gets a wrong answer, usually without a fault.

### 1.3 `sel.body` — the whole 24-bit field, 3 × 256 values × 2 input vectors
`db.json` models `body` as one opaque 24-bit `raw` field. It is **three located byte-fields**:

* **byte+3 = the predicate-FALSE operand.** With bit 7 set it is an 8-bit immediate **whose
  value is the byte itself** (128..255); with bit 7 clear it selects an operand that read 0 in
  this carrier. This was pre-registered as hypothesis H2 and then matched a host-computed
  oracle on **510 of 512** cases (the other 2 were environmental faults, §8) — that is a dense
  oracle over the entire byte, not an inertness test.
* **byte+2** splits cleanly into four 64-value classes: 128 cases inert, 128 wrong value, 128
  silent zero, **127 faults**.
* **byte+1** is the predicate/operand source selector: only 4 values (194, 198, 202, 206) are
  inert; 248 silently zero and 256 return a different value.

Confirmed independently and statically against five authored `?:` variants: `(a>5)?130:250`
compiles to `16 c2 a0 **fa**` (0xFA = 250), `(a>5)?100:200` to `16 c2 a0 **c8**` (0xC8 = 200).

### 1.4 `psel` — `flag`, `mode`, `sel`, each 256 values × 2 dispatch shapes
Same structure as `sel`, on `gsel4`'s grid-predicate select:

| field | result |
|---|---|
| `sel` (byte+3) | **512/512 matched the host-computed oracle** — identical immediate model to `sel.body`'s byte+3 |
| `mode` (byte+2) | inert exactly when **`(v & 0xC0) == 0x00`** (64 values); 127 values **fault** |
| `flag` (byte+1) | inert exactly when **`(v & 0x12) == 0x02`**; 256 values silently zero, 160 return a different value |

### 1.5 The `reg_move` / `uniform_mov` cluster — `dst` 16/16, byte+1 256, byte+2 256, byte+3 256
* **`dst`** (byte0 high nibble): all 16 values write r_D and nothing else.
* **`usrc`** (byte+1): **`usrc >= 0x80` materialises the immediate `usrc & 0x7F`** into the
  destination GPR — a 7-bit immediate move, *not* a uniform read. **128/128** immediate-region
  values matched their host-computed oracle exactly. Below 0x80 the byte selects a uniform
  register, **pair-quantised** (`usrc` and `usrc^1` read the same 32-bit word; consecutive
  uniforms step by 4); **8/8** of the indices holding our four bound magic constants returned
  them exactly (0x18/0x19 → u0, 0x1C/0x1D → u1, 0x20/0x21 → u2, 0x24/0x25 → u3). Buffer base
  addresses were observed at usrc 0x00/0x01 and 0x04/0x05; unallocated uniform indices return
  a **silent zero**.
* **byte+2** moves a value exactly when **`(v & 0xCB) == 0x01`** (8 of 256 values).
* **byte+3** moves a value exactly when **`(v & 0x0E) == 0x08`** (32 of 256 values).

### 1.6 Control flow, inside EXP-0090/EXP-0112's frozen skeleton
The skeleton's own per-lane oracle proves the surrounding control flow really executed: the
results require the loop to run 1, 2, 3, 4, 8, 16 and 32 times on lanes 1..7 and require lane 7
to take the if/else TRUE arm while lanes 0..6 take the FALSE arm.

| field | executed | result |
|---|---|---|
| `if_push.scope` | 256/256 | **completely inert across the full byte** |
| `if_push.scope_kind` | 256/256 | 64 values inert, 178 wrong value, 1 hang — **load-bearing** |
| `if_push_pred.scope` | 256/256 | **completely inert across the full byte** |
| `if_push_pred.level` | 64/256 | 4 inert (`(v & 0xFC) == 0x00`), 28 wrong, **2 hangs → arm stopped** |
| `jump.branch_ctrl` | 256/256 (run02) | inert across the full byte |
| `jump.link` | 256/256 | **completely inert across the full byte** |
| `jump_cond.cf_scope` / `.reserved` / `.offset` | 256/256/36 | every value inert — **see §5, the carrier does not make `jump_cond` live** |
| `pop_reconverge.scope` | 256/256 | **completely inert across the full byte** |
| `pop_reconverge.scope_kind` | 256/256 | 254 inert; **value 0 faults** |
| `pop_reconverge.reserved` (16-bit) | 34 samples (run02) | all inert |
| `ret.linkmode` | 256/256 (run02) | **only `(v & 7) == 4` runs — the other 224 values fault** |
| `ret.scoreboard` | 13/256 | **2 hangs → arm stopped** |

---

## 2. INTERPRETATION — what an emitter may now do

* `mov_imm`, `get_sr`, `sel`, `psel`, `uniform_mov` and the whole `reg_move` family can be
  **generated with arbitrary operands** inside the stated ranges. In particular an emitter now
  has **two independent ways to materialise a small constant**: `mov_imm` (7-bit, r0..r15) and
  the `0x?B` family with `usrc >= 0x80` (7-bit, r0..r15) — the latter previously documented as
  a uniform-register read only.
* `if_push` can be emitted freely in `scope` and must respect `scope_kind`.
* Several bytes previously carried as opaque are **not** don't-care. `get_sr.dp_width` and
  `.dp_marker`, `psel.mode` and `.flag`, and `ret.linkmode` each accept only a masked subset;
  outside it the usual Apple9 failure mode is a **silent wrong value**, not a fault.

## 3. NEGATIVE and INERT results (first-class)

`if_push.scope`, `if_push_pred.scope`, `jump.link`, `jump.branch_ctrl`,
`pop_reconverge.scope` are each **inert across all 256 values** in a program whose oracle
proves the branch and the mask stack executed. For a driver this is a licence: those bytes can
be filled with anything. `pop_reconverge.scope_kind = 0` is the single fatal value found in
that family.

## 4. `db_defects` — four corrections to `tools/agx-isa/db.json`

Recorded in `analysis/field_verdicts.json` under `db_defects`. **This experiment did not edit
`db.json`.**

1. **`reg_move_c0` / `c1` / `c2var` / `c9` / `cb` / `uniform_mov` are ONE instruction, not six.**
   A single 256-value sweep of byte+2 in one carrier shows the five "descriptors" are five
   values of one 8-bit form field, and only `(byte+2 & 0xCB) == 0x01` moves anything. The
   named-descriptor probe is decisive: of the five, only `reg_move_c1`'s discriminator moved a
   value; `c0` and `c2var` silently zeroed, `c9` and `cb` returned something else. `db.json`'s
   split of byte+1 into `src_reg` + `src_flag` also does not match hardware — bit 7 is the
   immediate-vs-uniform-file selector, not a register-file half flag.
2. **`sel.body` is not an opaque 24-bit field** — it is three byte-fields with the roles in
   §1.3.
3. **`mov_imm` with `imm_top = 1` does not write the destination at all.** EXP-0128 read
   immediates 128..255 as a "silent zero"; that reading was made against a zero-initialised
   read-back buffer. Against a **poisoned** buffer the paired control settles it: with 4 bytes
   of inert padding after it the destination keeps its previous value (7, not 0); without
   padding the following 2-byte instruction is consumed and the read-back store addresses the
   wrong word. An emitter must treat the immediate as **7 bits**; bit 7 selects a different,
   longer instruction rather than extending the immediate.
4. **`mov_imm` with `imm7 == 12` does not tokenize** under the current length rule (byte+1 =
   0x0C makes the 2-byte pair look like the 4-byte `0x?c` preamble group). It is the only
   immediate in 0..127 with this property, checked exhaustively over all 16 `dst` values. This
   is a decoder defect; whether the hardware agrees was not tested. Every immediate this
   experiment emits avoids 12.

## 5. What this experiment does NOT establish

* **`jump_cond` — all three fields stay `untested`, deliberately.** Every structured offset,
  including targets that are not instruction starts and targets **outside the program**,
  reproduced the baseline exactly, and so did all 256 values of `cf_scope` and `reserved`. The
  reason is structural: `jump_cond` is the loop-entry guard, and the only lane whose guard is
  true has trip count 0, so both paths compute the same value. The sweep therefore has **no
  discriminating power** over this instruction, however clean it looks — the carrier-liveness
  requirement of `FIELD-SWEEP-PROTOCOL` §3.2. **EXP-0115's branch reach was measured on `jump`
  and still does not transfer to `jump_cond`; that gap remains open.** A successor needs a
  carrier whose conditional-branch target is observable.
* **Four fields are one gated run short, not one hardware result short.**
  `jump.branch_ctrl` (256/256 executed in run02), `ret.linkmode` (256/256 in run02, exact rule
  `(v & 7) == 4`), `pop_reconverge.reserved` (34 samples in run02) and `ret.scoreboard`/
  `if_push_pred.level` (stopped by the hang budget) all lack a second agreeing capture, because
  run03 lost those arms (§8). Per `PRE_REGISTRATION.md` §10 they are reported `untested` rather
  than rounded up. **One more complete capture would very likely take `jump`, `ret`,
  `pop_reconverge` and `if_push_pred` to emittable, i.e. 18 of 23.**
* `mask_op`, `ret_luse`, `call`, `call_indirect` were **not swept at all** — they do not appear
  in the reused skeleton, and authoring new control-flow constructions for them was out of
  scope under the two-hang stop rule.
* Everything here is **M4/G16G**. No A18 replication (hands-off).

## 6. Adversarial tests and falsifiers

Eleven pre-registered `expect_match=False` cases. Ten behaved exactly as predicted, including
the four "correct program, unreachable oracle" positive controls that prove match-detection is
not a rubber stamp, and the four named `reg_move` descriptor discriminators. Independent second
methods: two different input vectors for `sel`, two dispatch shapes for `psel`, a 12-register
aliasing scan for `mov_imm.dst`, and the static five-variant `?:` compile check for `sel`'s
byte+3 immediate.

## 7. Disclosed surprise

`regmove.opdesc_redirect_scan` at byte+3 = 0x0C was pre-registered `expect_match=False` on
EXP-0087's report that bit 2 "redirects the write to a different register". It matched its
all-poison oracle instead: with bit 2 set the value is written to **none** of r0..r11. The
prediction was left unchanged at freeze; the observation refutes the "redirects to another
low register" reading and is consistent with `(byte+3 & 0x0E) == 0x08` simply not being
satisfied.

## 8. Contamination, and how much of it there was

This is the part a reader needs in order to know what evidence they are holding.

* **Four distinct contamination modes were seen, one of them new.**
  1. `...ErrorInnocentVictim` — our command buffer discarded because the GPU was recovering
     from someone else's error. Byte-identical programs passed 9/10 times.
  2. `STATUS OK` with nothing executed (EXP-0141's mode) — caught by the poisoned output
     buffer and the integrity sentinel; **98 cases in run02, 154 in run03** were classified
     `invalid_run` and excluded from the gate rather than being recorded as silent zeros.
  3. Reusing one splice-archive path — avoided from the start (unique path per request).
  4. **NEW: `MTLCompilerService` becoming unavailable machine-wide** ("Connection init failed
     at lookup with error 141 - Reentrancy avoided"). It killed run03 at case 7365 before any
     GPU work, and then blocked every further capture for the rest of the session: 20
     consecutive `shdump` probes over ~7 minutes all failed on a 4-line kernel while the device
     still enumerated as "Apple M4". No recovery action was attempted (no `macvdmtool`, no
     reboot) per `CLAUDE.md`. This belongs on the protocol's §7 list.
* **The `fault` label was never taken from one observation.** Every case ran 2 trials, and 3
  whenever the first was not `ok` or the first two disagreed; the majority wins, and every
  trial's status and OS fault-classification string is in the record.
* **All 30 periodic baseline re-validations in run02 passed** (28/28 in run03), so neither
  capture is a cascade.
* **The cross-run gate**: 7365 common cases, 6953 agree, 320 disagree, 92 excluded as
  environmental. Of the 320, **58 are `if_push_pred.level` and 2 are `sel.body.b3`** — i.e.
  almost all of the disagreement is one arm that run02 completed and run03 lost to its hang
  budget, not measurement noise. 65 cases were re-labelled `no_store` (see below).
* **A harness bug found after the captures and repaired in analysis, not in `raw/`:** the
  driver compared the raw u32 output word against a *signed* int32 oracle, so any expected
  value with bit 31 set scored a false mismatch. Exactly **4 records** were affected (the bound
  constant u0 = 0xA1B2C3D4 at usrc 0x18/0x19 in both runs). `analysis/verdicts.py` recomputes
  the outcome from each record's own stored `observed`/`oracle`, reports the count, and leaves
  the append-only capture untouched; `harness/run.py` was fixed for future captures.
* **`no_store` reclassification:** on the CF carrier there is no room for a sentinel prologue,
  so "no output word was written" is ambiguous between contamination and a field value that
  suppresses the store. 65 cases were `invalid_run` in **both** gated runs with **every trial
  reporting STATUS OK**; contamination does not reproduce that way, so they are re-labelled
  `wrong_value` with a `no_store` note. Cases that did not reproduce stay `invalid_run` and are
  excluded.

## 9. A methodological finding worth carrying forward

**Lengthening a control-flow carrier is not semantically neutral, even when the documented
`base_slot` trap is avoided.** `carrier_cf2.metal` — EXP-0112's carrier plus arithmetic on
`acc` **alone**, adding no new buffer reference, which is precisely the padding technique
EXP-0128 proposed for this purpose but never dispatched — moves the constant the reused
skeleton's select compares against, so every lane takes the TRUE arm, while every `base_slot`
value stays identical. `work/pilot/pilot8.py` isolates it: the original 152-byte carrier
reproduces the host oracle exactly on all eight lanes, the lengthened one does not, with the
sentinel prologue on *or* off. This is what run01's own periodic baseline check caught, and it
is why the CF arm here has no integrity sentinel.

## 10. Reproduction

```sh
cd experiments/EXP-0140-m4-emit-mov-cf
sh harness/build.sh work/bin
python3 harness/baseline.py                    # re-derive every carrier fact (no GPU)
python3 harness/cases.py                       # 7960 frozen cases (no GPU)
python3 harness/run.py --run <NEW_RUN_ID>
python3 analysis/verdicts.py m4_20260828_run02 m4_20260828_run03
python3 analysis/masks.py
python3 analysis/emittability.py
python3 analysis/make_manifest.py --check
```

## 11. Clean-room attestation

```
Clean-room provenance: HW-PROBE + OWN-SHADER
Inputs inspected: our own MSL (kernels/*.metal) and the machine code compiled from it;
                  instruction bytes assembled by our own tools/agx-isa (read-only use)
Apple binary introspection: NONE
Reproduction: the commands in §10
Evidence: raw/m4_20260828_run02/sweep.jsonl, raw/m4_20260828_run03/sweep.jsonl,
          raw/*/00_inputs.json (tool/harness/kernel SHA-256 + git revision),
          analysis/field_verdicts.json, analysis/field_masks.json, analysis/emittability.json,
          manifest.json
```

No Apple binary was disassembled, decompiled, symbol-dumped, strings-scanned or debugged. The
only machine code inspected or spliced is the compiled form of MSL we wrote. `db.json`,
`validation.json`, `docs/` and `PROVENANCE.md` were **not** edited; the per-field verdicts are
offered to the orchestrator in `analysis/field_verdicts.json` in the shape
`FIELD-SWEEP-PROTOCOL` §5 specifies.
