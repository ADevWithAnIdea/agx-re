# EXP-0064 results: bounded M4 public format behavior

> **QUARANTINED / NON-EVIDENCE.** This historical text and all associated raw
> output are retained only to disclose the failed process. They must not support
> a P1.2, M4, A18, native, or implementation claim; see `QUARANTINE.md`.

## Verdict

**PARTIAL / M4 public API only. P1.2 remains OPEN.** Both fresh runs exactly
matched for all six named cases, including the complete 384-byte render and
144-byte compute buffers and all guards. These observations establish selected
public Metal render-store/typed-read behavior only; they do not establish native
PBE/epilog behavior, descriptors, Linux packing, API capability completeness, or
A18 behavior.

**Process deviation (preserved):** the preregistration asked for separate
10-second build/completion caps. The retained runner instead used a 30-second
build timeout and 20-second per-process outer timeout; it did not implement
separate 10-second caps. No case timed out, but this deviation remains part of
the evidence record and narrows the process claim.

| case | physical texel bytes | typed compute words (little-endian uint32) |
| --- | --- | --- |
| RGBA8Unorm edges | `00 80 ff 80` | `00000000 3f008081 3f800000 3f008081` |
| BGRA8Unorm edges | `ff 80 00 80` | `00000000 3f008081 3f800000 3f008081` |
| RGBA8Unorm_sRGB threshold | `0a 0a bc 80` | `3b400c01 3b400c01 3f00b80c 3f008081` |
| R16Unorm midpoint | `00 80` | `3f000080 00000000 00000000 3f800000` |
| RGBA16Float finite edges | `00 80 00 3c ff 7b 55 35` | `80000000 3f800000 477fe000 3eaaa000` |
| R32Uint exact | `ef be ad de` | `deadbeef 00000000 00000000 00000001` |

The UNorm edge cases show the tested clamp endpoints and BGRA red/blue physical
order. The sRGB test produced equal physical bytes for the two named near-knee
red inputs; it does not resolve an untested transfer/rounding boundary. The
half cases show these selected finite encodings/expansions; no NaN, infinity, or
subnormal rule is inferred. R32Uint preserves the one tested word. Full raw
backings and environment records are hashed in `manifest.json`.

Untested P1.2 scope includes other formats, filtering, blendability, atomics,
MSAA/resolve, sparse/linear/compressed support, general rounding, and every
native/Linux/A18 mapping.
