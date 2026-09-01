# EXP-0223 results — generated G17P compare/select recipe

Status: **canonical compiler recipe proven over the tested 32-bit r0..r23-source / r0..r15-
destination envelope.**

Target: Apple A18 Pro / G17P, Metal family Apple9.  Every promoted instruction byte was generated
from the rules below.  No compiler-emitted field was copied.  Fresh own-MSL was consulted only
after the three pre-registered generated hypotheses failed, and only to nominate a new field
formula; the formula was then tested independently on hardware.

## Canonical encoding

Generate the ten-byte `isel10` form as:

```text
dst             = D
cmpA            = (A << 1) | 1
opsel           = 0
cmpB            = (B << 1) | 1
cmp_mode        = condition-dependent, below
selTrue         = T << 1
cc              = condition-dependent, below
flags           = 0xc0
selFalse_file   = 0
selFalse        = F << 1
```

It computes `D = predicate(A, B) ? T : F`.  The safe condition table is:

| predicate | `cmp_mode` | `cc` | note |
|---|---:|---:|---|
| unsigned `A > B` | `0x02` | 4 | native |
| unsigned `A < B` | `0x02` | 5 | native |
| signed `A > B` | `0x02` | 6 | native |
| signed `A < B` | `0x02` | 7 | native |
| integer `A == B` | `0x06` | 7 | native equality mode |
| integer `A != B` | `0x06` | 7 | swap T and F |
| float `A > B` | `0x02` | 2 | ordered; NaN is false |
| float `A < B` | `0x02` | 3 | ordered; NaN is false |
| float `A == B` | `0x06` | 0 | `-0 == +0`; NaN is false |
| float unordered `A != B` | `0x06` | 0 | swap T and F; NaN is true |

Integer `<=`/`>=` can be expressed by operand/arm reversal.  Ordered floating `<=`/`>=` must not
be implemented as a blind inversion of strict comparison because that would make NaN true; compose
strict comparison and equality when portable semantics require NaN-false.

## Source lifecycle and provenance

The conservative recipe above retains all four value sources.  Proven optional release controls,
all occurring after reads and regardless of the selected predicate arm, are:

- `opsel` bit 0 releases A;
- `opsel` bit 1 releases B;
- `cmp_mode` high class `0x80` releases T when the low mode remains legal;
- `selFalse_file` high class `0x80` releases F.

Destination publication follows releases, so an aliased destination contains the selected result.
The formal suite covers `D==A`, `D==B`, `D==T`, and `D==F`.

`flags=0xc0` is required for a compare/select to consume directly load-produced operands in the
tested carrier.  All other tested high classes consumed stale seeds even when the load's value
became visible to a later dump.  This is a consumer-side load-accept/dependency mode, not evidence
that the producer permanently failed.  Keep `0xc0` until a backend deliberately models provenance.

## Formal evidence

The final V4 captures are `g17p_e0223_run05` and `g17p_e0223_run06`, canonical and shuffled.  Each
contains 220 generated dispatches: eight slot probes and 212 V2 cases.

- 210/210 positive V2 programs per run matched the complete-state oracle.
- Both wrong-source/wrong-condition refuters fired in each run.
- The suite includes the ten condition recipes, all mapped lifecycle combinations, destination
  aliases, loaded A/B/T/F positions, representative sources spanning r0..r23, dense destinations
  r0..r15, and 100 deterministic mixed `iadd2`/`isel10` DAGs of 2..64 operations.
- Gate A: zero requested/actual-byte disagreements, zero field-decode errors, zero whole-program
  aliases, and zero leftover bytes.
- Gate D: `COPIED=0`, `CARRIER=0` in every case.
- Gate E: zero faults, hangs, victims, malformed replies, sentinel failures, program-hash
  mismatches, output-hash mismatches, foreign runners, or recovery-count changes.

Verify from raw rather than trusting the totals:

```sh
python3 experiments/EXP-0223-isel-canonical/analysis/verify_formal_v2.py
```

V2 run01/run02 are retained hardware evidence: all 209 positives were exact and both refuters
fired.  They failed the original formal contract only because an overfit corpus tokenizer shadowed
valid ten-byte forms.  V3 run03/run04 confirmed the corrected tokenizer with zero aliases, but a
post-run audit found the case generator used `range(15)` and omitted destination r15.  V4 adds that
boundary.  Neither earlier result was erased or misreported.

## Capability-map boundaries

The compiler recipe is complete without declaring every other encoding value understood.  Dense
discovery additionally established:

- `flags` low three bits select predicate/forced-T/forced-F behavior and bit 4 suppresses the
  destination write; other bits are bounded-neutral only in the stated mov-seeded carrier;
- legal compare modes satisfy `(mode & 3) == 2` in the swept form; other low classes faulted;
- `opsel` 4/5 are descriptor-ambiguous and 8..31 leave the proven ten-byte framing envelope;
- non-GPR true/false source classes return fixed/special values or zero in the tested descriptor;
- low sub-bits with no observed effect remain **unknown**, not unused.

Use only the canonical constants and condition table above in an initial compiler.
