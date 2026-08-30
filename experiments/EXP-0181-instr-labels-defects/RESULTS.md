# EXP-0181 — RESULTS

**Type: DESK EXPERIMENT, NO device work.** Nothing was dispatched to the neo (three device
experiments were live there and were not disturbed), to the M4 GPU, or to M5. `macvdmtool`
was not invoked. Every input is committed evidence already in this repository.

```text
Clean-room provenance: OWN-SHADER + HW-PROBE (re-analysis of committed evidence) + PUBLIC
Inputs: tools/agx-isa/{db.json,validation.json,isadb.py}; experiments/EXP-*/raw/**/*.jsonl
        (the recorded behaviour of OUR OWN compiled shaders, spliced by our own tools, on
        our own harnesses); experiments/EXP-M4-13-full-corpus/hex/** (our own compiled
        shader bytes); the cited experiments' RESULTS.md.
Apple binary introspection: NONE.
Reproduction: README.md -> Commands
Evidence: analysis/{dispatch_evidence,dispatched_bytes_check,anchor_check,
          anchor_reachability,defects_rederived,instruction_labels,
          orphaned_validation_rows,ab_metrics}.json
```

---

## 0. Headline

| | |
|---|---|
| **Task 1** — the 30 weak `_instruction` labels | **all 30 WERE dispatched on hardware.** Recommended: **18 `hardware-run`, 7 `isolated-byte-diff`, 5 stay weak.** |
| **the gate arithmetic, which is the point** | applying `_instruction` as a gate TODAY costs **30** (53 → 23). After this refresh it costs **5** (53 → **48**). |
| the 5 that must stay weak | `frag_depth_store`, `frame_marker_compact`, `n2_op6`, `sfu_marker`, `vary_slot` — and every one of them has ALL its fields at emitter grade, which is exactly why the field-only rule is unsafe |
| **Task 2** — the four defects | **4 of 4 CONFIRMED** by independent re-derivation, **3 narrowed and landed**, **1 refused with cause** (`pixel_order.scope`) |
| new defects found while re-deriving | **2** — `DEF-0181-1` (`pixel_order`'s match is contradicted by its own committed sweep) and `DEF-0181-2` (five descriptors' HW anchors do not tokenize) |
| `db.json` | 172 instructions, 1036 fields (**both unchanged**); sha `a77f8cfa163fcf72…` → `1ada4e7bb7879cd6…` |
| corpus gate | **833/1080 clean, 388,604 leftover, 25,419 tokens — IDENTICAL** |
| round trip | **302 OK / 0 FAIL / ALL PASS** — identical count, no fixture patch needed |
| `match_overlap_report.py` | **34 → 31** overlapping rows; zero-free-bit stays **0**; vacuous emitter-grade stays **0** |
| `validate_labels.py` | **exit 0**, only the `db_sha256` WARN (the orchestrator's). **0 orphans, 0 created rows, 3 re-spanned.** |
| headline effect of MY edits | **none.** 53/166 emittable and 621 emitter-grade fields before and after — measured, §5. |

> **Amendment A1 — a number in my dispatch moved under me, and it was not my edit.**
> The dispatch quotes *"52 of 166 emitter-relevant instructions emittable, 617 fields"*. The
> orchestrator committed `955eb6c7 exp(0179)` mid-experiment, which edited `validation.json`
> and made `call` emittable. **The live headline is 53 of 166 and 621 emitter-grade fields.**
> §5 isolates my `db.json` change against the same `validation.json` and shows it moves
> neither number. Every figure below is stated against the live file.

---

## 1. TASK 1 — what the 30 labels should be

### 1.1 The one fact that settles the shape of the answer

`analysis/scan_dispatch_evidence.py` walks **every** `experiments/EXP-*/raw/**/*.jsonl` in
the repository and accumulates, per (mnemonic, experiment), the case count, the outcome
histogram, how many records carry both an `oracle` and an `observed` block, and how many
baseline/anchor cases came back `ok`.

> **Every one of the 30 was DISPATCHED on real hardware — 230,804 raw cases in total, across
> 18 experiments and both targets.** Not one of them is a purely tokenized descriptor.

So `corpus-correlation` — *"the field's meaning is inferred from how its values co-vary
across a corpus. **Nothing was executed to test it.**"* — is **factually wrong** as a
description of 28 of the 30, and `tokenization-only` is wrong about the other 2's *bytes*
(though right about their semantics; see §1.4).

That is the answer to why `mov_imm` looks absurd: it is not an outlier. The labels were
written when the descriptors were located, and no wave since EXP-0138 has gone back to
them.

### 1.2 But "dispatched" is not "established" — the two instruments that keep them apart

Being conservative in the right direction needed two checks that no previous pass ran.

**(a) Harness attribution is not descriptor attribution.**
`analysis/verify_dispatched_bytes.py` takes every distinct `bytes` string a harness tagged
with one of the 30 mnemonics and asks `isadb.decode_one` which descriptor actually claims
it. Many of the 30 are dst-generalised siblings of a *different* HW-validated form
(`bf_add_dst` generalises `bf_alu`, `cvt_f2h_dst` generalises `cvt_f2h`), so a record tagged
`bf_add_dst` proves nothing about `bf_add_dst` until the bytes are checked.

**(b) `ok` does not always mean "matched a host oracle".**
`analysis/anchor_check.py` pulls each experiment's UNMUTATED anchor and its note. Three
distinct scoring regimes are in the corpus and they are not interchangeable:

| regime | example | what an `ok` proves |
|---|---|---|
| **host-computed semantic oracle** | EXP-0156 `bf_add_dst`: *"native bfloat ADD, host oracle = exact bf16 of a+b"* | the instruction computed what the descriptor says |
| **carrier oracle** | EXP-0157 ray-query getters: the whole kernel returns 8 authored quantities exactly | the instruction is load-bearing on a correct result |
| **baseline hash / movement** | EXP-0155, EXP-0172: `"oracle": null`, compare a hash against the unmutated run | the BYTES are live — nothing about semantics |

Rule **R5** (frozen in `PRE_REGISTRATION.md`) does the rest: *a descriptor earns nothing at
instruction level from its fields being `hardware-run`.*

### 1.3 The recommendations

`analysis/instruction_labels.json` carries each row in full — current value, recommendation,
range, target, evidence, the one-line reason with its citation, the **refuter**, the
caveats, and the machine-gathered case counts. Summary:

| instruction | current | recommended | target | raw cases | source experiments | HW anchor tokenizes? |
|---|---|---|---|---:|---|---|
| `bf_add_dst` | corpus-correlation | **hardware-run** | G17P | 4,152 | 0156 | **NO** |
| `bf_fma_dst` | corpus-correlation | **hardware-run** | G17P | 14,276 | 0156, 0171 | **NO** |
| `cvt_bf16` | corpus-correlation | **hardware-run** | G17P | 9,160 | 0144, 0162 | **NO** |
| `cvt_f2h` | corpus-correlation | **hardware-run** | M4+A18 | 7,651 | 0144, 0168 | yes |
| `cvt_f2h_dst` | corpus-correlation | **hardware-run** | G17P | 5,555 | 0144, 0162 | **NO** |
| `cvt_i2f` | corpus-correlation | **hardware-run** | M4+A18 | 5,475 | 0144 | yes |
| `falu3` | corpus-correlation | **hardware-run** | M4+G17P | 13,116 | 0138, 0154, 0160 | yes |
| `falu3_ext` | corpus-correlation | **hardware-run** | M4+G17P | 15,122 | 0138, 0154, 0160 | yes |
| `hminmax` | corpus-correlation | **hardware-run** | G17P | 2,608 | 0156 | **NO** |
| `irotate` | corpus-correlation | **hardware-run** | M4+G17P | 17,050 | 0146, 0154, 0172 | yes |
| `mov_imm` | corpus-correlation | **hardware-run** | M4+G17P | 4,192 | 0140, 0153, 0168 (+ **0167 generated**) | yes |
| `mov_zext16` | corpus-correlation | **hardware-run** | G17P | 9,701 | 0146, 0154, 0161/0165 (**generated**) | yes |
| `n3_mov` | corpus-correlation | **hardware-run** | G17P | 15,240 | 0146, 0157, **0174 generated** | yes |
| `pack_convert` | corpus-correlation | **hardware-run** | M4+A18 | 27,804 | 0144, 0168 | yes |
| `psel` | corpus-correlation | **hardware-run** | M4 | 4,618 | 0010, 0140 | yes |
| `ret_luse` | corpus-correlation | **hardware-run** | G17P | 1,324 | 0035, 0156 | yes |
| `sel` | corpus-correlation | **hardware-run** | M4 | 4,875 | 0010, 0140 | yes |
| `uniform_mov` | corpus-correlation | **hardware-run** | M4+G17P | 1,776 | 0020, 0140, 0168 | yes |
| `h_coord_hi` | corpus-correlation | **isolated-byte-diff** | G17P | 5,750 | 0157 | yes |
| `h_coord_hi_ext` | corpus-correlation | **isolated-byte-diff** | G17P | 3,795 | 0157 | yes |
| `iter_flat` | corpus-correlation | **isolated-byte-diff** | G17P | 3,247 | 0029, 0155 | yes |
| `rtq_state_move` | corpus-correlation | **isolated-byte-diff** | G17P | 5,756 | 0157 | yes |
| `shift_amt_move` | corpus-correlation | **isolated-byte-diff** | G17P | 3,722 | 0146, 0154, 0168 | yes |
| `sr_read_wide` | corpus-correlation | **isolated-byte-diff** | G17P | 9,581 | 0146, 0157 | yes |
| `vtx_coord_xform` | corpus-correlation | **isolated-byte-diff** | M4 | 3,746 | 0147 | yes |
| `frag_depth_store` | corpus-correlation | **corpus-correlation (KEEP)** | A18 | 1,550 | 0155 | yes |
| `n2_op6` | corpus-correlation | **corpus-correlation (KEEP)** | M4 | 17,539 | 0146, 0157 | yes |
| `vary_slot` | corpus-correlation | **corpus-correlation (KEEP)** | G17P | 7,282 | 0143, 0155, 0172 | yes |
| `frame_marker_compact` | tokenization-only | **tokenization-only (KEEP)** | M4+A18 | 568 | 0172 | yes |
| `sfu_marker` | tokenization-only | **tokenization-only (KEEP)** | G16G+G17P | 4,573 | 0146, 0157 | yes |

**H1 confirmed, and the pre-registered expectation held**: 25 of 30 meet R1 or R2 (predicted
≥ 20); 5 stay weak (predicted ≥ 3). **F1 did not fire** — no instruction turned out to be
merely tokenized.

### 1.4 The five that must NOT be promoted — the ones the task was really about

Each of these has **every declared field at emitter grade**. That is what makes them the
right test of R5.

1. **`frag_depth_store`** — three fields, all `hardware-run`, baselines `ok` 11/11 on G17P.
   And **the depth output has never been read back**: `db.json` says so itself, *"Not
   individually splice-validated (agxrender has no depth attachment to read back)"*, and
   EXP-0155 scored every case against a **colour** probe. The single thing the descriptor
   claims — *write the shader `[[depth]]` output to the tile depth buffer* — is unobserved.
   The descriptor does not even have an operand field for the depth value. **KEEP
   `corpus-correlation`.**

2. **`vary_slot`** — both fields `hardware-run`, 7,282 cases across three experiments, and
   its documented semantics is **REFUTED**. `db.json` says byte+3 is *"the varying slot
   (monotone, tracks the store slot)"*. DEF-0172-3 measured it: `slot` is live *"only bit 2
   and only on one of four carriers — all 128 values with bit 2 set move the observation,
   all 128 with it clear do not, and the other seven bits, **including bits 5–6 where the
   COMPILER encodes the varying index**, did nothing on any carrier."* Promoting it would
   certify a slot selector that does not select. **KEEP.**

3. **`n2_op6`** — six fields, all `hardware-run`, 17,539 cases on both targets. It is **not
   one instruction**: `db.json`'s own committed text calls it *"a genuine catch-all bucket
   (write-mask helper + compact select + fcmp-mask + SFU range-reduction select)"* whose
   *"per-sub-op value maps are mixed and needs-splice"*, and EXP-0157 measured a **different**
   accepted mask for `opsel` in each carrier instance. A bucket has no semantics to confirm.
   The fix is decomposition into per-sub-op descriptors, not a label. **KEEP.**

4. **`sfu_marker`** — both fields `hardware-run` on **both** targets, byte-invariance
   refuted, accepted sets measured in three independent G17P carriers, and one live bit
   shown to be a quadrant/sign control (byte+0 := 0x00 flips the sign of `fast::sin` on
   exactly the rows needing range reduction). And `db.json` states the conclusion:
   *"the exact micro-op is NOT-YET-CHARACTERIZED"*. Framing right, semantics unknown — the
   definition of `tokenization-only`. **KEEP.**

5. **`frame_marker_compact`** — `b1` is `hardware-run` (152 of 256 values move, identically
   in two runs). EXP-0148 records this descriptor as one of three **unresolved
   continuation-word candidates** — it may not be a standalone instruction at all — and
   `validate_labels.py` already prints it in that informational set. Live bytes in an
   unresolved continuation word are not an instruction. **KEEP.** (It also has a device
   hazard: `b1` = 3 and `b1` = 7 hang the GPU on four of five carriers.)

### 1.5 The two strongest rows, for contrast

- **`mov_imm`** — the dispatch's own example, and the evidence is overwhelming: EXP-0031
  proved the semantics by value on hardware (splicing byte+1 `0x20`→`0x21/0x40/0x11` changes
  the output to 33/64/17 — the literal, not an SR read); EXP-0140 swept `dst` 16/16 against
  a host oracle with four 12-register aliasing scans and corrected the immediate to **seven**
  bits against a poisoned read-back; and **EXP-0167 emitted 196,114 assembler-GENERATED
  `mov_imm` instances inside 233 zero-copied programs whose `01_results.jsonl` was
  byte-identical across two isolated gated runs.**
- **`n3_mov`** — EXP-0174 built every byte from the descriptor's bit geometry with zero
  bytes copied from any compiled shader and ran **840 generated 32-bit register copies over
  all 240 ordered `(dst ≠ src)` pairs**, in both instruction orders and both register plans,
  each scored against a full host-computed 16-register prediction: **0 failures**. Its own
  `analysis/field_verdicts.json` already records `n3_mov._instruction: hardware-run
  (generated)`. The blocker (DEF-0174-1) was landed by EXP-0175.

### 1.6 Where I am deliberately one rung below what the raw might support

Naming these, because they are the rows most likely to be argued with:

- **`falu3_ext` at `hardware-run` is the least comfortable of the 18.** Its operand-slot
  model is EXP-0138's HW-validated one and its byte+2 map is EXP-0160's dense G17P sweep —
  but the **saturate** that distinguishes it from `falu3` is not proven by value, and
  `db.json`'s own provenance says the extended tail is *"raw-captured (INFERRED), NOT
  HW-dispatch validated"*. If the label is meant to certify the saturate, this one belongs
  at `isolated-byte-diff`. Flagged rather than decided.
- **`sr_read_wide` is held at `isolated-byte-diff`** even though it has 9,581 cases and 6,955
  `ok`s, because EXP-0157 **refuted or could not observe two of the descriptor's own
  identifying claims**: `sel` is *"load-bearing but NOT the property selector"* and byte+7's
  documented candidate-vs-committed selector *"is not observable here"*. `dst` is PINNED in
  all three carriers — *"an emitter cannot choose the destination"*.
- **`iter_flat`, `h_coord_hi`, `h_coord_hi_ext`, `rtq_state_move`, `shift_amt_move`,
  `vtx_coord_xform`** are all held at `isolated-byte-diff` for the same reason: they ran
  with the predicted effect at the compiler's own operand values, but nothing about them was
  separated **by value** (no `sel` → varying map, no 0x26-vs-0x2e mul/fma proof, no chosen
  `(src, dst)` pair with a predicted register content).

### 1.7 A caveat that applies to five of the 18, and is not their fault

`analysis/anchor_reachability.py` asks a question nobody had: **does the committed tokenizer
decode the exact bytes that were dispatched?** For five descriptors it does not — see
DEF-0181-2 in §3.3. That is a DECODE gap in `isadb.py`'s length rule, not a doubt about the
hardware observation, and the two are kept apart in every recommendation.

---

## 2. TASK 2 — the four defects, re-derived before anything was changed

`analysis/rederive_defects.py` recomputes the free/pinned bit split **from `db.json` alone**,
then goes back to every committed raw record naming the field and scores the dispatched
values against the descriptor's own legal set, then checks what the own-MSL corpus emits.
EXP-0168's table was consulted only afterwards.

**All four are real.** `assemble()` refuses 254/256, 192/256, 240/256 and 240/256 of their
respective values today, so an emitter reading these tables is told a field is choosable
when it mostly is not.

| defect | field | declared | match pins | free bits | legal values | verdict |
|---|---|---|---|---|---:|---|
| DEF-0168-A | `iter_at.grp` | bits 0..7 | 0..6 = `0x2f` | **bit 7** | **2** | **NARROWED** |
| DEF-0168-B | `pixel_order.scope` | bits 24..31 | 28, 30 | 24..27, 29, 31 | 64 | **REFUSED — §3.2** |
| DEF-0168-C | `reg_move_cb.form` | bits 16..23 | 16..19 = `0xb` | **20..23** | **16** | **NARROWED** |
| DEF-0168-D | `shift_amt_move.kind` | bits 16..23 | 16..19 = `0xc` | **20..23** | **16** | **NARROWED** |

### 2.1 `iter_at.grp` — and the re-derivation turns a `untested` row into a result

EXP-0168 recorded this arm as **LADDER-FAILED / `untested`, "4 values swept"**, and the row
says *"a REPRODUCIBLE result deliberately NOT promoted"*. Scored against the field's **real**
encodable range that same raw is a **dense 2-of-2 sweep**, identical in `rclean07/08/09`:

| byte0 | `grp` (narrowed) | carrier `r_i8` (1 sample) | carrier `r_i8s` (4 samples) |
|---|---:|---|---|
| `0xaf` | 1 | **`ok`** | **`ok`** |
| `0x2f` | 0 | **`wrong_value`** | `ok` |
| `0x00`, `0x01` | *illegal* | **HANG** | **HANG** |

So the single free bit **moves the observation** on the carrier whose baseline note reads
*"baseline vs HOST oracle: EXACT"*, reproducibly, in three gated runs. The corpus emits
`0xaf` in **8 of 8** firings.

I recommend `isolated-byte-diff`, **not** `hardware-run`, and the reason is in the raw:
`r_i8s`'s own baseline record says *"baseline vs HOST oracle: MISMATCH"*, so only **one** of
the two carriers has a valid oracle, and EXP-0168's ladder clause was not met (`L_iter_loc`
was inert, correctly, because that rung only moves at 4 samples). The recommendation is in
`analysis/orphaned_validation_rows.json`; `validation.json` was not touched.

The hang result is worth keeping as a hardware fact in its own right: **254 of `iter_at`'s
256 byte0 values are a decode desync and two of the two tested HUNG the device on both
carriers, in all three runs.** That is why three experiments failed to sweep this field.

### 2.2 `reg_move_cb.form` and `shift_amt_move.kind` — the old counts were 16× too generous

Both narrow cleanly to a contiguous free high nibble. Re-scoring the existing dense sweeps
**restricted to the 16 legal bytes**:

| field | target / carriers | narrowed value → outcome |
|---|---|---|
| `reg_move_cb.form` | G17P, EXP-0169, `C1_alu` + `C3_uni` × 2 gated runs, all four identical | `0..3` → **`ok`**; `4..15` → `wrong_value` |
| `shift_amt_move.kind` | G17P, EXP-0154 `k_rot_var`, 2 gated runs identical | `1`, `3` → **`ok`**; every EVEN kind → `wrong_value`; every other ODD kind → `silent_zero` |
| `shift_amt_move.kind` | M4, EXP-0146 run01/run02, identical | `0,1,2,3` → **`ok`**; `4..15` → `silent_zero` |

Both are therefore **densely covered, 16 of 16**, and `shift_amt_move.kind` is dense on
**both** targets with **G17P's accept set a strict subset of M4's** — stated as such rather
than merged. The old rows' counts (`values_dispatched: 256`, `distinct_bytes: 256`,
`encodable_range: 256`) counted 240 values that encode a **different instruction**.

*Recorded, not smoothed:* on the same G17P carrier the hardware also accepts byte+2 `0x14`
and `0x34` — low nibble 4, **outside** this descriptor's match. So the `0xc` pin describes
the descriptor, not the hardware's full accept set. `shift_amt_move.kind`'s existing note
(*"ok at {0x14, 0x1c, 0x34, 0x3c}"*) silently mixes the two.

---

## 3. What I refused to do, and the two new defects

### 3.1 The re-derivation's own falsifier fired — as pre-registered

`PRE_REGISTRATION.md` F2 said a defect that does not survive re-derivation, or a field whose
free bits are not contiguous, must be **reported and not applied**. It fired on
`pixel_order.scope`, which is why that one is not in `db.json`.

### 3.2 `DEF-0181-1` — `pixel_order.scope` cannot be narrowed, and the reason is a second defect

Two independent obstacles, either of which alone would be enough:

**(a) The free bits are not contiguous.** The match pins bits 28 and 30 *inside* the field,
leaving 24..27, **29** and **31**. No single `(start, width)` expresses that. Truncating
`scope` to the contiguous run 24..27 would make **bit 31 unencodable — and bit 31 is exactly
the acquire-vs-release distinction (`0x50` vs `0xd0`) this descriptor documents.** That is a
worse defect than the one being fixed.

**(b) Splitting into three fields would express them — around a match that is itself
contradicted by the committed evidence.** I re-derived EXP-0147's dense M4 sweep (256 values
× 2 gated runs, both carriers) from its raw. The accept sets are exact and they reproduce
the note already in `validation.json`:

| carrier | accepted byte+3 | rule | high nibbles |
|---|---:|---|---|
| `pixel_order` (acquire) | **64 / 256** | `bit4 == 1 AND (bit6 XOR bit7) == 1` | 5, 7, 9, b |
| `pixel_order_rel` (release) | **64 / 256** | `bit4 == 1 AND bit7 == 1` | 9, b, d, f |
| *this descriptor's match* | 64 / 256 | `bit4 == 1 AND bit6 == 1` | 5, 7, d, f |

**Neither accept set is contained in the match's legal set.** Each carrier accepts 32 values
the match **rejects** (high nibbles 9 and b) and rejects 32 the match **admits**. Drawing new
field boundaries around bits 28 and 30 would bake that in — precisely the propagation
EXP-0175 refused for `mov_zext16`.

The pin comes from **EXP-0162 on G17P** and the refuting sweep from **EXP-0147 on M4**, so
this may be a target difference or a carrier difference. **It is not resolved here and no
boundary was moved on the strength of it.** The finding is written into the descriptor's
semantics and needs its own experiment: a G17P re-derivation of byte+3's accept set in both
members.

**For the label owner:** `pixel_order.scope`'s recorded range *"full 8-bit range, dense (256
cases)"* overstates the field by **4×** — only 64 of those 256 values are legal under the
descriptor. The row is otherwise untouched.

### 3.3 `DEF-0181-2` — five descriptors' HW-validated anchors DO NOT TOKENIZE

`analysis/anchor_reachability.py`. This was not being checked by anything.

| descriptor | anchor as DISPATCHED | `decode_one` says | corpus reaches it at |
|---|---|---|---|
| `bf_add_dst` | `21001c001100c081` (EXP-0156) | `operand_word`, len 2 | `11041c020100c081`, `51071c8105024000` |
| `bf_fma_dst` | `21001e0086041000c081` (EXP-0156) | `operand_word`, len 2 | `11021e0286040800c081` |
| `cvt_bf16` | `0101148105024000` (EXP-0162) | **unknown length** | `51033c8101024000`, `11033c8101024000` |
| `cvt_f2h_dst` | `c10114810402` (EXP-0162) | **unknown length** | `01011c8100c2`, `31053c810422` |
| `hminmax` | `22001c0010c0` (EXP-0156) | **truncated: needs 10, has 6** | `12021c0400c0`, `020e1c047808` |

`hminmax` is the sharpest: holding byte+1/byte+2 at the anchor's values, **only destination
nibbles 0 and 1 decode at length 6** — and the hardware-validated anchor is nibble **2**. So
the descriptor decodes at 2 of 16 destinations and not at the one that proved it.

The bfloat pair is DEF-0171-2, already recorded and owned by `isadb.py`'s owner (the
low-nibble-1 branch is gated on byte+1 ∈ {0x02, 0x04}; G17P emits `0x00`). The `cvt_bf16` and
`cvt_f2h_dst` cases are **new here** and are additionally entangled with EXP-0162's finding
that `cvt_bf16`'s match constant `[32,8,1]` names a value the hardware rejects.

**Reported, not patched.** It is a length-rule change in another owner's file and it would
move decode for a family wider than these five. Nothing in `db.json` was altered for it.

---

## 4. What was CHANGED in `db.json` — one coherent write

`analysis/apply_defects.py`, which asserts the pre-state of every field it touches.
sha `a77f8cfa163fcf72…` → `1ada4e7bb7879cd6…`. **172 instructions, 1036 fields — both
unchanged**; a narrowing removes no name.

| descriptor | before | after |
|---|---|---|
| `iter_at.grp` | `start 0, width 8, raw` | **`start 7, width 1, raw`** |
| `reg_move_cb.form` | `start 16, width 8, raw` | **`start 20, width 4, raw`** |
| `shift_amt_move.kind` | `start 16, width 8, enum {28: shift_amt, 60: rotate_amt}` | **`start 20, width 4, enum {1: shift_amt (byte+2 = 0x1c), 3: rotate_amt (byte+2 = 0x3c)}`** |

Each gains a `match_notes` entry recording the pinned remainder — the convention EXP-0175
established for the 25 zero-free-bit folds, with a `note` marking these as **PARTIAL**
narrowings so the two uses are not confused. Each descriptor's `semantics` records the
measurement, the carriers, the runs, and what was *not* established. `pixel_order` gains the
DEF-0181-1 paragraph and **no field change**.

**Direct effect on an emitter, which is the whole point.** Before, `assemble()` refused
every value whose pinned bits did not already agree — an implementer had to know the pin to
use the field. After:

```
iter_at.grp        0..1   -> 2f0054… / af0054…      (both legal encodings reachable)
reg_move_cb.form   0..15  -> 0b000b … 0b00fb        (all 16 legal encodings reachable)
shift_amt_move.kind 0..15 -> 0b000c … 0b00fc        (all 16 legal encodings reachable)
```

and every decode → re-assemble on real corpus and HW bytes is byte-exact
(`af14540c03000a01`, `2f14540c03000a01`, `0b003b00`, `0b001c05`, `0b003c05`, and both
`pixel_order` fixtures).

---

## 5. Gate results — and the isolation measurement that separates my edit from EXP-0179's

### 5.1 Corpus — the real check

| | clean | strict leftover | tokens | round trip |
|---|---|---:|---:|---|
| baseline (`a77f8cfa…`) | 833/1080 | 388,604 | 25,419 | 302 OK / 0 FAIL / ALL PASS |
| **after every EXP-0181 edit** | **833/1080** | **388,604** | **25,419** | **302 OK / 0 FAIL / ALL PASS** |

**Zero firing delta.** A field's span does not participate in matching or length, so
narrowing changes what the disassembler *reports*, never what it *claims*. Unlike EXP-0175,
no `roundtrip_test.py` fixture patch was needed: no field name was added or removed.

`ab_gate.py` runs each tree's `roundtrip_test.py` in a **subprocess**. I inherited EXP-0175's
already-fixed copy and re-read it before use, per DEF-0175-2 — the `runpy` version reports
the FIRST tree's database for every later tree and swallowed a real crash.

### 5.2 `match_overlap_report.py`

**34 → 31** overlapping rows. Zero-free-bit stays **0** and vacuous emitter-grade stays **0**
(EXP-0175 cleared both). The three that left are exactly the three narrowed; `pixel_order.scope`
remains, by intent, and is now the most over-declared row in the report.

### 5.3 `validate_labels.py` — **exit 0**

Only the `db_sha256` WARN, which is the orchestrator's to clear. **0 orphans, 0 created
rows.** All three narrowings keep the field's name, so validation.json still has exactly one
row per db.json field. Three rows are **RE-SPANNED** and are listed with re-scored
recommendations in `analysis/orphaned_validation_rows.json`:

| row | old span | new span | stale keys in the row | recommended |
|---|---|---|---|---|
| `iter_at.grp` | 0, 8 | **7, 1** | `start`, `width` | `isolated-byte-diff`, G17P, "0..1 dense, 3 gated runs, 2 carriers" |
| `reg_move_cb.form` | 16, 8 | **20, 4** | `start`, `width`, `values_dispatched`, `distinct_bytes`, `encodable_range` | `hardware-run`, G17P, "0..15 dense, 2 carriers × 2 gated runs" |
| `shift_amt_move.kind` | 16, 8 | **20, 4** | — (plus the whole `range`/`note` **value space**) | `hardware-run`, G16G+G17P, "0..15 dense, both targets" |

### 5.4 The headline — measured, not asserted

The dispatch quotes 52/166 and 617 fields. Running `validate_labels.py` against the
**pre-image** `db.json` (`work/db.json.before`, sha `a77f8cfa…`, byte-identical to
`HEAD:tools/agx-isa/db.json`) and the live `validation.json`:

| | pre-image db.json | after EXP-0181 |
|---|---|---|
| instructions / fields | 172 / 1036 | 172 / 1036 |
| `hardware-run` / `isolated-byte-diff` | 540 / 81 | 540 / 81 |
| emittable (emitter-relevant) | **53 / 166** | **53 / 166** |
| the DEF-0173-1 gap | 30 | 30 |

**Identical.** The 52 → 53 and 617 → 621 movement came from the orchestrator's
`955eb6c7 exp(0179)` landing mid-experiment (`call` became emittable), **not** from this
experiment. EXP-0181's `db.json` edit moves no headline number.

---

## 6. If the gate is applied — the number, and its direction

| | emittable |
|---|---:|
| today, field labels only (the live headline) | **53 / 166** |
| gated on `_instruction` **as the labels stand today** | **23** |
| gated on `_instruction` **with these recommendations** | **48** |

So the refresh converts a 30-instruction cliff into a **5-instruction, fully-argued cost**,
and the direction is **down by 5 from the published 53**. Per the dispatch's own preference —
*a smaller defensible number over a larger one I cannot justify* — **48 of 166 is the number
this experiment supports**, and the five it drops are named, with the reason and the
experiment that would restore each.

Two further reductions are worth the orchestrator's attention but are **not** mine to make:

- EXP-0175 recommends downgrading `ibfe.sign_ext` and `ibfe.b2_bit0` to
  `single-template-inference`, which drops `ibfe` out of the emittable set.
- `falu3_ext` (§1.6) belongs at `isolated-byte-diff` if the label must certify the saturate.

Neither changes the count above, which is computed on the live `validation.json`.

---

## 7. Limitations — what this experiment cannot do

1. **It cannot re-observe a hardware fact.** Every Task 1 recommendation is a judgement over
   a committed record. It checks that the record exists, that its scoring regime is what the
   label would imply, and that the bytes are attributable to the descriptor — it cannot
   re-run the GPU. Where I say "confirmed against a host oracle" I mean *the raw says so and
   the note describes an oracle independent of the GPU*; I did not re-derive the oracles.
2. **The per-instruction rulings are mine, not a computation.** The instruments are
   mechanical; the mapping from evidence to label is a reading of R1–R5. Each row carries the
   citation and the refuter so a reviewer can disagree row by row.
3. **`analysis/scan_dispatch_evidence.py` under-counts oracle-scored cases** for harnesses
   that keep the oracle at carrier level (EXP-0155, EXP-0157, EXP-0161, EXP-0172 report
   `oracle_scored_cases = 0` while genuinely having a carrier oracle). That is why §1.2's
   three-regime table exists and why the counts are not used as a threshold.
4. **`bf_add_dst`, `bf_fma_dst`, `cvt_bf16`, `cvt_f2h_dst`, `hminmax`** are recommended for
   `hardware-run` while their anchors do not tokenize (§3.3). Moving them down one rung to
   `isolated-byte-diff` would **not** change the gate number, because that label is also
   emitter grade. But if the orchestrator holds the stronger policy — *an instruction whose
   HW-validated encoding the tokenizer cannot reach is not emittable at all* — those five
   leave the set and the gate number becomes **43, not 48**. That is a policy call about what
   `emittable` should mean, and I have flagged it rather than pre-empted it.
5. **Task 2 fixed field spans, not accept sets.** The narrowings make the legal range
   reachable through `assemble()`; they do not establish what the free bits *mean*.
   `reg_move_cb.form` 4..15 and `shift_amt_move.kind`'s rejected values are recorded outcomes,
   not decoded semantics.
6. **`pixel_order` is left with a live contradiction** between its G17P match and its M4
   accept sets (§3.2). Until that is resolved on G17P, an emitter following `db.json` can
   encode only half of what each carrier accepts, and `assemble()` will refuse three quarters
   of the byte.
