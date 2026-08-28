# EXP-0092 — M4 sysval / `get_sr` ABI (Bundle C: GLIO-A02 / GLIO-A03 / GLIO-A05 / GLIO-A06)

## Question

`APPLE9_RE_OPENGL_TEXTURE_ADDENDUM.md` items GLIO-A02/A03/A05/A06, triaged as "Bundle C" in
`work/ADDENDUM-TRIAGE-20260828.md`:

- **GLIO-A02** — the complete `get_sr` operand/result model: not just the SR-number table EXP-0031
  established, but destination encoding, result width/type, the full legal SR-selector range, holes,
  first-invalid value, and observed failure mode.
- **GLIO-A03** — `base_vertex`/`base_instance` (SR `0x88`/`0x8a`) and the vertex/instance-ID/draw-ID
  family, currently carried as `(inferred)` in `docs/isa/README.md`.
- **GLIO-A05** — how a shader obtains the workgroup count (`load_num_workgroups`): SR read, uniform/
  preload, or driver-computed value, under direct and indirect dispatch.
- **GLIO-A06** — the finite-resource mandate applied per sysval touched by the above (byproduct of
  A02/A03/A05, not independently closable).

## Method

Four independent probes sharing one case matrix/runner/verifier (`casematrix.py`/`run.py`/`verify.py`):

1. **`srsweep`** — own-shader splice sweep of `get_sr`'s SR-selector byte (byte1) across its full legal
   range (0x00-0xFF, 256 cases), direct extension of EXP-0031's proven splice-and-observe method, via
   `tools/agxtest/agxtest.py` on `kernels/srprobe.metal`. `docs/isa/register-move-and-liveness.md`'s
   later-read discipline is honored: the spliced `get_sr`'s result is read by a later, separate `iadd2`,
   then a third, separate `device_store` — never inspected only via an adjacent consumer.
2. **`dstsweep`** — a register-address round trip: `get_sr`'s destination fields (`dst`+`dst_hi`) and
   `device_store`'s `index_reg` field are spliced IN LOCKSTEP to the same candidate register (a 23-point
   boundary set spanning 0-127), on `kernels/dstprobe.metal`. `device_store`'s `index_reg` is a genuinely
   separate, explicit, later register read (an address computation), satisfying the same later-read
   discipline without needing to reverse-engineer an unrelated ALU instruction's register-encoding.
3. **`drawparam`** — a real indexed+instanced draw with host-controlled, independently distinguishable
   `baseVertex`/`baseInstance`/index-buffer contents/`instanceCount`, via our own harness
   (`harness/agxvdraw.m`, own compile, **no splice**) on `kernels/vdraw_probe.metal`. The vertex function
   reads MSL's own `[[vertex_id]]`/`[[instance_id]]`/`[[base_vertex]]`/`[[base_instance]]` attributes and
   appends one record per invocation to a device buffer via an atomic counter — no rasterized-pixel
   inference needed.
4. **`numworkgroups`** — direct 3D (`dispatchThreadgroups:threadsPerThreadgroup:`) and indirect
   (`dispatchThreadgroupsWithIndirectBuffer:`) compute dispatch, via our own harness
   (`harness/agxcdispatch.m`, own compile, **no splice**) on `kernels/numwg_probe.metal`, which reads
   MSL's `threadgroups_per_grid` builtin.

Every case's expected value is computed host-side, independently, before the run (`casematrix.py`);
`run.py` never adjusts an oracle to match an observation. See `PRE_REGISTRATION.md` for the full
hypothesis/falsifier/confounder statement and `CAPTURE_CONTRACT.json` for the frozen schema.

## Commands

```sh
cd experiments/EXP-0092-m4-sysval-abi
python3 -B verify.py --selftest && python3 -B verify.py --seqtest   # required before any capture
python3 -B run.py --execute --run-id m4-20260828b-run01
python3 -B run.py --execute --run-id m4-20260828b-run02
python3 -B analysis.py --out analysis.json
python3 -B verify.py --captured
```

## Clean-room category

`OWN-SHADER` + `HW-PROBE`. `srsweep`/`dstsweep` splice bytes into our own MSL compiled through the
public `newLibraryWithSource:` API, re-assembled with the public `tools/agx-isa` DB (schema is PUBLIC;
no Apple binary introspected). `drawparam`/`numworkgroups` compile and run our own MSL natively (no
splice) with controlled draw/dispatch parameters read back through public Metal buffer APIs. No Apple
binary, framework, kext, or firmware is disassembled, decompiled, or otherwise introspected.
