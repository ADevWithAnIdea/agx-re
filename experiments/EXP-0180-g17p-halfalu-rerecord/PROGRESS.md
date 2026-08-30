# EXP-0180 — PROGRESS

Append-only. Timestamped per milestone. Written so a kill costs at most one milestone.

---

## M1 — 2026-08-30 — target set resolved, spans re-checked, db PINNED. No device touched.

**Pinned inputs (frozen before any build):**

| file | sha256 |
|---|---|
| `work/frozen/db.json` (copy of `tools/agx-isa/db.json`) | `a77f8cfa163fcf720c0c1093e4ddc5815ceb43c218bb64a87c86d3dcf975dc22` |
| `work/frozen/isadb.py` | `9cda47a1d4b3857c9f20423ab5d63c38050d37220da06bc5d2dc12a77d6ef1a8` |
| `tools/agx-isa/validation.json` (read-only) | `a30309f0bf0004085b8327de2eaeeae9f987a7b930961b303c654aa9764c9bc9` |

`validation.json.db_sha256 == a77f8cfa…` — the pinned db **is** the one the live label
table was generated against. **This experiment resolves `isadb` explicitly to
`work/frozen/`; the path fall-through that silently picked up the neo's stale shared copy
for a sibling experiment is removed, not merely reordered.**

Repo revision at pre-registration: `db7c3c957a8788b8589978a48c044b049dde2cc2`, working tree
dirty (25 unstaged/untracked paths, all sibling experiments). Per `SUBAGENT_BRIEF.md` the
gate is the **authored blob hashes**, not live `HEAD`.

**Target set (`analysis/target_rows.py` → `work/target_rows.json`):**

* **25 row-claims over 16 DISTINCT FIELDS.** The 9 `EXP-M4-14` rows are a **strict subset**
  of the 16 rows EXP-0169 held; the union is 16, not 25. Nine fields therefore carry two
  independent claims each and get two verdicts each.
* **0 spans moved** since EXP-0169 measured them; 0 fields absent from the pinned db.
* `EXP-M4-14` is cited by **46 rows across the whole db**; only 9 are in this family.

**Current committed state of the 16 (this is what a run must substantiate or withdraw):**

| citation | rows | labels |
|---|---|---|
| `EXP-M4-14` (A18, no `raw/` tree anywhere) | 9 | 6 `hardware-run`, 3 `isolated-byte-diff` |
| `EXP-0138` (M4) | 4 | 4 `hardware-run` |
| `EXP-0169` (G17P) | 3 | 3 `untested` |

## M2 — 2026-08-30 — root cause of the EXP-0169 ladder failure IDENTIFIED, offline, from committed raw

Named **DEF-0180-A**. See `PRE_REGISTRATION.md` §3. One-line form: the C1_alu seeds are
`falu2i` minifloat fixed points whose fp32 bit patterns have **zero low 16 bits**, and a
half-precision operand descriptor with its size bit clear reads exactly those 16 bits — so
the lifted anchor's operands were `0.0`, its result was `0`, and it wrote that `0` into a
register the same instruction had already released to `0`. The pre-registered falsifier
(byte0 → `0x00`) therefore scored `match: true` **by construction**, exactly as EXP-0140's
co-varying oracle did. This is a *carrier* defect, distinct from DEF-0169-1 (the async
`device_load`), and it is why the C1/C2 asymmetry existed at all.

## M3 — 2026-08-30 — the root cause is NOT what EXP-0169 assumed, and there is a db-model defect under it

All of this is **offline re-analysis of EXP-0169's committed `raw/g17p_20260830_run01/sweep.jsonl`**.
No device. It is recorded here before any build because it changes the design.

### DEF-0180-A (carrier) — the anchors were COMPUTATIONALLY DEAD in C1_alu

`half_alu` (6B) passed its falsifier; `half_alu_ext8` and `half_alu_fma12` failed it with
`outcome: ok, match: true`. The difference is not the instruction, it is the **anchor's base
operand values relative to the carrier's seeded state**:

* the ext8/fma12 anchors were lifted from `k_hfma` / `k_hfma_abs`, whose operand bytes name
  half-registers `0x81`/`0x83` — **registers 64/65**, which in the native kernel held
  `device_load` results and which the synthesized carrier **never seeds**;
* the C1_alu seeds are `falu2i` minifloat fixed points, so every GPR's **low 16 bits are
  zero**, and every EVEN half-register descriptor therefore reads `0.0`.

So the product term was `0`, the sum was `0`, and `0` was written where `0` already was.
The falsifier could not fire. Quantitatively, in EXP-0169's own raw (C1_alu, run01):

| field | moved / dispatched | which values moved |
|---|---|---|
| `half_alu_ext8.dst` | 28 / 256 | exactly `{2k+1 : k=0..13} ∪ {128+2k+1 : k=0..13}` |
| `half_alu_ext8.b5` | 28 / 256 | the identical set |
| `half_alu_ext8.rsv6` | 0 / 256 | — |
| `half_alu_ext8.b7_lo` | 0 / 2 | — |
| `half_alu_ext8.op_valid_marker` | **0 / 2** | — (a direct contradiction of the EXP-M4-14 claim) |

Only descriptors naming a **seeded register's non-zero half** could move anything;
`r14`/`r15` seed to `0`, which is why the set stops at `k=13`. **Bit 7 of the descriptor is a
don't-care** — `129..155` mirrors `1..27` exactly.

### DEF-0180-B (db model) — `half_alu*.dst` is at the WRONG OFFSET

Reading EXP-0169's `half_alu` `dst`/`srcB` sweeps value by value:

    anchor  10 02 1c 03 00 c0   (opsel=4 hadd, opflags=3, srcA=0x03, srcB=0x00, mod=0xc0)
    seeds   r0=5.0 r1=1.5 r2=3.0 r3=0.5   -> hi halves 0x40A0 0x3FC0 0x4040 0x3F00

| byte+1 (`dst` per db) | observed | reads as |
|---|---|---|
| `0x00,0x02,0x04,0x06` | r1 = `0x00003FC0`, all else = seeds | operand = an EVEN half = `0.0` → `1.9375 + 0` |
| `0x01` | r1 = `0x00004440`, **r0 → 0** | `1.9375 + 2.3125 = 4.25` = h1 = r0.hi, and r0 released |
| `0x03` | r1 = `0x000043C0` | `1.9375 + 1.9375 = 3.875` = h3 = r1.hi |
| `0x05` | r1 = `0x00004410`, **r2 → 0** | `1.9375 + 2.125 = 4.0625` = h5 = r2.hi |
| `0x07` | r1 = `0x00004360`, **r3 → 0** | `1.9375 + 1.75 = 3.6875` = h7 = r3.hi |

**byte+1 is a SOURCE half-register descriptor (half-reg index = the byte's value), not the
destination.** The result lands in **r1 in every case** — and `byte0 == 0x10`, whose HIGH
NIBBLE is `1`. `db.json` pins all eight bits of byte0 in `match: [[0,8,16]]`.

> **Hypothesis H0: the destination of the `byte0==0x10` half-ALU family is byte0 bits 4..7,
> exactly as in `falu2` (`dst 4 4`), `n3_mov`, `mov_zext16` and `cvt_f2h_dst` — and `db.json`
> models it at bits 8..15 instead.**

`db.json` already records this exact structure for the neighbouring families:
`cvt_f2h` — *"byte0 0x11 … (dst r1)"*, generalised by `cvt_f2h_dst` to *"ANY dst register
(byte0 high nibble)"*; `mov_zext16` — *"the pre-2026-08-30 descriptor pinned byte0 to the full
fixed byte 0x13 and modelled byte+1 as the source register, so the real register selector was
invisible to an emitter"* (DEF-0161-2). **This is the same defect, one family over, and it is
underneath two of my 25 rows** (`half_alu_ext8.dst`, `half_alu_fma12.dst`, both currently
`hardware-run`).

### DEF-0180-C (length model) — `opsel` bit 1 is the LENGTH bit, and `half_alu_fma12` has no length rule

`db.json length_rule.byte0_table["0x10"] = "6, or 8 if (byte+2 & 0x02)"`. Byte+2 bit 1 is
**bit 17 = `opsel` bit 1**. So half of every `opsel` sweep re-lengths the instruction, and
`half_alu_fma12` (length 12) has **no entry in the length table at all** — it is one of the
three instructions `db.json` itself flags as an over-consumer (`doc02_over_consumers_20260828`,
`emit_unsafe`). `half_alu_fma12.ext` is 64 bits wide with an encodable range of 2^64 and can
never meet the coverage bar.

## M4 — 2026-08-30 — DEF-0180-B and DEF-0180-D CONFIRMED offline; the falsifier EXP-0169 used was never valid for this family

### The `byte0` falsifier does not null the op — it MOVES THE DESTINATION

EXP-0169 `raw/g17p_20260830_run01`, `HALF_ALU@C1_alu`, `__falsifier_byte0`
(`10 02 1c 03 00 c0` → `00 02 1c 03 00 c0`):

    baseline   r0 = 40a00000   r1 = 00003fc0      <- result 0x3FC0 in r1.LOW half
    byte0=0x00 r0 = 40a03fc0   r1 = 00000000      <- SAME result, now in r0.LOW half,
                                                     r0's HIGH half preserved

**HW evidence, G17P, already in the committed corpus: the destination GPR of the
`byte0==0x10` half-ALU family is byte0's HIGH NIBBLE, and the result is written to that
register's LOW 16 bits.** `db.json` pins all 8 bits of byte0 in `match` (so an emitter
following it can only ever write `r1`) and calls bits 8..15 `dst`, which the same raw shows
is a **source half-register descriptor** (§M3). `isadb.instr_length` has the mirror-image
bug: its own docstring records that for the `0x09` float family "byte0's high nibble carries
the dst register number … using the full byte mis-tokenizes any falu2 whose dst >= 1", and
then line 1861 gates the half family on `b0 == 0x10` — the full byte.

**Consequence for EXP-0169's ladder: `__falsifier_byte0` is not a falsifier for this family.**
It changes only which register is written. For `half_alu` the result was non-zero so it moved
anyway; for `half_alu_ext8`/`half_alu_fma12` the result was `0` and the target low half was
already `0`, so it could not. The "ladder failure" that held 16 rows was an artefact of a
falsifier that does not falsify.

### DEF-0180-D — the length selector is `byte+4 & 3`, and `db.json`'s stated rule is wrong

`isadb.instr_length` implements, for `b0 == 0x10`: `6 + 2*(byte+4 & 3)`, with an
`8`-when-zero override if `byte+2 & 2`. `db.json length_rule.byte0_table["0x10"]` states
something different and simpler: `"6, or 8 if (byte+2 & 0x02)"`. Both cannot be right, and
**neither has ever been measured against the hardware.**

The code rule predicts EXP-0169's otherwise-unexplained `half_alu.srcB` (= byte+4) sweep
exactly:

| `byte+4 & 3` | predicted length | EXP-0169 observed at `srcB` ≡ that value (mod 4) |
|---|---|---|
| 0 | 6 (2 spare bytes → harmless `pad_operand`) | `match` (baseline) |
| 1 | 8 (the anchor) | `match` (baseline) |
| 2 | 10 (swallows 4 bytes of the following dump) | **every output word still `0xDEADBEEF`** — the program never stored anything |
| 3 | 12 (swallows 6 bytes) | r1 keeps its seed — the op did not write |

**So `half_alu_ext8.srcB_desc`'s low two bits and `half_alu_fma12.ext`'s byte+4 are LENGTH
selectors, not operand bits.** Three quarters of a 256-value `srcB_desc` sweep encode a
*different-length instruction* — the `falu2_uni.uni_mode` lesson (EXP-0169 §16b) at scale.
This is why every case in EXP-0180 records `tok_instr` **and** a hardware-measured length.

## M5 — 2026-08-30 — PRE-REGISTRATION FROZEN. Device NOT touched.

`PRE_REGISTRATION.md` (380+ lines) and `CAPTURE_CONTRACT.json` written before any build.
`README.md` written. **No SSH to the neo has been issued at any point.**

Design in one paragraph: two carriers (`C_HI` result > 1.0 / `C_LO` result < 1.0, different
shaders, different buffer signatures, different seed permutations, different tail slack,
`C_LO` with a second consumer), seven arms (`E8_ADD`, `E8_FMA`, `F12_FMA` generated on both
carriers; `E8_LIFT`, `F12_LIFT` as EXP-0169-anchor controls; `LEN` = a four-marker chain that
reads the **hardware's** instruction length directly; `DSTNIB` = the H0 destination probe),
~16.7 k cases per gated run, seeds proved per case by a PRE-dump, no refreshed baseline
anywhere, no abort path, and a frozen expressiveness rule that forbids promoting an inert
reading on a carrier that cannot express the field.

**Amendment 01 adopted before dispatch** on the coordinator's EXP-0179 relay: the
`carrier_dead` outcome class + a pilot rejection gate; `gate_expressiveness`; two extra
`C_LO` differences (tail slack for the framing dimension, a second consumer for the ordering
dimension); the run-id burn rule.

**Coordinator hold acknowledged. EXP-0179 has the device for a hang-candidate window. This
experiment is QUIET — nothing dispatched, nothing to checkpoint.** Next milestone is the
harness build, which is entirely offline.

## M6 — 2026-08-30 — amendment 02 adopted before dispatch; still QUIET, still zero SSH

Two items from the coordinator's EXP-0178 relay, both on this experiment's critical path:

1. **`tools/agxtest/persistrun.py` can manufacture hangs.** One reader thread per *line*,
   abandoned on timeout, re-resolving `self.proc` at execution time → after the first
   watchdog timeout it races the replacement child's stdout, `OUT 0 ` comes back truncated,
   and the shared parser raises. EXP-0178 saw one genuine hang produce **three consecutive
   FALSE hangs with `restarts=99`**. This experiment pre-registers **no abort path and no
   hang budget** and deliberately mutates length/identity bits, so desyncs and watchdog
   timeouts are *expected by design* — a false-hang cascade could make me **withdraw rows for
   a harness artefact**, the exact inverse of the defect that put them here.
   → `harness/saferunner.py :: SafePersistRunner` (adopted from EXP-0178's own file, our
   code, cited in the header): **one reader thread per child**, queue tagged by owner, lines
   from a killed child discarded. **The shared tool is NOT modified** — EXP-0179 is running
   against it. New outcome `measurement_failed`: a `MALFORMED` response is a *failure to
   measure*, never `hang`/`fault`/`ok`, raw lines kept, retried 3×, and **excluded from
   `values_dispatched`** so it cannot inflate coverage either. Post-hang quarantine: restart,
   unspliced health check, and re-run everything since the hang if the check is not `ok`.

2. **Geometry is a carrier variable.** EXP-0178 root-caused EXP-0169's `get_sr` ladder failure
   as `grid=1/tg=1`, where every reachable system value reads 0 — the same "carrier cannot
   express the question" class as my 25 rows. None of my 16 fields is a system-value read and
   the half ALU works on lanes *within* a register, so `grid=1` should be adequate — **so the
   pilot measures it instead of asserting it**: every (arm, carrier) runs its anchor, full
   ladder and all four falsifiers at **both** `grid=1/tg=1` and `grid=32/tg=32`, recorded
   side by side in `raw/pilot01/geometry.jsonl`, with a frozen re-basing rule.

**Status: QUIET. Zero SSH to the neo. Nothing to checkpoint.** Holding for the clear.

## M7 — 2026-08-30 — db defects numbered; runner checked against DEF-0178-1. Still QUIET.

* **`analysis/db_defects.json` written**, seven numbered entries the orchestrator can act on
  (`DEF-0180-1` … `DEF-0180-7`) plus two **method** defects kept in a separate
  `_method_defects_not_db` block so they cannot be mistaken for db edits:
  * `DEF-0180-1` — `half_alu*.dst` at the wrong offset; destination is byte0 bits 4..7,
    bits 8..15 are a SOURCE half-register descriptor. **LOAD-BEARING**; sits under two rows
    currently labelled `hardware-run`.
  * `DEF-0180-2` — the byte0 `0x10` length rule contradicts `isadb.instr_length`;
    `byte+4 & 3` is a length selector inside `srcB_desc` and `ext`. **LOAD-BEARING.**
  * `DEF-0180-3` — `half_alu_fma12.ext` is not a field (2^64, over-consumer).
  * `DEF-0180-4/5/6` — three citation defects readable from committed text alone.
  * `DEF-0180-7` — `isadb.instr_length` gates the half family on the full byte, so any half
    op with `dst != r1` does not tokenize; the same function's docstring records that this
    exact bug was fixed for the `0x09` family and never applied to `0x10`.
  * `DEF-0180-A/B` (method) — the dead anchor, and "the falsifier was never a falsifier".

  **Every entry is marked `PROPOSED`: offline derivation from committed evidence, no EXP-0180
  device run yet.** The gated pair will restate each as CONFIRMED or REFUTED. `db.json`,
  `validation.json`, `docs/` and `PROVENANCE.md` are untouched and stay that way.

* **Runner checked against DEF-0178-1 and subclassed.** `harness/saferunner.py` is in place
  (adopted from EXP-0178's own file, header preserved, render half removed, EXP-0180 rationale
  prepended). One reader thread per child, queue tagged by owner, lines from a killed child
  discarded; `MALFORMED` → `measurement_failed`, raw lines kept, retried, excluded from
  `values_dispatched`. **`tools/agxtest/persistrun.py` is NOT modified** — EXP-0179 is running
  against it. Parses clean.

**Status: QUIET. Zero SSH to the neo. Nothing dispatched, nothing to checkpoint.**
Remaining offline work: `kernels/*.metal`, `harness/{isa_helpers,casematrix,anchors,smoke,run,
procsample,selftest}.py`, `work/stub/fakerunner.py`, `analysis/{verdicts,merge_check}.py`.

## M8 — 2026-08-30 — harness COMPLETE and frozen offline; all nine offline gates pass. Still zero SSH.

Authored and hashed into `CAPTURE_CONTRACT.json:authored_source_sha256`; `raw/FREEZE_MARKER.txt`
written.

| file | what |
|---|---|
| `kernels/carrier_dag.metal`, `kernels/carrier_uni.metal` | `C_HI` / `C_LO`; lengthened over EXP-0169's because every case now dumps all 16 GPRs **twice** |
| `kernels/probes.metal` | six authored half-precision kernels; supply the two lift-control anchors |
| `harness/isa_helpers.py` | **explicit** pinned-ISA resolution (raises rather than falling back), the two-half seed construction, both frozen stage-2 variants, program builder with PRE-dump + POST-dump, marker chain, tail slack, second consumer |
| `harness/casematrix.py` | the frozen matrix: 7 arms, coverage rule, ladder, three falsifiers, `LEN`, `DSTNIB` |
| `harness/saferunner.py` | DEF-0178-1 subclass; shared tool untouched |
| `harness/run.py` | driver; no abort path; anchor captured **once** per (arm,carrier) and never refreshed; retries only non-observations |
| `harness/anchors.py`, `procsample.py`, `selftest.py`, `sync.sh` | anchor resolution, quiet-window measurement, offline gates, push/pull (`SSHPASS` only) |
| `analysis/verdicts.py`, `merge_check.py`, `db_defects.json`, `target_rows.py` | verdicts under the frozen gates; a merge gate that **refuses** a moved span or a missing coverage key |
| `work/stub/fakerunner.py` | offline proof of the DEF-0178-1 fix |

**Offline selftest: 9/9 PASS** (`work/selftest.json`) — pins, all 16 spans, both seed tables
adequate (28 distinct normal non-zero fp16 lanes each), exact minifloat fixed points, program
fits, every generated base has the intended `byte+4 & 3` length class and names **no unseeded
register and never the destination**, the matrix is deterministic and every case's value reads
back out of its own bytes through db.json's geometry, ladders ≥ 5 / falsifiers = 3 on every
generated arm with `byte0 → 0x00` confined to `DSTNIB`, and **G9: a truncated response yields
`MALFORMED` with the raw lines kept — never a crash, never a hang.**

Offline matrix (without the two lift-control arms, whose anchors resolve on the neo):
**12,761 cases**, `matrix_sha256` recorded in the contract. With the lift arms the gated pair
will be ≈ 16.7 k cases each, in line with EXP-0169's 16,827 in 190 s.

**Status: QUIET. Zero SSH to the neo. `raw/` holds only the freeze marker.** Ready to dispatch
the pilot the moment the device clears.

## M9 — 2026-08-30 — PILOT COMPLETE on G17P. The carrier repair WORKS, and the length rule is MEASURED.

`raw/pilot01`, 2241 cases: **0 hangs, 0 `carrier_dead`, 0 `invalid_run`, 0 `measurement_failed`,
0 victims.** Outcomes: 2065 `wrong_value`, 128 `fault`, 48 `ok`. `verify_remote.py` reported
**18/18 blobs matching on the neo** immediately before the capture.

### The seeds land, exactly as predicted, on every arm and both carriers
`seed_ok = True` and the FROZEN adequacy predicate `True` on all 11 (arm, carrier) anchors.
The observed pre-dump is bit-identical to the predicted `SEED_A` / `SEED_B`:
`40a044a0 3fc04440 40404470 bf003880 …`. **DEF-0180-A is repaired**: every GPR now carries two
distinct non-zero normal fp16 lanes, so all 256 descriptor values are informative rather than
28 of them.

### DEF-0180-1 CONFIRMED on hardware — 16 of 16 nibbles, on two carriers
The `DSTNIB` arm: `byte0 = n<<4` writes the result into **`r[n]`'s LOW 16 bits, preserving
`r[n]`'s HIGH 16 bits**, for every `n`. `n = 0`: `r0 40a044a0 -> 40a0470f`. `n = 7`:
`r7 415044f8 -> 4150470f`. Two explained exceptions, both harness artefacts, not hardware:
`n = 15` is the store index register the harness re-seeds before every store, and on `C_LO`
`n = 13` is the second-consumer destination.
**`db.json` pins all eight bits of byte0 in `match`, so an emitter following it can only ever
write `r1`. That is now HW-VALIDATED on G17P, not inferred.**

### The seed program is itself a 14-way confirmation
Stage 2 builds the low halves with `byte0 = (j<<4)|0x0` for `j = 0..13`, and all 14 landed in
`r_j` in every program of every case. The destination-nibble result is not resting on one arm.

### DEF-0180-2 CONFIRMED, and the exact rule is now MEASURED — 2048 cases, ZERO exceptions
`LEN` arm, four `mov_imm` markers at byte +6, surviving-marker count read directly:

    HARDWARE LENGTH, byte0 == 0x10, as a function of (opsel = byte+2 & 7, m = byte+4 & 3)

      opsel        m=0   m=1   m=2   m=3
      0,1,2,3,7     10    10    10     8
      4  (hadd)      6     8    10     6
      5  (hmul)      6     8    10     8
      6  (hfma)      6     8    10    12

**No (opsel, m) cell shows more than one length** — `opflags`, byte+4's upper six bits, and
byte+1/+3/+5 are all irrelevant to length. The F4 zero point passed (4 of 4 markers with no
instruction in front). Bounded: bytes +6.. are the marker chain, so a length dependence on
byte +6 or later is untested.

Both committed models are wrong, in different cells:
* `db.json`'s `"6, or 8 if (byte+2 & 0x02)"` — wrong in **26 of 32** cells; it has no byte+4 term at all.
* `isadb.instr_length`'s `(6 + 2*(b4&3)) if (b4&3) else 8` — wrong in **14 of 32** cells, including
  (opsel 4, m 3) → predicts 12, measured **6**, and (opsel 6, m 0) → predicts 8, measured **6**.

**DEF-0180-3 is REFUTED as stated, and I am withdrawing my own claim.** All four of our
compiled instances are lengthed correctly by the measured rule — `k_hadd` (opsel 4, m 0) = 6,
`k_hsat` (4, 1) = 8, `k_hfma` (6, 1) = 8, `k_hfma_abs` (6, 3) = **12**. `half_alu_fma12` IS a
real 12-byte instruction at (opsel 6, m 3); it is not an over-consumer there. What survives of
DEF-0180-3 is narrower and still true: `ext` is 64 bits with an encodable range of 2^64, and
its byte+4 is the LENGTH selector, so it is not a field.

### A second exact fault wall, in `opflags` — 128 cases, zero counterexamples

    fault  <=>  (byte+2 >> 3) >= 16  AND  (byte+2 & 7) in {4, 5}

i.e. **`opflags` bit 4 (instruction bit 23) set, with `opsel` = hadd or hmul, faults
unconditionally.** This lands directly on two of the 25 rows (`ext8.opflags`,
`fma12.opflags`). Faults were contained: no hang, no reset, no victim.

### The instruments, at BOTH geometries
`grid=1/tg=1` and `grid=32/tg=32` agree on **every** falsifier and ladder step, in every arm
and carrier — the §12b geometry check ran and agreed, so the gated pair runs at 1/1.

| arm | falsifiers | ladder | verdict |
|---|---|---|---|
| `E8_FMA` @ C_HI, C_LO | 3/3 fire | 4/5 move | **admissible, two carriers** |
| `F12_FMA` @ C_HI, C_LO | 3/3 fire | 4/5 move | **admissible, two carriers** |
| `E8_LIFT`, `F12_LIFT` @ C_HI | 3/3 fire | 4/5 move | **admissible** — and note EXP-0169's own anchors are LIVE in this carrier, which is the A/B the controls exist for |
| `E8_ADD` @ C_HI, C_LO | **0/3 fire** | **0/5 move** | **REJECTED: no detection power.** Its base (opsel 4 in the 8-byte form) writes nothing at all — every falsifier scored `ok/match=True`. Reported, not worked around; `E8_FMA` covers the same 11 fields on two carriers |

The two ladder steps that do NOT move are themselves results, and both were pre-registered as
diagnostic: `L_srcB_desc_samelen` (byte+4 `+4`, same length class) is inert on every ext8 arm
— **byte+4 is a pure length selector, not an operand** — and `L_ext_b9` (byte+9 `0x80 -> 0x00`)
is inert on every fma12 arm.

### Operand roles, read off the anchor and host-checkable
`E8_FMA@C_HI`: `r1 3fc04440 -> 3fc0470f`. `0x470f` = 7.0586 = `1.625 * 2.59375 + 2.84375`
= **byte+3 (`srcA`) x byte+1 (db's `dst`) + byte+5 (`b5`)**. byte+4 does not appear in the
arithmetic at all. This is the second independent line of evidence that db's `dst` is a source.

**Gated pair launched** (`g17p_run01` forward, `g17p_run02` reverse), with `procsample.py`
measuring concurrent GPU activity for the duration.

## M10 — 2026-08-30 — RUN ID `g17p_run01` IS BURNED. My own guard fired; the rule held.

I launched `procsample.py --run g17p_run01` one second before `run.py --run g17p_run01`.
`procsample` creates `raw/<run>/` to write `03_procsample.jsonl`, so `run.py`'s own
never-reuse guard saw the directory already existing and **refused to capture**:

    run id g17p_run01 already exists -- run ids are NEVER reused or topped up
    (SUBAGENT_BRIEF.md). Burn it and take a new id.

That is the guard working exactly as intended, on me. Per the frozen rule
(`CAPTURE_CONTRACT.json:runs.burn_rule`) **`g17p_run01` is retained as it stands — a
directory containing only its procsample trace — and the id is BURNED. It is not reused, not
topped up, not deleted.** The forward run takes a NEW id, `g17p_run03`.

`g17p_run02` (reverse order) launched normally and is capturing.
