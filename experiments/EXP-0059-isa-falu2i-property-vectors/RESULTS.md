# EXP-0059 results — FALU2I semantic property vectors

## Verdict

**STOPPED: unbound raw-analysis provenance. P0.6 remains open.** The retained
structural output reports 1,440 unique `falu2i` semantic-subset encodings that
assembled, decoded, and reassembled. That result is not promoted as evidence:
the frozen analyzer failed to record its own SHA-256 and the repository revision
at capture time. A later source/commit lookup would be reconstruction, not an
auditable binding of this raw invocation.

The output remains useful as a preserved process counterexample. It shows why a
passing codec audit is insufficient unless its exact authored analyzer and
inputs are bound before execution. No database descriptor, XML, or central
round-trip test is changed by EXP-0059.

## Direct retained observation (not promoted)

`raw/falu2i-property-v1.json` reports 1,440/1,440 unique 6-byte encodings and
`all_round_trip=true` over the frozen semantic-domain cartesian product. It
also explicitly lists excluded modifier fields `opflags`, `ctrl_lo`, and `mods`.
Because the raw file has no capture-time hash/revision for the analyzer itself,
these values are a process observation only, not a compiler property-vector
claim.

## Required successor controls

A successor must preregister and commit first, write a capture-input record
before running central tests, include exact repository revision and hashes for
the analyzer plus each inspected ISA input, enforce a closed raw tree, and
verify the raw report against those capture-time identities. It must retain the
same explicit semantic/non-semantic field separation and make no hardware/A18
claim unless a separately preregistered own-source live test is run.

Clean-room provenance: structural repository analysis only. Apple binary
introspection: NONE. Apple compiled-code, unknown-BO, and helper-byte
inspection: NONE.
