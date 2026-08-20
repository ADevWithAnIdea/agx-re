# EXP-0060 results — bound FALU2I semantic property vectors

## Verdict

**VALID STRUCTURAL INCREMENT; P0.6 remains open.** Under the frozen bounded
domain, all **1,440** `falu2i` semantic vectors produced unique six-byte
encodings, decoded back as `falu2i`, and byte-round-tripped. Capture-time input
hashes and Git revision bind the analyzer and every ISA input before execution.

This closes only the central property-vector gap for the enumerated `falu2i`
semantic sub-schema. It does not prove newly assembled bytes execute on Apple
hardware, make a compiler-ready general `falu2i` emitter, or cover the excluded
modifier fields `opflags`, `ctrl_lo`, and `mods`. Those fields remain explicitly
non-semantic/unsupported in this increment. No A18, M4, or native claim exists.

## Direct observation

`raw/run01/result.json` records `expected_vectors=unique_encodings=1440`,
`all_round_trip=true`, and encoding digest
`4bd29241b6ec078647e1e11aa6ce761ea9a4e4ad44113cb2c60fc88d36011606`.
The capture input record was written before the central test/vector generation
and binds commit `bf9a5aba8c4cd2d7e0d4e69eb982bd29d24ff1a6` plus the exact
pre-registration, analyzer, database, codec, and central-test hashes.

Clean-room provenance: STRUCTURAL / OWN-SHADER-derived repository data. Apple
binary introspection: NONE.
