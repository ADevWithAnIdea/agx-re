# EXP-0072 results

> **QUARANTINED / NON-EVIDENCE — see `QUARANTINE.md`.** No observation from
> this experiment may be staged, cited, or promoted. What is recorded here is
> the failure record only.

## What was attempted (pre-registered)

Second bounded increment of DRV-FMT-01: 34 preregistered compute-store +
typed-read cases over 14 public pixel formats (R8Unorm, R8Snorm, RG8Unorm,
RG8Snorm, RGBA8Snorm, R16Float, RG16Float, R16Sint, R16Uint, R32Float, R32Sint,
RG11B10Float, RGB9E5Float, RGBA16Uint), each with frozen expected texel words
and a/b/c derivation rules in `CAPTURE_CONTRACT.json`.

## What happened

- `verify.py --preflight` and `verify.py --selftest` passed; the self-test
  (added after EXP-0073) caught several real pre-capture schema bugs, including
  an unsatisfiable `command_buffer_error` status set.
- Capture run 01 executed: 34/34 case processes exit 0, all guards intact,
  no API rejection, timeout, fault, or hang.
- Every case payload was truncated by a harness print race (worker signals the
  dispatch semaphore before printing; main returns and exits mid-print), so the
  physical texel hex and typed read words were lost. 0/34 payloads parse.
- Repair post-capture is unauthorized (frozen hash binding), so the experiment
  is quarantined per the EXP-0064/EXP-0073 precedent. Successor:
  EXP-0075-m4-typed-format-conversion-batch2.

## OBSERVED (process history only, NOT evidence)

- All 34 case processes reported status fields "ok", all pipelines and textures
  created, command buffer status 4 — including RG11B10Float and RGB9E5Float
  under MTLTextureUsageShaderWrite|MTLTextureUsageShaderRead with shared-storage
  buffer backing. This is unverified process history from a defective harness;
  the successor must re-establish it from intact records.

## INTERPRETED

Nothing. No DRV-FMT-01 increment answer can be derived from this tree.

Clean-room provenance: HW-PROBE / OWN-SHADER / PUBLIC API (attempted; no usable observation)
Inputs inspected: authored MSL/harness/contract and public status objects
Apple binary introspection: NONE
Reproduction: none (quarantined); see `QUARANTINE.md` for the successor plan
Evidence: `QUARANTINE.md`, `PROGRESS.md`, `raw/m4-20260827-run01` (append-only process history)
