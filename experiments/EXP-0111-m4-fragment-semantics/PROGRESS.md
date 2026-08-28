# PROGRESS — EXP-0111 M4 fragment semantics (FS-01..FS-12)

## 2026-08-27/28 — setup, harness, pilot phase

- Read CLAUDE.md, CODEX.md, experiments/SUBAGENT_BRIEF.md, APPLE9_RE_IMPLEMENTATION_GAPS.md
  (FS-01..FS-12 exact wording located at lines 1038-1075), prior work: EXP-0029-fragment-isa
  (iter/interpolation/tilebuffer encodings), EXP-0091-m4-fragment-sample-discard (discard/demote/
  helper/depth-order/sample-shading state machine, GLFS-A01..A07, OPT-09), EXP-0031-sr-abi
  (get_sr SR-number table incl. FS position 0xa0/0xa1 -- flagged there as INFERRED-by-isolation,
  not HW-splice-validated for FS specifically), EXP-M4-13-full-corpus (deriv_scalar/deriv_vec4
  compile-only exploratory data), docs/isa/encoding-tables.md (tex_deriv 0x37, iter 0x2f family).
- Built experiment dir; harness/fsrun.m = EXP-0091's fsrun.m (our own prior authored tool, not
  Apple code) + ONE new capability (--rt-count, up to 3 color attachments) for FS-11. Verified
  MRT readback and raw-bit buffer readback both work correctly (pilot).
- **COMPLIANCE NOTE (self-disclosed, corrective action taken):** experiments/SUBAGENT_BRIEF.md
  was updated mid-session (observed here) to explicitly prohibit writing ANY file outside the
  repo, including /tmp, even briefly. Before noticing this update, several quick pilot/diagnostic
  commands in this session wrote throwaway files to /tmp (shdump_f1..f4/f4_both.log, x.bin,
  pilot_covfrac2.metal, ic.log, ic2.log, ic_C/D/E.log) while iterating on kernel designs. As soon
  as the updated brief was read, all of those files were identified and deleted from /tmp (verified
  removed); no other files were touched. All work from this point forward uses
  work/scratch/ inside this experiment directory for any throwaway/non-evidentiary output. None
  of the deleted /tmp content was evidence -- every finding derived from it was independently
  reproduced via the frozen kernels/harness before being relied on in RESULTS.md.
- Extensive pilot validation (host-side compiles + GPU dispatches, matching CODEX's "characterize
  before freezing" precedent, e.g. EXP-0091 section 1) for: pixel-coordinate convention (FS-01/02/
  03), quad-boundary derivative locality (FS-04), scalar derivative op count incl. an axis-byte
  labeling anomaly (FS-07), original-helper-lane position/derivative/status (FS-02/FS-06/GLFS-A03
  remainder), centroid-vs-center partial-MSAA-coverage extrapolation (FS-08), interpolate_at_offset
  numeric behavior -- found a significant, well-corroborated anomaly: the offset argument behaves
  as an ABSOLUTE window-space pixel-local coordinate (origin at the pixel's top-left corner, y
  DOWN) rather than the MSL-spec-documented signed offset from pixel CENTER (FS-08), convergent-
  vs-flat bit-exactness across 5 parameter configs (FS-09), dynamic fragment-input indexing via a
  local-array select (FS-10, functionally correct, oracle match confirmed).
- All pilot dispatches: STATUS OK, zero faults, zero hangs, zero command-buffer errors, zero host
  wedges, zero macvdmtool/A18/M5 contact.

## Next
- Finish kernel authoring: dynidx_out (FS-11), kill-remainder sample-mask-from-demoted-lane
  (FS-12), anomaly_helper_pre and anomaly_persample_discard (EXP-0091 anomalies a/b second
  methods).
- Freeze PRE_REGISTRATION.md + CAPTURE_CONTRACT.json (source hashes, case matrix, environment).
- Assemble schema.py/run.py/verify.py (EXP-0091 pattern).
- Two capture runs, cross-run gate, RESULTS.md.

## 2026-08-28T06:52Z — run01 captured

PRE_REGISTRATION.md + CAPTURE_CONTRACT.json frozen (32 authored files hashed, 56-case
matrix). All 5 standing gates re-verified PASS post-freeze (--selftest, --seqtest,
--smoke before raw/ existed). `python3 run.py --run run01 --out raw/m4_20260828_run01`:
56/56 cases, every status one of OK/SCANNED/REJECTED (all expected outcomes -- REJECTED
is the correct/predicted status for dynidx_out_reject_attempt). Zero HANG, zero
HARNESS_CRASH, zero unexpected COMPILE_FAIL, zero command-buffer error, zero host wedge.
Proceeding to run02.

## 2026-08-28T06:52-06:53Z — run02 captured; cross-run gate PASS

`python3 run.py --run run02 --out raw/m4_20260828_run02`: 56/56 cases, identical status
profile to run01 (all OK/SCANNED/REJECTED as expected). `python3 verify.py --crossrun
raw/m4_20260828_run01 raw/m4_20260828_run02` -> RESULT: PASS, byte-identical gated
records for all 56 cases. Re-ran --selftest and --seqtest post-capture: both PASS.
Zero faults, zero hangs, zero command-buffer errors, zero host wedges across both full
capture runs (112 total case executions) plus the earlier pilot phase. No macvdmtool
invocation, no A18/M5 contact anywhere in this experiment's lifetime.

Moving to RESULTS.md authoring.

## 2026-08-28T07:10Z — RESULTS.md, README.md, manifest.json complete; experiment done

RESULTS.md written with a full response block per FS-01..FS-12 (Status/Answer/Applies-to/
Evidence/OBSERVED/INTERPRETED/Driver-consequence), both EXP-0091 anomaly resolutions,
finite-resource-mandate table, explicit deferred-item list (6 items, none silently
dropped), gate results, and clean-room attestation. All cited numeric values re-extracted
directly from the frozen raw/m4_20260828_run01 JSON (not from memory of pilot runs) and
cross-checked against pilot findings -- all consistent. README.md and manifest.json
written. work/scratch/ contains only small diagnostic hex/text files (own-shader-compiled
hex byte dumps and JSON) generated during this session, no Apple binaries, no archives
committed as evidence (work/archives/*.bin are regeneratable shdump outputs of our own
MSL, same convention as EXP-0091).

Final tally: 12/12 FS items have a response block (CLOSED, or explicitly PARTIAL/deferred
with reasoning -- FS-03 sample-position, FS-05 ISA-level coarse mode, FS-08 sample-vs-
centroid full separation, FS-11 exact ISA mechanism, FS-12 stencil, plus the FS-07
axis-byte anomaly reported unresolved). Both EXP-0091 anomalies resolved (neither
reproduces under an independent method; both attributed to the original measurement
technique). Zero faults, zero hangs, zero host wedges, zero A18/M5 contact across the
experiment's full lifetime (pilot + 2 official runs, well over 150 individual GPU
dispatches).
