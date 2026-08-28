# EXP-0135 — M4 native mesh/object shading (DRV-P2-03)

## Question

`APPLE9_RE_IMPLEMENTATION_GAPS.md` row **DRV-P2-03**: "Decode dispatch,
object-to-mesh handoff, UVB/output layout and sizing, raster linkage, barriers,
indirect/ICB behavior, and allocation ownership. Otherwise do not expose it."

`experiments/EXP-0030-mesh/RESULTS.md` established this on the **A18 Pro**
(2026, G17P): mesh shading is a real hardware pipeline (graphics-path
submission, a distinct mesh-grid-dispatch VDM record, dedicated compiler
helper subroutines `_agc.object.write_childcount`/`_agc.mesh.write_uvb`), but
vertex/primitive emit itself uses ordinary `0xe7`/`0xd7` memory-store opcodes,
not a dedicated emit instruction; the only object/mesh-exclusive opcode found
was a 4-byte `0x43` control marker. That work never ran on M4 and does not by
itself meet the current implementation bar (finite-field sweeps to
first-invalid values, allocation-ownership determination, indirect/ICB
behavior) — this experiment closes that gap.

## Hypotheses

See `PRE_REGISTRATION.md` §1 (H-R re-validation, H-B payload, H-C UVB sizing,
H-D allocation/raster-linkage, H-I indirect/ICB) for the full falsifiable
statements, falsifiers, and confounders.

## Method

1. **Re-validation (Group R):** compile the A18-shaped object+mesh+fragment
   triangle (and a `primitive_count=0` control) via `shdump_mesh` +
   `agxparse.py`/`mesh_extract.py` (byte extraction, opcode census, `0x43`
   marker search) and via `iohello_mesh`/`iohello_draw`/`iohello_compute`
   under the `tools/iotrace` DYLD interposer (IOKit call-count comparison).
2. **Finite-resource sweeps (Groups B/C/D/I):** `harness/mesh_probe.m`, a
   single ObjC tool with four dispatch modes (`direct`/`indirect`/`icb_cpu`/
   `icb_gpu`), compiles `kernels/mesh_sweep.metal` (or the object-less
   `mesh_indirect.metal`) with per-case preprocessor macros
   (`NV`/`NP`/`PAYLOAD_BYTES`/`AMP_COUNT`), builds the mesh pipeline, and
   dispatches + reads back pixels — one case, one process, one changed
   variable, matching CLAUDE.md's recovery model. `analysis/gen_matrix.py`
   generates the fixed 103-case matrix; `analysis/run.py` executes it with a
   hard 30s per-case timeout and an automatic post-fault sanity re-check.
3. Two independent official runs (`raw/m4_20260828_run01/`,
   `raw/m4_20260828_run02/`); `analysis/verify.py --selftest/--seqtest/--captured`
   gate reproducibility.

## Commands

```sh
python3 analysis/verify.py --selftest
python3 analysis/run.py --run-id m4_YYYYMMDD_runNN     # x2, distinct ids
python3 analysis/verify.py --seqtest  --run01 <id1> --run02 <id2>
python3 analysis/verify.py --captured --run01 <id1> --run02 <id2>
```

## Clean-room category

**OWN-SHADER + HW-PROBE + DATA-TRACE + bounded PUBLIC** (public Metal.framework
headers and public MSL toolchain headers read for interface signatures only —
never Apple binary introspection). See `RESULTS.md` for the full attestation.

## Files

- `PRE_REGISTRATION.md`, `CAPTURE_CONTRACT.json` — frozen hypotheses/matrix.
- `kernels/` — our own authored MSL (mesh_sweep, mesh_indirect, mesh_icb_gpu,
  compute_emul).
- `harness/` — mesh_probe.m (main probe), shdump_mesh.m + agxparse.py +
  mesh_extract.py (byte extraction), iohello_mesh.m (DATA-TRACE).
- `analysis/` — gen_matrix.py, run.py, verify.py, iotrace_parse.py, fixtures/.
- `raw/m4_20260828_run01/`, `raw/m4_20260828_run02/` — the two gated captures.
- `work/` — build artifacts + the non-recorded smoke run (not evidence).
- `RESULTS.md` — findings, OBSERVED vs INTERPRETED, A18-vs-M4 comparison.
