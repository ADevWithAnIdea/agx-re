# Quarantined capture attempt 1 (m4-20260828-run01, pre-fix)

This is a RETAINED, NOT-REUSED partial capture from the first `run.py
--run-id m4-20260828-run01 --execute` invocation, under the pre-fix harness
(the "compute bundle" capability grammar: 6 axes per process, 858 total
cases). It ran 131/858 cases and then correctly STOPped (per its own
`STOP.json`) on an unexpected nonzero exit (SIGABRT) for
`cap_compute_00255_Depth24Unorm_Stencil8`.

Root cause: `newTextureWithDescriptor:` itself hard-aborts
("MTLTextureDescriptor has invalid pixelFormat (255)") for
`MTLPixelFormatDepth24Unorm_Stencil8` on this device -- a THIRD hard-abort
class beyond the two (F1/F2) already disclosed in `PRE_REGISTRATION.md`,
corroborating the prior EXP-M4-08 finding
(`docs/descriptors/format-table.md`: "Unsupported on this HW (Metal
rejects): depth24unorm_stencil8, x24_stencil8"). This is genuine hardware
evidence, not a defect in what it measured -- the defect was the harness's
axis-bundling, which let one format's abort discard five sibling axes'
already-computed results for the same process.

Per `SUBAGENT_BRIEF.md` ("A partial capture is retained, never reused...
capture under a NEW id"), this directory is retained exactly as produced and
is NOT topped up, repaired, or reused. The harness was fixed (every axis now
runs as its own process; `analysis/gen_contract.py`
`DEVICE_UNSUPPORTED_FORMAT_IDS`/`BLENDABLE_INELIGIBLE_KINDS`/
`DEPTH_STENCIL_DIRECT_ATTACH_INELIGIBLE_FAMILIES` derive `expect_may_abort`
from a full 138x11 pre-check, `provenance/pre_freeze/precheck/`) and the
real capture re-ran under the run ids named in the (updated)
`PRE_REGISTRATION.md` / `CAPTURE_CONTRACT.json`.

131/131 cases in this partial capture exited 0 except the terminal one
(SIGABRT, exit -6); no data here is silently discarded, just not promoted as
this experiment's evidence -- the corrected, complete run supersedes it.
