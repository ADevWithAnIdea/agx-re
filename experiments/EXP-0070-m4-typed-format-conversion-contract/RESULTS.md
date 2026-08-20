# EXP-0070 results

# EXP-0070 results — bounded M4 public typed-format behavior

**PASS / public M4 only.** Two contracted fresh runs passed the closed capture
verifier and are byte-exact equal for the six named 1x1 cases. These are direct
observations of complete owned shared backings after one authored public render
store and one in-bounds public typed compute read. P1.2 remains **OPEN** beyond
this exact matrix.

| case | physical texel bytes | typed compute words (little-endian uint32) |
| --- | --- | --- |
| RGBA8Unorm edges | `00 80 ff 80` | `00000000 3f008081 3f800000 3f008081` |
| BGRA8Unorm edges | `ff 80 00 80` | `00000000 3f008081 3f800000 3f008081` |
| RGBA8Unorm_sRGB threshold | `0a 0a bc 80` | `3b400c01 3b400c01 3f00b80c 3f008081` |
| R16Unorm midpoint | `00 80` | `3f000080 00000000 00000000 3f800000` |
| RGBA16Float finite | `00 80 00 3c ff 7b 55 35` | `80000000 3f800000 477fe000 3eaaa000` |
| R32Uint exact | `ef be ad de` | `deadbeef 00000000 00000000 00000001` |

The observations support only the selected public stores/readbacks. They do not
establish general rounding, filtering, blending, atomics, MSAA, sparse or
compressed behavior, NaN/infinity/subnormal handling, native PBE/epilog,
descriptors, Linux mappings, A18 behavior, or a broader capability claim.

Clean-room provenance: HW-PROBE / OWN-SHADER / PUBLIC API
Inputs inspected: authored MSL/harness, public status/error objects, and full owned readbacks
Apple binary introspection: NONE
Reproduction: `python3 -B verify.py --captured`; `python3 -B analysis.py --run-a m4-TODO-run01 --run-b m4-TODO-run02`
Evidence: `raw/m4-TODO-run01`, `raw/m4-TODO-run02`, `analysis.json`, `manifest.json`
