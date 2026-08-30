# RESULTS — EXP-0167, G17P generator synthesis RE-CONFIRMED under isolation

**Target: A18 Pro / G17P** (`Mac17,5`, macOS 26.6, `AGXAcceleratorG17P`, 5 GPU cores).
**Status: CONFIRMED. The pre-registered cross-run gate PASSES.**

---

## 0. The headline

> **EXP-0158's 233 survives, and it survives in a much stronger form.**
> Under isolation, **233 of 237** zero-copied programs matched their exact host-computed
> oracle **in each single run, twice, byte-identically** — not pooled across four passes
> under a permissive "attributable" rule. `verify.py --captured`, the pre-registered gate
> EXP-0158 left **FAILING**, **PASSES** here on the same 289 programs.

| metric (denominator 237) | ISOLATED (EXP-0167) | CONTENDED (EXP-0158) |
|---|---|---|
| **M1 STRICT-PAIR** — matched in **both** gated runs, no revalidation credit | **233** | **96** |
| **M2 MATCHED-EVERYWHERE** — EXP-0158's published strict figure | **233** | **149** |
| **M3 ATTRIBUTABLE** — ≥ 1 `ok` and never a wrong value | **233** | **233** |
| **M4 CROSS-RUN GATE** — `01_results.jsonl` byte-identical across the pair | **PASS** | **FAIL** |

The same pre-registered gate, on the same 289 byte-identical programs, passes here and failed
there. **That comparison is this experiment's contribution**: EXP-0158's gate failed because
of the machine it ran on, not because of anything about the programs.

Every committed prediction held (`PRE_REGISTRATION.md` §4): H1 M1 ≥ 225 → **233**;
H2 M2 ≥ 229 → **233**; H3 M3 ∈ [229, 237] → **233**; H4 gate **PASS**; H5 all **28**
pre-registered-to-FAIL cases still fail.

**The honest-lower branch (§4.1) was not taken** — but it was live, and this section would
have led with it. `M3 < 225` would have meant the 233 was contamination-inflated. It is not.

---

## 1. What was directly OBSERVED

### 1.1 The two gated runs are byte-identical

```
verify.py --captured
  01_results.jsonl byte-identical across both runs:
    434f00b5ff8912efb21f9651829faf2976b12ed59fac09f0ad93c468de9dea73
  g17p-20260830-iso01: 32/289 cases MISMATCHED oracle (4 unexpected)
  g17p-20260830-iso02: 32/289 cases MISMATCHED oracle (4 unexpected)
  captured: PASS
```

Both runs, independently: 289 cases, **257 matched, 285 as-predicted,
`zero_copied_and_matched` = 233**, outcomes `{ok 257, silent_zero 15, wrong_value 12,
no_write 2, fault 3}`. The 4 unexpected mismatches are exactly EXP-0158's 4 known
`IADD_SYNTH` failures, returning identical values in both runs (44 / still-poisoned /
22 / 120).

### 1.2 The contamination is gone — measured, not asserted

| | iso01 | iso02 | EXP-0158 run03 | EXP-0158 run04 |
|---|---|---|---|---|
| `kIOGPU…InnocentVictim` cases | **0** | **0** | 51 | 70 |
| total in-case victim retries | **0** | **0** | 328 | 636 |
| `fault` | **3** | **3** | 30 | 44 |
| `victim` | **0** | **0** | 51 | 70 |
| `invalid_run` | **0** | **0** | 0 | 2 |
| cascade witness OK | **7/7** | **7/7** | 6/7 | 5/7 |

All **3** faults in each isolated run are the **deliberate fault arms**
(`regb_R126_faultarm`, `regb_R127_faultarm`, `adv_iadd_dst_reg96`), each **3/3** on the
majority-of-3 revalidation pass and **5/5** on the witness-gated pass. Nothing else needed
revalidating: `revalidated_cases = 3`, against EXP-0158's 81 and 114.

### 1.3 Nondeterminism on identical bytes: 102 → 0

Witness-gated 5-repeat pass (a sentinel-only witness program run immediately **before** every
observation; any observation whose witness failed is discarded):

| | ISOLATED (EXP-0167) | CONTENDED (EXP-0158) |
|---|---|---|
| cases | 148 | 174 |
| observations | **740** | 870 |
| **MIXED outcomes across 5 runs of identical bytes** | **0** | **102** |
| observations discarded because the witness failed | **0** | 0 |
| majority `fault` | **3** | **93** |
| majority `ok` | 116 | 66 |

**The witness never failed once in 740 attempts.** EXP-0158's *first* re-confirmation attempt
produced 427 `Caused GPU Hang Error` observations in consecutive streaks and had to be
discarded entirely.

### 1.4 Two of EXP-0158's five asserted fault verdicts are REFUTED

This is the most specific result in the experiment. EXP-0158 §4 named five cases that
"faulted 5/5 in the witness-gated pass" and called them "the only fault verdicts this
experiment asserts". Re-run 5/5 under isolation:

| case | EXP-0158 witness-gated | EXP-0167 witness-gated | verdict |
|---|---|---|---|
| `regb_R126_faultarm` | `fault` 5/5 | **`fault` 5/5** | holds (reproduces EXP-0112 on M4) |
| `regb_R127_faultarm` | `fault` 5/5 | **`fault` 5/5** | holds |
| `adv_iadd_dst_reg96` | `fault` 5/5 | **`fault` 5/5** | holds (EXP-0139 `dst ≥ 96`) |
| **`iaddsyn_A11_B22_N1_D0_add`** | `fault` 5/5 | **`ok` 5/5** | **REFUTED** |
| **`dag_040_n20`** | `fault` 5/5 | **`ok` 5/5** | **REFUTED** |

**`iaddsyn_A11_B22_N1_D0_add` is the more consequential of the two**, because EXP-0158 did not
merely record it — it *explained* it: §6.1 attributes the fault to "`iadd2` destination r0,
which collides with `srcA`'s implicit r0 read". **That mechanism is not supported.** The
program runs correctly, 5/5, on a quiet machine. `iadd2` register mode with destination r0
works.

Consequently **`IADD_SYNTH` is 12 of 16 under isolation, not 11 of 16**, and the family's
failure list is 4 cases, not 5 (§1.6).

**`dag_040_n20`** is the cleanest demonstration of the failure mode: `ok` in EXP-0158's run03,
`victim` in its run04, `fault` **5/5** in its witness-gated pass — and it was counted *inside*
its 233 on the strength of that single `ok`. Under isolation it is `ok` 5/5. A 20-node DAG
program that computes its oracle exactly, every time, on a quiet machine was being reported as
a reproducible hardware fault.

### 1.5 The error is ONE-DIRECTIONAL — a reusable methodological result

Across the 100 cases both experiments re-confirmed at 5 reps, **48 majorities flipped**, and
**every flip runs in the same direction**: a contended `fault` majority becoming the case's
real outcome under isolation.

- **42** flips `fault`-majority → **`ok` 5/5**
- **3** flips `fault`-majority → **`wrong_value` 5/5**
- **3** flips `fault`-majority → **`silent_zero` 5/5**
- **0 flips in the other direction.** No case that was `ok` under contention became a fault,
  a wrong value, or a silent zero under isolation.

Of the 100, only 45 agreed *and* were unanimous under contention; 55 either differed or were
MIXED there.

**Contention manufactures faults; it does not manufacture correct answers.** That asymmetry is
the same one EXP-0158's attributable rule assumed and EXP-0160 used to justify adjudicating
offline from poisoned dumps, and this experiment measures it directly rather than assuming it.
It is a fact about the method, transferable to any experiment on this host: a `fault` observed
under sibling load is evidence about the machine; a bit-exact match against an independently
computed host oracle cannot be produced by another process's GPU reset.

**Corollary — the attributable rule was sound.** EXP-0158 chose a permissive-about-faults,
strict-about-wrong-answers rule and disclosed the deviation rather than hiding it. Its 233
matches this experiment's 233 exactly. It reached the right number by the right reasoning from
bad data.

### 1.6 The failure envelope is unchanged and now fully deterministic

The **4** zero-copied programs that are genuinely wrong, each **5/5 identical** under isolation:

| case | outcome 5/5 | observed |
|---|---|---|
| `iaddsyn_A33_B44_N13_D9_sub` | `wrong_value` | 44 — the second operand alone |
| `iaddsyn_A127_B1_N15_D10_add` | `no_write` | still `0xDEADBEEF` |
| `iaddsyn_A11_B22_N1_D95_add` | `wrong_value` | 22 — the second operand alone |
| `iaddsyn_A7_B120_N4_D47_add` | `wrong_value` | 120 — the second operand alone |

EXP-0158's `srcA` interpretation of the signature (three of four return the second operand
alone, never a partial sum) is **unaffected** by this experiment and is neither confirmed nor
extended here. Its proposed next step — a `srcA` × `dst` cross-sweep — remains the right one.

The `REGBOUNDARY` predictions all hold, now without a single contaminated observation:
**R = 63 delivers the loaded value; R = 64 does not** (`silent_zero` 5/5); R = 65…112
`silent_zero` or `no_write` 5/5; **R = 126 / R = 127 fault** 5/5. `as_predicted` for the family
is **38 of 38** under isolation, against 30 of 38 under contention.

### 1.7 Per family

`matched` is `summarize.py`'s matched-everywhere; `as_pred` counts a pre-registered-to-fail
case as correct when it fails.

| family | n | zero-copied | **ISO** matched / as_pred | EXP-0158 matched / as_pred |
|---|---|---|---|---|
| `MAIN_DAG` | 100 | 100 | **100 / 100** | 51 / 51 |
| `INLINEIMM` | 76 | 76 | **76 / 76** | 63 / 63 |
| `DAG_INLINE` | 24 | 24 | **24 / 24** | 11 / 11 |
| `REGBOUNDARY` | 38 | 38 | **21 / 38** | 13 / 30 |
| `IADD_SYNTH` | 16 | 16 | **12 / 12** | 11 / 11 |
| `CF` | 12 | 0 | 12 / 12 | 12 / 12 |
| `IADD_ANCHOR_COPIED` | 12 | 0 | 12 / 12 | 12 / 12 |
| `ADVERSARIAL` | 11 | 11 | 0 / 11 | 0 / 11 |

Zero-copied totals: **100 + 76 + 24 + 21 + 12 = 233**, against 51 + 63 + 11 + 13 + 11 = 149.

### 1.8 The carrier baseline reproduces exactly

`baseline.py` re-derived both carriers from source **on the target** before each capture:
`carrier_dag.metal` → **1590** bytes, `carrier_cf.metal` → **152** bytes, with the same
`base_slot` order including `carrier_cf`'s documented buffer(1)/buffer(2) reversal — identical
to EXP-0158's and to the M4's.

---

## 2. The isolation evidence

This is the deliverable EXP-0158 could not produce about itself. Its RESULTS.md can only
report "8–12 sibling GPU experiments" from the orchestrator's knowledge. Here it is measured.

**No lock was taken, because none exists.** `~/agxre/gpulease.sh` on the target has been a
**neutralised pass-through shim** since 2026-08-30 00:02 —
`shift 2; [ "$1" = "--" ] && shift; exec "$@"` — which takes no lock, and no lock directory
exists on the machine. **EXP-0158's own `run03`/`run04` were launched through that same
shim**, so those runs were never locked either; that is consistent with its symptoms. Isolation
here was established by the orchestrator quiescing the other device agents by hand, and
**verified** by `harness/gpuwatch.py`, which reads `/bin/ps` and `sysctl` only.

### 2.1 Pre-dispatch baseline (the §6 precondition)

**149 samples over 309.8 s before any device operation of this experiment:**
`n_foreign == 0` in **every** sample; max concurrent foreign harness processes **0**; **0**
samples with a busy `MTLCompilerService`; load average visibly settling **3.99 → 1.72** as the
quiesce took effect. Three idle `MTLCompilerService` XPC instances were present throughout —
normal on this host, and not contention.

### 2.2 During the capture

2,637 samples across three files spanning 07:51:40Z–08:28:16Z.

The **ancestry-resolving** sampler (`gpuwatch2.py`, §2.3): **669 samples, `n_foreign` = 0 in
every one**, max concurrent processes of mine 8, 3 `MTLCompilerService` instances, **0** busy.

### 2.3 A false positive, root-caused rather than waved away

The first sampler (`gpuwatch.py`, v1) recorded **91** sightings it labelled foreign — 46 in
`00_prewindow.jsonl` and 45 in `01_gated.jsonl`, **all of them after my own capture began, none
in the 149 pre-dispatch samples**. Every one of the 91 is `(agxrun)` or `(shdump)` with
`etime ≤ 00:01`.

Root cause, verified on the target: **macOS `ps` truncates the `comm` column to 16 characters**
(a Python process reports `comm = "/Applications/Xc"`), and a process whose `argv` is momentarily
unreadable — the fork/exec transition — is rendered by `ps` as `(agxrun)` in **both** `comm` and
`args`. v1 matched the harness regex against `comm` (which `(agxrun)` satisfies) and then looked
for the marker in `args` (which `(agxrun)` lacks), so it filed **its own child, caught
mid-`exec`, as foreign**. The same truncation is why v1's `n_mine` was 0 throughout, including
for the sampler process itself.

`agxrun` and `shdump` are the two binaries **this experiment** builds into its own `work/` and
runs several hundred times per pass; they appear only while its captures run and never before.
`harness/gpuwatch2.py` resolves the ambiguity structurally — it matches full `args`, walks the
**ppid chain** to attribute each candidate, and puts an unreadable-argv process in its own
bucket rather than asserting it belongs to someone else. It reports **0 foreign** and 9 samples
containing 1 unresolved-unreadable process, all `(agxrun)`/`(shdump)` at `etime ≤ 00:01` during
this experiment's own capture.

**v1 was left running unmodified for the whole experiment**, so both records cover the same
window and can be compared; its file is append-only and was not edited.

**Verdict on §7's pre-committed claim:** the isolation claim **stands**. Max concurrent foreign
processes = **0** on the instrument able to answer the question, and every v1 sighting is
positively attributed to this experiment's own process tree.

---

## 3. The provenance check EXP-0158's round-trip could not perform

Prompted by DEF-0166-1 (`isadb.assemble()` OR-ed `match` constant bits and then OR-ed field
values on top with no clear step, so any bit a `match` constant set inside a field's span was
**stuck at 1**; fixed at commit `4b16d0b4`, 53 fields affected).

**Why `assert_round_trip()` structurally cannot catch this.** It disassembles a program and
re-assembles it **from the disassembled fields**. A defect that is *symmetric across encode and
decode* is present on both sides of that comparison and cancels: the round trip passes while
telling you nothing about whether the emitted field equals the value the generator **chose**.
**Any round-trip gate in this repository has the same blind spot**, including
`tools/agx-isa/roundtrip_test.py`. A round trip proves self-consistency, not fidelity to intent.

`analysis/assemble_defect_check.py` performs the test that is not blind to it. It wraps the
**pinned, pre-fix** `assemble()`, records every call made while building the corpus
(**204,044** calls; **2,396** distinct `(mnemonic, field-values)` pairs across 18 mnemonics),
and then:

1. re-assembles each pair with the **corrected** algorithm over the **same pinned
   descriptors** — **0 differences**. DEF-0166-1 altered no emitted field in this corpus.
2. **disassembles** each emitted instruction and compares the decoded value against the value
   the generator **requested** — **0 mismatches**.

**Both CLEAN.** No stuck bit smuggled an undocumented constant into EXP-0158's or EXP-0167's
programs; every field carries the value its provenance ledger says was computed. This is a
strengthening of the 233, not a formality: it tests the *claim* ("every field generated from a
documented rule") rather than the *measurement*.

---

## 4. What is INTERPRETATION, not observation

- **"EXP-0158's gate failed because of concurrent GPU load"** is an interpretation. What was
  *observed* is that the same 289 byte-identical programs, on the same machine and toolchain,
  produced 0 victims / 0 retries / byte-identical results with a measured-quiet process table,
  and 51–70 victims / 328–636 retries / a failing gate without one. Concurrency is the variable
  that changed; a hidden third factor (thermal state, an OS-level change between 00:24Z and
  07:57Z, uptime) is not excluded by this design.
- **"`iadd2` register mode with destination r0 works"** rests on `ok` 5/5 in the witness-gated
  pass plus `ok` in both gated runs, for **one** operand triple (A = 11, B = 22, N = 1). It
  refutes EXP-0158's fault claim for that program; it does not establish r0 as generally safe
  across the `srcA` × `dst` space.
- **"The error is one-directional"** is measured over the 100 cases both experiments
  re-confirmed at 5 reps. It is a strong regularity in this corpus on this host, not a proven
  property of the driver's error handling.
- **`dag_040_n20`'s contended `fault` 5/5 was contamination** is the reading; what was observed
  is `fault` 5/5 there and `ok` 5/5 here, on identical bytes.

---

## 5. Limitations

1. **The corpus is 289 cases but only 277 distinct programs.** 11 of the 12 `CF` cases share a
   single program (they vary only their input buffer values, which is legitimate for that
   carrier), and `dag_002_n4`/`dagi_002_n4` and `dag_003_n5`/`dagi_003_n5` coincide because
   those DAGs carry no float constant for `DAG_INLINE` to move inline. A reader quoting "289
   programs" overstates the corpus. Inherited from EXP-0158 **by design** — holding the
   artifacts byte-identical was the point of this experiment — and not fixed here.
2. **3 of the 237 have an entirely-zero oracle — `inl_k36`, `inl_mul_k00`,
   `iaddsyn_A0_B0_N1_D3_add` — and for those three a silent zero is indistinguishable from a
   correct answer.** `classify_word` tests `got == expected` *before*
   the zero test. On an ISA whose characteristic failure mode is a silent zero, that is a real
   limit on those three cases, not a technicality. Also inherited by design.
3. **This experiment measures conditions, not new hardware facts.** It establishes no new
   encoding. Its contribution is the reliability of EXP-0158's, plus the two refuted fault
   verdicts (§1.4) and the round-trip blind spot (§3).
4. **One machine, one session, one afternoon.** The quiet window was ~37 minutes of device
   time. Long-run thermal or DVFS behaviour is not characterised; only load average was
   recorded.
5. **The `CF` family still has no integrity sentinel** — the 152-byte carrier cannot hold the
   extra 16 bytes, and lengthening a carrier is not semantically neutral (EXP-0140). Unchanged
   from EXP-0158.
6. **`falu2.srcB_class = 2`** remains a named, untested hole (it hung the device on first
   contact in EXP-0158 and was excluded from the corpus). This experiment did not probe it.
7. **The 24 donor-dependent cases are untouched** — 12 `CF` and 12 immediate-mode `iadd2`.
   `IADD_ANCHOR_COPIED` and `CF` still contain copied fields and are still excluded from the
   237. Closing them was the named optional follow-on and was correctly not traded against the
   confirmation.

---

## 6. What this supports for DRV-ISA-01 / P0.6

EXP-0158's claim stands, with its evidence upgraded from "233 pooled across four passes under a
disclosed deviation from the pre-registered gate" to **"233 in each of two byte-identical runs
that pass the pre-registered gate literally, with zero contaminated observations and zero
nondeterminism across 740 witness-gated repeats."**

> **A generator can synthesize, from documented per-family rules with ZERO verbatim tokens,
> arbitrary dataflow programs over `const` / `device_load` / `falu2` / `falu2i` /
> `device_store` plus `iadd2` register mode — and get 233 of 237 of them exactly right on the
> A18 Pro, reproducibly.**

Still **not** the whole DRV-ISA-01 bar, unchanged from EXP-0158 §8: control flow and the
immediate-mode `iadd2` tail remain template replay (24 cases needing a donor), and
`iadd2` register mode is bounded at **12/16** (up from 11/16, §1.4).

Corrections this experiment makes to EXP-0158's record — for the orchestrator, who owns those
files:
- its §4 list of five asserted `fault` verdicts loses two (`iaddsyn_A11_B22_N1_D0_add`,
  `dag_040_n20`), and the r0/`srcA`-collision mechanism in its §6.1 is unsupported;
- its §1.1 `IADD_SYNTH` row becomes **12 of 16**, and its §6.1 failure table loses the
  `11 22 1 r0 add` row;
- its §7 limitation 1 ("a repeat on a quiet machine would convert the attributable number into
  the pre-registered one, or expose a real failure the noise is hiding") is now **discharged**:
  it converted, and it exposed no hidden failure.

---

## 7. Clean-room provenance

```
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: EXP-0158's own authored generator/emitter/harness code and carrier MSL,
  copied BYTE-IDENTICAL (hashes in PRE_REGISTRATION.md section 8, re-verified on the target);
  a PINNED, hash-recorded snapshot of this repository's own tools/agx-isa isadb
  (db.json 418d7808..., isadb.py 1d60d36d...); this experiment's own gpuwatch.py,
  gpuwatch2.py, compare.py, isolation_report.py and assemble_defect_check.py; the target's
  own process table via /bin/ps and sysctl.
Apple binary introspection: NONE.
Reproduction: README.md's command sequence.
Evidence: raw/g17p-20260830-iso01/, raw/g17p-20260830-iso02/, raw/isolation/ (3 files,
  2637 samples), work/reconfirm/, analysis/summary.json, analysis/comparison.json,
  analysis/isolation_report.json, analysis/assemble_defect_check.json.
```

**Corpus identity, proven before the run:** both trees build 289 programs with
`sha256(concatenated program hex) = f08d598832ea7bbb5ad90f32a9c52cd6cd9402d3bf9cf52ac6dc047f259e4e87`.
Any difference in outcome is attributable to the machine, not to the corpus.

**Concurrent GPU experiments during these captures: 0, measured** (§2), against EXP-0158's 8–12.
