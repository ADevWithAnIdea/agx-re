# EXP-0201 PROGRESS

## 2026-08-30 — pre-registration frozen
- Read SUBAGENT_BRIEF, NEO-TARGET-BRIEF, FIELD-SWEEP-PROTOCOL (3,5a,5b,7,9), CODEX, evidence-classification.
- Pinned db.json / isadb.py / agxparse.py / persistrun.py / shdump.m into pinned/ (sha256 in CAPTURE_CONTRACT.json).
- PRE_REGISTRATION.md written BEFORE any build. Amendments A1 (copysign oracle, not range) and A2 (three distinct prior failure modes) folded in pre-build on coordinator intel.
- analysis/oracle_check.py PASSES on the host: every carrier library is pairwise-distinct (9-14 members), copysign(a,b) != -a, roles do not collide, rsqrt(a) vs rsqrt(b) well separated.
- analysis/verdicts.py selftest PASSES: gate refuses an aliased sweep, a constant oracle and an indistinguishable field, and PROMOTES a width-1 field with moved=1/disagree=0.

## DECLARED HAZARD (courtesy, protocol section 7)
- falu3.op / falu3_ext.op values with (v & 7) == 7 are a REPRODUCIBLE CONTAINED FAULT per EXP-0160 (32 of 256). They are dispatched anyway: there is no hang budget (protocol 3c).
- falu3_srcmod12.opsel values with bit 17 clear leave the modelled mnemonic and land on falu_srcmod12b, where opsel==4 is documented to corrupt an unrelated register (EXP-0119). Dispatched and recorded as such.

## 2026-08-30 — census run (exploratory, NOT gated evidence), two pre-run amendments
- First census: 15 carriers, 53 arms, 4407 cases, **0 aliasing/span errors** -- the `opsel`
  arms pass the pre-dispatch non-aliasing check, because values are spliced as raw bits and
  no assembler can silently re-OR the pinned bit 17.
- **DEFECT FOUND IN MY OWN CENSUS, before any gated run.** The byte-granularity signature scan
  reported an `09 80 0a 29 91 35 05 80` at offset 79 of `f3_two`, which is THREE BYTES INSIDE a
  real 6-byte `falu2_uni` at offset 76 -- and the pinned `decode_one` confirms it as `falu3`.
  Splicing there would corrupt two real instructions and any movement would be about neither
  field. AMENDMENT: an occurrence is admitted as an arm only if it is also a TRUE BOUNDARY of a
  tokenizer walk from offset 0 (`locate201.walk_offsets`). Rejected occurrences are kept in
  `work/census.json` with the reason.
- AMENDMENT: added a third `falu3_ext` carrier (`k_f3e_two`). The pre-registration (A2) requires
  >= 3 independent arms per `op` field because both were withheld on ONE arm each; the first
  census yielded only 2 for `falu3_ext`. Made before any gated run; contract re-frozen.
- OBSERVED, recorded now so it is not mistaken for a later rationalisation: our own
  `precise::divide(1,x)` lowers to `fspecial_est` subop **0x0d** on G17P, and both
  `precise::rsqrt` and `precise::sqrt` lower to subop **0x0f**. `db.json`'s enum reads
  9=rcp / 11=rsqrt / 13=sqrt / 15=rsqrt(G17P precise). This is a compiler-lowering observation
  about our own source, not a hardware claim.
- `k_cs_alu` (copysign of ALU-sourced operands) emits **no** 4-byte `copysign` at all; it is
  carried as a null carrier and reported, not silently dropped.

## 2026-08-30 — gate amendment made DURING run01, BEFORE any verdict was computed
`analysis/verdicts.py` originally dropped hard outcomes (`fault`, `hang`,
`measurement_failure`, `invalid_run`, `nondeterministic`) from the cross-run comparison
entirely. That is a LENIENCY, not a strictness: a value that faults in run01 and runs clean
in run02 would fall out of `common` instead of counting as the disagreement it is, and
`falu3.op` has 32 values that are documented reproducible faults. PRE_REGISTRATION section 7
says agreement is measured "over the values common to both runs", and a faulting value IS a
common value carrying the observation "it faulted".

AMENDED: hard outcomes now enter the cross-run comparison as their own class
(`hard:<outcome>`), while still being EXCLUDED from `moved` (control C5 -- a GPU fault is not
movement). Made while run01 was still executing and before `verdicts.py` had been run against
any capture. Contract re-frozen; the amended file is hashed in CAPTURE_CONTRACT.json.

Note for auditors: `CAPTURE_CONTRACT.json`'s `repo.revision` is rewritten by each re-freeze and
now reads `ff747ca3`; the revision at the ORIGINAL pre-registration freeze, before any build or
device run, was **`f59821fe`**. It moved because sibling experiments land continuously. Per
`SUBAGENT_BRIEF.md`, captures are gated on the AUTHORED BLOB HASHES, never on live `HEAD`.

## 2026-08-30 — AMENDMENT A, frozen before its first dispatch
`RE_EXPERIMENT_PROCESS_CORRECTIONS.md` landed in the repository while runs 01-04 were
executing. It is normative and overrides this experiment's original gates where they conflict.
`PRE_REGISTRATION-A.md` is the amendment, frozen (hashed into CAPTURE_CONTRACT.json) BEFORE the
first dispatch of `g17p_20260830_a_run01`.

Runs 01-04 are RETAINED UNCHANGED and reclassified on the six axes; nothing is discarded and
nothing that already meets a gate is re-run (section 9/10 of the corrections).

What the amendment adds:
- **Gate A** caller -> ACTUAL-dispatched-byte ledger per case: requested value, requested bytes,
  bytes re-extracted from the blob about to be dispatched, the value decoded back OUT of those
  bytes by an independent expression, program sha256, main/instruction offsets, db + harness
  hashes. The gate refuses any arm with a single mismatch or with distinct actual encodings
  fewer than distinct requested values.
- **Gate C** adversarial float inputs on five new arms: -0.0, +0.0, +inf, -inf, NaN, the
  smallest denormal, and the 2^24 rounding boundary. `oracle_check.py` now compares library
  members by BIT PATTERN (value equality cannot see +0.0 vs -0.0 and reports NaN != NaN) and
  **it caught a real collision in the first draft of the adversarial copysign set** -- with all
  signs opposite, copysign(a,b) equals -a and the library cannot tell a sign COPY from a
  NEGATION. The set was changed before any device time.
- **Gate E** `--order forward|reverse|shuffle`; the confirmation pair runs forward then
  reversed, and promotion requires a STRICTLY quiet machine (zero foreign GPU-runner samples).
- **Six independent verdict axes** (geometry / liveness / semantics / recipe / target /
  reproducibility). Liveness never rounds up into semantics: the gate now refuses
  `sem_checked == 0`, and the selftest asserts that it does.

Re-derived runs 01+02 under the amended gate: all six fields NOT PROMOTED, blocked on Gate A
(no actual-byte ledger) and Gate E (both runs measured BUSY). That is the correct answer for a
capture taken before the gate existed.

DECLARED HAZARD for the amendment runs: unchanged from above, plus the adversarial arms feed
NaN/inf into a three-source float ALU whose op field is being swept, which has not been done on
this device before.
