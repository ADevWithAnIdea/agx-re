# RESULTS -- EXP-0090 (M4 hand-built program suite, DRV-ISA-01 acceptance test)

**STATUS: CAPTURED / PROMOTED.** Both gated captures closed and valid.
`verify.py --captured` PASSES: `raw/m4-20260827-run01/01_results.jsonl` and
`raw/m4-20260827-run02/01_results.jsonl` are byte-identical
(sha256 `3c7949547ad6e3a4e74067fc43d688507b97937ba9a45253098b8b604081d59`).
24/24 cases matched their independent Python oracle in BOTH runs, across
three programs (P1, P2, P3). A fourth program (P4) could not be made to
work and is reported below as a first-class negative result, per this
project's standing rule that a failed construction is itself a success for
the experiment.

Target: **local Apple M4 / G16G only** (macOS 26.6.2 build 25G82, Metal 4,
`clang -fobjc-arc`, `--no-fast-math`). No A18 Pro (G17P) replication (hands
off, per standing directive). No M5 evidence used anywhere.

---

## 1. Per-program pass/fail against oracle

| program | cases | matched (run01) | matched (run02) | notes |
|---|---|---|---|---|
| P1 -- arithmetic dataflow chain | 7 | 7/7 | 7/7 | float chain + independent integer op |
| P2 -- memory round trip | 10 | 10/10 | 10/10 | single-store design (see §4 "P2 echo anomaly") |
| P3 -- control flow | 7 | 7/7 | 7/7 | real loop + if/else->select, byte-reconstructed |
| P4 -- register-pressure/move | 0 (excluded) | -- | -- | **NEGATIVE RESULT**, see §6 |
| **Total** | **24** | **24/24** | **24/24** | |

Every case's full record (params, oracle, observed, match, raw hex output)
is in `raw/m4-20260827-run0{1,2}/01_results.jsonl`; per-case identity is
`casematrix.py::build_cases()[i]`.

---

## 2. OBSERVED vs INTERPRETED

**OBSERVED, directly, from the raw records:** for all 24 cases, on both
independent captures, `STATUS=OK` (no command-buffer fault, no timeout, no
harness exception), and the decoded output word(s) at the program's own
predicted byte offset matched the independently-computed Python oracle
bit-exactly (floats compared as their exact IEEE-754 bit pattern via `==`
in `harness/case_exec.py::decode_case`, not a tolerance compare -- the ISA
being deterministic, an exact byte match is the correct bar). No case was
retried; every case ran in its own fresh subprocess.

**INTERPRETED:** the whole-program construction method -- concatenating
`isa_helpers.py` wrappers (each one `tools/agx-isa`'s own `isadb.assemble()`)
into a single byte string, padding to an exactly-measured carrier length,
splicing at `_agc.main` offset 0, and running -- correctly executes
non-trivial, multi-instruction-family, hand-built AGX9 programs on real M4
hardware, for the SPECIFIC instruction-family combinations enumerated in
§5's confirmed column. This is **not** a universal claim that any
combination of documented fields works; §5 and §6 are equally load-bearing
parts of this result.

**Alternative explanations not excluded:** the M4-only scope (no A18 Pro
cross-check); single-thread (`grid=1,tg=1`) dispatch only (no divergence,
no cross-lane interaction tested); the specific packed-minifloat immediate
domain (this experiment never probes the SFU/transcendental paths).

---

## 3. Operand-field matrix results

### P1 (item `P1`, 7 cases)
| field varied | values tested | result |
|---|---|---|
| float immediate (`falu2i` `k`) | 0.0, 2.0, 0.5, -1.0, 30.0 (max representable), -30.0 (min representable) | all exact, via `isadb.imm_encode`/`imm_decode` round trip |
| integer immediate (`iadd2` `srcB_imm`, K) | 0, 100, 127 (max reachable without `srcB_imm_hi`) | all exact |
| liveness-violation bit (`falu2i` `opflags` bit0 on R1's first read) | natural (0) vs corrupted (1) | natural: `out0=7.5`; corrupted: `out0=11.5` -- see §5 |
| `falu2`/`falu2i` `opflags` (both-real srcB case) | 1 (bit0 only) vs 3 (bit0+bit1) | 1 = silent zero (FALSIFIED); 3 = correct (CONFIRMED) -- decisive finding, see §5 |

### P2 (item `P2`, 10 cases)
| field varied | values tested | result |
|---|---|---|
| `idx_off` (11-bit load field) | 0, 5, 1000, 2047 (max), 2048 (first value NOT representable in 11 bits) | all exact; 2048 masks to 0 (`idx_off & 0x7FF`), reproducing EXP-0082's own finding that the field has no "first invalid value" of its own -- 2048 is simply a different, still-legal, encoded value (0) |
| `elem_size` code (load) | 0 (16B), 1 (1B, collapses per EXP-0082), 2 (2B, collapses), 3 (4B, baseline), 4 (8B) | all exact, matching `ELEM_SCALE={0:16,1:1(collapsed),2:2(collapsed),3:4,4:8}` |
| `base_slot` | 1 (baseline), 129 (=1+128, EXP-0083 7-bit mirror) | both exact and BYTE-IDENTICAL output -- CONFIRMS the EXP-0083 mirror for this instruction form too |
| index register value | 0, 1, 3 | all exact |

### P3 (item `P3`, 7 cases)
| field varied | values tested | result |
|---|---|---|
| loop trip count (`n`, data-driven) | 0, 1, 3 (baseline), 20 | all exact (`out0` = 47.0, 48.5, 51.5, 77.0 respectively) |
| if/else natural selection (`a`, data-driven) | 50.0 (selects false arm), 150.0 (selects true arm) | both exact |
| `icmp_pred` `cond` field | 6 (s_gt, native compile) vs 7 (s_lt) | field genuinely changes hardware behavior (CONFIRMED the enum is real and load-bearing) but controls the LOOP-ENTRY GUARD in this program, not arm-selection as first assumed -- a labeling correction, see §5 |
| liveness-violation bit (`falu2i` `opflags` bit0 on the loop-carried accumulator's producer read) | natural (0) vs corrupted (1) | natural: `out0=309.0` (a=150 case); corrupted: `out0=-3.0` -- corruption propagates to BOTH the arm computation AND the arm-selection decision, see §5 |

---

## 4. Every place our documented field model proved wrong (or incomplete)

1. **`falu2`'s `opflags` field (currently `db.json`: untyped 5-bit `mod`) has
   a SECOND load-bearing bit, not just the EXP-0086 last-use bit.** When a
   register-form `falu2` combines two values BOTH computed by prior
   instructions (as opposed to one real GPR + an unwritten "don't care"
   register), `opflags` must be `3` (bit0 AND bit1), not `1` (bit0 alone).
   `opflags=1` is a SILENT ZERO of the `srcB` read -- falsified 4 independent
   ways in the pilot phase, re-confirmed permanently in
   `diagnostics/redecisive_output.txt` (`finding_1`). **REFINED** (not
   REFUTED: bit0's last-use role from EXP-0086 still holds; this adds a
   second, previously-undocumented requirement on top of it).
2. **`device_store`'s `extmode` byte (currently `db.json`: untyped `mod`,
   EXP-0082's own text: "value register supplied implicitly by the
   preceding op/amode") has a concrete formula: `extmode = 2 * data_reg`**
   (for `addr_mode=0x54`, ALU-forwarded stores), confirmed independently
   across 3 different own-compiled kernels plus re-derived fresh in
   `diagnostics/redecisive_output.txt` (`finding_5`). **REFINED** into a
   testable, reusable rule.
3. **`device_load`'s destination-register model
   (`dst=dst_lo|(dst_ext9<<2)`, EXP-M4-13 R8) does NOT, by itself, let a
   freshly hand-constructed instruction reliably bridge a loaded value into
   `falu2`/`falu2i`.** 5+ independently varied constructions all produced a
   silent zero; re-confirmed permanently in `diagnostics/redecisive_output.txt`
   (`finding_2`), with a same-carrier CONTROL (`finding_3`) proving the
   splice/harness mechanism itself is not at fault -- `device_load` ->
   `device_store` direct-forward (`addr_mode=0x56`) works reliably with the
   IDENTICAL load bytes. **PARTIAL / an open gap**, not a full REFUTATION:
   `device_load` -> `device_store` (item 4 below) and `device_load` ->
   `iadd2` via one specific verbatim anchor (item 5 below) both DO work, so
   the destination-register field is not meaningless -- but this
   experiment could not establish the rule that would let a compiler freely
   choose which register a load's consumer reads from.
4. **`reg_move` (the EXP-0087 `byte+2=0x01,op_desc=0x08` encoding,
   previously HW-VALIDATED) does not reliably read a GPR that a
   `falu2`/`falu2i` instruction had just written**, despite reading an
   independently-proven-correct source value. Falsified 3 independent
   ways; re-confirmed permanently in `diagnostics/redecisive_output.txt`
   (`finding_4`). EXP-0087's own validated cases were, on inspection, ALL
   sourced from the UNIFORM register file (its whole carrier kernel was
   `uniform_mov`-based) -- a narrower scope than "any GPR" that its own
   RESULTS.md did not flag as a limitation. **REFINED / SCOPE-NARROWED**:
   EXP-0087's finding stands for its own tested scope; this experiment
   shows that scope does not extend to reading a value newly computed by a
   different instruction family within the same program.
5. **Carrier `base_slot` assignment is not `buffer(N) -> base_slot=N` in
   general.** `carrier_p3.metal`'s own compile maps `buffer(1)->base_slot=2`
   and `buffer(2)->base_slot=1` (reversed from `carrier_p1.metal`/
   `carrier_p2.metal`'s `buffer(N)->base_slot=N`). This is compiler/
   register-allocator behavior, not a hardware field defect, but it is a
   real trap for a hand-assembling implementer: **the mapping must be
   independently re-derived per carrier** (by forcing a `tid`-indexed
   reference to each buffer and disassembling the result), never assumed.
6. **`device_store`'s `idx_off` unit is 16 bytes, confirmed AGAIN in a
   fresh, independent context** (P1's integer-op output landed at word 4,
   not word 1, for `idx_off=1`) -- corroborates EXP-0082's own finding
   rather than contradicting it, but is worth recording as an independent
   re-confirmation from a completely different program shape.
7. **A second load+`iadd2`+store ("echo") sequence, appended immediately
   after a first, complete, working one, landed its store at an unexpected
   byte offset** (evidence consistent with the index-setup register
   silently holding a different value than the immediately-preceding
   `mov_imm` should have given it, though the exact mechanism was not
   isolated). This is why P2's GATED design uses a SINGLE load-transform-
   store, not the two-store "round trip with echo" originally planned.
   **UNKNOWN / open finding**, explicitly not resolved by this experiment.

---

## 5. Per-instruction-family verdict

| family | verdict | decisive case |
|---|---|---|
| `falu2i` (register + packed-minifloat immediate) | **CONFIRMED** | every P1/P3 arithmetic step; immediates at 0/±30 boundary all exact |
| `falu2` (register-register), ONE real operand (srcA) + a don't-care/unwritten srcB | **CONFIRMED** | P1 chain steps combined with `falu2i`; `finding_3`/`finding_5` controls |
| `falu2` (register-register), TWO real operands | **REFINED** | requires `opflags=3`, not the previously-assumed bit0-only; `finding_1` |
| `device_load` -> `device_store` direct forward (`addr_mode=0x56`) | **CONFIRMED** | `finding_3`; P2's load-then-transform-then-store as a whole (via the `iadd2` bridge) |
| `device_load` -> `iadd2` (one specific verbatim anchor, `srcB_imm` varied) | **CONFIRMED (narrow)** | P1's integer op; P2's transform step; all `int_k`/`tk` field-matrix cases exact |
| `device_load` -> `falu2`/`falu2i` (freely constructed) | **REFUTED (for the constructions tried)** | `finding_2`; not attempted in any GATED case |
| `iadd2` register-mode (`srcA`/`srcB` both GPR) | **UNKNOWN / not independently re-derived** | scattered-bit `srcB` encoding and the `srcA=0x88` vs `0xa8` mode-flag byte were never confidently isolated (see PRE_REGISTRATION.md pilot notes); this experiment only uses the immediate-mode anchor |
| `reg_move` (compact move family) | **REFINED / SCOPE-NARROWED** | `finding_4`; correct for EXP-0087's own uniform-sourced scope, not shown to extend further |
| `icmp_pred` (loop-guard compare) | **CONFIRMED**, role **CORRECTED** | `cond` field changes real hardware behavior exactly per its documented enum, but this experiment's specific instance controls the loop guard, not arm-selection (a labeling fix, not a field-semantics defect) |
| `isel10` (select/join) | **CONFIRMED (structural)** | byte-for-byte reconstruction of a real compile via `isadb.assemble()`, 0 residual diffs, executes correctly across both select outcomes |
| `jump`/`jump_cond`/`if_push`/`pop_reconverge` (loop back-edge/reconverge) | **CONFIRMED (structural, verbatim)** | reconstructed field-by-field from a real compile (0 byte diffs after reconstruction); NOT independently varied (their scope/scope_kind semantics remain `db.json`-flagged "not GPU-dispatch validated" -- this experiment did not attempt to change them) |
| `mov_imm` | **CONFIRMED** | used throughout as the index-register / zero-register seed |
| `device_store` `extmode` | **REFINED** (new field formula) | `finding_5` |

---

## 6. P4 negative result -- register-pressure/move program

**P4 could not be made to produce correct results in the time available and
is EXCLUDED from the formal two-run gate.** This is reported, not hidden,
per this project's standing rule.

**What was attempted:** seed 6 float values into `r0-r5` (via `falu2i`
unwritten-register+immediate, itself independently proven correct), snapshot
them to `r6-r11` and rotate back into `r0-r5` using ONLY the EXP-0087
HW-VALIDATED move encoding (`byte+2=0x01,op_desc=0x08,src_flag=0`), store the
rotated values, and probe one register's liveness with a repeated
`falu2i`-based read. Every attempt read back `0.0` for every slot.

**Root cause (established, `finding_4`):** `reg_move`'s `src_reg` field does
not reliably read a GPR that a `falu2`/`falu2i` instruction wrote, despite
the source value being independently proven correct at the point of the
move. This is not a timing/latency issue (multiple padding instructions
between producer and move made no difference in the earlier pilot phase).
Whether `reg_move` can read a GPR written by `device_load`, or ONLY by
other `reg_move`/`uniform_mov` instructions (EXP-0087's own narrow tested
scope), remains **UNKNOWN** -- this experiment did not additionally test
`device_load -> reg_move` given the time already spent falsifying the
`falu2i -> reg_move` path.

**Consequence for DRV-ISA-01:** a compiler backend targeting this ISA
**cannot currently assume `reg_move` interoperates with values computed by
the float-ALU family** without further hardware characterization. This is
exactly the kind of implementer-blocking gap this experiment exists to
surface (see the CLAUDE.md brief's own opening motivation -- an external
compiler engineer's reported blocker on this same move family, which
motivated EXP-0086/0087 in the first place). Raw evidence:
`diagnostics/redecisive_output.txt` (`finding_4`); the original P4 program
design lives (unused, historical) in `programs.py` alongside a comment
explaining why it is not called by `casematrix.py`.

`kernels/carrier_p4.metal` (the intended P4 carrier, base_slot-verified
during the design phase) is retained though unused by the final capture, as
part of the honest record of what was attempted.

---

## 7. What the assembler could/could not express

`tools/agx-isa`'s `isadb.assemble()` correctly expressed every instruction
this experiment used, INCLUDING every deliberately "wrong" field-matrix
value (silent-zero `opflags`, the out-of-range `idx_off=2048`, the flipped
`cond`, the flipped liveness bit) -- **no assembler gap was found**; every
observed failure in §4/§6 is a HARDWARE/FIELD-SEMANTICS gap, not a tooling
gap. The one friction point: `db.json`'s field types (`mod` for `opflags`
and `extmode`) do not yet reflect the refined semantics this experiment
found (§4 items 1-2); `tools/agx-isa/db.json` itself was NOT edited (per
the read-only tools convention) -- the correction is reported here for the
orchestrator to fold into `docs/`.

---

## 8. Gate results

- `verify.py --selftest`: **PASS**, 13 checks (uses a REAL recorded
  hardware fixture, `harness/recorded_fixture_case0.json`, per CODEX gate
  (e) -- not a synthetic fixture built from the implementation's own
  constants).
- `verify.py --seqtest`: **PASS** in all three tree states (`PRE_GPU`,
  `RUN01_PRESENT`, `RUN02_PRESENT`), 3/3/4/4 checks respectively across the
  four invocations actually run.
- `make_manifest.py --check`: **PASS** (16 authored files present).
- `verify.py --preflight`: **PASS**.
- `verify.py --between-runs`: **PASS** -- gated ONLY on
  `authored_{code,kernel,doc}_sha256`; explicitly does NOT compare live git
  HEAD (per the orchestrator's mid-run correction, recorded in `run.py`'s
  `git_revision_informational_only` field and `verify.py::between_runs`'s
  docstring).
- `verify.py --captured`: **PASS** -- `01_results.jsonl` byte-identical
  across both runs; `01_timing.jsonl` correctly differs (nondeterministic
  fields, e.g. `duration_ms`, are kept OUT of the gated file, per the
  standing gate-set requirement to separate timing from any byte-compared
  record).
- No STOPs occurred in either run (`raw/m4-20260827-run0{1,2}/` contain no
  `STOP.json`).

---

## 9. DRV-ISA-01 statement: what can now be GENERATED vs. what still cannot

**CAN be generated today, independently, by this repository's own tools,
with hardware-validated correctness (24/24 cases, 2 independent runs):**
- Arbitrary-length dependent chains of `falu2i` (register+packed-minifloat-
  immediate float ALU), including immediates across their full representable
  range, with correct liveness-bit discipline (opflags bit0 = last-use of
  srcA, copied per the compiler's own convention, per
  docs/isa/register-move-and-liveness.md section 2.4's standing guidance,
  and independently re-derived here where that guidance was silent).
- `falu2` register-register combination of two independently-computed
  values, PROVIDED `opflags=3` is used (a new requirement this experiment
  establishes; `opflags=1` silently corrupts the result).
- A `device_load` -> `device_store` direct round trip with fully
  independently variable `idx_off` (including the field's own encoding
  boundary), `elem_size` code, `base_slot` (including the 7-bit mirror), and
  index register -- matching EXP-0082/0083's own validated model exactly.
- A `device_load` -> `iadd2` -> `device_store` integer transform, with the
  SAME memory-addressing fields independently variable, and the integer
  immediate (`K`) independently variable, via one verbatim structural
  anchor.
- A real compiled loop (carried accumulator) + if/else->select control-flow
  program, reconstructed field-by-field via `assemble()` from our own
  compile (proving field-level understanding, not merely a byte copy), with
  the loop trip count and the arm-selection data independently variable,
  plus ONE structural field (`icmp_pred cond`) independently variable.

**CANNOT yet be reliably generated (open gaps, explicitly not closed by
this experiment):**
- A hand-constructed `device_load` feeding an ARBITRARY `falu2`/`falu2i`
  register choice (only the two proven bridges -- direct-store-forward, and
  one verbatim `iadd2` anchor -- are currently safe).
- `iadd2` register-mode (`srcA`/`srcB` both GPR) with independently chosen
  operand registers -- the scattered-bit `srcB` encoding and the
  register/immediate mode-flag byte were not confidently re-derived.
- `reg_move` reading a value computed by a DIFFERENT instruction family (the
  P4 blocker) -- currently only trustworthy for EXP-0087's own narrower
  uniform-sourced scope.
- Any independently-chosen destination register for `device_load` beyond
  the specific `(dst_lo,dst_ext9)` combinations this experiment happened to
  reuse verbatim from real compiles.

This satisfies the DRV-ISA-01 acceptance bar's core test -- whole, hand-
constructed, multi-family programs, independently oracle-checked, on real
hardware -- for the families listed as CAN-generate above, and precisely
scopes what remains for the families listed as CANNOT.

---

## 10. Clean-room provenance

```
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: our own carrier MSL (kernels/carrier_p{1,2,3,4}.metal,
  kernels/pilot_immadd.metal), our own hand-assembled instruction bytes
  (isa_helpers.py/programs.py, built entirely from tools/agx-isa's
  read-only isadb.assemble()/disassemble()/imm_encode/imm_decode), our own
  splice+run harness (harness/case_exec.py over tools/agxtest/agxtest.py,
  tools/shdump for carrier compilation).
Apple binary introspection: NONE.
Reproduction: see README.md's command sequence.
Evidence: raw/m4-20260827-run01/, raw/m4-20260827-run02/ (byte-identical
  01_results.jsonl, sha256 in analysis.json), diagnostics/redecisive_output.txt
  (permanent re-derivation of the 5 decisive pilot findings after the
  original informal-pilot scratch artifacts were correctly-but-
  unfortunately cleaned before this file was written -- see PROGRESS.md's
  "INCIDENT" entry for the full, honest account).
```
