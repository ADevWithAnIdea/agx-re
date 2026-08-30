# EXP-0153 — PRE-REGISTRATION (FROZEN)

**Frozen 2026-08-30T05:2x UTC, before any device run.** Nothing below is edited
after the first capture. Amendments, if any, are appended as numbered sections
at the end with their own timestamp and the reason.

**Target: Apple A18 Pro / G17P** (`users-MacBook-Neo.local`, 192.168.10.243,
`Mac17,5`, `AGXAcceleratorG17P`, arch `applegpu_g17p`, 5 GPU cores, macOS 26.6
build 25G5043d, Metal family Apple9). **Every result this experiment produces is
labelled `target: G17P`.** No M4 label is ever carried onto a G17P record and no
G17P label onto an M4 record.

```
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: our own MSL (kernels/*.metal, all five verbatim copies of
  kernels already committed by EXP-0138/0139/0141/0146), the AGX bytes those
  compile to on G17P, and the outputs the GPU produced from them; for arm G,
  the own-MSL corpus at experiments/EXP-M4-13-full-corpus/corpus.
  tools/shdump, tools/agxtest and tools/agx-isa are used READ-ONLY and
  unmodified.
Apple binary introspection: NONE
Reproduction: harness/build.sh; harness/run.py --run-id <id> ...;
  analysis/verdicts.py; analysis/tokenize_corpus.py
Evidence: raw/<run_id>/{00_env.json,00_build.json,00_manifest.json,
  01_progress.json,sweep.jsonl}
```

---

## 1. Question

Every load-bearing ISA finding in this repository was measured on **M4 / G16G**
and its G17P status is `INFERRED`. The A18 Pro is now the test target. Which of
the seven highest-value M4 findings **reproduce as direct observation on G17P**,
and which **refute**?

A refutation is the more valuable outcome. One G16G↔G17P divergence is already
open (`tg_addr_compute`: on M4 only byte0 `0x1c` works and EXP-M4-14's A18
`0xfc` does not reproduce), so transfer is not a safe default.

This experiment **re-runs** committed experiments; it does not re-derive them.
Each arm therefore uses the same carrier, the same input vectors and the same
construction as the M4 experiment it revalidates.

## 2. Hypotheses, each with its refuter

`H0` for the whole experiment: **every M4 rule below holds unchanged on G17P.**
The global refuter is any arm in which the G17P accepted set, fault boundary or
numeric result differs from the M4 result on identical stimulus, reproducibly,
in **both** gated runs.

| id | claim under test (M4 source) | pre-registered G17P prediction | refuted if |
|---|---|---|---|
| **H-A1** | `device_load.dst_lo` accepts exactly `v & 3 == 1` (EXP-0141) | 1 of 4 values accepted, at both r7 and r20 | any other value works, or 1 fails |
| **H-A2** | `device_load.dst_ext9` accepts exactly `v & 1 == 1` (EXP-0141) | 64 of 128 accepted, the odd ones | the accepted set is not "odd" |
| **H-A3** | the (`dst_lo`,`dst_ext9`) pair accepts exactly `v & 0x181 == 0x81` (EXP-0141) | 64 of 512 | any other count/shape |
| **H-A4** | `extmode = 2*R` selects the destination; bit 0 don't-care; **R reachable 0..63 only, R ≥ 64 silently zeroes** (EXP-0141) | `extmode` 0..127 all work (both parities), 128..255 all silently zero | the 128 boundary moves, or odd values fail, or R ≥ 64 works |
| **H-B1** | `falu2.mod_lo` is an operand-SOURCE-CLASS field: bit0 = srcA class (1 ⇒ reads 0.0), bits[2:1] = srcB class (0 GPR, 1 non-GPR, 2/3 read 0.0, **bit2 dominates bit1**) (EXP-0138) | the model scores 64/64 | any case contradicts, in particular `mod_lo=6` returning the `mod_lo=2` value |
| **H-B2** | with `mod_lo` bits[2:1] = 1, `srcB_reg` **64..127 is an inline 8-bit minifloat**: k = v−64, e = k>>3, m = k&7, value = m·2⁻⁵ (e=0) else (8+m)·2^(e−6) (EXP-0138) | the formula scores 64/64 dense, and in particular reproduces the ten M4 HW points k = 0, 2, 3, 31, 32, 48, 56, 61, 62, 63 → 0, 0.0625, 0.09375, 1.875, 2.0, 8.0, 16.0, 26.0, 28.0, 30.0 | any k mismatches |
| **H-B3** | in the non-GPR class, `srcB_reg` 0..63 indexes an operand file that holds our bound `constant float4&` (M4: indices 6..9 = 101/202/303/404) (EXP-0138) | same four values appear somewhere in 0..63 | *(a MOVE of the indices is a CARRIER/container property, not a hardware refutation, and is reported as such; the absence of the values anywhere IS a refutation)* |
| **H-C1** | flipping `iadd2.addsub` (byte0 `0x1f` → `0x9f`) in the compiled `ulong a−b` turns it into an **exact single-instruction 64-bit ADD with carry across the word boundary** (EXP-0146) | all 12 rows exact, in 5/5 repetitions, in both runs; in particular 2⁶³+2⁶³ = 0, 0x7FFF…F+1 = 0x8000…0, 0xFFFFFFFF00000000+0xFFFFFFFF = 0xFFFF…F, 0xFFFF…E+3 = 1 | any row wrong, or the low→high carry does not propagate |
| **H-D1** | a 7-bit register field value R aliases `r(R mod 64)` for R ∈ [64,112]; **126/127 fault** (EXP-0112) | `falu2.srcB_reg` 64..112 reproduces `r(R mod 64)`; 126/127 fault reproducibly | aliasing absent (silent zero instead), or the fault boundary moves |
| **H-D2** | that aliasing does **NOT** hold for `iadd2.dst`, and **reg ≥ 96 faults** (EXP-0139) | `dst` = 140/141 (reg 70) does NOT reach r6; `dst` ≥ 192 faults reproducibly | reg 70 aliases to r6, or the fault boundary is not 96 |
| **H-E1** | `ibfe.offset` is **LITERAL**: 0–31 shift normally, 32–63 shift the field out entirely (result 0). The mod-32 model fits only 32/64 (EXP-0139) | literal model 64/64, mod-32 model 32/64 | mod-32 fits better |
| **H-E2** | `ibfe.width` is **TAKEN MOD 32**; the literal-clamp model fits only 37/64 (EXP-0139) | mod-32 model 64/64 | literal-clamp fits better |
| **H-F1** | `mov_imm`'s immediate is **7 bits**; with `imm_top = 1` the instruction **does not write at all**, and unpadded it consumes the following 2-byte instruction (EXP-0140) | padded: destination keeps its previous value (the poison 7); unpadded: the read-back store addresses the wrong word | the destination reads 0 in the padded form (a silent zero, not a non-write), or both forms agree |
| **H-F2** | `mov_imm` with `imm7 == 12` **does not tokenize** under the current length rule; whether the hardware agrees was never tested (EXP-0140) | the decoder still fails to tokenize (a `db.json` property, target-independent); **the hardware writes 12 normally** | the hardware also fails, i.e. `imm7 = 12` does not reach the destination |
| **H-G1** | the four EXP-0148 length-rule corrections hold on G17P-compiled code | tokenizing a **G17P-compiled** rebuild of the 1080-program own-MSL corpus with the current (patched) `db.json` gives clean-file and leftover-byte counts comparable to the M4 post-patch baseline **832 clean / 389 368 leftover bytes** | materially worse counts on G17P, i.e. the corrections are G16G-specific |
| **H-G2** | *(new, a stronger form of the same question)* `CLAUDE.md` records A18↔M4 byte-identity for every driver-emittable subsystem | a large majority of the 1080 corpus programs compile **byte-identically** on G17P and M4 | widespread byte differences — in which case the per-file differences are the finding |

## 3. Variables

- **Independent:** exactly one instruction field per case (or, for arm C, one
  bit of one field). Arms A and D-iadd2 additionally co-vary the *consumer*
  register with the swept destination, which is intrinsic to a
  destination-selector sweep and is stated in each case's `note`.
- **Controlled:** carrier MSL, input buffers, dispatch shape, tool revisions,
  and the field's own siblings, all frozen in §7 and re-recorded in
  `raw/<run>/00_env.json` at capture time.
- **Dependent:** the read-back words, the command-buffer status, and the OS
  fault-classification string.

## 4. Confounders and how each is handled

1. **A different `_agc.main` length on G17P.** The M4 constants (170 for the
   synthesis carrier, 300 for the uniform carrier, 1536 for the DAG carrier)
   are **not** used. `harness/run.py :: prepare()` compiles every carrier on the
   target and derives its region length; the value is recorded in
   `00_build.json`. Hard-coding an M4 length would be an automatic stop.
2. **A moved splice anchor.** Every splice target is located by tokenizing our
   own compiled carrier with `tools/agx-isa` at run time (`anchors.find`), and
   the resolved offset, length, bytes and decoded fields are recorded in
   `00_build.json`. The field setter is round-trip-checked against `isadb`
   before the first case (`anchors.check_field_setter`).
3. **A moved uniform-file index (H-B3).** Where the container places our bound
   `constant float4&` is a property of the compiler and the carrier, not of the
   ALU. Arm B therefore sweeps `srcB_reg` 0..63 **densely** and *discovers* the
   indices rather than assuming 6..9; a move is reported as a carrier
   observation and explicitly not as a hardware refutation.
4. **Innocent-victim contamination.** Other agents share this GPU. Every non-OK
   response's `kIOGPUCommandBufferCallbackError*` class is recorded;
   `InnocentVictim` responses are retried (bounded) and never by themselves make
   a case a `fault`; a `fault` verdict requires reproduction in ≥ 2 of 3
   non-innocent attempts; a non-`ok`, non-fault verdict requires two agreeing
   observations or is recorded `nondeterministic`.
5. **A command buffer that reports OK having executed nothing.** Two
   independent defences. (a) Every output slot is bound as an **input file
   pre-filled with `POISON_WORD(i) = 0xDEADBEEF + i`**, so an unwritten word
   identifies itself and is distinguishable from a genuine silent zero;
   `outcome = not_written` is a distinct verdict and is retried, never recorded
   as a property of the swept value. (b) Every carrier's program writes a fixed
   **sentinel through a path that does not involve the instruction under
   test**, *before* that instruction runs: `synth` → `out[4] = 8.0` via
   mov_imm+falu2i+store; `uni` (arms B/D-falu2) → `out[12] = 26.0` from the
   falu2i seed prologue; `uni` (arm F) → `out[12] = 26.0f` written by **falu2i**,
   deliberately not by the `mov_imm` under test; `dag` → `out[4] = 33` stored
   before the `iadd2`. The `bfe`/`shr`/`u64` splice carriers have no spare
   independent path — there the poison test plus the periodic baseline health
   check are the integrity check, and this is stated as a limitation.
6. **A GPU error cascade.** The unmutated carrier is re-run every 120 cases; on
   failure the runner process is restarted and the check repeated, and a second
   failure aborts the carrier with `cascade` recorded rather than continuing to
   record the cascade as data.
7. **Decoder-vs-hardware confusion.** `db.json` is target-independent, so any
   tokenization result (H-F2, arm G) is a statement about our decoder unless a
   hardware case accompanies it. Every synthesised case records its own
   `rt` (round-trip) result separately from its hardware outcome.
8. **Reused archive filenames.** EXP-0141's pilot measured ~7–8 % spurious
   `CMDBUF_ERROR` when one archive filename is reused across persistent-runner
   requests. Every request here writes a **unique** archive path and unlinks it
   afterwards.

## 5. Method

- Two **gated capture runs** (`run01`, `run02`), independent processes, full
  matrix each. A claim is only reported reproduced if the two agree case-for-case
  on the relevant outcome.
- A third **revalidation pass** re-runs every non-`ok` case of `run01` five
  times each, **under the GPU lease** (`~/agxre/gpulease.sh EXP-0153 900 -- …`),
  so the re-runs are not themselves victims. Bulk runs are executed
  **unlocked/concurrently**, per the orchestrator's 2026-08-30 direction.
- Arm G is desk-side: compile the own-MSL corpus on G17P, then tokenize both
  the G17P and the committed M4 hex with the **same** `db.json`, so the two
  numbers come from one tokenizer.

## 6. Coverage (FIELD-SWEEP-PROTOCOL §3)

| arm | field | coverage | cases |
|---|---|---|---|
| A | `device_load.dst_lo` | all 4, at r7 and r20 | 8 |
| A | `device_load.dst_ext9` | all 128, at r7 and r20 | 256 |
| A | `(dst_lo, dst_ext9)` | the full 512-value product at r7 | 512 |
| A | `device_load.extmode` | all 256, consumer r(v>>1) | 256 |
| B | `falu2.mod_lo` | all 8 × 4 operand configs × 2 ops | 64 |
| B | `falu2.srcB_reg` @ `mod_lo=2` | all 128 (both halves) | 128 |
| D | `falu2.srcB_reg` @ `mod_lo=0` | all 128 | 128 |
| D | `iadd2.dst` | all 256 | 258 |
| E | `ibfe.offset` | all 64 (6-bit field) | 64 |
| E | `ibfe.width` | all 64 (6-bit field) | 64 |
| E | `ibfe.offset` in a 2nd lowering | all 64 | 65 |
| F | `mov_imm.imm7` | all 128 | 128 |
| F | `mov_imm.imm_top` | 5 immediates × padded/unpadded | 10 |
| C | `iadd2.addsub` | the one bit, × 5 repetitions × 12 input rows | 7 |
| — | controls / falsifiers | — | 10 |
| | | **total per run** | **1958** |

Every field of width ≤ 8 is swept over all 2^w values, as the protocol requires.

## 7. Frozen inputs

Repository revision at freeze: **`76b9544bbc9dd9b7da1639f3d414091093ddb8ee`**
(6 unrelated files dirty in the working tree, all belonging to sibling
experiments; per SUBAGENT_BRIEF a capture is valid if the authored blob hashes
match, and `HEAD` moving because a sibling lands is not contamination).

Tool files, verified byte-identical on the neo and in this repo before freeze:

| file | sha256 |
|---|---|
| `tools/agx-isa/db.json` | `f5db942f03c9ad3870a102e0e34f705217ffa7ea5883dd960d0ffec93e76e36e` |
| `tools/agx-isa/isadb.py` | `1d60d36d2da7b681028c201013a510603d8fb7909bb59186e7534296e3b6e0d1` |
| `tools/agxtest/persistrun.py` | `fb057160bd96792b342053e7f45f800261b44df435110551b746a4407520f20d` |
| `tools/agxtest/agxrun_persist.m` | `04e892e734679fb0450c2e246e65c409a0b0d565975a844361b6be2f3ece1834` |
| `tools/shdump/agxparse.py` | `72911ee524fa1e327914445a0b38837b4a71e8525565a03f2cb7f520733c6a0f` |

Authored inputs:

| file | sha256 | provenance |
|---|---|---|
| `kernels/carrier_synth.metal` | `1bcf6d70674a4d104a00e31d9ed5afa3cf8cc4495b50be0841c14fa359717cf0` | verbatim EXP-0141 `kernels/carrier.metal` + header |
| `kernels/carrier_uni.metal` | `1cb6f83a715389ae30bb14c5bfe4d6601317c1082eed11395f431bbe6fdf7a1a` | verbatim EXP-0138 |
| `kernels/carrier_dag.metal` | `8b402a5827067fc2e83c796c501d23ac59a8e8fb50c15b639a25f42f7e7fadba` | verbatim EXP-0139 |
| `kernels/k_u64sub.metal` | `fdfa01ede52fb0bccacd981ceae934f94f5e2a983fc18e50cbb33bec6f1714a6` | verbatim EXP-0146 |
| `kernels/ialu_probes.metal` | `922af2a9b572513d3e047d4d043aeb02aa51ef17d2f707557a065b1c71078e13` | the two ibfe kernels of EXP-0139 |
| `harness/isa_helpers.py` | `22b23b318b294238573c8ef4b75c5e2d898c7cbb02e1ca4326efdd5d354f55e1` | merged EXP-0138 + EXP-0141 |
| `harness/anchors.py` | `069dbd104a93fccb0f8b31efe976d868ccb93f760de753fb664512adb3d9f2c3` | EXP-0139, tools path relocatable |
| `harness/carriers.py` | `ce81f48f11241e3e4f1db1b7655c04f13710ca04daf8ab98f4390784b284d055` | new |
| `harness/cases.py` | `8734865c00e37bfbc487d2572e9e4f1e055ffc77ad6b28a72e7bb7a0b49ecd73` | new |
| `harness/run.py` | `f4b18d00eb3629bb31fad777f356dd18b04fe43c636d1251c8b832cb0128b872` | adapted EXP-0141 `sweeprun.py` |

Input vectors are frozen in `harness/carriers.py` and copied verbatim from the
M4 experiments (`MEM_F32`, `UNI_VALS`, `A_IN`/`B_IN`, `U64_A`/`U64_B`), plus
four extra 64-bit boundary rows named in this experiment's dispatch.

**These hashes are the gate.** A capture whose `00_env.json` records different
kernel/harness hashes is not a capture of this pre-registration.

## 8. Raw-record schema

One JSON object per case, appended and fsync-ed immediately to
`raw/<run_id>/sweep.jsonl`:

```json
{"arm":"A_dst_pair","i":129,"rep":0,"carrier":"synth","instr":"device_load",
 "field":"dst_pair","value":129,"bytes":"<the instruction under test, hex>",
 "observed":{"out0":[...],"n_0":0,"first_0":[],"sha_0":"...","unwritten":0},
 "oracle":{"0":[...]},"match":true,"outcome":"ok","status":"OK","rt":true,
 "statuses":null,"fault_classes":null,"innocent_retries":null,
 "observations":null,"confirmed":null,"expect_match":true,"note":"..."}
```

`outcome` ∈ `ok` | `silent_zero` | `not_written` | `wrong_value` | `fault` |
`hang` | `nondeterministic`. `fault`/`hang` are results and are kept.
`_HEALTH` records carry the same schema with `arm = "_HEALTH"`.

## 9. Environment and timeouts

- Every SSH invocation is wrapped in `perl -e 'alarm N; exec @ARGV'`.
- Per-request GPU watchdog: **10 s** (`run.py :: REQ_TIMEOUT`), enforced by
  `persistrun.PersistRunner`, which kills and restarts the child on a wedge.
- `shdump` compile timeout 180 s; `agxparse` 60 s.
- Hang budget: **2 reproduced hangs abort an arm**, **6 abandon a carrier**
  (FIELD-SWEEP-PROTOCOL §8). An aborted arm is reported PARTIAL, never rounded
  up.
- Neo working directory `~/agxre/EXP-0153/`; `raw/` is pulled back into this
  repository after each run, before the next begins.

## 10. Analysis plan, fixed in advance

1. A field's G17P verdict is `hardware-run` only if **both gated runs agree**
   case-for-case on its accepted set. Otherwise the field is reported
   `PARTIAL`/`inconclusive` — never rounded up.
2. Competing models (E1's mod-32 offset, E2's literal-clamp width) are scored
   on the **same records** as the pre-registered model, and the fit counts are
   published side by side.
3. Every arm reports **reproduced / refuted / inconclusive**, with the M4 value
   printed beside the G17P value.
4. `analysis/field_verdicts.json` uses only the eight labels of
   `docs/evidence-classification.md`, each with `range`, `target: "G17P"`, and
   `evidence: ["EXP-0153"]`.
5. Negative results, faults, aborted arms and `nondeterministic` cases are
   reported in `RESULTS.md`; none is dropped.
6. `db.json` / `validation.json` / `docs/` / `PROVENANCE.md` are **not** edited
   by this experiment, and nothing is committed by it.

---

## 11. Note recorded at freeze time (not an amendment)

Between writing §7 and writing `CAPTURE_CONTRACT.json` — a gap of a few seconds
— repository `HEAD` moved from `76b9544bbc9dd9b7da1639f3d414091093ddb8ee` to
`7dc67d768ada3c016771923bffd5b9647dd14813` because a sibling experiment landed.
Both values are recorded; neither is a gate. **The gate is the authored blob
hash table in §7**, exactly as `SUBAGENT_BRIEF.md` requires ("a cross-run gate
written as 'HEAD must not move' will abort mid-sequence through no fault of your
experiment"). This is noted here rather than silently edited.

## 12. AMENDMENT 1 — 2026-08-30T05:20 UTC, before any gated capture

**What changed.** `harness/anchors.py :: tokenize()` was made tolerant of
`isadb.disassemble`'s terminating `<unknown>` record (mnemonic `<unknown>`,
`length` `None`, no `fields` key), which the EXP-0139 original assumed away.

**Why.** Nothing to do with the hypotheses: the first `prepare()` call on the
target raised `KeyError: 'fields'` before any case ran. Tokenizing a carrier is
a *harness* step, not a measurement.

**Effect on the contract.** `harness/anchors.py` sha256 changes from
`069dbd104a93fccb0f8b31efe976d868ccb93f760de753fb664512adb3d9f2c3` to
`d2a4d6f1fe77abaa8de7dcaa6e6cbc89136f7bcfda6e03ad61aa8912efe3425b`. §7's table
is superseded for that one file only; the value above is what every gated
capture's `00_env.json` must record. No hypothesis, oracle, carrier, input
vector or case value is affected.

**Smoke evidence that the amendment is sound** (`raw/smoke01/`, 40 cases + 12
health checks, retained as evidence and never reused): every carrier compiled,
every anchor resolved, and all six carriers tokenized **end-to-end with zero
leftover bytes** on G17P.

## 13. AMENDMENT 2 — 2026-08-30T05:41 UTC, between gated captures

Two changes, both operational, neither touching a hypothesis, oracle, carrier,
input vector or case value.

**(a) `harness/run.py :: GuardedRunner`.** The second gated capture
(`g17p-20260830-run02`) stalled at case 215/258 of `D_iadd2_dst`. Diagnosed, not
guessed: its `agxrun_persist` child had exited, and
`tools/agxtest/persistrun.py :: request()` then busy-looped forever — its read
loop treats a line as unrecognised rather than as EOF, so a dead child produces
an unbounded stream of empty strings. The parent was observed at 61.3 % CPU in
state `RN` with no `agxrun_persist` child of its own in `ps`. `persistrun.py` is
used READ-ONLY, so the fix is a **subclass in this experiment** that maps EOF
onto the watchdog's existing wedge path; the tool is unmodified. Recorded as
`db_defects → DEF-0153-2`.

Per `SUBAGENT_BRIEF` ("a partial capture is retained, never reused") the 1731
records of `run02` are kept exactly as captured, carry their own `PARTIAL.md`,
and are **not** used as the second gated run. The replacement was captured under
the **new** id `g17p-20260830-run03`.

**(b) `--revalidate-only`.** §5 planned to re-run every non-`ok` case five
times under the GPU lease. That is 854 cases × 5 = 4270 requests, and the lease
is a scarce resource shared with five sibling experiments. FIELD-SWEEP-PROTOCOL
§7.1 only requires the **fault/hang class** to be re-run in isolation, so the
pass was narrowed to `fault, hang, nondeterministic, silent_zero` — 75 cases ×
5 = 375 measurements (`g17p-20260830-reval02`). The `wrong_value` cases keep the
evidence they already have: majority-of-3 within each gated run, plus exact
agreement between two independent runs.

This narrowing is recorded because it is a **reduction in scope from the frozen
plan**, and because it turned out to matter: the pass showed that 4 of the 5
`F_imm_top` unpadded cases are not faults at all (RESULTS.md §4.1).

**Hash after both amendments** (this is what every gated capture's
`00_env.json` records):

| file | sha256 |
|---|---|
| `harness/anchors.py` | `d2a4d6f1fe77abaa8de7dcaa6e6cbc89136f7bcfda6e03ad61aa8912efe3425b` |
| `harness/run.py` @ `smoke01`, `run01`, `run02` | `f4b18d00eb3629bb…` |
| `harness/run.py` @ `run03` (after amendment (a)) | `1df3a4184a863b3c…` |
| `harness/run.py` @ `reval02` (after amendment (b)) | `7fe845586cf96fc7…` |

`harness/cases.py` (`8734865c00e3…`), `harness/carriers.py` (`ce81f48f1124…`),
`harness/isa_helpers.py` (`22b23b318b29…`) and every `kernels/*.metal` are
**byte-identical in all five captures**, as each capture's own `00_env.json`
records. Those are the files that determine *what was measured*; only the
executor's plumbing changed.
