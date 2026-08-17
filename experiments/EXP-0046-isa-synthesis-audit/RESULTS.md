# EXP-0046 Results — compiler-ready ISA synthesis audit

## Direct structural observations

The existing central round-trip suite passes. Against the current checked-in database:

- 170 descriptors contain 1,022 declared fields;
- 59 descriptors still contain one or more `raw` fields (133 raw fields total);
- 66 descriptors contain an explicit inferred/inference qualifier;
- 6 descriptors explicitly say more splicing is required;
- 6 descriptors are fallback tokens explicitly labelled as not standalone hardware ops;
- fixed real/program/synthetic vectors reach 78 of 170 descriptors;
- only 19 unique descriptors have a synthesized field-vector case in the central test;
- 92 descriptors have no fixed vector in the central test; and
- generated `agx3.xml` contains 329 instruction elements and 129 `<zero>` placeholders.

These metrics reproduce exactly from `raw/audit.json` with `verify.sh`.

## Interpretation

The database is valuable for decoding, exact re-encoding of observed bytes, and instruction
boundary recovery. Those capabilities do not establish compiler-ready synthesis. A raw field
can preserve bytes without identifying semantic operands, and a codec can round-trip a fixed
vector without proving legal ranges, cross-field constraints, or live behavior of a newly
assembled combination.

P0.6 remains open. Closing it requires a supported semantic opcode subset with no raw or
fallback dependency, explicit operand/range/property tables, generated boundary and cross-
product cases, and live execution of independently assembled programs. Unsupported residue
must be excluded by a documented compiler lowering or software fallback rather than silently
accepted as an opaque token.

## Prioritized queue

The 92-name list in `raw/audit.json` is the mechanical fixed-vector backlog. Within it, the
load-bearing groups are texture sample/write/addressing, fragment depth/output and tile paths,
control-flow mask variants, memory fences, conversions/high registers, and stack/frame forms.
The six non-opcode fallback tokens must never be compiler emission targets.

## Limitations

- This audit measures the central database and test suite, not every historical one-off
  splice log in the repository.
- A descriptor counted as having a fixed vector may still have untested fields or values.
- A descriptor without a central vector may have useful live evidence elsewhere; that evidence
  must be promoted into a reproducible generative test before it can help close P0.6.
- No new M4/A18 behavior is claimed.

## Clean-room provenance

```text
Clean-room provenance: STRUCTURAL analysis of OWN-SHADER-derived repository data
Inputs inspected: tools/agx-isa source, database, tests, and docs/isa/agx3.xml
Apple binary introspection: NONE
Reproduction: experiments/EXP-0046-isa-synthesis-audit/verify.sh
Evidence: raw/audit.json
```
