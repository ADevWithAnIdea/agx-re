# Apple9 RE experiment process corrections

**Status:** normative for new ISA/capability experiments and for any future evidence
promotion. This document supplements `CODEX.md`, `CLAUDE.md`,
`docs/evidence-classification.md`, and `experiments/FIELD-SWEEP-PROTOCOL.md`. Where a
single field label or a mechanical promotion rule conflicts with this document, this
document wins.

**Scope:** discovery and documentation only. This does not authorize driver code, and it
does not retroactively relabel the ISA database. Existing raw observations remain evidence;
they are to be reclassified by the gates below, not discarded wholesale.

## 1. Keep both goals explicit

There are two separate deliverables:

1. A compiler-safe specification: the implementation team can choose every required
   operand and generate a working Apple9 program without copying a captured token.
2. A hardware-capability map: every userspace-visible encoding bit and every finite
   hardware resource is investigated, including capabilities that Mesa does not currently
   need.

The second goal is not optional. Do not stop when one canonical compiler recipe works.
Equally, do not assume every varying or apparently spare bit is an independent feature.
Encoding bits may be opcode/framing constants, aliases, reserved values, future-family
space, length/alignment bits, contextual selectors, or fields whose effects are invisible
to the present carrier. The experiment must distinguish these possibilities.

The safe negative wording is:

> `inert in <exact tested envelope>; global role unknown`

Do not write `unused`, `reserved`, `don't-care`, or `may be chosen arbitrarily` from a
single carrier or from a sweep that has no detection power for the suspected role.

## 2. One label must no longer carry four conclusions

Every field or finite resource gets independent status on these axes. A result on one axis
must never imply a result on another.

| Axis | Question | Example statuses |
|---|---|---|
| Encoding geometry | Did the requested value produce the intended distinct bits and preserve instruction framing? | `unverified`, `ledger-verified`, `geometry-mapped` |
| Liveness | Does the value change an observable in a stated carrier and state envelope? | `live`, `accepted-inert`, `fault`, `hang`, `carrier-undecidable` |
| Semantics | Can an independent predictor map value and context to result/fault/no-effect? | `unknown`, `hypothesis`, `bounded-map`, `semantically-mapped` |
| Compiler recipe | Can a complete instruction/program be generated without copying the field from a captured donor? | `not-generated`, `generated-point`, `canonical-recipe-proven` |
| Target | On which GPU was each of the above established directly? | `G16G-direct`, `G17P-direct`, `cross-target-inferred` |
| Reproducibility | Is the claim linked to immutable raw data, authored inputs, hashes, and repeatable analysis? | `incomplete`, `auditable`, `independently-confirmed` |

These axes are required in experiment verdicts even if the current database sidecar cannot
yet store all of them. Until its schema is extended, put them in
`analysis/field_verdicts.json` and `RESULTS.md`; do not round liveness up into the legacy
semantic/emitter label.

Legacy label mapping remains strict:

- `hardware-run` requires semantic checks against an independent predictor over the stated
  range. A stable byte-to-output change is only liveness.
- `isolated-byte-diff` requires a predicted semantic effect at the tested point, not merely
  an isolated byte difference.
- `emittable` additionally requires a complete generated recipe. Field labels alone are not
  an emittability proof.
- A target-specific fact requires direct evidence on that target. M4/G16G evidence may seed
  a G17P hypothesis but cannot close it.

In particular, `sem_checked == 0` can never produce `hardware-run`,
`semantically-mapped`, or `canonical-recipe-proven`.

## 3. The five promotion gates

### Gate A — requested bytes really existed

For every dispatched case, preserve all of:

- the caller's requested field value;
- the complete requested instruction bytes;
- the complete actual instruction bytes extracted from the final dispatched program;
- an independently decoded value from those actual bytes;
- full-program bytes or a cryptographic hash plus the instruction offset;
- descriptor/database revision and harness revision.

Before any hardware conclusion, require:

```text
requested field value == value decoded from actual dispatched bytes
```

Also report requested case count, distinct requested values, distinct actual encodings, and
any collision caused by `match` bits or overlapping fields. A symmetric
assemble-disassemble round trip is only a tokenizer test. It is not this gate.

This gate would have caught DEF-0166 immediately: a requested bit that the assembler could
not clear would not appear in the actual-byte ledger.

### Gate B — the carrier can see the proposed effect

Every arm pre-registers a positive control that must change the same observable by a known
mechanism. The observable must be independent of the swept field: it may not move the
readback register, address, branch path, or store selector along with the field.

Record complete relevant state, not only the expected destination. Poison untouched state
and use independent pre/post sentinels. If the positive control fails, the arm is
`carrier-undecidable`; zero movement is not evidence of inertness.

### Gate C — behavior matched an independent model

Pre-register the competing semantic models and a prediction for every case before seeing
the output. The predictor must be independent of the GPU result and must distinguish at
least:

- correct value/effect;
- a different but coherent effect;
- silent zero/no write/dead path;
- rejected/faulted/hung execution;
- invalid measurement or contamination.

A difference from baseline is not a semantic oracle. Cross-run agreement proves
repeatability, not meaning. A field becomes `semantically-mapped` only when the observations
select a predictive model over the claimed domain and the model survives adversarial cases.

This gate prevents the EXP-0169 Tier-2 error: stable movement with zero semantic checks is
valuable liveness evidence, but it says only `live; role unknown`.

### Gate D — generate the compiler recipe

To call an instruction compiler-usable, construct every required byte from documented
rules, run the exact generated program, and compare complete state with a host prediction.
The evidence record must identify every copied region and prove that no required instruction
field came from a compiler-emitted donor.

Generated-point and canonical-recipe status are separate. A canonical recipe must cover the
operand classes and context the compiler will actually select; it need not wait for every
capability bit to be understood, but the remaining bits stay open on the capability map.

### Gate E — confirm cleanly on the claimed target

Discovery sweeps may run concurrently. Promotion/confirmation runs may not rely on a busy
machine sweep. Require two clean G17P runs in reversed or shuffled case order, with identical
actual-byte ledgers and no victim/cascade evidence. For load-bearing inertness or a surprising
semantic claim, require a genuinely different carrier or second method as well.

Fault, hang, silent-no-write, and finite-limit overflow claims must be repeated in isolation.
A malformed runner response is `measurement_failure`, never a hardware outcome.

## 4. Pre-registration and immutable capture

Before the first dispatch, freeze and hash:

- the exact claim matrix and the axis each arm is allowed to advance;
- competing hypotheses and falsifiers;
- carrier identity and why it has detection power;
- field domain, planned coverage, and stopping rule;
- mutation ledger and actual-byte verification method;
- input/state seeds, sentinels, readback plan, and host oracle;
- target, tool, database, harness, and repository revisions;
- concurrency/isolation policy and recovery policy.

If the design changes after observations are seen, retain the old run and start a named
amendment or new experiment whose revised preregistration is frozen before its first dispatch.
Do not edit a hypothesis to match data already captured.

Raw files are append-only. Each case must include at minimum:

```text
case id; target; carrier/context id; requested field/value; actual instruction bytes;
decoded actual value; program hash; complete seeded input state; complete relevant output
state; independent sentinels; host prediction; semantic-check result; command-buffer status;
fault classification; timeout/retry/contamination flags; run id and case order
```

An analysis program may change, but its input raw files and hashes may not.

## 5. How to investigate every bit without fooling ourselves

Use staged discovery. Do not ask one carrier to answer every question.

### Phase 1 — geometry

Toggle every not-yet-explained bit in safe authored carriers and verify actual emitted bytes.
Map instruction length, match/fixed bits, overlaps, aliases, and which requested encodings are
unreachable under the current descriptor. A fixed bit belongs in `match`; it is not a user
operand merely because the database currently exposes it as a field.

### Phase 2 — individual field liveness

- Finite selectors, modes, register numbers, widths, formats, and fields of width at most 8:
  dispatch every encoding unless doing so is demonstrably unsafe. Map unsafe regions with a
  separately declared, recoverable experiment.
- Larger numeric fields: exercise constituent bits, zero, one, extrema, signed boundaries,
  alignment boundaries, powers of two, cross-byte combinations, and values chosen to
  distinguish candidate formulas. Do not claim exhaustive value coverage when it was not done.
- Addresses and offsets: test the formula, alignment, carry between components, representable
  boundaries, and out-of-range behavior. Enumerating an address space is neither required nor
  meaningful.

For every finite domain, report exact numerators and denominators: encodable values, dispatched
values, distinct actual encodings, legal values, silent/no-effect values, faults, hangs, aliases,
and untested values. Never report only a percentage.

### Phase 3 — semantics

Choose asymmetric inputs that discriminate every plausible operation. Examples:

- seed every source register/lane with a unique codeword so register, lane, width, swizzle,
  sign, absolute, and immediate interpretations cannot alias;
- for floating point, include signed zero, infinities, NaNs, denormals, rounding boundaries,
  and values that separate competing operations;
- for predicates/logic, derive the truth table rather than naming an opcode from two vectors;
- for memory, use distinct buffers, slots, offsets, widths, guard regions, and data patterns;
- for control flow, use unique per-path signatures, both branch polarities, and multiple trip
  counts;
- for texture/fragment state, use non-affine coordinates/channel values, distinct descriptors,
  samplers, render targets, sample states, and stages;
- for synchronization, use a real multi-invocation ordering litmus. Scalar success cannot
  assign ordering semantics.

### Phase 4 — context and interactions

Single-field sweeps cannot discover conditional fields. Maintain a field-dependency graph and
add an edge whenever accepted values or effects change with another field or carrier property.
Test interactions especially among fields sharing a byte or controlling:

- opcode/sub-op, instruction length, operand class, width, format, and register bank;
- execution mask, control-flow scope, scoreboard/order state, and register lifecycle;
- shader stage, interpolation/derivative mode, resource class, descriptor type, and memory space.

Start with pairwise covering arrays. When context dependence appears, run the full finite cross
product needed to describe it. A byte that is inert under one opcode or length is not globally
inert.

### Phase 5 — independent carriers and generated recipes

Repeat surprising results with a carrier that differs in the dimension the bit might control.
Two generated carriers with the same leaf callee, state shape, or observation path count as one
method for that dimension. Then build both a safe canonical compiler recipe and, separately,
capability probes for noncanonical accepted encodings.

## 6. Special carrier rules

### Sources and destinations

Seed all candidate sources with unique values and dump all architecturally observable registers,
not just one presumed destination. Keep the store/readback index fixed while sweeping a
destination. Use at least two disjoint register/readback plans so a hidden write or destination
alias cannot masquerade as inertness.

### Register lifecycle and operand provenance

Treat value provenance and lifetime as experimental context, not noise. Repeat relevant fields
with values produced by ALU, uniform/system input, memory load, texture/interpolator, and other
available producer classes. Vary immediate use, intervening independent ALU, asynchronous work,
control-flow merge/reconvergence, overwrite, and epilog/export position. Poison destination
pre-state and dump complete state.

If behavior depends on how or when a register was defined, document the lifecycle rule and do not
misattribute it to an encoding bit. This is now a required dimension for register, memory,
scoreboard, and control-flow experiments.

### Memory and finite slots/resources

Use canaries and guard regions around every buffer. Give each slot/descriptor a distinct base,
shape, and data pattern so the selected resource, address formula, width, and channel map can be
recovered independently.

For every finite resource — base slots, texture selectors, register banks, scoreboards, queues,
nesting stacks, masks, descriptor tables, shared memory, or any newly discovered lifecycle pool —
establish:

1. the exact usable count and whether it is per instruction, stage, shader, context, or device;
2. allocation/selection encoding and any reserved indices;
3. initialization, lifetime, destruction, reuse, and aliasing rules;
4. behavior at the last valid entry and first invalid/excess entry;
5. overflow behavior: reject, fault, hang, alias/wrap, spill, serialize, evict, or silent wrong
   result;
6. whether capacity changes with formats, widths, stages, concurrency, or other state.

A nominal size without excess-capacity behavior is an incomplete result.

## 7. Proving an apparently constant or inert bit

It is reasonable to suspect that an encoding bit has a hidden role. Investigate it aggressively,
but keep the conclusion bounded.

To promote from `accepted-inert in one carrier` to a general accepted-inert rule, require:

- at least three structurally different carrier/context classes where such carriers exist;
- a positive detection-power control in every carrier;
- interactions with every plausible selector identified by geometry/corpus evidence, including
  opcode/sub-op, length, operand class, stage, mask/order state, and register lifecycle;
- two clean isolated repetitions; and
- an independent compiler-differential or generated-carrier method where available.

Then classify the best supported explanation separately:

- fixed opcode/framing bit;
- accepted alias/redundant encoding;
- contextual field with stated predicate;
- reserved/illegal value;
- accepted-inert over the tested hardware envelope;
- unobservable with current instrumentation;
- still unknown.

Even after this gate, state the tested target and envelope. `Globally unused in all hardware` is
normally stronger than black-box evidence can establish. For compiler purposes, a documented
canonical accepted value may be sufficient while capability discovery remains open.

## 8. Promotion must inspect evidence, not citations

`validate_labels.py` currently validates the sidecar's schema and label consistency. It must not
be used as the evidence-promotion gate by itself. A promotion checker must open the cited raw and
derived files and reject promotion when any of these is true:

- evidence path or authored input is missing;
- target does not match the claimed target;
- actual-byte ledger is missing or requested/decoded values disagree;
- distinct actual encodings do not cover the claimed range;
- semantic checks are zero or do not cover the claimed behavior buckets;
- the carrier's detection-power control failed;
- required isolated repetitions or second method are missing;
- copied donor fields remain in a claimed generated recipe;
- fault/hang/limit claims were not confirmed free of cascade contamination.

The checker should emit separate geometry, liveness, semantics, recipe, target, and audit reports.
It must not derive a single `N of 166 emittable` headline from field labels.

## 9. Progress accounting that cannot reset itself

Maintain separate dashboards for:

1. encoding geometry coverage;
2. field/bit liveness coverage;
3. semantic-map coverage;
4. canonical generated-recipe coverage;
5. direct G17P revalidation coverage;
6. reproducible evidence-chain coverage;
7. finite-resource limit and overflow coverage.

An experiment may advance one dashboard and leave the others unchanged. That is real progress.
A later semantic correction does not erase geometry or liveness evidence. A broken citation or
missing raw artifact downgrades auditability; it does not by itself prove the hardware fact false.
Conversely, remembered success without auditable evidence cannot enter the normative spec.

Never bulk-withdraw results merely because a shared tool had a defect. First re-read actual raw
bytes and determine the precise affected cases. Preserve unaffected observations. Retract a
semantic claim only for direct contradictory evidence or because its stated gate was never met;
record the reason and retain the earlier observation as superseded history.

Do not retroactively call an observation false merely because a later acceptance gate is stricter
than the experiment's frozen gate. Record two facts instead: whether the experiment passed its
own pre-registered gate, and whether its evidence is sufficient for the current geometry,
liveness, semantic, recipe, target, and audit gates. `Legacy evidence; insufficient for current
semantic promotion` is a bounded status, not zero progress and not a hardware contradiction.

Every progress update must state separately:

- new raw observations;
- new geometry facts;
- new liveness facts;
- new semantic facts;
- new generated recipes;
- claims downgraded, with exact reason and scope;
- bounded unknowns remaining.

Do not count “fields touched” as semantic progress.

## 10. Immediate operating instructions

For ongoing work:

1. Stop using liveness-only sweeps to promote `hardware-run` or `emittable`.
2. Do not discard or rerun everything. Reclassify existing raw on the independent axes first.
3. Rerun only the cases missing a required actual-byte ledger, semantic oracle, target validation,
   independent carrier, or clean confirmation.
4. Add register lifecycle/provenance and field-interaction dimensions to the next targeted arms.
5. Keep pursuing every unexplained bit after a canonical compiler recipe is known.
6. Validate each experiment's evidence chain before merging its claims, so a later global audit
   finds bounded gaps rather than forcing a headline reset.

## 11. Known failures this process prevents

| Failure | Required prevention |
|---|---|
| DEF-0166 assembler could not clear some requested bits | Caller-to-actual-byte ledger and distinct-encoding count (Gate A) |
| EXP-0168 destination/readback co-varied | Fixed independent readback plus complete register dumps and alternate plans (Gate B) |
| EXP-0169 stable differences were promoted despite no semantic oracle | Separate liveness from semantics; forbid promotion with zero semantic checks (Gate C) |
| EXP-0179 carriers agreed on an apparently inert call bit but shared the same blind dimension | Independent carrier/method chosen for the suspected role (Phases 4–5) |
| Busy-machine faults/hangs and reader cascades looked like hardware behavior | Quiet confirmation, poisoned state, sentinels, and `measurement_failure` classification (Gate E) |
| EXP-0189-style closing audits changed a global count by applying a later rule to mixed evidence | Preserve the original-gate result, score every current axis separately, and rerun only the missing gate (§9) |
| Later audits repeatedly changed one global completion number | Separate monotonic dashboards and precisely scoped downgrades (§9) |

The objective is not to make experiments harder. It is to make each dispatch answer one stated
question, retain every answer it actually supports, and expose exactly which next experiment is
needed for the questions it does not answer.
