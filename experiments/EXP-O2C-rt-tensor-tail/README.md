# EXP-O2C: RT completion tail + tensor ops (O2-C / O2-F)

- **Date:** 2026-07-07
- **Clean-room category:** OWN-SHADER (compile our own MSL → extract our own AGX
  bytes → byte-diff + splice-and-observe on the real GPU) + HW-PROBE (public
  `MTLDevice` capability queries; real AS build + trace/render).
- **Phase / question:** Objective-2 clusters **O2-C** (ray-tracing tail, extends
  EXP-0023) and **O2-F** (tensor/matrix ops, extends EXP-0022).
- **Device state:** Apple A18 Pro / G17P, SoC T8140, macOS 26.6 (25G5043d),
  5 GPU cores, Metal 4 / Apple9, SIP off. `supportsRaytracing=1`,
  `supportsRaytracingFromRender=1`, `supportsPrimitiveMotionBlur=1`,
  `supportsFunctionPointers(FromRender)=1` (raw/caps.txt). No faults, no reboots.

## Hypotheses

**RT tail (extends EXP-0023):**
1. `ray_data` payload has a defined copy-in/out ABI (address space + marshalling).
2. `supportsRaytracingFromRender` works and reuses the compute RT lowering.
3. `supportsPrimitiveMotionBlur` adds a *time* operand to the intersect op, not a
   new opcode.
4. The intersect op does **not** vary by primitive tag; the `0x5f` companion +
   ray-move ops are decodable memory/marshalling ops.

**Tensor (extends EXP-0022):**
5. All `mpp::tensor_ops` (beyond `matmul2d`) and matrix load/store/transpose lower
   to the same `0xcf`, not new opcodes.
6. The `0xcf` A/B/dst operand selectors, dtype, and mode are splice-decodable on a
   known matmul.

## Method (all clean-room legal)

- **OWN-SHADER:** every AGX byte comes from MSL **we wrote** (`kernels/*.metal`),
  compiled at runtime by `tools/shdump` and carved with `agxparse.py`. Multi-kernel
  files are split per-function (`splitk.py`) so one invalid tag doesn't poison the
  library. Compile failures are recorded as first-class negative results.
- **Byte-diff:** `analyze.py` (tokenizes with the read-only `tools/agx-isa/isadb`
  length rule + the EXP-0023 RT extensions) and `rt_ops.py` extract/compare the
  specific ops across provocations.
- **Splice-and-observe (HW):** `cf_decode.py` splices each `0xcf` field on `mad_f32`
  and runs it over one 32-lane simdgroup via `tools/agxtest` persistent runner,
  classifying the read-back matrix against every candidate product.
- **End-to-end HW:** `rtrender.m` builds a real triangle AS and traces from a
  **fragment** shader into an 8×8 target; `mbval.m` builds a real 2-keyframe motion
  AS and traces at 5 times. Both only observe hardware behaviour.

## Procedure

```sh
# on device (~/cleanroom_work/exp_o2c): tools built once (shdump, agxrun_persist, agxrender)
./caps                                   # capability flags
./extract.sh tensor|mpp|rtpay|rtprim|rtfrag   # compile+extract _agc.main hex (mpp/rtprim isolated)
python3 cf_decode.py                     # HW splice decode of 0xcf operands
clang -fobjc-arc -framework Metal -framework Foundation -o rtrender rtrender.m && ./rtrender
clang -fobjc-arc -framework Metal -framework Foundation -o mbval    mbval.m    && ./mbval
# on host:
python3 analyze.py raw/mains.txt         # structural census (0xcf/RT-op counts, back-edges)
python3 rt_ops.py all <fn...>            # extract rt_intersect / 0x5f / 0xdf / ray-move / rt2-27
```

## Raw results — see `raw/`

- `caps.txt` — capability flags (all YES).
- `mains.txt` — all 34 extracted `_agc.main` hex streams (group fn hex).
- `structural.txt` — per-kernel op census (0xcf, RT ops, back-edges, coverage).
- `cf_decode.txt` — **HW** `0xcf` operand splice sweep.
- `rt_ops.txt` — extracted RT instructions for byte-diff.
- `rtrender.txt` — **HW** RT-from-render 8×8 hit grid.
- `mbval.txt` — **HW** motion-blur time-interpolation.

## Analysis / established facts → docs

See `RESULTS.md` for the full write-up and `new_descriptors.json` for the DB
deltas (updated `matrix_mac` + `rt_intersect`; new `rt_ray_mem` `0x5f`,
`rt_transform_test`, `ray_move`; length-rule additions). Headlines:

- **`0xcf` operand decode HW-validated** → `docs/isa` matrix section.
- **RT-from-render + primitive motion blur HW-validated** → `docs/isa` RT section.
- **All MPP tensor ops lower to `0xcf`; transpose/load/store = memory+moves**.
- **`ray_data` payload rides the RT ray-data memory path (`0x5f`), a distinct
  address space; intersection functions invoked by traversal via the function
  table (no shader CALL).**

## Follow-ups

- Splice-validate `0x5f` / `rt_transform_test` / `ray_move` fields (needs an
  AS-aware splice testbed — `agxtest` extended to build+bind an AS).
- HW-validate the curve intersector hit and the custom-bbox-function payload path
  end-to-end (needs curve-geometry / intersection-function-table harnesses).
- The `0xcf` intra-byte register encoding (is `a_reg` `(reg<<1)|size` like the ALU?).
- The WWDC "reorder/sort" RT stage — still not visible as a single opcode.
