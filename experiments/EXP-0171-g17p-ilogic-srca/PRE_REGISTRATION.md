# EXP-0171 — PRE-REGISTRATION

**Frozen 2026-08-30, before any GPU dispatch.** Target: **A18 Pro / G17P**
(`users-MacBook-Neo.local`, `192.168.10.243`). Repo revision at freeze:
`dc367a43dc83b58d4b60b4d9f9fd92295379a9b1`. The gate is the authored blob hashes in
`CAPTURE_CONTRACT.json`, **not** live `HEAD` (SUBAGENT_BRIEF; EXP-0082 lost a run to a
HEAD gate while siblings committed).

```text
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs: kernels/probes.metal + kernels/carrier_dag.metal (authored by us) and the AGX
        machine code the PUBLIC Metal runtime API compiled FROM THEM; plus this
        repository's own committed evidence and tools/agx-isa.
Apple binary introspection: NONE. No Apple binary is disassembled, decompiled or
        inspected. The only machine code touched is the compiled form of our own MSL.
```

**Step 0 is compile-only and ran BEFORE this freeze, deliberately.** `harness/anchors.py`
compiles our own MSL and tokenizes it; it dispatches nothing. It ran first so this frozen
contract can carry the exact case count and matrix hash rather than a promise —
"an underspecified frozen contract is an automatic stop" (CODEX). Its output
(`work/anchors/anchor_report.json`) is an input to the frozen matrix and its findings are
in §2 below, because two of them changed the design.

---

## 1. The question

Two things, in rank order.

**Target 1 — close `ilogic` on G17P.** `EXP-0166` §2.1 left a live M4↔G17P contradiction.
On **M4** (EXP-0146, carrier `k_logic_and`, result CONSUMED BY A STORE) `ilogic.outmod` is
dense-live over 0..255: 128 values move the observable and every value with **bit 7 clear
silently zeroes**. On **G17P** (EXP-0154, carrier `SYNTH+LIFTED:k_and@ilogic[32:42]`, a
16-REGISTER DUMP) the same field read inert across the whole range, and EXP-0164 withdrew
that verdict for single-carrier inertness, so it now reads `untested`. EXP-0166's
prescription, verbatim: *one G17P `ilogic` arm with a store-consumed observable settles
`outmod`.*

**Target 2 — the `srcA` and `tail` levers.** After `dst` (35 descriptors, EXP-0168's),
`tools/agx-isa/emit_worklist.py` ranks `srcA` (17) and `tail` (15) as the most load-bearing
field NAMES. Six arms are pre-registered, ranked by distance-to-emittable.

**Headline this experiment is measured against: 40 emittable / 126 blocked / 166, 614
fields** (regenerated from live `tools/agx-isa` at freeze; the figures 44 and 79 are
superseded and are not cited).

---

## 2. What Step 0 already established, and how it changed the design

These are **observations**, made by compiling our own MSL and tokenizing it with our own
tools. They are the reason the arm table looks the way it does.

### DEF-0171-1 — `ilogic`'s byte0 match is over-fitted to destination r0
Our own `out[g] = a[g] & b[g]` compiles on G17P to
`2b 03 1f 01 00 00 00 80 00 00`. `db.json`'s `ilogic` match is `[[0,8,11]]` — a **full
8-bit byte0** — so it matches only byte0 `0x0b`. Every other destination register falls
through to `b_alu10_lof` (match `[[0,4,11],[16,4,15]]`) or `b_alu10_loe`
(`[[0,4,11],[16,4,14]]`), whose **low-nibble-only** match is accompanied by a modelled
`dst` at byte0's high nibble. Verified locally on the frozen snapshot:
`0b031f01000000800000` → `ilogic`; `2b031f01000000800000` → `b_alu10_lof`. The field
structure is byte-for-byte parallel:

| byte | `ilogic` | `b_alu10_lof` / `loe` |
|---|---|---|
| 0 | (fixed match) | `dst` (high nibble) |
| +1 | `srcA` | `src_reg` + `src_flag` |
| +2 | `op_base` (bit16) + match | `opsel_hi` (high nibble); the lof/loe split IS `op_base` |
| +3 | `srcB` | `srcA` |
| +4 | `lut_a_sel`/`lut_a_free`/`lut_a_z` | `modA` |
| +5 | `lut_b` | `modB` |
| +6 | `z6` | `z6` |
| +7 | `outmod` | `outmod` |
| +8 | `z8` | `ext8` |
| +9 | `z9` | `ext9` |

Consequence for the design: **one sweep serves both key sets**, and the arm reports under
both. EXP-0154's G17P `ilogic` rows are therefore rows about **destination r0 only**.

### DEF-0171-2 — `tools/agx-isa` has no length rule for byte0 == 0x31, so G17P's own bfloat ALU does not tokenize
Our own `bfloat` add/mul/fma compile to `31 00 1c 00 11 00 c0 81` (8 B),
`31 00 1d 00 11 00 c0 81` (8 B) and `31 00 1e 00 86 02 10 00 c0 81` (10 B). All three come
back `<unknown>`, `length: None`. Separately, `db.json`'s `bf_alu` match demands byte0
`== 0x11` (an 8-bit match — **the same dst-nibble over-fit as DEF-0171-1**, 0x31 vs 0x11 is
dst r3 vs r1) and byte+1 `== 0x02`, while G17P emits byte+1 `== 0x00`; `bf_fma_dst`'s `fmt`
enum `{2: bf, 4: bf2}` likewise does not contain the emitted `0x00`. The lengths are
**pinned** in the frozen matrix (`anchor` overrides) on evidence from the compiled programs
themselves: the following `mov_imm` (`0c da`) begins at exactly +8, +8 and +10, which is
`db.json`'s own length for these descriptors. Every such case records
`anchor_pinned: true`.

### Two further Step-0 observations, carried into the arms
* **`fspecial_est` byte+3 == `0x0f`** in G17P's precise `rsqrt` lowering — a `subop` value
  absent from `db.json`'s enum `{9: rcp, 11: rsqrt, 13: sqrt}`.
* **The predicate-consumed `ilogic` pole is not reachable from our own MSL on G17P.** Both
  `(a&b)!=0 ? 7 : 9` and the `if` form lower to `isel10` with no logic op at all, so
  `db.json`'s "byte+7 bit7 clear on the dec2 predicate-consumed forms" cannot be provoked
  this way. Recorded as `instr_absent`, not silently dropped.

---

## 3. Hypotheses, expected observations, and refuters

**H1 (primary).** `ilogic`/`b_alu10_*` byte+7 (`outmod`) is a **consumer-path** control,
not a GPR-write control. Expected: on the **NAT** carrier (result consumed by the
compiler's own `device_store`) values with **bit 7 clear** do NOT deliver the result to
memory — `out[]` either stays **poisoned** or reads a wrong value — while on the
**SYNTH/FRAME** carrier (16-register dump) the same values are `ok`. Predicted split:
128 of 256 move on NAT, 0 of 256 move on SYNTH.

* **R1a (refuter).** byte+7 is inert on NAT too — all 256 `ok` — *while the NAT liveness
  ladder is demonstrably live*. Then G17P genuinely differs from M4 and that is the
  result: a **cross-target divergence**, reported as such, with no promotion forced.
* **R1b (refuter).** byte+7 moves on SYNTH as well. Then EXP-0154's inert reading was a
  coverage artefact and both prior records need correcting in the other direction.
* **Prior evidence against a GPR-write reading (offline, from EXP-0154's committed raw):**
  its baseline seeds r0 = 10 and the `ilogic` writes r0 = 2 (= 10 & 34); with byte+7 = 0x00
  r0 is **still 2**. So on G17P the GPR write happens with bit 7 clear. Whatever M4 saw was
  the store path or the target, not the register write.

**H2.** `ilogic.lut_a_free` (byte+4 bits 2..4) is a genuine **don't-care** inside the LUT
selector. Expected: dense-inert across **five carriers that differ in the dimension it
would control** — which boolean function the LUT selects (`k_and`, `k_or`, `k_xor`,
`k_andn`, `k_nand`), all store-consumed. R2: it moves on any of them, in which case the
"free" name is wrong and the LUT model needs a third selector field.
**A proven-inert field with an unknown role is labelled `single-template-inference`, not
`hardware-run`** — emitter grade asserts the implementer may *choose* the value.

**H3.** `ibitcount.tail` on G17P reproduces the M4 rule (EXP-0139 DEF-0139-3): **only bit 2
is load-bearing** — 128 values with bit 2 set compute the correct result, 128 with bit 2
clear return a wrong constant. Expected: accept-set exactly `{v : v & 4}`. R3: any other
accept-set, or dense inertness with a live ladder.

**H4.** `bf_fma_dst.tail` (w = 32) and `bf_alu.tail` (w = 24) contain at least one
load-bearing bit each. Expected: ≥ 1 of 256 values per byte moves on ≥ 1 carrier.
R4: dense inertness on all four bytes with a live ladder → the `raw`-typed 32-bit `tail`
is a don't-care region and reports as `single-template-inference`.

**H5.** `fspecial_est.srcA` and `.subop` move once the estimate is **not** refined.
EXP-0161 could promote neither because both its carriers were the precise forms, where the
Newton–Raphson refinement that follows corrects the estimate whatever it was. The SYNTH
carrier lifts the estimate ALONE with nothing after it. Expected: `srcA` selects a register
(dense movement tracking the seed table) and `subop` shows a small accept-set around
`0x0f`. R5: inert on SYNTH too → the fields are not what the descriptor says.

**H6.** `iadd2.srcA` (byte+7 = `0xa8`) is **not** an operand selector — `db.json` already
records that `srcB_ext` is the srcA register selector (EXP-0154, 248/248) — so byte+7 is a
modifier of unknown role. Expected: a small accept-set, or inertness.
**If inert with an unknown role it is labelled `single-template-inference`, not
`hardware-run`.** R6: it tracks the seed table like a register selector, refuting
EXP-0154's operand model.

**H7 (structural, and it settles the keying of H1/H2).** byte0 of the `ilogic`/`b_alu10_*`
instruction is `(dst << 4) | group`. Expected on the SYNTH carrier's dense byte0 sweep:
every value `v` with `v & 0x0F == 0x0B` computes the same function into **register
`v >> 4`**, and no other low nibble does. R7: it does not — then DEF-0171-1 is wrong, the
`ilogic` and `b_alu10_*` names are NOT the same instruction, and the ILOGIC arm reports
under `b_alu10_*` only. The same sweep runs on `bf_alu`'s byte0 (predicted `0x?1`) and
`bf_fma_dst`'s.

---

## 4. Variables

| | |
|---|---|
| independent | one BYTE of the instruction under test, dense 0..255 (plus the §3.3 set for `w > 8` fields, written across all their bytes at once) |
| dependent | NAT: the 16 words of `out[]` + 2 sentinel words. SYNTH/FRAME: the 16 GPRs + PRE/POST sentinel words |
| controlled | every other byte of the instruction at its compiler-emitted anchor value; the same input vectors, grid, threadgroup, seeds and dump list in every case; one carrier per (style, probe) |
| carrier axis | **NAT** (store-consumed, buffer-loaded operands) vs **SYNTH** (register-file observable, `mov_imm`-seeded operands) vs **FRAME** (SYNTH + a framing probe after the block) — plus, for ILOGIC, five NAT carriers differing in which LUT function is selected |

## 5. The oracle, and the defect it is built to avoid

**R1 — THE OBSERVABLE MUST NOT CO-VARY WITH THE FIELD UNDER TEST.** EXP-0140's
`uniform_mov.dst` sweep built its read-back as `device_store(..., data_reg = D)` where `D`
was the swept `dst`, so a *correct* hardware result was a constant observed vector **by
construction** and "0 moved" was the **passing** outcome of a test that could return
nothing else (EXP-0168 §3). Checked here before freezing:

* **NAT** — the read-back is the **compiler's own** `device_store`, a different
  instruction from the one under test; no swept byte can change which register it reads.
  `ilogic` has no `dst` field at all in `db.json`, and byte0 (which DEF-0171-1 shows
  carries `dst`) is swept **only on SYNTH**, never on NAT.
* **SYNTH/FRAME** — the read-back is **all 16 GPRs, always, in a fixed order**, so the
  verdict is a function of *which slot changed*; no swept field can change the dump list.

**Primary comparator: a HOST-COMPUTED oracle**, for the arms where the semantics are
exactly host-computable — every NAT integer kernel (`and`, `or`, `xor`, `andn`, `nand`,
`popcount`, `clz`, `extract_bits` signed and unsigned, `+`). Those 18 expected words are
computed in `harness/sweeprun.py::host_oracle_nat` with **no GPU involvement**, including
the 8 words at grid = 8 that must remain `0xDEADBEEF` and the two sentinel constants.
This is EXP-0166's amendment A3 applied at capture time rather than in re-analysis:
*contamination can destroy an observation but never fabricate a coherent one.*

**Secondary comparator: the measured unmutated baseline**, used for the SYNTH/FRAME
register-file observable and for every float/half/bfloat arm (estimates and rounding are
not exactly host-computable). Those arms are **declared baseline-comparator arms**; the
comparator's identity is recorded in **every** case as `oracle.source`, the baseline digest
is recorded alongside, and the baseline is re-validated every 250 cases, so either
adjudication can be redone offline.

## 6. Falsifiers and positive controls (FIELD-SWEEP-PROTOCOL §3.5)

1. **F1 — per-carrier falsifier.** Every (arm, carrier) dispatches byte0 := `0x00`,
   pre-registered to be **non-`ok`**. A carrier whose falsifier passes has no detection
   power and is discarded, not reported as evidence of inertness.
2. **F2 — liveness ladder, per carrier.** Each carrier densely sweeps ≥ 1 byte already at
   `hardware-run` on G17P in `validation.json`. A carrier that cannot show its ladder is
   **discarded**. This is EXP-0164's rule: two carriers identical in the controlled
   dimension are one carrier.
3. **F3 — cross-kernel transplant (positive control, ILOGIC).** Splice kernel *Y*'s
   selector bytes (+2, +4, +5) into kernel *X*'s `ilogic`, in *X*'s own NAT carrier, and
   predict *X*'s output becomes **Y's boolean function**, host-computed. 20 ordered pairs
   over `{and, or, xor, andn, nand}`. This demands a specific non-baseline answer, so it
   cannot pass by inertness. `k_andn`'s anchor has its operands swapped relative to
   `k_and`'s (byte+1/+3 = `01`/`03` vs `03`/`01`), so for that pair BOTH operand orders are
   scored and which one matched is recorded — the DEF-0154-5 operand-swap check, for free.
4. **F4 — H7's byte0 prediction** is itself a positive control: it names, in advance, which
   register slot must change for each of 16 values.

## 7. Instruments against contamination (FIELD-SWEEP-PROTOCOL §7, binding)

| instrument | how |
|---|---|
| poisoned read-back | every output buffer filled with `0xDEADBEEF` before **every** dispatch; `poison_out` counts how many expected-written words came back still poisoned. This is what distinguishes "wrote 0" from "never ran" |
| integrity sentinel on an independent path | NAT: `sent[0] = 0x5A5A5A5A` / `sent[1] = 0x0BADF00D` in a **separate device buffer** (index 4), written through a different base slot from `out`. SYNTH/FRAME: EXP-0154's PRE/POST sentinels stored to their own words |
| "STATUS OK and wrote nothing" | if both sentinels AND every expected word are still poisoned, the case is `undecodable` + `invalid_run` — **never** `silent_zero` (EXP-0160 saw 25 such observations with no victim string) |
| OS fault class recorded | `fault_class` carries the OS's own `localizedDescription` verbatim on every non-OK attempt |
| victim segregation | `...ErrorInnocentVictim`-class failures flagged `victim`; baseline acquisition retries with backoff through a victim wave rather than losing the arm (EXP-0154 amendment_02) |
| never conclude `fault` from one observation | majority-of-3; a clean dispatch settles a case in one attempt |
| coverage is counted, not asserted | `analysis/coverage.py` counts **DISTINCT `bytes` strings**, never the dispatched-value count — `assemble()` could not clear a bit and 53 fields were silently under-swept (DEF-0166-1, fixed `4b16d0b4`). Swept values are spliced as **raw bytes**; `isadb.assemble()` is never on the sweep path |
| concurrency | sweeps run **unlocked** (§7); `00_env.json` records the concurrent `agxrun_persist` count as a measurement |

## 8. Promotion rule (frozen)

A `<mnemonic>.<field>` row may be promoted only if **all** hold:

1. two gated runs, **≥ 99 % per-value cross-run agreement**, and **movement ≥ 2 × the
   disagreement count**;
2. every value covered by **both** runs (`n_runs ≥ 2`) — a value only one run reached is
   not promotable (EXP-0154 amendment_02);
3. `distinct_bytes == encodable_range` for the field's own bits (the A5 decomposition over
   dense byte sweeps), counted from `raw`;
4. the carrier that carries the row passed **F1 and F2**;
5. **a field that never moves is promotable only if the carriers differ in the dimension
   the field controls**, named explicitly in the verdict row. If they do not, or if the
   role is unknown, the label is `single-template-inference`, never `hardware-run`;
6. `sentinel_bad` ≤ 1 % of the field's cases, and no `invalid_run` case counted as
   evidence.

Every verdict row carries machine-readable coverage: `values_dispatched`,
`distinct_bytes`, `encodable_range`, `start`, `width` — currently 0 of 614 rows do.

## 9. Scope, and what is deliberately NOT claimed

Owned here: `ilogic.*`, `b_alu10_lof.*`, `b_alu10_loe.*` (the DEF-0171-1 aliases, claimed
by nobody), and the `srcA`/`tail` levers with their descriptor-completing companions —
`ibitcount.tail`, `bf_fma_dst.{tail,fmt}`, `bf_alu.{srcA,srcB,tail}`,
`fspecial_est.{srcA,subop}`, `iadd2.{srcA,b2_fmt}`, `ibfe.{srcA,sign_ext,b2_bit0}`.

Explicitly **not** claimed, and swept only as instruments:
* **every `.dst` field** — EXP-0168 owns the name on all 14 descriptors. `dst` bytes are
  swept as ladder bytes and byte0's `dst` nibble is swept to prove H7, but **no `.dst`
  verdict is emitted by this experiment**, in any arm.
* **`bf_alu.opsel`** — EXP-0169's row; byte+2 is this arm's liveness ladder only.
* EXP-0168's other 12 one-field-away rows and EXP-0169's `falu2*` / `half_alu*` /
  `iunary` / `reg_move_*` / `icmp_pred.cond` / `get_sr.*` / `device_store.*` sets. Checked
  against both pre-registrations at freeze: **no verdict-key collision**.
* `packed_half2_hi` — dropped from the matrix: 3 blocking fields, one a 16-bit `mods`, and
  half-precision rounding leaves no exact host oracle.

## 10. Known confounders, and what is done about each

| confounder | mitigation |
|---|---|
| a sibling experiment's GPU hang resets the device and discards our command buffers | victim classification + backoff on baseline acquisition + majority-of-3 + poison adjudication offline |
| `tools/agx-isa` drifts while sibling experiments extend it (EXP-0154 lost its `lut_a` row to exactly this) | `work/frozen/{db.json,isadb.py,validation.json}` snapshot, sha256 in `CAPTURE_CONTRACT.json`, and `harness/isa_helpers.py` prefers it over the repo copy |
| the mutated instruction is undecodable by OUR disassembler | recorded per case as `rt_ok: false`; the hardware, not `tools/agx-isa`, is the authority on what bytes mean. Every bf case is `rt_ok: false` by construction (DEF-0171-2) |
| a lifted logic op whose operands the compiler chose as (r1, r0) computes `21 & 10 == 0` under EXP-0154's bit-disjoint seeds — a baseline that is itself a silent zero | `SEED_I` replaced with high-popcount seeds; **no pair ANDs to zero**, asserted at import |
| `mov_imm.imm7` ≥ 128 silently zeroes (EXP-0128) | hard-rejected in `mov_imm()` |
| the SYNTH sentinel registers (r12/r13) can be named by a swept `dst` | recorded as `sentinel_bad`; a row whose inertness rests on `sentinel_bad` cases fails gate 8.6 |
| a dense `fspecial_est` byte+3 sweep is adjacent to a known hang region (`fspecial` byte+3 ≥ 192) | flagged in `PROGRESS.md` as §7 courtesy; the arm is abandoned and reported PARTIAL after 2 genuine hangs (§8) |
| `iter_at` with `grp = 0x50` is a known real `ErrorHang` on this device | `iter_at` is not in this matrix at all |

## 11. Frozen procedure and timeouts

| | |
|---|---|
| matrix | `harness/casematrix.py::build_cases(anchor_report)`, **35,949 cases**, `matrix_sha256` in `CAPTURE_CONTRACT.json` |
| gated runs | two, the SAME matrix, executed in opposite (arm, carrier) order (`--order forward` / `reverse`) so concurrent siblings do not see both hit the same illegal encoding at the same moment |
| per-request watchdog | 8 s (`persistrun.PersistRunner`), child killed and restarted on a wedge |
| shdump compile | 300 s |
| baseline re-validation | every 250 cases; drift restarts the child |
| hang stop | 2 genuine hangs in one (arm, carrier) → that pair ABANDONED, reported PARTIAL (§8) |
| incremental write | one JSONL record per case, `flush` + `fsync` immediately; nothing buffered |
| resume | by `idx` already present in `raw/<run>/sweep.jsonl`; a run id is **never** reused or topped up |

## 12. Raw record schema (`raw/<run_id>/sweep.jsonl`, one JSON object per case)

`idx`, `seq`, `t`, `arm`, `rank`, `instr`, `carrier`, `probe`, `carrier_id`, `role`
(`falsifier`\|`ladder`\|`target`\|`wide`\|`xplant`), `field`, `byte_index`, `value`, `mut`,
`bytes` (the FULL mutated instruction — the unit `analysis/coverage.py` counts),
`anchor_bytes`, `instr_len`, `observed.{digest,words}`, `oracle.{digest,source}`,
`baseline_digest`, `match`, `outcome` (`ok`\|`silent_zero`\|`wrong_value`\|`fault`\|`hang`\|
`undecodable`), `kind`, `rt_ok`, `victim`, `poison_out`, `sentinel_bad`, `invalid_run`,
`fault_class`, `attempts[]`, `predict`, `xplant_from`, `note`.

Also per run: `00_env.json`, `01_progress.json`, `02_summary.json`, `03_matrix.json`,
`baseline.jsonl`.

## 13. Deliverables

`README.md`, this file, `CAPTURE_CONTRACT.json`, `manifest.json`, `harness/`, `kernels/`,
`analysis/{coverage.py,emit_verdicts.py}`, `analysis/field_verdicts.json` (flat
`<mnemonic>.<field>` per FIELD-SWEEP-PROTOCOL §5, with the coverage keys), `RESULTS.md`
separating observation from interpretation, `PROGRESS.md` after every milestone.
**No `git commit`. No edits to `db.json`, `validation.json`, `docs/`, `PROVENANCE.md`.**
