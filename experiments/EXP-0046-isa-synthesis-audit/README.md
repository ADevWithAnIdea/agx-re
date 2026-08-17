# EXP-0046 — Compiler-ready ISA synthesis audit

## Question

Does the current Apple9 ISA database demonstrate that arbitrary semantic instructions can
be synthesized, or does it primarily demonstrate lossless decoding/tokenization of observed
own-shader bytes?

This is a structural audit of repository-authored code and evidence. It creates no new
hardware fact and cannot close P0.6 by itself.

## Pre-registered hypothesis and falsifier

Hypothesis: the central round-trip test passes, but descriptor-level synthesis coverage is
substantially lower than tokenization coverage; raw fields, inferred semantics, fallback
tokens, and descriptors lacking any fixed test vector remain.

Falsifier: every descriptor has fully semantic typed fields, at least one synthesized
field-vector test, live independently generated execution evidence, and no fallback or
inferred residue.

## Method

`analysis/audit_synthesis.py` loads only repository-authored `tools/agx-isa` sources. It:

1. runs the existing round-trip suite;
2. inventories descriptor and field types in `db.json`;
3. decodes every fixed own-shader instruction/program vector in `roundtrip_test.py`;
4. measures unique descriptors reached by fixed and synthesized vectors; and
5. counts inference markers, raw fields, and non-opcode fallback tokens.

The committed `raw/audit.json` is a deterministic snapshot checked by `verify.sh`.

## Reproduction

```sh
./verify.sh
```

## Clean-room provenance

```text
Clean-room provenance: STRUCTURAL analysis of OWN-SHADER-derived repository data
Inputs inspected: tools/agx-isa source, database, tests, and docs/isa/agx3.xml
Apple binary introspection: NONE
Reproduction: experiments/EXP-0046-isa-synthesis-audit/verify.sh
Evidence: raw/audit.json and RESULTS.md
```
