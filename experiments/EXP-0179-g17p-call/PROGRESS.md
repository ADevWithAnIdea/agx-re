# EXP-0179 — PROGRESS (append-only; newest last)

Rule: one timestamped entry per milestone. On resume, re-orient from THIS file,
`CAPTURE_CONTRACT.json` and what is actually in `raw/` — never from memory.

## 2026-08-30 — M0 START: analysis + carrier design (no device contact yet)
- Read `CLAUDE.md`, `CODEX.md`, `SUBAGENT_BRIEF.md`, `FIELD-SWEEP-PROTOCOL.md` (§3 five
  rules, §7 concurrency + confirmation exception).
- Read the gap: `docs/P0-P1-CLOSURE.md` P0.8, `EXP-0177/analysis/p08_gaps.md` G2.
- Located the PRIOR ART that EXP-0156 did not have: **call carriers already exist in this
  repo.** `EXP-0035/kernels/{direct_call,chain,abi,fptr_table,fptr2,dylib_*}.metal` and
  `EXP-0038/kernels/frame.metal` all compile `__attribute__((noinline))` helpers into real
  out-of-line calls, and EXP-0035 HW-validated dispatch through them on G17P.
  **So milestone 1 of the dispatch ("get the compiler to emit a call at all") is very
  likely already solved; the census still has to be run and reported on the CURRENT G17P
  toolchain.**
- Picked the harness lineage: `EXP-0174-g17p-n3mov/harness/{isa_helpers,sweeprun,run}.py`
  (SYNTH carrier = the whole `_agc.main` replaced by a program we assemble; poisoned
  read-back; PRE/POST sentinels; tail poison; blind/pad-masked slot bookkeeping).
- Repo revision at design time: `12e059e5aab38258c55ce490a01e146e6fae30d9`, clean.
- Pinned `work/frozen/db.json` sha256 `a77f8cfa163fcf720c0c1093e4ddc5815ceb43c218bb64a87c86d3dcf975dc22`
  (172 instructions / 1036 fields) and `isadb.py` `9cda47a1…`. NOTE this is NOT the same
  db.json EXP-0174 pinned (1062 fields) — EXP-0175's defect corrections landed in between.
  Fail-closed resolution, no path search.
- NO DEVICE CONTACT YET. Waiting for the orchestrator's go (EXP-0169 hang-prone sweep +
  EXP-0178 queued ahead of us).

## 2026-08-30 — M1 COMPLETE: design + pre-registration frozen. Still NO device contact.
Written and self-checked locally (repo host only; nothing has touched the neo):
- `PRE_REGISTRATION.md` — H1..H7, two carriers, the observable, 14 arms, 6 falsifiers, the
  confounder table (all five §3/§7 rules answered), the promotion gate, the safety plan, and
  §0: the DECLARED CLEAN-ROOM BOUNDARY (we do not characterise Apple's inlining heuristic;
  we author our own MSL until the instruction appears).
- `CAPTURE_CONTRACT.json` — 24 authored-blob sha256s, case-matrix sha256
  `dd9726be0effc1cd85738baa2399dbd1f2452c36646843e5a0016161d85c7504`, **3189 cases/run**,
  pinned toolchain, timeouts, raw schema, the five-item closed calibration list.
- `README.md`, `manifest.json`.
- `kernels/carrier_call.metal` (SYNTH carrier) + 9 census MSL files, 24 constructs.
- `harness/{isa_helpers,cases,sweeprun,run,calib,census}.py`, `harness/sync.sh`,
  `harness/fndump.m` (EXP-0035's, verbatim).
- `analysis/{analyze,verdicts,census_report,freeze_contract}.py`.

**Local verification, no GPU:** `assert_geometry()` passes 21 generated call encodings
(offset -552..+65536 x three b3/b5/b6/tail triples) that all re-decode to the fields they
were built from; ALL 3189 cases construct a valid program; max program 478 B; the target
identity `CALLEE_AT == CALL_AT + 4 + offset` holds for every layout including the depth-2
inner call; whole-program round-trip is True (recorded, cited nowhere).

**KEY PRIOR-ART FINDING that changes the shape of the work.** EXP-0156 reported `call` as
NOT ATTEMPTED because it had no carrier. But `EXP-0035/kernels/*.metal` and
`EXP-0038/kernels/frame.metal` ALREADY compile `__attribute__((noinline))` helpers into real
out-of-line calls, and EXP-0035 HW-validated dispatch through them **on G17P**. So milestone 1
("get the compiler to emit a call") is very likely a re-confirmation, not the hard part. The
hard parts that remain are (a) the census on the CURRENT toolchain, (b) GENERATING a call
rather than splicing one, and (c) the four `call` bytes + `ret.scoreboard`.

**A second extrapolation worth naming:** every call in this repository's corpus is BACKWARD,
because in every compiled program the callee precedes the caller. This experiment's generated
calls are all FORWARD. Whether a positive displacement works at all has never been tested.

NEXT: message the orchestrator and WAIT for the go (EXP-0169 hang-prone sweep running,
EXP-0178 queued). Then, on the neo, in order: push+build, arm Z census (compile-only, no GPU),
calibration, run01, run02, mapping passes if a contiguous hazard appears.

## 2026-08-30 — M1a: the census detector VALIDATED OFFLINE against committed own-shader bytes
Still no device contact. `harness/census.py` detects a `call` two independent ways; both were
just checked against **committed OWN-SHADER evidence already in this repository** —
`EXP-0035/raw/direct_call.txt`, which holds the `_agc.main` hex of our own `call_noinline`
kernel and of its paired inlined baseline, compiled from our own MSL.

- **Positive (74 B main, `call_noinline`):** the position-independent raw `match`-byte scan
  finds exactly one call, at region offset **36**, bytes `0f05541a8f005698ffffffffff00`
  (offset field = 0x98ffffffffff = **−104** signed 48-bit, matching EXP-0035's `k_add`).
- **Paired negative (58 B main, `call_inlined`, identical math):** **zero** calls. So the
  detector fires on a real call and not on its inlined twin.
- **The tokenizer agrees with the raw scan** on the pinned `db.json`, 0 leftover both times:
  positive `{get_sr, device_load x2, frame_marker, call, pop_reconverge, device_store, stop}`
  vs negative `{get_sr, device_load x2, falu3, device_store, stop}`.

Two things fall out of that histogram and they matter for arm `M`:
1. the compiled bracket really is **`frame_marker` immediately before, `pop_reconverge`
   immediately after** — and there is NO `if_push` around a top-level call, which is exactly
   why carrier `C2 nested` (one `if_push` deep) is a genuinely different carrier and not a
   cosmetic variant;
2. the caller of a LEAF helper carries **no `frame_prologue`** — the non-leaf frame machinery
   belongs to the callee, as EXP-0038 said.

This de-risks arm Z before it ever touches the device: whatever the census reports, its
primary detector is known to be sensitive AND specific on our own committed bytes.

## 2026-08-30 — M2 COMPLETE: the CENSUS (arm Z, compile-only, no GPU dispatch)
`raw/prefreeze/census_20260830a` (24 frozen constructs) + `raw/prefreeze/census_20260830b_ext`
(3 EXTENSION constructs, added after the first pass returned no render-stage call; they are
NOT part of the 24 frozen in `CAPTURE_CONTRACT.json` and are labelled as an extension).
→ `analysis/call_census.json`. **27 constructs: 15 DIRECT_CALL, 2 INDIRECT_CALL, 9 NO_CALL,
1 REJECTED.** Both detectors (raw `match`-byte scan and the pinned tokenizer) agree on every
compiled construct.

**H1 CONFIRMED. The answer to "can this ISA make a non-inlined call" is YES, and the compiler
emits one from our own MSL on the current G17P toolchain.** `__attribute__((noinline))` in
both spellings, a void helper, a `float4` return, a struct return, twelve arguments, leaf,
non-leaf, three-deep and spilling frames all produce the 14-byte `0f 05 54 1a 8f 00 56 <off> 00`.

Things that are NEW here, not re-confirmations:
- **C10 (1592 B body) and C11 (1936 B, twelve call sites), both with NO attribute, INLINED.**
  Nothing we tried forced an out-of-line call without an explicit attribute. Reported as a
  per-construct outcome only — we do not model the heuristic.
- **C14 MUTUAL recursion COMPILES** (3 calls, 2 non-leaf frames, 3 rets in `__text`) and so
  does **C13 non-tail recursion**. EXP-0035 only tried tail self-recursion.
- **C22 taking the ADDRESS of a plain local function COMPILES and lowers to `call_indirect`.**
  I pre-registered the expectation that it would be rejected; it was not.
- **C19 a `[[visible]]` function called DIRECTLY is REJECTED at pipeline creation** —
  `unresolved visible function reference: vadd / Reason: visible function not loaded`. It is
  not an ordinary local call; it needs the linked-functions path. (`api-accept-reject`.)
- **C21 a CONSTANT visible_function_table index produces NO call at all** — devirtualized,
  matching EXP-0035's constant-program observation.
- **THE FRAGMENT STAGE PRODUCED NO CALL IN EITHER ATTEMPT** (C23 small helper, C25 a 48-round
  dependent chain): zero `call` bytes anywhere in the fragment stage's whole `__text`. The
  VERTEX stage DID, once the helper was large enough (C26). This is directly on P0.8's
  VS/FS/CS row and is recorded as a bounded negative: **2 of 2 fragment constructs tried, no
  call**; the caveat is that the render-stage extraction may not expose every region, so it
  is `PARTIAL`, not "fragment shaders cannot call".

NEXT: calibration (GPU, ~10 dispatches) then run01/run02 for arms G,T,M,B3,B5,B6,TL,R,L
unlocked per the orchestrator's staged ruling; STOP before O/F/N and request the exclusive
window.

## 2026-08-30 — M3/M4 COMPLETE: the generated call WORKS; four fields promoted; the tail is pending
GPU work, all on G17P. Runs: `raw/prefreeze/calib_20260830a` (retained, ordering defect),
`calib_20260830b` (the frozen calibration), `calib_20260830c_amend` (the carrier amendment
probe), `raw/g17p_20260830_run01` (retained; its C2 half is the DEAD carrier measurement),
`raw/g17p_20260830_run03` (forward) + `run04` (reverse) = the gated pair. **0 hangs anywhere,
0 invalid runs, 100.0000% cross-run agreement on every field.**

**HEADLINE: 192 distinct GENERATED calls, 384 observations across two gated runs, 0 failures.**
Every byte of the call, the callee and the ret computed from the pinned descriptor geometry;
nothing copied from a compiled shader.

- `target = call_addr + 4 + offset` is EXACT on G17P **for FORWARD displacements**, at 2-byte
  granularity across a +-8 window (the landing ladder resolved every rung the host predicted)
  plus 48 more displacements. A call to a **bare `ret`** returns correctly.
- **The `0f 06` pop_reconverge after a call is REQUIRED (fault without it); the `43 00 00 01`
  frame marker is OPTIONAL.** Both carriers, both runs, unanimous.
- `call.b3`: live field is **bits 5:2**; bits 1:0 and 7:6 INERT (0 violations in 1024 cases).
  Codes taking the call: {6,8,9,10,11,12,13,15}; the rest FALL THROUGH cleanly, never fault.
- `call.b5`: **legal iff `(b5 & 0x06) == 0`** -- 64 of 256. bit1 faults, bit2 suppresses the
  branch, bits 0/3/4/5/6/7 inert.
- `call.b6`, `call.tail`: **INERT** over 0..255 -- ONE distinct full observation per carrier
  across 256 values x 2 runs.
- `ret.scoreboard`: inert here, and **DECLINED anyway**, as pre-registered -- neither carrier
  differs in the ORDERING dimension the field controls, so zero movement means the carrier
  cannot ask the question. Arm O is the construction that could settle it.
- `ret.linkmode` control: 0x02 and 0x12 return; 0x04/0x05 do not. EXP-0156's label untouched.

**AMENDMENT-01, recorded not absorbed.** The frozen `C2 nested` carrier was MEASURED DEAD in
run01 (1395 cases: PRE sentinel written, everything after it still 0xDEADBEEF). Cause isolated
in `calib_20260830c_amend`: an unconditional `if_push` with `scope_kind == 0x01` masks off the
only lane of a one-thread dispatch, in BOTH banks; `scope_kind == 0x1a` does not. C2 became
`if_push(0x56, 0x1a)`. run01 retained and never reused; run02 burned; the pair re-run as
run03/run04. Also recorded: my own calibration ordering defect (calib_a probed extmode with
the bracket that faults), fixed in calib_b, calib_a retained.

Deliverables written: `analysis/call_census.json`, `analysis/gate.json`,
`analysis/field_verdicts.json`, `RESULTS.md`, `PRE_REGISTRATION.md` section 13,
`CAPTURE_CONTRACT.json` `amendment_01` + `defect_01_self_inflicted`.

NEXT (needs the orchestrator's exclusive window -- DECLARED HANG CANDIDATES): arm **O** (the
ret.scoreboard ordering grid, 384 cases), arm **F** (F3 corrupt the 0x8f signature byte, F4
callee with no ret, F6 unbalanced mask stack), arm **N** (depth-2 generated call with NO
link_save_restore -- hardware stack vs single link register). Then arm **S**, the splice
second method, which is NOT hang-prone and can run unlocked.

## 2026-08-30 — M5: ARM S (second method) run unlocked — and it CORRECTED one of my results
`raw/g17p_20260830_splice01` (forward) + `splice02` (reverse), 1024 cases each, dense 0..255
on b3/b5/b6/tail, mutated in the REAL compiler-emitted call inside our own compiled
`c_frame.metal` (`k_chain`, one call site at `_agc.main + 36`, BACKWARD displacement, NON-LEAF
callee). Host oracle `k_chain(3,5) = 23.0f` exactly, over a 0xDEADBEEF-poisoned output.

- `call.b3`: **identical 16-code table** to the generated carriers, 256/256 cross-run.
- `call.b5`: `(b5 & 0x06) == 0` holds exactly, 256/256 cross-run.
- `call.tail`: all 256 legal here too — a don't-care on all three carriers.
- **`call.b6`: CONTRADICTS the generated arms.** Inert across 0..255 on both generated
  carriers; on the compiled call **bit 1 (0x02) MUST BE SET** — 128 legal, 126 wrong, 2
  NONDETERMINISTIC across runs (0.0 vs 3.0), 254/256 agreement. The generated callee is a
  LEAF entered and left immediately and never exercises what b6 bit 1 controls: the same
  carrier-blindness as `ret.scoreboard`, but caught by a second method instead of by argument.
  Promotion NARROWED: `hardware-run` for the rule "bit 1 must be set", with the generated
  carriers' inertness reported as blindness, not as a don't-care finding.

`analysis/splice_verdicts.json` written; `analysis/field_verdicts.json` updated in place with
`second_method_arm_S` per field and the corrected b6 semantics; `RESULTS.md` §3 and new §8.

STILL PENDING THE EXCLUSIVE WINDOW: arms O, F (F3/F4/F6), N. ~400 cases, seconds of GPU time.

## 2026-08-30 — STOPPED at the hang-prone boundary, as instructed
Arms O, F(F3/F4/F6) and N are NOT dispatched. The orchestrator holds the exclusive window and
has been messaged. Everything else is complete, pulled back, and analysed in this directory.
Nothing is committed (the orchestrator owns commits); `docs/`, `PROVENANCE.md`,
`tools/agx-isa/db.json` and `validation.json` were NOT touched.

## 2026-08-30 — checked against the newly added FIELD-SWEEP-PROTOCOL rule 3(d)
Rule 3(d) (the shared `persistrun.py` reader-thread bug: the FIRST watchdog timeout can
silently manufacture every later "hang") landed while this experiment was running. **The
precondition never occurred here**, and that is measured, not assumed: across all 10,484
recorded dispatch results in every capture — run01/03/04, splice01/02, both calibrations, all
baselines — the status histogram is `OK` 9273 / `CMDBUF_ERROR` 1211, with **0 HANG, 0
invalid_victim, 0 malformed/unpack errors, 0 carrier_hangs, no stopped arms**. No result here
can be a 3(d) artefact. Written up as `RESULTS.md` §7a. The 3(c) mapping-pass machinery was
built and pre-registered but never had to fire; it stays in place for the pending O/F/N arms.
