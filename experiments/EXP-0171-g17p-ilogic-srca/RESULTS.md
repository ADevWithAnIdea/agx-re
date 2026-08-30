# EXP-0171 — RESULTS

**Target of this experiment: Apple A18 Pro / G17P** (`users-MacBook-Neo.local`, SoC T8140,
`AGXAcceleratorG17P`, 5 GPU cores, macOS 26.6 build 25G5043d, Metal family Apple9). The M4
was not dispatched to, M5 was not touched, `macvdmtool` was not invoked.

```text
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs: kernels/probes.metal + kernels/carrier_dag.metal (authored by us) and the AGX
        machine code the PUBLIC Metal runtime API compiled FROM THEM.
Apple binary introspection: NONE.
Reproduction: harness/sync.sh push
              python3 harness/anchors.py                        (compile-only)
              python3 harness/run.py --run g17p_20260830_run01 --order forward
              python3 harness/run.py --run g17p_20260830_run02 --order reverse
              python3 analysis/coverage.py      raw/g17p_20260830_run01 raw/g17p_20260830_run02
              python3 analysis/emit_verdicts.py raw/g17p_20260830_run01 raw/g17p_20260830_run02
              python3 analysis/closure.py
Evidence: raw/g17p_20260830_run01, raw/g17p_20260830_run02, raw/isolation/iso01.json
```

---

## 0. Headline

**`ilogic.outmod` is settled, and there is no cross-target divergence: the M4↔G17P
contradiction was a carrier artefact, exactly as EXP-0166 §2.1 predicted.** M4's result
reproduces on G17P **value-for-value**, on five independent store-consumed carriers — and
the poisoned buffer shows `db.json`'s *mechanism* for it is wrong.

**Four instructions close on movement evidence alone** — `ibitcount`, `bf_fma_dst`,
`bf_alu`, `fspecial_est`. A fifth, `ibfe`, closes only if the orchestrator accepts two
promotions from *proven inertness*; it is reported separately for exactly that reason.
**`ilogic` does NOT close** (5 blocking fields → 3).

| | |
|---|---|
| cases dispatched | **71,898** (2 × 35,949, one frozen matrix, opposite order) |
| byte-sweeps, dense-complete 256/256 | **139 of 139 in BOTH runs**, **0 under-covered** |
| cross-run agreement | **1.0000 on every promoted row** (0 disagreements) |
| hangs | run01 **0**, run02 **1**; 0 arms abandoned |
| carriers admitted by F1+F2 | **26 of 27** (the one rejection is a result, §4) |
| verdict rows emitted | 37, **all 37 carrying the five coverage keys** |
| labels | 22 `hardware-run`, 5 `isolated-byte-diff`, 10 `single-template-inference` |

---

## 1. What was directly OBSERVED

### 1.1 `ilogic` / `b_alu10_*` byte+7 (`outmod`) — the primary target

Dense 0..255, both gated runs, cross-run agreement 1.0000 (256 agree / 0 disagree):

| carrier | style | distinct observations | **moved** | which values |
|---|---|---:|---:|---|
| `NAT:k_and` | store-consumed | 2 | **128** | **exactly the 128 with bit 7 CLEAR** |
| `NAT:k_or` | store-consumed | 2 | **128** | same |
| `NAT:k_xor` | store-consumed | 2 | **128** | same |
| `NAT:k_andn` | store-consumed | 2 | **128** | same |
| `NAT:k_nand` | store-consumed | 2 | **128** | same |
| `SYNTH:k_and` | 16-register dump | 1 | **0** | — |
| `FRAME:k_and` | dump + framing probe | 1 | **0** | — |

`accept-set = the 128 values with bit 7 set`. Hypothesis **H1 confirmed**; refuters **R1a
and R1b did not fire**.

### 1.2 The mechanism, from the poisoned buffer — and it is NOT an "output/store flag"

On every bit-7-clear case `poison_out == 0` and **both integrity sentinels are intact**
(`0x5A5A5A5A`, `0x0BADF00D`): the store executed and wrote something. What it wrote:

| kernel | byte+7 = `0x80` (anchor) | byte+7 = `0x00` |
|---|---|---|
| `k_and` | `a & b` (= host oracle) | **0** |
| `k_or` | `a \| b` | **0** |
| `k_xor` | `a ^ b` | **0** |
| `k_andn` | `a & ~b` | **0** |
| **`k_nand`** | `~(a & b)` | **`0xFFFFFFFF`** |

**`nand` is the discriminator.** A flag that zeroed the OUTPUT would give `0` for `nand`
too. `0xFFFFFFFF` is `~(0 & 0)` — **the LUT still evaluates and the destination register is
still written; it is both SOURCES that read as ZERO.** `db.json`'s
`enum {128: "output/store"}` and its prose "outmod (byte+7) bit7 = an output/store flag"
describe the symptom, not the control.

**Reproduced adversarially** (`raw/isolation/iso01.json`, a FRESH process after both gated
runs): 20 cases × 5 repetitions, **20 of 20 reproducible**, 100 dispatches each with a
non-zero `GPUTIME_NS` (5.1–8.0 µs), host-oracle match at `0x80` on all five probes,
`all_zero_except_nand: true`, `nand_all_ones: true`. Values `0xFF`/`0x7F` behave as
`0x80`/`0x00`, i.e. only bit 7 matters.

### 1.3 `ilogic` byte0 is `(dst << 4) | 0x0b` — DEF-0171-1, hardware-proven

Dense byte0 sweep on the SYNTH carrier (16-register dump). Every value with low nibble
`0xb` put the AND result (73 = 93 & 107) in register `value >> 4`:

`0x0b`→r0, `0x1b`→r1, `0x2b`→r2 (the anchor), `0x3b`→r3 … `0xeb`→r14 — **15 of 15
observable registers, 0 misses.** (`0xfb`→r15 is not observable in this carrier by
construction: r15 is the harness's own `device_store` index register, re-seeded before every
dump store.) Hypothesis **H7 confirmed**, refuter **R7 did not fire**.

Also observed: byte0 `0x23` reproduces the anchor's full register state exactly — a second
low nibble reaching the same datapath, not chased here.

### 1.4 F3 positive control — 20 of 20 transplants produced the transplanted function

Splicing kernel *Y*'s selector bytes (+2, +4, +5) into kernel *X*'s logic op, in *X*'s own
NAT carrier, made *X* compute **Y's boolean function**, checked against a host-computed
oracle, for all 20 ordered pairs over {and, or, xor, andn, nand}, in both gated runs.
16 matched exactly; the 4 sourced from `k_andn` matched **only with the operands swapped** —
its compiler anchor carries byte+1/+3 = `01`/`03` where the other four carry `03`/`01`.
That is DEF-0154-5's operand swap, arriving as a **pre-registered prediction** rather than
as an accident. This is *generation*: any of the five functions can be synthesised into any
of the five kernels and the result is predicted before the dispatch.

### 1.5 The `srcA` / `tail` levers

All figures: dense 0..255 per byte, both gated runs, agreement 1.0000 unless stated.

| field | moved / sub-values | decisive carrier | accept-set |
|---|---:|---|---|
| **`ibitcount.tail`** | **128 / 256** | `NAT:k_popcnt` (4 carriers agree) | **exactly the 128 values with bit 2 set** |
| **`bf_alu.srcA`** | 254 / 256 | `NAT:k_bfadd` (4 carriers) | `{0, 128}` |
| **`bf_alu.srcB`** | 248–254 / 256 | `SYNTH:k_bfadd` | 4–8 values |
| **`bf_alu.tail`** (w=24) | 42 / 42 §3.3 values; per-byte dense 248 / 224 / 224 of 256 | `NAT:k_bfadd` | — (§3.1) |
| **`bf_fma_dst.tail`** (w=32) | 50 / 50 §3.3 values; per-byte dense 252 / 248 / 224 / 224 | `NAT:k_bffma` | — (§3.1) |
| **`fspecial_est.srcA`** | 254 / 256 | `SYNTH:k_rsqrt` | `{0x03, 0x83}` |
| **`fspecial_est.subop`** | 255 / 256 | `SYNTH:k_rsqrt` | `{0x0f}` (§3.2) |
| **`iadd2.srcA`** | 252 / 256 (64 contained faults) | `NAT:k_u32add` | `{0xa8, 0xac, 0xb8, 0xbc}` |
| **`ibfe.srcA`** | 192 / 256 | `NAT:k_bfe` (3 carriers) | 64 values |
| `iadd2.b2_fmt` | **0 / 64** — dense-INERT | — | all 64 |
| `ibfe.sign_ext` | **0 / 2** — dense-INERT | — | both |
| `ibfe.b2_bit0` | **0 / 2** — dense-INERT | — | both |
| `ilogic.lut_a_free` | **0 / 8** — dense-INERT on **7** carriers | — | all 8 |
| `ilogic.z6 / z8 / z9` | **0 / 256** each — dense-INERT | — | all 256 |

`ibitcount.tail`'s accept-set is **exactly** M4's rule (EXP-0139 DEF-0139-3, "only bit 2 is
load-bearing"), reproduced value-for-value on G17P. **H3 confirmed.**

### 1.6 Detection power, measured not assumed

Every inertness reading above comes from a carrier whose **byte0 falsifier was proven
non-`ok`** and whose **liveness ladder was proven live on the same run**. Two examples of
the instrument working:

* `iadd2.b2_fmt` is inert over its own 64 sub-values while **byte+2 itself moves 128 of 256
  on the NAT carrier** — that movement is bits 0–1 (`b2_bit0` / `store_en`), so the byte is
  demonstrably live and `b2_fmt` really is inert.
* `ibfe.sign_ext` is inert over its 2 sub-values while **byte+6 moves 254 of 256**.

---

## 2. Interpretation — separated from the above

1. **The M4↔G17P `outmod` contradiction is resolved and it is not a silicon difference.**
   EXP-0154's "inert across the whole range" was a 16-register-dump carrier being blind to a
   control that only shows up when the result is consumed by an adjacent memory operation.
   EXP-0166's diagnosis was right; its recommended experiment was the right one.
2. **What byte+7 bit 7 most likely IS.** The sources read as zero when it is clear, and only
   on the carrier whose operands arrive from an **asynchronous `device_load`** issued
   immediately before. That points at a *pending-load / operand-delivery* (scoreboard or
   forwarding) control, of the same family as `ibitcount.cache` and `iadd2.store_en`.
   **Alternative not excluded:** a plain writeback/publish bit whose absence is invisible
   whenever the consumer is far away — the SYNTH carrier has 30-odd instructions between the
   op and the dump, so it cannot separate the two. **A successor discriminates it** by
   placing the dump store immediately after the block in a synthesized program.
   For a driver the actionable statement is target-independent either way: *an emitter that
   clears byte+7 bit 7 on a logic op whose result is consumed by a memory operation loses
   the operands.*
3. **`ilogic` and `b_alu10_lof`/`b_alu10_loe` are one instruction** (DEF-0171-1). The
   practical consequence for `docs/`: EXP-0154's committed G17P `ilogic` rows are rows about
   **destination r0 only**, and an emitter that wants any other destination must write
   byte0's high nibble — which `ilogic`'s descriptor does not model at all.
4. **`fspecial_est`'s row is about liveness, not semantics.** The SYNTH carrier lifts the
   estimate alone, and its baseline (`r0 = -1.5e-07` for the seeded input) is **not**
   `rsqrt(1.5)`, so the standalone 6-byte `fspecial_est` does not by itself compute the
   estimate on G17P — the precise lowering surrounds it with `isel8` / `pad_operand` /
   `fspecial`. The verdict establishes that both fields are dense-live and every encoding
   executed; it does **not** establish a sub-op map. See §3.2.
5. **`ibfe.sign_ext` is not the sign control.** It is inert in BOTH the unsigned (`k_bfe`)
   and signed (`k_bfe_s`) anchors. Those two compiler-emitted anchors differ in byte+6 bit 1
   *and* in `srcC_flags` byte+9 bit 0 (`0x11` unsigned vs `0x10` signed); the sweep shows
   byte+6 bit 1 is not the cause, so `db.json`'s "signed sets `sign_ext` (b6 bit1)" is a
   **correlation across two compiler forms, not a control**. The attribution to
   `srcC_flags` bit 0 is `INFERRED` — byte+9 was not swept in this matrix.

---

## 3. Limitations — what a reader must not over-read

1. **`bf_alu.tail` and `bf_fma_dst.tail` are 24- and 32-bit fields.** The
   FIELD-SWEEP-PROTOCOL §3.3 bar is met (0, 1, 2, max−1, max, every power of two, 16
   asymmetric interior — 42 and 50 values, all distinct encodings) **and** every spanned
   byte was swept dense 0..255, but 42 of 2²⁴ and 50 of 2³² is not exhaustive. Their
   accept-sets are empty **by construction**: the anchor composite value is not a member of
   the §3.3 sample set, so no sampled value can reproduce the baseline; the per-byte dense
   accept counts are in `analysis/field_verdicts.json`.
2. **`fspecial_est.subop`'s accept-set is a singleton `{0x0f}`.** Per EXP-0166 §6.2, a
   singleton accept-set establishes "every other value breaks THIS carrier", **not** an
   operand map — and for a *sub-op selector* a non-`ok` outcome may simply mean "a different
   function", not "invalid". Note also that `0x0f` is **absent from `db.json`'s enum**
   `{9: rcp, 11: rsqrt, 13: sqrt}`; G17P's precise `rsqrt` lowering uses `0x0f`.
3. **Five rows are promoted FROM PROVEN INERTNESS** to `isolated-byte-diff`:
   `ilogic.lut_a_free`, `b_alu10_lof.src_flag`, `b_alu10_loe.src_flag`, `ibfe.sign_ext`,
   `ibfe.b2_bit0`. Each required ≥ 2 carrier STYLES *and* ≥ 2 **independent
   compiler-emitted anchors**, with the controlled dimension named in the row. They are the
   right place for an adversarial re-audit to start, and `analysis/closure.json` lists them
   explicitly. **`ibfe` is the only instruction whose closure depends on any of them.**
   `ilogic.lut_a_free`'s case is the strongest of the five: inert over all 8 sub-values on
   **seven** carriers spanning five different LUT2 boolean functions — the dimension the
   field would control.
4. **`ilogic.z6 / z8 / z9` are dense-inert on three carrier STYLES but only ONE anchor**, so
   they are held at `single-template-inference`. "Any value works" is still a statement
   about one template. A successor needs a second `ilogic` anchor — a different LUT base, a
   uniform-operand form, or a 64-bit form.
5. **The predicate-consumed `ilogic` pole is unreachable from our own MSL on G17P.** Both
   `(a&b)!=0 ? 7 : 9` and the `if` form lower to `isel10` with no logic op at all, so
   `db.json`'s "clear on the dec2 predicate-consumed forms" could not be provoked. Recorded
   as `instr_absent`, not dropped.
6. **`b_alu10_*.opsel_hi` and `bf_fma_dst.fmt` were not covered.** `bf_fma_dst.fmt` is
   already `hardware-run` in `validation.json`, so **no row is emitted for it** — nothing
   here can downgrade it (`analysis/field_verdicts.json` → `_no_row`).
7. **Everything is G17P.** No M4 row is retracted and nothing is promoted across targets.
8. **`run02` recorded 1 hang** (contained; no arm abandoned) and both runs share 128
   `invalid_run` cases, which are excluded from every verdict by the hygiene gate.
9. The neo's shared `~/agxre/tools/agx-isa/db.json` is **stale** (sha `f5db942f…`, 171
   instructions / 1036 fields, `ilogic` still un-split). This experiment pinned its own
   snapshot (sha `322847609de7…`, 172 / 1062) and both runs' `00_env.json` prove the pin
   held. The shared tree was read only, never edited.

---

## 4. Negative and null results — first class, per CLAUDE.md

* **A carrier was rejected by its own falsifier.** `NAT:k_rsqrt@fspecial_est+18` returned
  **`ok` for byte0 := 0x00**, so it has no detection power and was DISCARDED — it also read
  `0 moved` on both target fields, i.e. it would have reported *inertness* had the falsifier
  not caught it. That is EXP-0161's failure mode (the Newton–Raphson refinement corrects the
  estimate whatever it was), now **diagnosed by the instrument instead of mistaken for a
  result**. 26 of 27 carriers admitted.
* **`iadd2` did not close.** `srcA` moved 252/256, but `b2_fmt` is dense-inert on one
  anchor and stays `single-template-inference`. H6's prediction that byte+7 would be inert
  or nearly so was **refuted**: it is dense-live with 64 contained address faults.
* **`ilogic` did not close.** 5 blocking fields → 3.
* **`z6`/`z8`/`z9`/`ext8`/`ext9`** (10 rows across three descriptors) are proven dense-inert
  and deliberately **not** promoted.
* **`db.json` defects found and reported, not patched** (`db.json` is the orchestrator's):
  DEF-0171-1 (byte0 over-fit), DEF-0171-2 (no length rule for byte0 `0x31`; the `bf_alu`
  match and `bf_fma_dst.fmt` enum do not describe what G17P emits), DEF-0171-3
  (`ibfe.sign_ext` is not the sign control), DEF-0171-4 (`ilogic.outmod` is a source-read
  control, not an output/store flag), DEF-0171-5 (`fspecial_est.subop == 0x0f` on G17P,
  absent from the enum).

---

## 5. Verdict

| | |
|---|---|
| **`ilogic` closed?** | **No.** `outmod` → `hardware-run` and `lut_a_free` → `isolated-byte-diff`, so it goes from **5 blocking fields to 3** (`z6`, `z8`, `z9`, all proven dense-inert on one anchor). The M4↔G17P contradiction that blocked it **is resolved**, and the mechanism is corrected. |
| **`srcA` / `tail` descriptors that MOVED** | `ibitcount.tail`, `bf_fma_dst.tail`, `bf_alu.tail`, `bf_alu.srcA`, `bf_alu.srcB`, `fspecial_est.srcA`, `fspecial_est.subop`, `iadd2.srcA`, `ibfe.srcA` — **9 rows, every one at `hardware-run`, cross-run agreement 1.0000.** |
| **Instructions closed on movement evidence alone** | **`ibitcount`, `bf_fma_dst`, `bf_alu`, `fspecial_est`** (4). |
| **Closed only with a promotion from proven inertness** | **`ibfe`** — flagged for the orchestrator's call. |
| **Also moved** | `b_alu10_lof` and `b_alu10_loe` each go **11 blocking fields → 5**; `iadd2` **2 → 1**. |

`analysis/field_verdicts.json` (full, with per-carrier detail, carrier gates and the
transplant control), `analysis/field_verdicts_flat.json` (the flat `<mnemonic>.<field>`
merge file, FIELD-SWEEP-PROTOCOL §5, **all 37 rows carrying `values_dispatched`,
`distinct_bytes`, `encodable_range`, `start`, `width`; 0 under-covered**),
`analysis/coverage.json` (139/139 dense-complete, both runs), `analysis/closure.json`.
