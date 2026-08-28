# Part-II answer blocks, wave 2 — ready to splice into `APPLE9_RE_IMPLEMENTATION_GAPS.md`

**Do not edit `APPLE9_RE_IMPLEMENTATION_GAPS.md` from this file by hand.** Each section gives an
`ANCHOR:` line copied byte-for-byte from the task list, followed by the block to insert
**immediately after that line, separated by one blank line**, with the same `  > ` indentation as
the blocks already in the file. Every anchor below was verified unique (`grep -Fxc` == 1) at the
time of writing. Companion: `work/GAPS-ANSWER-BLOCKS.md` (wave 1), `work/GAPS-COVERAGE.md`.

**Scope of this wave.** A desk pass over the committed corpus against the 27 items
`work/GAPS-COVERAGE.md` listed as UNANSWERED. No GPU work was run (three GPU-contending agents
were live). Verdicts and numbers are copied from the cited `RESULTS.md` / `validation.json`;
nothing is inferred into an answer.

**Two numbering warnings a reader must not miss.**

1. **Part-II `P2-01..06` are NOT the Part-I `DRV-P2-01..05` rows.** Part-II `P2-*` is
   BF16 / cooperative-matrix / mesh-stage / ray-query / FP64. `DRV-P2-*` is lossless compression /
   tessellation / mesh / ray tracing / Metal-unreachable encodings. EXP-0134 ("P2-01"), EXP-0135
   ("P2-03") and EXP-0136 ("P2-05") name themselves after the **`DRV-P2-*`** rows. They are cited
   below only where they genuinely bear on the Part-II question, never by id-matching.
2. **`I64-01..06` is CLOSED by EXP-0146**, and a splice-ready block already exists at
   `experiments/EXP-0146-m4-emit-int-misc/analysis/I64_answers.md` (anchor:
   `  These answers validate the current \`lower_int64_options\` mask instead of merely inheriting it.`).
   It is not restated here. `work/GAPS-COVERAGE.md` predated it and has been corrected.

**Two classes of block below, labelled inline.**
`[HW]` — the verdict is a hardware observation copied from an experiment.
`[DESK-AUDIT]` — the question asks *"is X fully hardware-validated / completely known?"*; the
answer is a checkable statement about the committed evidence record (`tools/agx-isa/validation.json`
per-field labels, per `docs/evidence-classification.md`), not a new hardware fact. These are
first-class **No** answers under `CODEX.md` §7, and each names exactly what would flip it.

---

### ANCHOR:   this compiler?**

  > **Answered 2026-08-28 (desk pass over EXP-O2D / EXP-M4-13 / EXP-M4-02) — P2-01 PARTIAL. [HW +
  > DESK-AUDIT]**
  > **The hardware half is YES; the emit half is NO.**
  > **Native BF16 scalar AND packed arithmetic exists and is a distinct instruction group** —
  > byte0 `0x11`, *not* the `0x10` native-fp16 group and *not* an fp32 widen/narrow lowering
  > (a single `0x11` op does the add; no widen-add-narrow sequence appears). `byte+1 = 0x02`
  > selects the **scalar** form, `byte+1 = 0x04` the **packed `bfloat2`** form; `byte+2` opsel
  > `0x1c` add / `0x1d` mul / `0x1e` fma (the fma form is 10 bytes, add/mul 8). The add/mul
  > selector is the only bf16 field ever executed: splicing `byte+2 0x1c -> 0x1d` flipped a
  > native bfloat `1+2` into `1x2` (EXP-O2D, **A18 target**). Conversion is a separate 8-byte
  > `cvt_bf16`: `byte+1` source width (`0x03` f32, `0x02` f16), `byte+6` direction (`0x40` result
  > bfloat, `0x80` result half); bfloat->float is a free widen because bf16 is the top 16 bits of
  > fp32 (EXP-M4-13, **M4 target**, corpus-correlation). `bf_add_dst`/`bf_mul_dst`/`bf_fma_dst`
  > generalise the group to any destination register (EXP-M4-13, M4, corpus-correlation).
  > BF16 also reaches the matrix unit: every correct bf16 `simdgroup_matrix` spelling compiles on
  > M4 and is **identical to A18** (EXP-M4-02; the one apparent M4 delta was a flaw in our own MSL
  > — a `1.0` *double* literal where the scalar-broadcast constructor wants `vec<bfloat,64>` — not
  > a hardware or compiler difference).
  > **Why the answer is not a plain Yes: no bf16 operand field has ever been executed.** In
  > `tools/agx-isa/validation.json`, `bf_alu.srcA`/`srcB` are `untested`, its `tail` is
  > `tokenization-only`; `bf_add_dst`/`bf_mul_dst`/`bf_fma_dst` have `dst`/`srcA`/`srcB`/`srcC`/
  > `tail` all `untested`; `cvt_bf16` has 5 of its 8 fields `untested`; `bf_alu8_var` is
  > `tokenization-only` throughout. Per `docs/evidence-classification.md`'s **`emittable` rule**,
  > the whole bf16 family is therefore **"decodable, not yet emittable"** — a backend can be told
  > the group exists and which opsel byte selects add/mul/fma, but cannot yet be told which byte
  > carries an arbitrary source register, and on Apple9 a wrong operand field yields a **silent
  > zero, not a fault**.
  > **Conservative compiler response until that changes:** do not expose a native NIR bf16 ALU
  > type; keep bf16 as a storage/convert type (widen to fp32 for arithmetic), and route
  > cooperative-matrix bf16 through the `0xcf` matrix path (P2-03), which *is* emittable.
  > A live successor exists: `EXP-0145-m4-emit-bf16-half` was running at the time of this pass and
  > had no committed `RESULTS.md`; it is the experiment that would flip this to a plain Yes.
  > Targets as stated per fact (A18 for the executed opsel splice; M4 for the corpus location);
  > no bf16 claim here is M4-executed.
  > Evidence: `experiments/EXP-O2D-compute-frag-tail/`, `experiments/EXP-M4-13-full-corpus/`,
  > `experiments/EXP-M4-02-capabilities/`, `tools/agx-isa/validation.json`
  > (`bf_alu`, `bf_add_dst`, `bf_mul_dst`, `bf_fma_dst`, `bf_alu8_var`, `cvt_bf16`).

---

### ANCHOR: - **P2-02 — Are BF16 conversion, rounding, denormal, and NaN semantics fully hardware-validated?**

  > **Answered 2026-08-28 (desk audit of the committed evidence record) — P2-02 NO. [DESK-AUDIT]**
  > **No committed experiment has measured a single BF16 numeric result.** The FP semantics work
  > (EXP-0103, M4/G16G, commit `bbb1e9fc`) is explicitly FP32 and FP16 only — its own limitations
  > section records "No FP64, no non-default rounding modes" and it never lists a bfloat kernel;
  > the packed-conversion work (EXP-0102, commit `958f8307`) covers unorm/snorm/half packing, not
  > bf16. The exhaustive sweeps that exist for the neighbouring types — 65536/65536 bit-exact for
  > the packed converts, 1886/1886 RTE for fp32->int, the 65536-pattern FP16 subnormal survey —
  > have **no bf16 counterpart anywhere in `experiments/`**.
  > What *is* on record is structural only: the `0x11` group's existence and its add/mul opsel
  > (EXP-O2D, A18 splice), and `cvt_bf16`'s source-width and direction bytes located over an
  > own-MSL corpus (EXP-M4-13, M4, `corpus-correlation`). Nothing states bf16's rounding mode, its
  > denormal handling (fp32's DAZ+FTZ model established by EXP-0074/EXP-0103 must **not** be
  > assumed to transfer — FP16 already contradicts it, preserving subnormals where FP32 flushes),
  > or its NaN contract.
  > **Required compiler response:** treat bf16 rounding/denormal/NaN as `UNKNOWN`. Where the
  > result is observable, widen to fp32, operate, and convert once — do not rely on a native bf16
  > op reproducing any particular rounding. A future experiment closing this must run the same
  > shape EXP-0103 ran for fp32/fp16: directed exceptional values plus a dense sweep, scored
  > against a host oracle, on M4.
  > M4 target for the corpus location; A18 target for the one executed splice; **no bf16 numeric
  > observation on either target.**
  > Evidence (absence is the finding; these are the files that would have contained it):
  > `experiments/EXP-0103-m4-fp-transcendental-semantics/RESULTS.md`,
  > `experiments/EXP-0102-m4-int-pack-semantics/RESULTS.md`, `tools/agx-isa/validation.json`.

---

### ANCHOR:   cooperative-matrix operations?**

  > **Answered 2026-08-28 (EXP-0147, M4/G16G, commit `487caaad`; operand semantics EXP-0022 /
  > EXP-O2C / RT-10, A18) — P2-03 YES, upgraded this wave. [HW]**
  > **`matrix_mac` is now EMITTABLE.** EXP-0147 swept the two fields that were blocking it and
  > promoted both, so all **12 of 12** fields are `hardware-run` or `isolated-byte-diff` and the
  > family clears `docs/evidence-classification.md`'s `emittable` rule
  > (`analysis/emittability.json`: `blocking_after: []`, `emittable_after: true`).
  > `dst_desc` (byte+9): all **256/256** values, twice, 100 % cross-run agreement — correct
  > `A*B+C` iff **bit6 = 1 and bit7 = 0** (64 values); `0x00-0x3f` and `0x80-0xbf` give a **silent
  > zero**; `0xc0-0xff` give a wrong value. `b11hi` (byte+11 bits 1-7): all **128/128** values,
  > twice — correct iff **`(b11hi & 3) == 0`** (32 of 128). Liveness was proven, not assumed:
  > forcing the op-enable byte+10 `0x24 -> 0x00` drops the multiply and the read-back becomes C
  > passthrough, in both runs, on M4.
  > **A hardware capability Metal never emits was found in the process:** `b11hi`'s two low bits
  > are **accumulator sign controls**, resolved per tile row — `0` = `+C` everywhere, `1` = `-C`
  > on rows 0-3 only, `2` = `-C` everywhere, `3` = `-C` on rows 4-7 only. So the matrix unit does
  > **`A*B - C`** and a **half-tile** variant, neither of which
  > `simdgroup_multiply_accumulate` ever produces.
  > Selection constraints a NIR cooperative-matrix lowering must respect, from the prior decode:
  > one `0xcf` = one full **8x8x8** tile MAC (512 MACs), row-major
  > `d[i][j] = C[i][j] + sum_k A[i][k]*B[k][j]`; `byte+1` dtype `0x00` = 16-bit half, `0x02` =
  > 32-bit float (bfloat shares the 32-bit datapath with input conversion); `byte+2` mode `0x56`
  > standalone vs `0x54` tiled, and **mode is semantic, not a hint** — splicing standalone->tiled
  > **zeroes** the result because tiled mode sources its accumulator from the MPP tile context;
  > `byte+11` bit0 = accumulate-enable (`simdgroup_multiply` clears it); operand identity is
  > unambiguous (byte+5 = A, byte+6 = B, byte+7 = C, byte+8 = dst, proven by splicing A to B's
  > register -> `B*B` and swapping +5/+6 -> `B*A`, matmul being non-commutative). **Only 8x8 is
  > exposed** (16x16 / 8x16 / 4x4 / 32x32 rejected); element types half, float, bfloat including
  > mixed half/bfloat -> fp32 accumulate; **all integer matrices are REJECTED** (no int8
  > cooperative matrix), so a Vulkan int8 cooperative-matrix path must be emulated in the ALU.
  > All MPP tensor ops (`matmul2d` multiply / multiply_accumulate / transpose / f32 / 16x16x16 /
  > 2-simdgroup) lower to this same opcode — there is no separate tensor opcode; transpose is
  > data movement (`ray_move`-family 4-byte ops), and `simdgroup_load`/`store` (including
  > `transpose:true`) are ordinary `0x67`/`0xe7` memory ops.
  > **Target split, stated rather than blurred:** the two newly promoted fields and the liveness
  > proof are **M4**; the operand-selector, dtype, mode, `a_desc` and accumulate-enable results
  > are **A18** (EXP-0022 / EXP-O2C / RT-10-isa-pass2), and `matrix_mac`'s rows in
  > `tools/agx-isa/validation.json` still carry `target: A18` because that file has not yet been
  > regenerated with EXP-0147's promotions. The baseline encoding executes correctly on M4.
  > One recorded caveat carried forward: the `0x24` op-enable value is **fp32-datapath-specific** —
  > the half datapath (dtype `0x00`) uses byte+10 `0x8c` / byte+11 `0x00` and **its accumulate
  > byte is uncharacterized**.
  > Evidence: `experiments/EXP-0147-m4-emit-pipeline-misc/` (§2.1, `analysis/field_verdicts.json`,
  > `analysis/emittability.json`; 2 gated runs, 12 532 cases each, 98.37 % cross-run agreement),
  > `experiments/EXP-0022-simdgroup-matrix/`, `experiments/EXP-O2C-rt-tensor-tail/`.

---

### ANCHOR:   enough for independent compilation?**

  > **Answered 2026-08-28 (desk pass over EXP-0135 / EXP-0147 / EXP-0030 / EXP-M4-13) — P2-04 NO.
  > [HW + DESK-AUDIT]**
  > **The mesh/object *pipeline* contract is well characterized on M4; the mesh/object *stage ISA*
  > is not, and that is what this question asks for.**
  > What IS established (EXP-0135, M4/G16G, commit `661f1258`, 107 records per run x 2 runs,
  > 107/107 byte-exact on the gated fields): mesh is a **native hardware pipeline on M4**, with
  > both fixed-size compiler helper subroutines **byte-length-identical to A18** (128 B
  > `write_childcount`, 576 B `write_uvb`) and the `43 00 00 01` pre-call frame marker present
  > exactly once in each of the object and mesh streams, byte-identical whether or not the mesh
  > emits a triangle. Hard capacities: object->mesh payload **16,384 B**, enforced at
  > *pipeline-creation* time; UVB output **256 vertices** and **512 primitives** per meshlet, two
  > independently-capped fields (256 != 512), both enforced at *MSL-compile* time. Grid
  > amplification genuinely drives the rasterizer but **silently dies at exactly 65,536**
  > threadgroups (`STATUS OK`, zero error) against Metal's own reflected ceiling of 1,048,576 —
  > independently reproduced on the unrelated top-level indirect-draw mesh-grid mechanism. Buffer
  > allocation is **firmware-managed** (the 37-BO sel-9 size multiset is byte-identical across a
  > payload / vertex-count / primitive-count / amplification sweep).
  > What is NOT established, and blocks "independent compilation": **no field of any mesh-stage
  > instruction has ever been executed.** `mesh_out_src` (the 2-byte compact source op feeding the
  > following `0xe7` store) is `corpus-correlation` with its `sel` field `untested`, and EXP-0147
  > **pre-registered `mesh_out_src.sel` as not attempted** because it needs an object/mesh render
  > pipeline that harness does not build — it remains `untested` with that reason recorded.
  > `ibfe_mesh_attr` (bitfield-extract of a packed flat per-primitive mesh attribute, source-address
  > mode `byte+2 == 0x66`) is likewise `corpus-correlation` only. So the mesh **varying/output**
  > encoding is located but not emittable, and no experiment has isolated mesh/object-stage
  > **register** conventions, a stage-specific **barrier**, or the stage **termination** sequence
  > as distinct from the generic `threadgroup_barrier`/`stop`.
  > One interpretive correction EXP-0135 recorded and this block carries: the `0x43` marker is
  > **not** object/mesh-exclusive — `tools/agx-isa`'s DB already generalizes it to a pre-call
  > frame-setup marker appearing before every out-of-line CALL in any stage; object/mesh merely
  > hit it because their compiler-generated helpers are call sites. EXP-0030's narrower framing is
  > superseded on this point, not contradicted.
  > **Required compiler response:** treat the mesh/object stages as pipeline-level capabilities
  > with documented capacities, not as an independently compilable stage; a driver must still
  > obtain mesh-stage code from a path it does not synthesize field-by-field. Closing this needs a
  > mesh-pipeline splice harness — the same successor EXP-0147 names.
  > M4 target throughout (EXP-0030's A18 figures are cited for comparison only); A18 deferred.
  > Evidence: `experiments/EXP-0135-m4-mesh-object-shading/`,
  > `experiments/EXP-0147-m4-emit-pipeline-misc/RESULTS.md` §1 and §5,
  > `experiments/EXP-0030-mesh/`, `tools/agx-isa/validation.json` (`mesh_out_src`,
  > `ibfe_mesh_attr`).

---

### ANCHOR:   complete enough for independent NIR lowering?**

  > **Answered 2026-08-28 (desk audit over EXP-0023 / EXP-M4-14 / EXP-O2C / EXP-M4-13) — P2-05 NO.
  > [DESK-AUDIT]**
  > **Ray tracing is proven native and end-to-end functional, but only 2 of the ~13 committed
  > ray/query instructions have any hardware-run field, and both were validated on A18.**
  > Established: `raytracing::` kernels emit opcode groups a hand-written software Moller-Trumbore
  > loop never produces (dedicated ray-intersect op, byte0 low-nibble `0x4` / `byte+1 0xea`, and
  > dedicated AS/ray-data loads byte0 `0xdf`; the software control contains **zero** of either),
  > so the silicon is real — but traversal is a **compiler-generated software BVH loop**
  > (a back-edge at offset -88), not a fire-and-forget trace instruction (EXP-0023, **A18**).
  > `rt_intersect` is `hardware-run` (6 known rays against a built acceleration structure returned
  > correct t / prim / barycentrics; EXP-0023 + RT-5, **A18**) and `rt_query_traverse` is
  > `hardware-run` (`intersection_query` committed-distance against a 2-triangle AS, near `t=1` /
  > far `t=5`, with every byte of the load swept; EXP-M4-14, **A18**).
  > Everything else in the family is decode-only in `tools/agx-isa/validation.json`:
  > `rt_as_load` and `rt_ray_mem` are `corpus-correlation` with the explicit note *"the traversal
  > loop they drive was executed end to end, but no field of this op was independently"* validated;
  > `rt_ray_mem_ldidx`, `rt_ray_mem_short`, `rt_transform_test`, `rt_query_traverse2`,
  > `ray_move_copy6`, `ray_move_zero6`, `ray_move_zinit` are "located and length-anchored over the
  > own-MSL RT corpus" (M4, `corpus-correlation`); `n4_rt_word` is `tokenization-only`.
  > That maps onto the question's four parts as: **operands** — not established beyond the two
  > executed ops; **control flow** — the traversal loop shape is observed, not specified;
  > **memory layout** — the ray/query struct marshalling ops are located but no field is decoded,
  > and the **BVH node format is GPU/firmware-authored and opaque to userspace** in a layout
  > userspace never constructs (EXP-0023 §"the BVH build is GPU/firmware-managed"), which is a
  > kernel/firmware coordination item rather than a userspace lowering input;
  > **synchronization** — untouched.
  > **Required compiler response:** do not attempt an independent NIR ray-query lowering. Consume
  > ray-tracing through whatever path supplies compiled traversal code, and coordinate the BVH
  > builder with the kernel/firmware team. Flipping this needs the ray/query family's operand
  > fields swept the way EXP-0147 swept `matrix_mac` — on **M4**, since the two executed results
  > are A18-era.
  > A18 target for both executed results; M4 target for the corpus locations; **no ray/query
  > operand field is M4-executed.**
  > Evidence: `experiments/EXP-0023-raytracing/`, `experiments/EXP-M4-14-a18-splice/`,
  > `experiments/EXP-O2C-rt-tensor-tail/`, `tools/agx-isa/validation.json` (`rt_*`, `ray_move*`,
  > `rtq_*`, `n4_rt_word`).

---

### ANCHOR:   usable residency code for every filtered, gathered, and fetched form?**

  > **Answered 2026-08-28 (EXP-0122, M4/G16G, commit `f2b8ef66`) — TEX-12 PARTIAL: the *unmapped*
  > *fetched* quadrant is closed; mapped, filtered, gathered and the residency code are open.
  > [HW]**
  > **UNMAPPED, fetched form — CLOSED.** Across 4 configurations (single-tile page16, multi-tile
  > 4x4 page16, single-tile page64, and a degenerate tile-larger-than-texture page256 case) x 3-5
  > coordinates each, **every coordinate in every configuration** read back all-zero component
  > bytes with `cb_status = 4` (completed) and **no error**, in all 4x2 = 8 executions
  > (`analysis/summary.json: sparse_unmapped_read.every_case_all_zero == true`). Unmapped
  > sparse-texture access is **fault-free and reads as zero** — the same quiet-zero model already
  > established for buffer OOB (EXP-0076), holding uniformly across all four tile-size/texture-size
  > relationships.
  > **MAPPED — a confirmed, reproducible NEGATIVE that this item must not lose.** Mapping one tile
  > via `MTLResourceStateCommandEncoder updateTextureMapping:mode:region:mipLevel:slice:` has a
  > real, correctly-sized effect (`heap.usedSize` grows by **exactly** one tile: 16384 B for the
  > single-tile case, one 16384 B tile of the 65536 B four-tile case). But a compute-kernel write
  > into a coordinate inside that freshly-mapped tile, read back on a separate
  > `waitUntilCompleted`-serialized command buffer, returns **all-zero, not the written pattern**
  > (`write_appears_to_persist == [false, false]`), and a three-stage read-after-write /
  > read-after-unmap / read-after-remap probe reads all-zero at **every** stage. Every
  > public-API synchronization explanation was tried and ruled out (`hazardTrackingMode = .tracked`,
  > an explicit `MTLFence`, `useResource:`/`useHeap:`, a 500 ms delay, reduction to one tile in a
  > single-tile texture, `setPurgeableState: .nonVolatile`), and an identical non-sparse
  > heap-allocated private texture writes and reads back correctly through both a compute read and
  > a blit copy — isolating the negative to the `MTLHeapTypeSparse` path specifically. **Root cause
  > is not established.** The named untested candidate is the macOS 26 `placementSparsePageSize` /
  > `MTLHeapTypePlacement` / `MTL4UpdateSparseTextureMappingOperation` path, which this experiment
  > never touches.
  > **Still open, explicitly:** (a) the **residency code** — EXP-0122's kernels are
  > `tex.read(coord)` on `access::read` only, so no `sparse_color` / `.resident()` form was ever
  > exercised; (b) the **filtered** and **gathered** forms — no sampler was bound in any sparse
  > case; (c) mapped-texel colour correctness, which is blocked behind the write-persistence
  > negative above; (d) sparse aliasing between two resources (only single-resource mapping tested).
  > Supporting geometry established in the same experiment: `sparseTileSizeInBytes = 16384`, and
  > `sparseTileSizeInBytesForSparsePageSize:` returns **16384 / 65536 / 262144** for
  > `MTLSparsePageSize{16,64,256}` — at least three page-size classes exist, so a driver must query
  > rather than assume the legacy 16 KiB tile.
  > **Conservative driver response meanwhile:** a Vulkan `sparseResidency*` implementation gets
  > non-faulting zero-return for unmapped fetches for free on M4, but must not advertise
  > residency-code queries or filtered/gathered sparse sampling, and must not assume a mapped tile
  > is writable through the classic `MTLHeapTypeSparse` path.
  > M4 target; A18 deferred. Runs `raw/m4-20260828-run01`, `raw/m4-20260828-run02`, 87/87 cases,
  > **0 mismatches** on the cross-run gate.
  > Evidence: `experiments/EXP-0122-m4-sparse-vm-conventions/RESULTS.md` §3.1-3.5,
  > `analysis/summary.json`, `kernels/sparse_access.metal`.

---

### ANCHOR:   Record API rejection separately from raw shader behavior: zero, alias, fault, or device loss.

  > **Answered 2026-08-28 (EXP-0095, M4/G16G) — TEX-20 PARTIAL: the unpopulated-entry sub-question
  > has a recorded M4 verdict; the >= 1,000,000 and nonresident sub-questions remain DEFERRED as
  > EXP-0106 recorded. [HW]**
  > **Unpopulated / out-of-range bindless texture entry — recorded verdict (EXP-0095's
  > finite-resource table, M4, HW):** with a genuine runtime `uint` selector into a
  > driver-declared array of size `CAP`, entries `[K, CAP-1]` that were never encoded **behave
  > identically to true out-of-bounds**, and both they and `index >= CAP` give **silent zero on a
  > load** and are **silently dropped, with no aliasing, on a store or atomic**. Explicitly: *no
  > mirroring or aliasing risk was observed*, which is the opposite of the buffer base-slot family,
  > where an out-of-range base slot silently **aliases** a real slot (EXP-0083). Tested at
  > `CAP = 256` with `K = 8` populated canaries, with feasibility-only exploration to `N = 4096`.
  > Practical consequence: it is **safe to leave argument-buffer texture entries unbound**.
  > **Still open (both recorded DEFERRED by EXP-0106, commit `2858c20f`):** (a) behaviour at an
  > index **at or above 1,000,000** — EXP-0095 established the pattern only to index 512, and
  > confirming it at the documented ceiling is a large allocation-and-sweep campaign, not a small
  > addition; (b) the **nonresident-resource** case — no experiment in the corpus exercises a
  > texture made non-resident (`useResource:` withheld) behind a bindless index.
  > No API-rejection half was observed to separate here: the failures above are raw shader
  > behaviour, and no Metal-level rejection occurred at any tested index.
  > **Conservative driver response meanwhile:** rely on silent-zero/silent-drop only within the
  > declared `CAP`; bounds-check any index a shader could drive past the declared array size, and
  > do not assume the ceiling behaviour extrapolates from `CAP = 256` to 1,000,000.
  > M4 target; A18 deferred.
  > Evidence: `experiments/EXP-0095-m4-texture-image-matrix/RESULTS.md` (bindless rows of the
  > finite-resource table, and §"Bindless capacity beyond the declared CAP=256 array"),
  > `experiments/EXP-0106-m4-texture-isa-semantics/RESULTS.md` (TEX-19/TEX-20 deferral scope).

---

### ANCHOR:   32x/64x/128x, and what does each unsupported code do?**

  > **NOT one of the 27 open items — this is a refinement that UPGRADES the existing TEX-26
  > `PARTIAL` (raw-field half) to a full answer. Splice at the orchestrator's discretion.**
  > **Answered 2026-08-28 (EXP-0136, M4/G16G, commit `2e2bc21a`) — TEX-26 raw half CLOSED: NO,
  > anisotropy is NOT limited to 16x. [HW]**
  > **The sampler hardware natively resolves anisotropy to at least 128x; Metal's 16x cap has zero
  > hardware backing.** Patching the sampler descriptor's 3-bit log2 `maxAnisotropy` field
  > (byte2 bits[4:6]) to codes 5/6/7 (= 32x/64x/128x, values the public API can never produce) and
  > sampling a hand-authored mip chain under an explicit `gradient2d` derivative gives a
  > **measured, monotonic, threshold-exact quality effect**, not merely "does not fault"
  > (16/16 cases, byte-identical across both runs):
  > at derivative ratio 16, real aniso 1/2/4/8 blur to 0.498 and real aniso 16 resolves to 1.000;
  > at ratio 64, real aniso 16 blurs (0.498) and patched 64x/128x resolve (1.000);
  > at ratio 128, only patched 128x resolves. The patched value resolves **exactly when it is
  > `>=` the ratio** — the signature a genuine unclamped anisotropic filter produces.
  > This does not contradict the previously recorded API half (EXP-M4-08, M4+A18 cross-confirmed):
  > requesting `maxAnisotropy = 32` through the public API still clamps all the way to **field 0
  > (1x)**, not to 16x. Both are true — the clamp is pure software.
  > **Finite-resource row:** sampler max anisotropy, 3-bit log2 field, **HW-usable 1x..128x, all 8
  > codes functionally distinct and correctly resolving**, Metal-exposed 1x..16x, first
  > Metal-unreachable value that works = **32x (code 5)**. An implementer may expose anisotropy
  > above 16x. Tested range: aniso codes 0-7, ratios 16/64/128 only (power-of-two ratios at the
  > code boundaries; intermediate ratios such as 20:1 or 48:1 were not swept and would refine the
  > crossover shape without changing the headline).
  > **TEX-27's raw half (lodMax field > 112, i.e. above 14.0, up to 127 = 15.875) was NOT tested by
  > this experiment and remains open.**
  > M4 target; A18 deferred. 97/97 cases per run x 2 runs, `cross_run_gate_pass: true`,
  > `issues_total: 0`.
  > Evidence: `experiments/EXP-0136-m4-unreachable-encodings/RESULTS.md` §1 and §9.

---

### ANCHOR:   semantic limit from the values Metal happens to emit.

  > **Answered 2026-08-28 (EXP-0136, M4/G16G, commit `2e2bc21a`) — TEX-28 PARTIAL: address, border
  > and swizzle are CLOSED; the filter sub-field is not. [HW]**
  > This supersedes the "TEX-28 DEFERRED — address codes 4/6/7 and border code 3 remain untested"
  > line in the EXP-0106 block for the address and border halves.
  > **Address modes — all three unnamed codes are exact, deterministic hardware ALIASES.** A
  > 4-point signature (u = 1.2, 1.7, 2.6, -0.4; v = 0.5; `address_t = clampToEdge` throughout),
  > 32/32 cases, byte-identical across both runs: **code 4 is byte-identical to code 0
  > (clampToEdge)** at all 4 points; **codes 6 and 7 are both byte-identical to code 3
  > (clampToBorder)** at all 4 points. Not garbage, not faults, not new modes. The method has
  > proven power to see a real difference: code 5 (`mirrorClampToEdge`) in the same test shows
  > itself **genuinely distinct**, matching code 0 at 3 of 4 points and diverging at u = -0.4.
  > **The 3-bit/8-value address field is hardware-limited to exactly 5 distinct behaviours** — the
  > same 5 Metal exposes. Tested range: 8 codes x 4 UV points, all outside [0,1]; in-range u and
  > the 3D `address_r` axis were not tested.
  > **Border colour — code 3 is an exact alias to preset 0 (transparent black),** adversarially
  > confirmed across **3 different creation contexts** (samplers created transparentBlack /
  > opaqueBlack / opaqueWhite all read (0,0,0,0) when patched to code 3), 12/12 cases. The same
  > test carries its own falsifier: codes 0/1/2 read their expected preset regardless of the
  > creation-time value, so the patch — not the creation value — controls the field. **There is no
  > 4th preset and no room for an arbitrary RGBA border colour**, so Vulkan
  > `VK_EXT_custom_border_color` must be software-emulated.
  > **Swizzle — the unnamed codes are deterministic INVALID values, the one family here where the
  > hardware actively rejects rather than aliases.** Codes 0-5 reproduce the predicted channel
  > routing exactly (R, G, B, A, constant-1, constant-0), upgrading EXP-0015's DATA-TRACE-only
  > swizzle table to **HW-VALIDATED by direct construction**; **codes 6 and 7 hard-fault the
  > command buffer** (`CMDBUF_ERROR`, GPU-hang class, fault-contained, no host wedge), tested on
  > component0 (both codes) and component1 (code 6). 11/11 cases.
  > **Filter — NOT closed, and this is the item's remaining half.** EXP-0136 did not probe the
  > filter enums. From the committed descriptor map (`docs/descriptors/README.md`, EXP-0015):
  > `magFilter` is bit 23 and `minFilter` is bit 25 (1 bit each, no unnamed encodings), but
  > **`mipFilter` is a 2-bit field at bits[27:28] with only 3 named values (none / nearest /
  > linear), leaving code 3 unnamed and untested**, and **bits 24 and 26 are unassigned in that
  > table**. Also still undecoded: the MSL 4.0 per-sampler **`bias(float)` STATE field** (spec
  > §2.7), distinct from the per-instruction `bias()` operand EXP-0094 characterized — its raw bit
  > location is unknown and is a concrete probe target. Anisotropy, if counted as a filter
  > encoding, goes the other way: its unnamed codes 5/6/7 are **additional supported modes**
  > (32x/64x/128x) — see the TEX-26 refinement block.
  > **So the answer to TEX-28 as posed is "yes for three of the four sub-fields, and the
  > classification differs per field": address = alias, border = alias, swizzle = deterministic
  > invalid (hard fault), filter = UNTESTED.**
  > M4 target; A18 deferred. 97/97 cases per run x 2 runs, `cross_run_gate_pass: true`,
  > `issues_total: 0`; the descriptor-patch technique is validated by a bit-exact positive control
  > and by a disclosed prior failure mode (patching between two dispatches is silently reverted by
  > Metal's own re-bind, so patches are applied inside the single observed command buffer).
  > Evidence: `experiments/EXP-0136-m4-unreachable-encodings/RESULTS.md` §2, §3, §4, §8, §9;
  > `docs/descriptors/README.md` "Sampler descriptor — 8 bytes".

---

### ANCHOR:   primitive hardware-validated?**

  > **Answered 2026-08-28 (desk audit of `tools/agx-isa/validation.json` against EXP-0103) —
  > TRIG-01 NO and TRIG-02 NO. [DESK-AUDIT]** (One block answers both; TRIG-02's own last line is
  > not unique in the file.)
  > **Neither the trigonometric/reduced-range primitive nor the `0x2b` range-reduction operation
  > has a single hardware-run operand or modifier field.** Per-field state, from the labelling
  > standard in `docs/evidence-classification.md`:
  > `tex_coord_setup` — the 10-byte `0x?b`-leader member of the `0x2b`/`0x3b`/`0x5b` register/
  > shift-prep family, which is the op `docs/isa/README.md` identifies as the range-reduce step in
  > `sin`/`cos`/`tan` (`a 0x2b reduce op + quadrant select`, then an fma polynomial): instruction
  > level `corpus-correlation` (M4, EXP-M4-13, "polymorphic 10-byte 0x2f form located over the
  > own-MSL corpus"); `srcA`, `form` and `idx` `corpus-correlation`; `dst_lo`, `b1`, `subop`, `b5`,
  > `b6`, `b8`, `b9` all **`untested`**.
  > `shift_amt_move` (the 4-byte member of the same family): every field `corpus-correlation`
  > except `op_desc`, which is `untested`.
  > `sfu_marker`: `tokenization-only` — "byte-invariant 2-byte token (06 02); **exact micro-op NOT
  > characterized**".
  > `fspecial_est` (the SFU seed op): instruction level `isolated-byte-diff` (A18, EXP-0026) and
  > `subop` `corpus-correlation` (`0x09` rcp / `0x0b` rsqrt / `0x0d` sqrt); `dst` `untested`;
  > `srcA`, `b4`, `b5` `tokenization-only`.
  > This is consistent with what EXP-0103 (M4/G16G, commit `bbb1e9fc`) itself recorded: its TRIG-03
  > and TRIG-04 answers are **PARTIAL — structural (198 vs 238 bytes), not field-level**, and its
  > limitations section states outright that *"TRIG-01/02 (full encoding of the trig primitive and
  > the `0x2b` range-reduction op) ... were not attempted"*. Nothing in the corpus has since
  > attempted them.
  > **Consequence for an emitter:** under the `emittable` rule, both ops are **decodable, not yet
  > emittable**. A backend must not synthesize a range-reduction op with chosen operands; it must
  > lower `sin`/`cos`/`tan` through the ordinary ALU/SFU sequence whose *numerics* EXP-0103 did
  > establish (`precise::` accurate to <= 2 ULP up to `FLT_MAX`; `fast::` correct only below a
  > cliff located at `(6587824, 6588825]` and a total failure above it; `fast::sin(NaN) = +0` vs
  > `precise::` propagating qNaN). Flipping TRIG-01/02 to Yes requires field-level splice-and-observe
  > on the `0x2b` family, on M4.
  > A18 target for `fspecial_est`'s one executed level; M4 target for the corpus locations; **no
  > operand field of either op is executed on either target.**
  > Evidence: `tools/agx-isa/validation.json` (`tex_coord_setup`, `shift_amt_move`, `sfu_marker`,
  > `fspecial_est`), `experiments/EXP-0103-m4-fp-transcendental-semantics/RESULTS.md` (TRIG-03/04
  > and Limitations), `docs/isa/README.md` (`0x2b` family, sin/cos/tan lowering).

---

### ANCHOR:   to achieve its claimed result accuracy?**

  > **Answered 2026-08-28 (confirmation of EXP-0103's recorded disposition) — SFU-04 remains
  > DEFERRED, and the block is a clean-room rule, not an effort gap. [DECISION, not evidence]**
  > **The question as posed asks us to count the refinement iterations in Apple's
  > compiler-generated reciprocal sequence. That is exactly what `CLAUDE.md` FORBIDDEN rule 5
  > prohibits** — "do not lift long compiler-generated instruction sequences and present them as an
  > algorithm to copy". EXP-0103 (M4/G16G, commit `bbb1e9fc`) pre-registered SFU-04 as `DEFERRED`
  > for this reason and recorded it as **the sole `DEFERRED` item** in its 31-item scoring
  > (`DEFERRED = 2 (TRIG-01,02; SFU-04, counted once)`), noting that EXP-0026's A18 answer is *"an
  > inferred precision-doubling argument (8 -> 16 -> >= 24 bits), explicitly not a literal
  > instruction count"*. **This wave confirms that reading and does not work around it.**
  > **The two hardware facts that let an implementer answer the underlying engineering question
  > themselves, without us transcribing anything:**
  > (1) the **seed accuracy** — `fspecial_est` delivers a **~7.5-8 mantissa-bit** Newton-Raphson
  > seed for rcp/rsqrt/sqrt (EXP-0026, A18, `isolated-byte-diff`); and
  > (2) the **final accuracy that must be reached** — `precise::rcp` on FP32 is **0 ULP over the
  > normal range**: 1856/1886 corpus values bit-exact, and all 30 mismatches are subnormal,
  > DAZ+FTZ-explained (**0 normal-range divergences**); `fast::rcp` by contrast is 1742/1886 with
  > 114 normal-range divergences at max 1 ULP (EXP-0103, M4, HW). Determinism is
  > proven black-box: **47/47 cases, every input in every case, byte-identical between run01 and
  > run02**, including all 65536x4 rcp/rsqrt FP16/FP32 fast+precise combinations.
  > From (1) and (2) an implementer derives their own iteration count for their own sequence
  > (each Newton-Raphson step roughly doubles the correct mantissa bits, so reaching fp32's 24
  > requires two from a ~8-bit seed) — **that derivation is theirs to make, and it is not a
  > transcription of Apple's code.** We state the hardware endpoints; we do not state Apple's
  > sequence.
  > Also recorded and carried: `rcp`/`rsqrt`/`sqrt` share division's DAZ+FTZ model **exactly**
  > (184/184 divergences predicted, zero residual), and FP16 SFU **neither DAZs nor FTZs** across
  > all 65536 patterns — so the FP32 flushing is a datapath property, not a global mode.
  > **This item needs a decision (accept the reframing above, or close it as permanently
  > out-of-scope), not more evidence.** Recommendation: mark SFU-04 **OUT-OF-SCOPE (clean-room
  > rule 5)** in the questionnaire, with facts (1) and (2) as the documented substitute, rather
  > than leaving it as an open experimental gap that implies a future experiment could close it.
  > M4 target for the accuracy and determinism results; A18 target for the seed-accuracy result.
  > Evidence: `experiments/EXP-0103-m4-fp-transcendental-semantics/RESULTS.md` (SFU-03/SFU-04
  > entries, accuracy table, Limitations), `experiments/EXP-0026-transcendentals/`,
  > `tools/agx-isa/validation.json` (`fspecial`, `fspecial_est`), `CLAUDE.md` FORBIDDEN rule 5.

---

### ANCHOR:   FP32, vectors, and I64 values?**

  > **Answered 2026-08-28 (desk audit over EXP-0020 / EXP-0141 / EXP-0146 / EXP-0113) — ENC-03 NO,
  > with an exact per-type inventory of what IS known. [DESK-AUDIT over HW results]**
  > **FP16 / half registers — largely known.** 16-bit halves are **independently addressable,
  > packed 2 per GPR** (64 `half` values occupy 50 GPRs); native-half access is via the `0x10` /
  > `0x11` groups, and the restriction that matters is that **the `0x09` 32-bit form's size bit
  > reaches only the LOW half** (EXP-0020). `half_alu`'s `srcA`, `srcB` and `src_modifier` are
  > `hardware-run` (A18, EXP-M4-14/EXP-0033), but its `dst` and `opflags` are `untested`.
  > **FP32 / GPR indices — known per instruction form, and the forms differ.** There is no single
  > register-field width: the 6-byte `falu2` destination is a **4-bit nibble (r0-r15 only)**, a
  > high float destination requires the 8-byte `falu3` form (`dst = byte+1`, 7-bit, r64 observed),
  > and integer `dst = b3` plus all source fields are 7-bit `(reg<<1)|size` spanning r0-r127 over a
  > 96-entry file (EXP-0020). The addressable file is ~96 GPRs, and this is corroborated from two
  > independent families: `device_load`'s destination is `extmode = 2*R` for **R in 0..63**, with
  > 128..255 (r64+) **silently zero** and bit 0 a don't-care (EXP-0141, M4, `hardware-run`); its
  > `index_reg` accepts r0..r95 with bit 7 ignored (128..255 mirror 0..127) and **r96..r127 FAULT**;
  > and the 64-bit `iadd2` form faults for destination byte values `0xBE..0xFF` (register index
  > >= 95) (EXP-0146, M4). Note the asymmetry: a too-high *destination* is a silent zero on
  > `device_load` but a **contained GPU address fault** on the 64-bit `iadd2`.
  > **I64 register pairs — explicitly NOT known, and the owning experiment says so.** EXP-0146
  > (M4/G16G, commit `f36b2ac4`) established that the 64-bit form's destination is a
  > **register-PAIR base encoded `(reg<<1)|size` in byte+3 whose size bit is a don't-care**, and
  > that in the source-A descriptor (byte+7) **every value with bits 0 and 1 both set faults**
  > (64 of 256). What it explicitly did **not** establish is *"whether the operation works at other
  > pair placements"* — because moving a source descriptor also changes which register is read, so
  > in a carrier whose loads write fixed registers a relocated operand reads garbage and is
  > indistinguishable from an illegal placement. Its verbatim instruction to the implementer:
  > **"Do not assume unaligned pairs work."** Closing this needs the `device_load` destinations
  > co-mutated with the `iadd2` operands — EXP-0146's own named successor.
  > **Vectors — no evidence at all.** No committed experiment establishes a consecutive-register or
  > alignment requirement for multi-component (vec2/vec3/vec4) operands as such; `device_load`'s
  > multi-element forms are characterized by `ld_format` / `elem_size` accepted-value sets
  > (21 and 48/96 accepted codes respectively, EXP-0141) rather than by a register-tuple rule.
  > **One live constraint an emitter must not miss** (EXP-0141, M4): the `dst_lo`/`dst_ext9` pair
  > rule is *mostly* `ld_format`-independent but tightens for narrow formats —
  > `dst_lo == 1` and `dst_ext9` bit 0 == 1 hold under **all 21** accepted formats, but
  > `dst_ext9`'s upper don't-cares shrink from `v & 0x181 == 0x081` (16 codes) to
  > `v & 0x1C1 == 0x081` (codes 3/7/9/13) to `v & 0x1E1 == 0x081` (code 39).
  > **Also on record and NOT to be re-derived:** EXP-0113 (M4) decisively **refuted** its own
  > candidate mechanism for reading r64-95 as an ALU source — the same spliced bytes gave
  > *different* results across two independent process launches for 4 of the singlehop/mismatch
  > cases, which
  > is outright nondeterminism and rules out indexed register-file addressing; **the only validated
  > path to r64-95 anywhere in this repository remains `get_sr`'s WRITE-side `dst`/`dst_hi`
  > mechanism (EXP-0092)**. And per the dispatch-level retraction list, EXP-0139 showed EXP-0112's
  > `r(R mod 64)` aliasing does **not** transfer to `iadd2.dst`.
  > **Answer: No — completely known for FP16 and for FP32 GPR indexing per form, NOT known for I64
  > pair placement, and untouched for vectors.** Conservative rule: emit only aligned pairs at the
  > placements EXP-0146 executed; stay within r0..r63 for `device_load` destinations.
  > M4 target for EXP-0141/EXP-0146/EXP-0113; A18 target for `half_alu` and the `frame_prologue`
  > family; A18 deferred elsewhere.
  > Evidence: `experiments/EXP-0146-m4-emit-int-misc/analysis/I64_answers.md` (I64-03),
  > `experiments/EXP-0141-m4-emit-mem/RESULTS.md` §H1/§H8/§8,
  > `experiments/EXP-0113-m4-register-file-model/RESULTS.md` §0, `docs/isa/README.md`
  > "Machine model" / "Register-field widths", `tools/agx-isa/validation.json`.

---

### ANCHOR:   determined for every stage?**

  > **Answered 2026-08-28 (desk audit over EXP-0020 / EXP-0024 / EXP-M4-09 CMD-8) — ENC-15 NO.
  > [DESK-AUDIT over HW results]**
  > **Only one occupancy field is decoded, it belongs to the compute stage alone, and its
  > predictor is a compiler property rather than a register count.**
  > What is known: the CDM launch-descriptor config word (`0x100000b0000 + 0x00`) is
  > `0x00080000` (bit19 always set) plus **bit 23 = a single-bit, 2-tier occupancy/register-class
  > flag**. Across ~50 kernels (footprint f0 = 2..96) the word is *only ever* `0x00080000` or
  > `0x00880000` — no higher bit ever lights — so it is **not** the LSB of a GPR-count field; the
  > actual GPR count lives in the shader BO / USC config. Atomics, barriers, simd ops and
  > threadgroup memory do not touch it.
  > **The obvious model is recorded as FALSE.** EXP-M4-09/CMD-8 corrected it: *"the earlier
  > interpolated 'clear <= 11 / set >= 12 GPRs' is FALSE"*. The flip is driven by the compiler's
  > **peak register-pressure / occupancy class**, not the total-GPR (metadata field-0) count, and
  > it happens far below 12 — an f0 = 8 kernel with two loop-carried chains (`N2E0`) is **SET**
  > while other f0 = 8 kernels (`N1E3`, `N0E7`) are **CLEAR**; f0 = 9 likewise splits
  > (`N1E4`/`N3E0` set, `N0E8` clear); the **lowest SET is a half-datapath kernel at f0 = 5**.
  > bit 23 correlates **1:1** with the presence of our own shader's `__GPU_METADATA` field-32 — a
  > compiler-computed occupancy property, not a quantity a driver can read off a register count.
  > The recorded driver instruction is therefore: *"A Mesa driver must set bit23 from its own
  > register allocator's occupancy decision (peak-GPR class), not from a `>= 12` test."*
  > **"For every stage" fails outright.** No committed experiment establishes a register-pressure ->
  > metadata mapping for the **vertex** or **fragment** stages; the per-stage USC uniform-preamble
  > header carries a `0x008800XX` register/shader-config tag (XX = stage x 0x0c) whose
  > register-count field is not decoded (EXP-0024/EXP-0042). And the surrounding model is recorded
  > as incomplete in the deliverable itself: `docs/capability-completeness.md` lists **Dynamic
  > Caching** (register file as cache; dynamic alloc/dealloc; occupancy vs live-set) and the
  > **full halfregs -> max-threads occupancy curve** as **NOT-YET-CHARACTERIZED**, and
  > `docs/mesa-userspace-requirements.md` records the occupancy/cycle model as *partial* with
  > "no full halfregs->max-threads occupancy curve, no per-op latency/throughput/cycle model".
  > **Answer: No.** Documented conservative response (already in `docs/porting-guide.md`): use the
  > **static** model that *is* decoded — 96 GPRs before spill, the spill threshold, and the
  > peak-pressure occupancy tier — and accept that a wrong occupancy choice is a performance
  > defect, not a correctness one.
  > Compute-stage evidence is A18-measured (the f0 splits above) and M4-cross-confirmed via
  > EXP-M4-09; the M5 figure (bit23 set for f0 >= 20) is **not** Apple9 evidence and is excluded.
  > Evidence: `docs/cmdstream/README.md` "Compute config word + threadgroup-memory size (EXP-0024;
  > occupancy tier CORRECTED EXP-M4-09/CMD-8)", `docs/isa/README.md` "Footprint declaration",
  > `docs/capability-completeness.md`, `docs/mesa-userspace-requirements.md`.

---

### ANCHOR: - **ENC-16 — Is scratch spill addressing and frame-size metadata fully known for generated shaders?**

  > **Answered 2026-08-28 (desk audit over EXP-0107 / EXP-0125 / EXP-M4-14 / EXP-0041) — ENC-16 NO,
  > with the exhaustion ceiling now exact. [DESK-AUDIT over HW results]**
  > **Frame-size metadata: known in outline, NOT resolved at the sub-field level.**
  > `frame_prologue` is `hardware-run` (A18, EXP-M4-14 — every byte of the prologue swept on an
  > executed non-leaf callee frame): `subop` runs only for values with **bits[1:0] == 0b11**
  > (`0x03`/`0x0b`/`0x13`/`0x23`/`0x43` run; `0x00`/`0x01`/`0x02`/`0x04` fault); `marker` is
  > reserved/inert. But `frame_size` carries an explicit unresolved note: it is **16-byte
  > granular**, **over-allocation is tolerated** (`0x20 -> 0x30`) while too-small or misaligned
  > **faults**, and it is **NOT cleanly monotonic — `0x40` faults while `0x30` runs — so the
  > sub-field layout is NOT fully resolved.**
  > `spill_frame_marker`'s **exact role is UNRESOLVED**: byte0/+1/+2 sweeps are runtime no-ops and
  > only byte+3 = `0xff` faults, and EXP-0041 found this exact word **absent from all nine
  > retained M4 own mains including 208-576 B of declared scratch** — so it is **not** a universal
  > spill marker.
  > `link_save_restore` is the one part that is fully mapped, and it corrects the database: in a
  > race-free frame it is a no-op fence with every payload field inert, but in a **spilling** frame
  > (12 live temporaries) byte0 `0x07 -> 0x00` corrupts the SAVE and **hangs** the RESTORE; `scope`
  > passes only when bit7 AND bit0 are both set (`0x81`/`0x83`), corrupts+hangs at
  > `0x00`/`0x80`/`0x01`, and page-faults at `0xff`; **`dir_offset` is 16-bit (bytes +5/+6), NOT
  > the DB's former 24-bit field** — byte+7 is reserved and inert on both instances.
  > **Scratch spill ADDRESSING: not located, at every point in the userspace lifecycle this
  > project's tooling can reach — a strong, bounded negative.** EXP-0107 (M4) pushed declared
  > per-thread scratch from 0 to **261,728 B** (~454x beyond EXP-0041's 208-576 B range) across
  > CS/VS/FS, 64 to **4,194,304** dispatched threads, threadgroup shapes 32/256/1024, and up to
  > 1,000 runtime spill/fill passes — 30 cases, captured twice, both fully hardware-run — and found
  > **no scratch-correlated BO, helper-program record, or doorbell/ABI structure** through the
  > widened DATA-TRACE boundary. EXP-0125 (M4) confirmed the same negative at a **third** point,
  > before dispatch and before compile: the full address-free BO inventory is **byte-identical**
  > between a never-spilling process and one spilling 98,320 B/thread at **all six** lifecycle
  > checkpoints in both gated runs, and the single code-shaped region (VA `0x10000000000`) is
  > exactly `0x10000` B at every checkpoint **including `DEVICE_CREATED`, before a line of MSL is
  > compiled**. Selector-5 ("shared pages") was never observed to be called at all.
  > **What IS now exact, and is new to this row: the exhaustion boundary.** All three stages
  > (CS/VS/FS) **independently bisect to the identical ceiling — last success K = 65,431
  > (261,740 B declared scratch), first failure K = 65,432 (261,744 B)** — a 4-byte (one array
  > element) resolution, byte-identical across both gated runs for all three stages. The failure
  > is clean, at pipeline-creation time (`newComputePipelineStateWithFunction` -> *"Compute
  > function exceeds available stack space"*), with **no device fault, timeout, or corruption**.
  > That is **~2.003x below** mesa's own `AGX_MAX_SCRATCH_DWORDS` (131,072) and is not fully
  > explained by a units artifact.
  > **Answer: No.** Conservative response: a driver may size scratch up to the measured
  > stage-uniform ceiling and expect a clean creation-time rejection above it, must over-allocate
  > rather than under-allocate the 16-byte-granular frame field, must not emit
  > `spill_frame_marker` as if it were a required spill marker, and must treat the scratch base /
  > helper handoff as an open userspace<->kernel coordination item rather than a discovered
  > userspace structure.
  > M4 target for EXP-0107/EXP-0125 (the ceiling and the negatives); A18 target for the
  > `frame_prologue` / `spill_frame_marker` / `link_save_restore` sweeps (EXP-M4-14); A18 deferred
  > elsewhere.
  > Evidence: `experiments/EXP-0107-m4-scratch-helper-abi/RESULTS.md`,
  > `experiments/EXP-0125-m4-scratch-helper-init/RESULTS.md` (H1/H2/H3),
  > `experiments/EXP-0041-scratch-helper-abi/`, `tools/agx-isa/validation.json`
  > (`frame_prologue`, `spill_frame_marker`, `link_save_restore`).

---

### ANCHOR:   to be documented.

  > **Answered 2026-08-28 (desk pass over EXP-0010 / EXP-0020 / EXP-0083 / EXP-0141 / EXP-G1a) —
  > MEM-18 PARTIAL, leaning "intermediate preload file", with the mapping itself still undocumented.
  > [DESK-AUDIT over HW results]**
  > **The evidence points at the intermediate base-register/preload file, not at a direct index
  > into the userspace resource table — but no experiment has framed or tested it as MEM-18, and
  > the exact table-to-preload mapping the item demands does not exist.**
  > Three committed observations, each hardware-backed, point the same way:
  > (1) **The pointer is not in the code and not in the constant program.** "Buffer base pointers
  > are preloaded into a uniform/binding slot, selected by `device_load` byte+4 (HW-proven:
  > splicing the slot changes which bound buffer is read). The pointer is *not* in the shader code
  > and *not* in the constant_program — it is supplied by the command stream / USC" (EXP-0010).
  > The general statement of the ABI is: *"no stage preloads IDs into GPRs ... only buffer/vertex
  > base pointers + scalar uniforms are preloaded into the **uniform register file** (selected by
  > `device_load` byte+4 `base_slot`; the **vertex-buffer base = slot `0x03`**)"*.
  > (2) **The slot file's CONTENT is program-dependent, which a direct resource-table index could
  > not be.** EXP-0083 (M4/G16G, commit `8d47a271`, 351 cases x 2 runs = 702 executions, zero
  > faults) found slot 0's anomalous content *"tied to whether the compiler hoisted thread-invariant
  > loads into the constant program for that specific kernel, not to a hardware-fixed 'slot 0 is
  > always X' rule"* — in one kernel shape slot 0 reads the hoisted witness value, in another
  > (gid-variant indices, no hoist) it reads the plain bound buffer 0.
  > (3) **The selector's shape is a file, not a table.** The selector is **effectively 7-bit**:
  > values 128..255 mirror 0..127 **byte-for-byte** on every op path tested (census31 load 256/256,
  > census4 load, store, atomic), which explicitly *refutes* the naive "slots outside 0..30 are
  > simply zero" framing — slots 128..158 are not zero, they mirror 1..30's non-zero content.
  > Out-of-range or unpopulated access never faults in 702 executions: LOAD reads zero (non-mirror
  > region) or mirrors; STORE and ATOMIC discard silently or redirect to the mirrored binding.
  > `device_load.base_slot` is confirmed live and per-EXP-0083 in the current emitter spec
  > (EXP-0141, M4), and on the `atomic_mem` carrier it is **inert (256/256) with one bound target**.
  > **What is missing for a `No`-to-direct-indexing to be complete, in the item's own words —
  > "the exact table-to-preload mapping and its independent capacity":** EXP-0083 states plainly
  > that *"full characterization of the constant-program slot table is out of scope"* and makes
  > **no constant-program/uniform-pipe slot-table claim** beyond the slot-0 load-path observation.
  > The USC side is only structurally known: buffers reach the GPU as a flat table of 8-byte LE
  > GPU VAs at `0x10000100000 + 0xa0`, one per bound buffer in index order, while the uniform
  > preload is done by the USC program **body** (`0x67` loads), *not* a fixed tag list, under
  > per-stage header tags `0x0088_00XX` (register/shader-config), `0x0042_XXXX` (uniform-data
  > pointer) and `0x0020_00XX` (uniform-slot count/id) (EXP-G1a/EXP-0042). Nobody has connected
  > "binding index N" to "preload slot S" as a rule.
  > **Capacity, as far as it is known:** 31 usable slots via the direct `[[buffer(N)]]` API
  > (MEM-15), a 7-bit selector space (MEM-16), and EXP-0083's explicit note that whether an
  > architectural ceiling exists above 31 via a non-direct population mechanism (argument buffers /
  > bindless) **cannot be probed** through that API path.
  > **Conservative driver response:** treat `base_slot` as an index into a program-specific
  > preload file that the USC/uniform program populates, not as the API binding index; never rely
  > on slot == binding index; and bounds-check, because an out-of-range slot **silently aliases a
  > real binding** rather than faulting.
  > M4 target for EXP-0083/EXP-0141; the EXP-0010/EXP-0020/EXP-G1a statements are A18-era and are
  > cited as the structural model, not as M4 measurements. A18 deferred.
  > Evidence: `experiments/EXP-0083-m4-base-slot-census/RESULTS.md` (§H2, the 7-bit finding, and
  > "Remains open / flagged for the successor (MEM-18/19)"),
  > `experiments/EXP-0141-m4-emit-mem/RESULTS.md` §8, `docs/isa/README.md` "How uniforms & buffer
  > pointers reach registers (EXP-0010)" and "Preloaded-register ABI",
  > `docs/cmdstream/README.md` "USC / resource bind grammar — RESOLVED (EXP-G1a)".

---

## Items deliberately left UNANSWERED by this wave

No block is proposed for these. Each genuinely needs hardware; writing an answer from the
adjacent evidence would be a fabrication.

| item | why no block | what would close it |
|---|---|---|
| **P2-06** (native FP64) | The only thing on record is `docs/capability-completeness.md`'s "(absent) — not exposed by MSL on Apple GPUs", sourced to a **premise**, not a probe. No experiment ever compiled a `double` kernel or searched the opcode space for an FP64 op. Corpus byte0-census coverage proves nothing here: the corpus is compiled from an MSL that has no `double`. EXP-0146's native 64-bit integer ADD is integer register-pair machinery — exactly what the question excludes. | An MSL `double` compile-rejection probe (cheap) **plus** an opcode-space search, on M4. |
| **TEX-01** (projective divide) | `tex_addr_setup.form = 0x01` is identified as "coordinate projection (samples level 0)" and the whole op was byte-swept — but on **A18** (EXP-M4-14), and no numeric edge case (zero, signed zero, inf, NaN, array coordinate) was ever fed to it. MSL exposes no `sample`-with-w-divide entry point, so there is no compiler-emitted evidence to read. | `op+2` bit-space fuzzing on a spliced valid `tex_sample` bundle plus directed edge-case inputs, on M4. `lower_txp` stays enabled meanwhile. |
| **TEX-19** (bindless texture to 1,000,000) | EXP-0095 closed only the *shape* at `CAP = 256` / `K = 8` (feasibility exploration to N = 4096); EXP-0106 recorded it DEFERRED because confirming the documented ceiling is a large allocation-and-sweep campaign. The per-lane non-uniform half is separately supported by EXP-0106 TEX-06 (4 lanes, 4 distinct textures, correct `get_width`/`get_num_mip_levels` per lane) but only at 4 entries. | Re-run EXP-0095's GLIMG-A02 methodology at boundary values near 1,000,000, on M4. |
| **TEX-21** (bindless sampler to 499,999) | The only evidence is **A18** (EXP-O2B): `maxArgumentBufferSamplerCount = 500000` as a queryable capability, the 8-byte `gpuResourceID` = dense sequential index representation, and dynamic shader-computed indexing shown for a handful of entries. It explicitly did not sweep the range or the boundary, and it predates the M4-only directive. | M4 re-run of EXP-O2B §4's methodology at boundary values near 499,999. |
| **TEX-22** (500,001st sampler / destroyed ID) | EXP-O2B's own "Recommended next" section names exactly this gap (dedup/reuse check); it was never executed on any target. | The same successor as TEX-21, extended to allocation failure, ID reuse after destruction, and dedup. |
| **MEM-19** (USC preload capacity) | EXP-0083 flagged it and deferred it; nothing since has touched it. The USC side is known only structurally (per-stage `0x0020_00XX` uniform-slot count/id tag; preload performed by the program body's `0x67` loads, not a tag list) and **no experiment has driven the declared preload count past capacity**. | A USC uniform-program probe that varies the declared preload count across and beyond the supported capacity, on M4 — the successor EXP-0083 named. |
