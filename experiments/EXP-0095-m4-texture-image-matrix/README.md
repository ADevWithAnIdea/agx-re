# EXP-0095 M4 texture/image dimension-and-format operation matrix

Public-Metal behavioral execution matrix (compile / pipeline-create / dispatch / CPU-owned-buffer
readback) answering addendum Bundle E: **GLTEX-A04, GLTEX-A05, GLTEX-A06, GLTEX-A07, GLIMG-A01,
GLIMG-A02** (`APPLE9_RE_OPENGL_TEXTURE_ADDENDUM.md`), on the local M4 (G16G). Successor/deepening
work for `TEX-09`, `TEX-11`, `TEX-13`, `TEX-23`, `DRV-TEX-01`, `DRV-FMT-01`, `ATOM-*`, and builds
directly on `EXP-0034` (texture-variant instruction completeness), `EXP-0083` (base-slot census
methodology, applied here to image/PBE descriptor capacity), and `EXP-0079`
(typed-format-conversion gate/harness pattern this experiment's `run.py`/`verify.py` are adapted
from).

**85 frozen cases** across eight sub-families: `a05` (1D/1D-array op matrix, 12 cases), `a06`
(shadow/cube/cube-array compare matrix, 8), `a04` (array-layer conversion + boundary, 7), `a07` +
`a07_descriptor` (texel-buffer boundary, 11 + 4), `a01` (image load/store/size op×dimension matrix,
23), `a02_direct` + `a02_bindless` (image-descriptor capacity census, 4 + 16). Full per-case detail,
hypotheses, and falsifiers: `PRE_REGISTRATION.md`; frozen matrix: `CAPTURE_CONTRACT.json`.

Method: a single generic ObjC harness (`harness/probe.m`) reads one case's parameters as a JSON blob
(`--args`) describing textures/samplers/uniform-buffers/argument-buffers to create and a sequence of
compute dispatches to run, all drawn from ~74 authored MSL kernels
(`kernels/matrix.metal` + generated `kernels/direct128.metal`). Content is CPU-populated via
`replaceRegion:`/direct buffer writes wherever possible (avoiding circularity between a probe and its
own fixture); every output buffer carries a 16-byte 0x5a/0xa5 guard frame around a 16-word
0xEEEEEEEE-sentineled result region, so an unexpected write is directly visible downstream — the
`docs/isa/register-move-and-liveness.md` discipline ("validate by a downstream consumer read, never
the producing instruction's own result alone") applied to public-Metal image operations rather than
ISA splicing.

Pre-freeze exploration (not evidence; `provenance/pre_freeze/`) shaped the matrix: MSL's real 1D
operation surface, native-atomic dimension support, the 128-entry direct texture-argument-table
ceiling (with a separate 8-entry `read_write` sub-ceiling), the texel-buffer 2^28-element width
ceiling, and the same-thread same-invocation `t.fence()` requirement for write-then-read visibility.
See `PRE_REGISTRATION.md` for the full list and how each shaped a frozen hypothesis.

## Commands (in order)

```sh
python3 -B verify.py --selftest                        # required before any build
python3 -B verify.py --seqtest
python3 -B make_manifest.py --write && python3 -B make_manifest.py --check
python3 -B verify.py --preflight                        # PRE_GPU: no raw tree may exist
python3 -B run.py --execute --run-id m4-20260829-run01
python3 -B make_manifest.py --write && python3 -B make_manifest.py --check
python3 -B verify.py --between-runs
python3 -B verify.py --selftest                          # must still run with run01 present
python3 -B verify.py --seqtest
python3 -B run.py --execute --run-id m4-20260829-run02
python3 -B analysis.py --run-a m4-20260829-run01 --run-b m4-20260829-run02 --write
python3 -B make_manifest.py --write && python3 -B make_manifest.py --check
python3 -B verify.py --captured
```

Clean-room provenance: HW-PROBE / OWN-SHADER / PUBLIC
Inputs inspected: authored MSL/harness/runner/verifier/analysis sources only; `MTLPixelFormat`
public API surface and MSL public standard-library header *syntax* (calling conventions only, not
hardware behavior) consulted for correct public API usage
Apple binary introspection: NONE
Reproduction: the command sequence above, from this directory
Evidence: `raw/m4-20260829-run01`, `raw/m4-20260829-run02`, `analysis.json`, `manifest.json`
