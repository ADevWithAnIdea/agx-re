# EXP-0130 -- M4 BG/EOT construction (P0.4 / DRV-UAPI-04)

## Question

`docs/P0-P1-CLOSURE.md` P0.4 requires **independently generated, authored**
BG/EOT/partial-BG/partial-EOT programs -- not a decoded Apple template
(EXP-0048/EXP-0108 already established, HW-PROBE/DATA-TRACE, that no such
template is even visible to userspace on this path). EXP-0120 read the
UAPI (`mesa/include/drm-uapi/asahi_drm.h`) and established exactly which
fields a driver must fill: `struct drm_asahi_bg_eot { __u32 usc; __u32
rsrc_spec; }`, four unconditional instances (`bg`, `eot`, `partial_bg`,
`partial_eot`) per `drm_asahi_cmd_render`. This experiment asks: **can we
construct, from our own MSL, a program that performs the actual work an
EOT program must do (read the tilebuffer, write an attachment), get it to
execute on real M4 hardware, and verify it by pixel readback against a
host oracle** -- and precisely what blocks registering that construction
as the literal UAPI fields.

## Hypotheses

See `PRE_REGISTRATION.md` for the full falsifiable statements (H1-H3) and
confounders. Summary: H1 -- a tile_read+ALU+frag_color_store fragment
program is constructible and behaviorally exact against a host oracle on
M4; H2 -- structurally, only the non-elidable (`f_eot_combine`) shape
actually reaches the `tile_read`/`frag_color_store` hardware ops, while a
pure-identity shape (`f_eot_evict`) is compiled to a no-op by Metal's own
compiler; H3 -- no path reachable from this host can register a value as
the literal `drm_asahi_bg_eot.usc`/`rsrc_spec` fields of a real
`DRM_IOCTL_ASAHI_SUBMIT` (wrong OS; and even setting that aside, no
independent command-stream submission path exists on this host either,
per P0.5's own `OPEN` status).

## Method (clean-room)

- **PUBLIC**: read `mesa/include/drm-uapi/asahi_drm.h` and Mesa's own
  from-scratch BG/EOT construction path (`agx_bg_eot.c`, `agx_state.c`,
  `hk_cmd_draw.c`, `hk_queue.c`, `cmdbuf.xml`) to establish the exact UAPI
  field shape and the *shape* of what a driver must produce (CLAUDE.md
  explicitly sanctions this reading of `mesa/`). Also read Mesa's
  M1/M2-class compiler backend (`agx_compile.c`, `agx_opcodes.py`) for
  cross-generation context only -- no specific byte value from those two
  files is used as an Apple9 fact.
- **OWN-SHADER**: author fresh MSL (`kernels/eot_construct.metal`),
  compile it at runtime via the public `newLibraryWithSource:` API, run it
  on the real M4 GPU via an ordinary render pass (`harness/render_eot.m`),
  and separately extract its compiled AGX bytes via a locally-rebuilt
  `tools/shdump`/`agxparse.py` (read-only use of already-validated
  tooling; pinned hashes in `PRE_REGISTRATION.md`).
- **HW-PROBE**: pixel readback compared against a Python-computed host
  oracle at float32 precision (exact, not tolerance-based -- every tested
  value is exactly representable in IEEE-754 float32).
- A trivial host-environment check (`uname`, `/dev/dri` listing, this
  repo's own `docs/P0-P1-CLOSURE.md` P0.5 status) for H3.

No Apple binary is disassembled, decompiled, or introspected anywhere in
this experiment. No raw byte-splicing is performed (deliberate scope
bound; the paired-control + structural-presence design is the falsifier
tier used instead -- see `PRE_REGISTRATION.md` Section 2).

## Commands (reproduce)

```sh
cd experiments/EXP-0130-m4-bg-eot-construction
clang -fobjc-arc -framework Metal -framework Foundation -o harness/render_eot harness/render_eot.m
clang -fobjc-arc -framework Metal -framework Foundation -o harness/shdump ../../tools/shdump/shdump.m
python3 harness/run.py --run-id <new-id> --out-root raw   # a fresh id; run01/run02 ids are already used
python3 analysis/verify.py --selftest --seqtest --captured --run01 m4_20260828_run01 --run02 m4_20260828_run02
```

## Files

- `PRE_REGISTRATION.md`, `CAPTURE_CONTRACT.json` -- frozen before either
  official capture.
- `kernels/eot_construct.metal` -- the three authored MSL fragment
  functions.
- `harness/render_eot.m`, `harness/casematrix.py`, `harness/run.py` --
  authored capture driver. `harness/shdump`/`harness/agxparse.py` are
  local rebuilds of `tools/shdump/*` (pinned hashes, read-only use).
- `raw/host_check.json`, `raw/m4_20260828_run01/`, `raw/m4_20260828_run02/`
  -- immutable capture evidence.
- `analysis/verify.py` -- the three standing gates.
- `RESULTS.md` -- OBSERVED vs INTERPRETED, CONSTRUCTED-vs-COPIED field
  table, what P0.4 still needs.
- `PROGRESS.md` -- milestone log, including two pre-freeze bugs the smoke
  gate caught.

## Clean-room provenance

```text
Clean-room provenance: OWN-SHADER + HW-PROBE + PUBLIC (mesa/, read-only,
  cited by exact file/line; a fixed, pinned revision)
Inputs inspected: authored MSL (kernels/eot_construct.metal), authored
  ObjC harness (harness/render_eot.m, harness/run.py, harness/casematrix.py),
  our own compiled shader bytes (extracted via a locally-rebuilt,
  pinned-hash copy of tools/shdump/shdump.m + tools/shdump/agxparse.py),
  public Mesa source (mesa/, pinned revision 3c4d3e46, hashes in
  PRE_REGISTRATION.md), a trivial host-environment probe (uname, /dev/dri)
Apple binary introspection: NONE
Reproduction: see Commands above
Evidence: raw/host_check.json, raw/m4_20260828_run01/, raw/m4_20260828_run02/
  (append-only, immutable); PRE_REGISTRATION.md, CAPTURE_CONTRACT.json
  (frozen before capture); PROGRESS.md (milestone log)
```
