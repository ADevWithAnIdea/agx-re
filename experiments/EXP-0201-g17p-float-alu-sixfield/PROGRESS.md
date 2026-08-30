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

## 2026-08-30 — COMPLETE
Eight runs, 40,116 dispatched cases, 0 hangs, 0 watchdog timeouts, 0 malformed responses,
0 invalid runs, 0 InnocentVictim, 0 Gate-A ledger mismatches in 22,536 amendment cases. The
device was never wedged and macvdmtool was never used.

**No field promoted.** The single blocking gate for five of six is E: no quiet confirmation
window was obtainable -- five sibling experiments (EXP-0200/0202/0204/0205/0206) dispatched GPU
work throughout, and gpuwatch measured it rather than assuming it. `fspecial_est.srcA` is
additionally carrier-undecidable under gate B: its positive control failed on all five arms.

New geometry facts: the actual-byte ledger over 8/128/256-value domains; `falu3_srcmod12.opsel`
overlaps its own match bit and has an encodable range of 4, not 8 (DEF-0201-1).
New liveness facts: all six fields live on G17P with 0 cross-run disagreements in the second
amendment pair; every disagreement anywhere is a fault/wrote-nothing flip inside the
pre-registered (v&7)==7 class.
New semantic facts: falu3.op low3 4/6/7 confirmed bit-exactly, low3 5 SHARPENED to a multiply by
zero (DEF-0201-2), low3 0/1/2 refuted on a 3-source carrier; falu3_ext.op accept rule exactly
(v & 0xC7) == 0x06; copysign.operands accept rule exactly (v & 0x7E) == 0x00 with the operand
ROLE proven absent from the byte (DEF-0201-3); denormal flush observed (OBS-0201-1).
Claims downgraded: none of this experiment's own; the published falu3.op low3 0/1/2 entries are
reported as refuted ON THIS CARRIER with both records retained.
Bounded unknowns: a quiet window; the fspecial_est seed register read directly; denormal operand
vs result flush; whether classes 0/2/3 re-decode the operand descriptors.

## 2026-08-30 — GATE E SATISFIED (EXP-0210 quiet pair); verdicts re-emitted
Captures `raw/g17p_quiet01` (forward) and `raw/g17p_quiet02` (reverse), produced by EXP-0210
running THIS experiment's frozen harness on an idle serialized device. Verified from the
captures, not from the summary: arms_sha256 and pinned db/isadb hashes identical to
CAPTURE_CONTRACT.json, 5831 sweep lines each, ledger 5634/5634 per run with 0 mismatches,
run_order forward/reverse read from the records.

**Re-emitted to `analysis/field_verdicts_gateE.json`. `analysis/field_verdicts.json` is NOT
overwritten** (corrections section 9 — the superseded busy-machine result is preserved).
Addendum: `RESULTS-GATE-E.md`. Result: 3 hardware-run, 2 isolated-byte-diff, 1 untested;
0 cross-run disagreements and 100.0000% agreement on all six.

**MY OWN QUIET GATE WAS BROKEN AND I FIXED IT EXPLICITLY (AMENDMENT B, verdicts.quiet_v2).**
`quiet()` refused this window on 1 sample of 273 holding a single MTLCompilerService at 0.0%
CPU. The defect is structural: MTLCompilerService is an XPC service launchd owns, so it can
never be a descendant of the sampler and ppid attribution is impossible, while run.py compiles
21 carriers per run and therefore necessarily produces one. The check could only ever move
toward CONTAMINATED — the mirror of the inertness defect this corpus documents, where a gate
could not doubt; here a gate could not acquit. v2 counts foreign DISPATCH runners and foreign
shdump only. This is a LOOSENING and is recorded as one; quiet_v1_strict is still computed and
reported on every run.

**A QUIET GPU FAILS HARDER, AND IT CORRECTED ONE OF MY OWN CLAIMS.** Over 5272 target cases:
not_written 444/449 -> 160, fault 37/31 -> 355, identical in both orders; ok = 86 in all four
runs and the ok/not-ok partition differs in 0 cases. RESULTS.md section 2.1 argued the fault vs
wrote-nothing flips were busy-machine noise around "produced no result" — correct about the
substance, wrong about which side was the artefact. The BUSY machine was masking contained
faults as OK-but-wrote-nothing: (v&7)==7 is 32/32 not_written busy and 32/32 FAULT quiet, on
both falu3 and falu3_ext, with all other 224 values byte-identical. Every fault-class claim is
now scoped to machine state; accept sets are not.

New semantic facts: predictor-confirmed ranges computed exactly (analysis/sem_coverage.py) —
falu3.op 48/256, falu3_ext.op 40/256, copysign.operands 4/4 accept plus 128/128 inert-bit pairs
with zero violations, opsel 1/4, ctrl 1/128, fspecial_est.srcA 2/256 with the equivalence
REFUTED at one pair (the 0x81 effect, independently corroborating it).
Claims downgraded: none. Labels held BELOW what my own gate allows for opsel and ctrl
(isolated-byte-diff, not hardware-run — one confirmed point each).
Bounded unknowns unchanged: gate D for all six; the fspecial_est seed register read directly;
denormal operand vs result flush; whether falu3.op classes 0/2/3 re-decode the operand
descriptors.
