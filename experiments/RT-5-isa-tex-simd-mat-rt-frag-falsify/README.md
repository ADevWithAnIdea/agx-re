# RT-5 — Red-team falsification of the texture / subgroup / matrix / RT / fragment ISA

**Role:** RED-TEAM verifier. Assume the texture, subgroup, matrix, ray-tracing and fragment
findings in `docs/isa/README.md` + `docs/isa/encoding-tables.md` (and `tools/agx-isa/db.json`)
may be **subtly wrong in fields**. Run splice-and-observe tests that try to **break** the
documented claims, not confirm them. Finding nothing strengthens the docs.

**Clean-room category:** OWN-SHADER + HW-PROBE. Every byte inspected/spliced is the compiled
form of MSL *we wrote* (`kernels/*.metal`), run on the real A18 Pro GPU. No Apple binary was
disassembled. Device workspace: `~/cleanroom_work/rt5/`.

## Method
Compile our MSL → extract `_agc.main` (`tools/shdump`) → find the target instruction's byte
offset (tokenizer) → splice one/few bytes → run on hardware and read back outputs. Every
test feeds **distinct, decodable inputs** so a field's true role is unambiguous:

- **matrix:** A[i][j]=i, B[i][j]=j, C=1000 ⇒ A·B=8ij, B·A=140 (const), A·A=28i, B·B=28j —
  all four products + the accumulate are individually distinguishable, so an operand-select
  splice reveals exactly which byte picks A/B/C.
- **subgroup:** each lane gets a distinct value (lane, lane·10+5) so a reduce/shuffle/ballot
  result is a known function of the op.
- **texture:** 2–3 solid textures of distinct colour + a 2×2/2×1 filter-sensitive texture,
  2 samplers (nearest/linear); splice the slot/variant/gather bytes and watch the read-back
  colour switch.
- **fragment:** a varying with 4 distinct components (0.2/0.4/0.6/0.8); splice an `iter`
  varying-slot and watch the pixel channel walk the components.
- **RT:** a built primitive acceleration structure (triangle at z=3); trace one ray, splice
  the `rt_intersect` fields, watch the hit change.

## Harness (`harness/`) — all our own clean-room code
- `find_op.py` — compile + extract `_agc.main` + tokenize; prints each instruction's byte offset.
- `matrix_test.py` — `0xcf` operand map (A=+5 B=+6 C=+7 dst=+8 accum=+11).
- `subgroup_test.py` / `scan_test.py` — `simd_reduce`/`shuffle`/`ballot`/scan op-select + dtype.
- `texrun.m` — **compute runner with N textures + M samplers bound** (extends the agxrun pattern);
  supports a writable `rgba32float` texture dumped after (`--rwtex`).
- `tex_map.py` / `tex_slotmap.py` / `tex_samp_test.py` / `tex_variant_test.py` / `texwrite_test.py`
  — texture slot / sampler slot / variant / gather / write falsification.
- `render_test.py` (+ `agxrender`) — fragment `iter` varying-slot / mode and `frag_color_store`.
- `rtrun.m` — **RT runner: builds a primitive AS, binds it, runs a spliced compute archive.**
- `rt_test.py` / `rt_controls.py` — `rt_intersect` field splices + effectiveness controls.
- `census.py` — tokenize big compute + fragment shaders, report coverage + undecoded leaders.

## Kernels (`kernels/`)
`matmul` · `simd_reduce`/`simd_scan`/`simd_exclscan`/`simd_bcast`/`simd_xor`/`simd_ballot` ·
`tex_sample`/`tex_read`/`tex_read3`/`tex_write` · `render_vary` · `rt_query` ·
`big_compute` (subgroup+matrix+atomic+tex) · `big_frag` (3 tex, 2 samp, MRT, flat+smooth varyings).

## Results
See `RESULTS.md`. Raw runtime logs in `raw/`. Every "CONFIRMED" / "DISCREPANCY" below is a
verbatim hardware read-back. Deliverable did **not** edit `tools/agx-isa/`, `docs/`, or commit.
