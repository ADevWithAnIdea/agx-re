# PRE_REGISTRATION — EXP-0105 M4 encoding/registers (ENC-* cluster)

**Pinned repository revision (per SUBAGENT_BRIEF.md — record and compare
against THIS value, never live `HEAD`):** `0f1af7fa1d3e21a9996c3b49d7d91f6377427225`
(tree dirty with unrelated sibling-experiment untracked artifacts at pin
time — EXP-0101/0102/0103/0104/0106/0107/0108/0109/0110/0111 and others,
per the standing multi-agent orchestration model; expected and explicitly
not a contamination signal per SUBAGENT_BRIEF.md).

Target: **local Apple M4 / G16G only.** macOS 26.6.2 (build 25G82), Metal 4.
No A18 Pro (hands-off, standing directive). No M5 evidence used anywhere.

## 0. Origin and status of this document

Written **after** an honestly-disclosed pilot phase (PROGRESS.md Milestones
1-3), consistent with every prior experiment in this line (EXP-0086/0089/
0090/0099). The pilot: (a) surveyed every register-typed field in
`tools/agx-isa/db.json`; (b) attempted, and ABANDONED, a second
register-addressing method using `iminmax` after it produced two
unexplained, uninterpretable failure modes on real hardware (PROGRESS.md
Milestone 2 — a first-class negative finding, not hidden); (c) redesigned
the matrix around ONLY EXP-0090/EXP-0099's own extensively proven falu2/
falu2i construction and ran it, un-gated, once, to confirm every case
produces a clean `STATUS OK` and an interpretable result (PROGRESS.md
Milestone 3). No case's **hex bytes or oracle** were adjusted after seeing
a GPU result beyond this go/no-go triage — every hypothesis-bearing case's
prediction was written into `casematrix.py` before this document was
frozen and matches verbatim what is recorded there.

## 1. Task scope — the 16 ENC-* items (APPLE9_RE_IMPLEMENTATION_GAPS.md,
"P1 — Register files, immediates, and instruction encoding")

Per-item plan, stated explicitly as HW-TESTED (new evidence from this
experiment) / DESK-AUDIT (answered from existing PROVENANCE-linked
evidence, no new hardware run) / DEFERRED (left open, with the reason).

| item | plan | why |
|---|---|---|
| **ENC-01** GPR fields decoded for every initial-compiler instruction? | DESK-AUDIT (PARTIAL) | `docs/isa/encoding-tables.md` covers every family in the census; several (falu3 tail forms, `int_alu_ehi`, `isel*`) remain db.json-flagged "inferred"/"NOT HW-dispatch validated." This experiment's own HW test of falu2i's srcA_reg (previously untested) narrows one specific such gap. |
| **ENC-02** Every instruction addresses every legal register incl. r15+/r63+? | **HW-TESTED — TOP PRIORITY** | The experiment's central question. See §2-4. |
| **ENC-03** Even/odd register-pair restrictions for FP16/FP32/vec/I64? | DEFERRED | Not probed this round (time budget went to ENC-02). `docs/isa/README.md` documents 16-bit-half packing and the u64 carry-chain's implicit register sequencing, but no explicit alignment-restriction test exists. `UNKNOWN`. |
| **ENC-04** Uniform-register sources independently selectable per ALU family? | DESK-AUDIT (PARTIAL) | `falu2_uni`/`uniform_mov` `HW-VALIDATED` (EXP-0020/RT-1a-FIX, both float uniform-source encodings). Integer ALU's uniform form is still "byte-diff-inferred" per `docs/isa/README.md`. Not re-tested here. |
| **ENC-05** Immediate ranges/encodings/sign/NaN-literal rules per family? | DESK-AUDIT (PARTIAL) | `falu2i` minifloat `HW-VALIDATED` exact range (EXP-0006: `{0, ±1/32..30}`, out-of-range falls back to register form). `mov_imm`'s 8-bit range `HW-VALIDATED` (EXP-0031). `iadd2`'s integer immediate mode is entangled with a "scattered" register-mode encoding this experiment's own pilot could not safely characterize (PROGRESS.md Milestone 2) — flagged, not resolved. NaN/Inf float-literal handling: not found documented anywhere in this repository — a genuine, disclosed gap. |
| **ENC-06** Modifier interactions (abs/neg/sat/width/cache/src-file) validated? | **HW-TESTED (partial extension)** | EXP-M4-10 validated several float-ALU modifier bits; EXP-0086/0089/0090/0099 showed the "cache/last-use" bits are NOT simply inert. This experiment's CAND_BANK_FALU2 group directly extends this: `opflags` bits22/23, `mod_hi` bit44, and 4 of `ctrl`'s 7 bits, previously wholly untested, are now classified. See §5. |
| **ENC-07** Reserved/constant bits known well enough for independent assembly? | **HW-TESTED (partial extension)** | Same CAND_BANK_FALU2 data directly answers this for the specific fields tested: several are NOT safely-reserved (silent corruption), a small number are confirmed inert. General policy conclusion in RESULTS.md. |
| **ENC-08** Instruction length unambiguous from decoded fields, no catch-all? | DESK-AUDIT (PARTIAL) | RT-ISA-FIX census: ~87-91% corpus tokenization (EXP-0036 subcorpus 90.6%), named residue (`0x2b`/`0x3b`/`0x5b` register/shift-prep family). Not `0` leftover on every realistic kernel. No new HW work this round. |
| **ENC-09** Encode/decode round trips lossless for every initial instruction? | DESK-AUDIT + this experiment's own gate | `tools/agx-isa/roundtrip_test.py` exists repo-wide; this experiment's OWN `verify.py --selftest` round-trips all 16 of its own cases (`isa_helpers.assert_round_trip`), `PASS`. Repo-wide coverage remains uneven per-family (many "inferred" families untested). |
| **ENC-10** Independently-assembled reps of every family execute correctly in ONE generated shader? | DESK-AUDIT + **new negative data point** | EXP-0090: 3/4 hand-built whole programs matched oracle; 2 named blockers (load-to-ALU, GPR-sourced move) remain `OPEN` per EXP-0099. This experiment's OWN abandoned `iminmax` construction (PROGRESS.md Milestone 2) is a THIRD, independently-discovered family this session could not get to behave correctly in a hand-built program — added to the list, not resolved. |
| **ENC-11** Program-end/stop encoding + alignment known for all stages? | DESK-AUDIT (mostly closed, compute; PARTIAL other stages) | `stop` `HW-VALIDATED` (EXP-0003/EXP-0010 E4): 4B, reserved body inert, true terminator is out-of-band metadata length. Cross-stage (VS/FS/mesh/RT) presence is corpus-observed, not independently splice-tested per stage. |
| **ENC-12** Branch displacement origin/unit/width/sign/range validated? | DESK-AUDIT (PARTIAL) | `jump` `HW-VALIDATED` (EXP-0010 E6: real backward offset, zero-offset hang, off-boundary fault). `jump_cond`/`call` offset model confirmed by dispatch + byte-diff (EXP-0035/RT-ISA-FIX) but not exhaustively range-swept for the LEGAL max/min displacement. |
| **ENC-13** Call/return/frame/reconvergence sufficient for nested control flow? | DESK-AUDIT (substantially closed for tested depth) | EXP-0035/EXP-0038 `HW-VALIDATED`: 3-level nested calls, non-leaf frame prologue, link save/restore, correct dispatch results. Deeper/broader shapes (recursion, deep reconvergence nesting) `UNKNOWN`. |
| **ENC-14** Max usable GPR count exactly 96 for every stage? | DESK-AUDIT (doubly HW-VALIDATED, compute; PARTIAL other stages) | `HW-VALIDATED` independently TWICE: EXP-0006/EXP-0020 (96 addressable GPRs, r96+ faults as memory-index / reads 0 as ALU source, no mod-64 aliasing) and EXP-0092 GLIO-A02 (`dstsweep`, coupled `get_sr`+`device_store` round trip, 0-95 exact, 96-127 deterministic-fault-mostly with one flaky register at 112). Per-stage (VS/FS/mesh/RT) re-verification not independently performed. |
| **ENC-15** Register-pressure-to-occupancy mapping fully determined per stage? | DEFERRED | `docs/isa/README.md` explicitly flags this `UNKNOWN`: only 2 data points (f0=8 clear, f0=14 set) exist for the occupancy-tier config bit; the claimed 11-vs-12 GPR threshold is an unverified interpolation. Not probed this round. |
| **ENC-16** Scratch spill addressing + frame-size metadata fully known? | DEFERRED (sibling workstream) | `docs/isa/README.md` explicitly flags the scratch-base location as "a follow-up." A concurrently-running sibling experiment (`EXP-0107-m4-scratch-helper-abi`, present untracked in the working tree at pin time) appears to be the assigned owner of this exact question — not duplicated here. |

**Coverage summary:** 1 item (ENC-02) is this experiment's primary,
decisively HW-tested contribution. 2 items (ENC-06, ENC-07) receive
genuine new HW data as a secondary product of the SAME case matrix. 1 item
(ENC-10) receives an honest new negative data point. The remaining 12
items are answered by DESK AUDIT of already-`PROVENANCE`-linked evidence
(cited above, not re-derived) or explicitly left `DEFERRED`/`UNKNOWN` —
stated, not silently assumed.

## 2. Hypothesis under test (H1 — the ENC-02 core question)

**H1 — REGISTER 64-95 ADDRESSING, falu2i's `srcA_reg` field (bits 25-31,
untested by EXP-0099).** Does `falu2i`'s `srcA_reg` field genuinely address
registers 64-95 as a plain 7-bit index (current `db.json` model), or does
it alias to its low 6 bits (EXP-0099's finding for the SIBLING
register-register form, `falu2`)?

- **Falsifier design (identical methodology to EXP-0099's own H1, applied
  to a field EXP-0099 explicitly did not test):** seed a KNOWN value
  `V_LOW=30.0` into register r3 via an independently `HW-VALIDATED`
  ALU-only path (`falu2i(srcA=UNWRITTEN, K=30.0)`, EXP-0090/EXP-0099).
  Register 67 is NEVER written by any case in this matrix. Read back via
  `falu2i(dst, srcA_reg=X, K=0.0)` for `X ∈ {3, 67}` (67's low 6 bits == 3,
  its weight-64 bit set).
  - **CONFIRMS a genuine wide (≥7-bit) field:** `X=67` reads **0.0**
    (register 67, genuinely unwritten — exactly EXP-0099's own decisive
    signature).
  - **CONFIRMS aliasing (mod-64 or low-6-bit) collapse, matching EXP-0099's
    falu2 finding extended to falu2i:** `X=67` reads **30.0** (r3's seeded
    value).
  - **Refuter:** any THIRD value (neither 0.0 nor 30.0) means neither
    hypothesis is confirmed and the field's behavior is `UNKNOWN`.

**H2 — CANDIDATE "SEPARATE BANK-SELECT BIT" (CAND_BANK_FALU2 group).**
Inspired by `get_sr`'s OWN, structurally analogous, `HW-VALIDATED`
mechanism (a register-extension field, `dst_hi`, living in a SEPARATE byte
from the primary `dst` nibble — EXP-0092 GLIO-A02): does ANY field OTHER
than `falu2`'s own reg-field top bit (already `HW-REFUTED` as an addressing
or retention mechanism, EXP-0099 H1/H2) act as such a bank selector? Tested
fields: `opflags` bits22/23 (the 2 of 5 `opflags` bits EXP-0099 did not
already characterize), `mod_hi` bit44 (the 1 of 4 `mod_hi` bits EXP-0099's
H4 route sweep did not touch), and a 4-of-7-bit walk of `ctrl` (wholly
untested before this experiment).

- **Falsifier design:** for each candidate bit, two cases — same
  construction at `reg=3` (low, calibrated against a baseline that is
  ALREADY `HW-VALIDATED` inert, EXP-0099) and at `reg=67` (high field
  value; r67 unwritten).
  - **CONFIRMS the candidate is a genuine bank selector:** the `reg=67`
    case reads something OTHER than 0.0 (and specifically NOT 30.0, which
    would instead indicate the candidate broke the aliasing behavior a
    different way) while the `reg=3` case is UNCHANGED from baseline
    (30.0) — i.e. the bit's effect is SPECIFIC to unlocking the high
    register, not a general corruption.
  - **REFUTES the candidate as inert (matching baseline both ways):** both
    `reg=3` and `reg=67` cases read identically to their respective
    baselines (30.0 and 0.0).
  - **A THIRD outcome (silent corruption, independent of register value):**
    the `reg=3` case ALSO changes (typically to 0.0) — this means the
    candidate bit is LOAD-BEARING (matches the "silent zero" pattern
    documented throughout `docs/isa/register-move-and-liveness.md`
    section 2.5) but is NOT specifically a bank-select mechanism; it is
    reported as such, not conflated with either of the above.

## 3. Independent / controlled variables

- **Independent:** `srcA_reg` field value (`3` vs `67`, H1); the specific
  candidate bit under test and its value (H2); register selector for the
  CAND_BANK group (`3` vs `67`, crossed against each candidate).
- **Controlled/held fixed within each comparison:** carrier kernel and its
  measured `_agc.main` length (170 bytes, `--no-fast-math`, re-derived
  fresh by `baseline.py` — BYTE-IDENTICAL kernel text to EXP-0099's own
  proven-splicable carrier), buffer slot assignment (`SLOT_OUT=0`, no
  `buffer(1)`/mem use in this matrix — bound with a small zero-filled
  buffer purely as insurance against Metal argument-validation faulting on
  an unbound declared buffer, never referenced by any spliced program),
  the seed value `V_LOW=30.0` (the fixed point of
  `isadb.imm_encode/imm_decode(42.5)`, EXACTLY EXP-0099's own sentinel),
  the read-back immediate `K=0.0` (also an exact fixed point), dispatch
  shape (`grid=1, tg=1`), `--no-fast-math`, per-case timeout (60s).

## 4. Expected observation and refuters — summary table

| group | independent var | if genuine wide field | if aliasing (EXP-0099-style) | refuter (neither) |
|---|---|---|---|---|
| `REG64_FALU2I_ALIAS` | srcA_reg ∈ {3,67} | 67 → 0.0 | 67 → 30.0 | any 3rd value |
| `CAND_BANK_FALU2` @ reg=3 | candidate bit ∈ {0,1} | (no claim) | still 30.0 (inert) | 0.0 or other (load-bearing, NOT a bank selector) |
| `CAND_BANK_FALU2` @ reg=67 | candidate bit ∈ {0,1} | changes from 0.0 to a genuine unlock | still 0.0 (inert, matches EXP-0099) | n/a — 0.0 is itself ambiguous between "correctly reads unwritten r67" and "still corrupted"; disambiguated by whether the SAME bit is inert or corrupting at reg=3 |

## 5. Known confounders

- **`iminmax` was abandoned as a second, structurally different family**
  after producing two unexplained failure modes (PROGRESS.md Milestone 2).
  This narrows H1/H2's independent-method coverage to falu2/falu2i's own
  sibling instructions (a real, but weaker, form of independence than a
  structurally different field encoding would have given) — disclosed,
  not hidden.
- **Minifloat immediate rounding** (`isadb.imm_encode`/`imm_decode`,
  EXP-0006): `V_LOW`/`K` are computed via `H.imm_value()` (a fixed point
  of that codec), never a raw literal, so the oracle can never disagree
  with what the assembler actually encodes.
- **`ctrl`'s untested bits (4,5,6)**: only a 4-of-7-bit walk (bits 0-3) is
  performed, for time-budget reasons (disclosed, not silently narrowed to
  "the whole field is inert").
- **CAND_BANK's `reg=67` cases cannot, by themselves, distinguish "reads
  correctly from a genuinely unwritten r67" from "the candidate bit
  corrupts the read to 0.0 regardless of register"** — resolved ONLY by
  cross-referencing the SAME candidate bit's `reg=3` result (§2, H2 third
  outcome).
- **Compiler-emitted vs hand-assembled bytes**: every instruction here is
  assembled via `tools/agx-isa`'s own `isadb.assemble()`, never copied
  from a captured template, and every case round-trips through
  `isadb.disassemble`+`assemble` before being accepted into the matrix
  (`isa_helpers.assert_round_trip`, called by `casematrix._case`).

## 6. Environment / tool revisions

- macOS 26.6.2 (build 25G82), Apple M4 (G16G), Metal 4.
- `tools/agx-isa/isadb.py`, `tools/agxtest/agxtest.py`, `tools/shdump/*`:
  read-only, used exactly as documented in their own READMEs; not
  modified.
- Python 3.14 (`/opt/homebrew/opt/python@3.14/bin/python3.14`), invoked as
  `python3 -B` throughout (no `.pyc` cache writes into the tree).

## 7. Raw-record schema (frozen)

Gated (`01_results.jsonl`, byte-compared across runs): `i, name, group,
oracle, expect_match, notes, dispatch, status, pipeline_source, out_hex,
observed, match`. Non-gated (`01_timing.jsonl`, NOT byte-compared): `i,
duration_ms, argv, stdout, stderr`. See `run.py`'s `SMOKE_KEYS`/
`GATED_KEYS`/`NONGATED_KEYS` for the single authoritative definition
imported by both the runner and `verify.py --selftest`. Every oracle word
carries an explicit `kind` (`"f32"` here throughout — this matrix never
uses `"u32"`, unlike the abandoned `iminmax`-based design's need for
bit-exact integer comparison) so a word is decoded exactly one way, never
reinterpreted implicitly.

## 8. Timeouts

Per-case hard timeout 60s (subprocess), `agxtest.py --run-timeout 30`
internal GPU timeout. Environment/build commands: 5-120s. Full run: no
overall wall-clock cap beyond the sum of 16 cases' individual timeouts
(~16 minutes worst case).
