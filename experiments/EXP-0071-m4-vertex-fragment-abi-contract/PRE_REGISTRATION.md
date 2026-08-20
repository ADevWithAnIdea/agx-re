# EXP-0071 pre-registration — M4 public vertex/fragment ABI contract

**PRE-GPU only.** No compilation, allocation, submission, or observation exists.
This P0.8 experiment asks only how authored public Metal vertex descriptors,
typed attributes, and selected fragment interpolation qualifiers affect full
owned render-target backings on local M4/G16G. It does not cite quarantined
EXP-0050 and makes no native, descriptor, Linux, A18, or binary claim.

The frozen 11-case matrix is in `CAPTURE_CONTRACT.json`: separate/interleaved
float attributes; matching non-zero resource/descriptor offsets; U8/U16 normalized
float paths; U8 raw uint path; perspective, no-perspective, and flat varying
paths; and a fragment-constant control. Each case renders the same asymmetric
4x4 triangle. The interpolation triangle has unequal clip-space W values so the
two center modes have designated distinguishing pixels.

Every case owns two shared 1,152-byte backings: 64 `0x5a`, four 256-byte rows,
64 `0xa5`, for one RGBA16Float and one RGBA8Uint target. The harness may retain
only complete backing hex, derived texels, and public status/error identity.
All texture writes are within 4x4. No archive, shader bytecode, binary, BO,
pointer, command/state trace, private API, or Apple helper is retained/inspected.

Falsifiers: an equivalence-layout mismatch; changed guard; malformed/full-size
readback failure; wrong raw uint components; normalized values inconsistent with
the named inputs; no perspective/no-perspective difference at designated pixels;
flat output varying across covered pixels; command error/timeout; or repeat
mismatch. Any failure writes `STOP.json` and ends that run without retry.

Before build, `python3 -B verify.py --preflight` must pass. Future runs bind Git
revision, every authored SHA-256, `sw_vers`, `xcrun --version`, device/machine,
argv, timeouts, stdout/stderr, and public command status. A second run is allowed
only after a closed run-01 verifier and identical revision/hash map. Promotion
requires two exact run trees, matching environment outputs, full guards, and
byte-exact derived analysis.

Clean-room provenance: OWN-SHADER / PUBLIC API (planned HW-PROBE)
Inputs inspected: committed authored source and contract only
Apple binary introspection: NONE
Reproduction: `python3 -B verify.py --preflight`
Evidence: no raw observations exist
