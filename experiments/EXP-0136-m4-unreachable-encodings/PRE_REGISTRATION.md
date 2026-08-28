# PRE_REGISTRATION — EXP-0136 M4 unreachable descriptor/opcode encodings

**Pinned revision:** `ea1e17dadfb4052537da1449bcdc133c6a09127d` (repo HEAD at time of
pre-registration). Captures are validated against the **authored blob hashes** listed in
`CAPTURE_CONTRACT.json`, not against live `HEAD` — the orchestrator commits sibling
experiments continuously and a moved `HEAD` is not contamination (SUBAGENT_BRIEF.md).

**Target:** Apple M4 (G16G), local host only, macOS 26.6.2, Metal 4. No A18 Pro claim
anywhere in this experiment (A18 hands-off per CLAUDE.md).

**Governing task:** `APPLE9_RE_IMPLEMENTATION_GAPS.md` § DRV-P2-05 ("Metal-unreachable
encodings and performance model"). Only the *encoding-envelope* half of that row is in
scope here (finite raw sampler/address/swizzle/border/aniso values, arbitrary restart and
raster modes, native geometry-shader/stream-output paths, other Metal-unreachable
descriptor/opcode values); the *performance model* half (occupancy curves, latency/
throughput, cache behavior, tile/parameter-buffer sizing, workgroup repacking) is
explicitly deferred and out of scope for this experiment, per the row's own text ("Unknown
hard resource capacities must be promoted to P0/P1 **even if the performance model remains
deferred**").

## 0. A NON-RECORDED technical feasibility spike preceded this pre-registration

Per the standing "NON-RECORDED smoke gate before any raw/" rule and the established pattern
in sibling experiments (e.g. EXP-0123 `work/pilot_run`), a spike under `work/spike/`
(never committed to `raw/`) was required *before* a matrix could be responsibly frozen,
because the core technique below — directly overwriting the live bytes of a Metal-internal
resource descriptor from our own process — is novel to this repo and its viability (and
correct timing relative to Metal's own internal writes) was unknown going in. The spike:

- established that a naive "patch between two dispatches, reusing the same MTLSamplerState"
  design **fails silently** (Metal's own `-setSamplerState:atIndex:` on the *second* encode
  rewrites the descriptor pool entry back to the object's creation-time bytes before the
  second dispatch ever runs — a real, load-bearing negative finding in its own right, folded
  into the frozen method below);
- established the working technique (§1) and validated it with a **bit-exact positive
  control** against a real Metal-API-generated encoding (see §2);
- ran informal (non-recorded) single-point probes of all four target families to confirm
  none of them hangs the host and that the harness produces *some* well-formed result for
  every planned case shape, so the frozen matrix below is not a guess.

No claim in this document is drawn from the spike's raw output; the spike's role is method
validation only. All promoted facts come from the two official gated runs under `raw/`.

## 1. Technique (frozen)

**"Direct descriptor patch"** (`harness/descpatch.m`), for the sampler/texture family only:

1. Build a real `MTLSamplerState`/`MTLTexture` via the public Metal API with an explicit,
   Metal-legal baseline configuration.
2. Encode exactly ONE compute dispatch (`texture(0)`, `sampler(0)`, `buffer(0)`=output —
   the exact EXP-0011/EXP-0015 3-slot binding shape) and call `-endEncoding` — do **not**
   commit yet.
3. Trigger `tools/iotrace`'s existing, **unmodified**, read-only SIGUSR1 BO-dump mechanism
   from this same live process (repeated with a settle delay until the dumped BO-file count
   stabilizes — the spike found the relevant registration is not synchronous with
   `-endEncoding` returning). Parse the resulting `bo_*.hex` files to find: which BO holds
   the Tier-2 argument buffer (by searching for our own output buffer's public
   `.gpuAddress` as an 8-byte LE needle — a value we already know), the 8-byte GPU-VA
   pointer to the sampler/texture descriptor at the known slot offset, and which dumped
   BO's `[gpu_va, gpu_va+size)` window contains that pointer.
4. Because that memory is "regular userspace VM registered into the GPU VM" (EXP-0009), the
   descriptor's **live CPU address in this same process** is `matched_bo.cpu + (desc_gpu_va
   - matched_bo.gpu_va)` — an ordinary pointer into our own address space. Read the current
   8 bytes there (self-check against the dump-file copy), overwrite **exactly one byte**
   with `(old & ~mask) | (value & mask)` (a surgical single-field mutation — every other bit
   stays exactly what Metal itself wrote), and read back to confirm the write landed.
5. **Only now** call `-commit` + `-waitUntilCompleted` on the SAME command buffer whose
   descriptor bytes were just patched, and read back the result. A separate process run with
   an **empty** patch list is the paired control/baseline case for comparison (never a second
   dispatch in the same process — see §0).
6. Re-dump once more post-commit and self-check the bytes were not silently reverted by
   anything other than a fresh `-setSamplerState:`/`-setTexture:` call (which this design
   never issues after patching).

For the restart/raster family (`harness/gfxprobe.m`) and the geometry/stream-output probe,
every input is directly settable through the public Metal API (index-buffer bytes, vertex
positions, `rasterizationEnabled`), so no memory patching is needed — pure HW-PROBE.

For the opcode-space family, `tools/agxtest` (read-only, copied unmodified into
`work/bin/agxtest_src/` and built there) splices bytes into `_agc.main` of our own compiled
MSL and runs it on hardware, exactly as documented in `tools/agxtest/README.md`.

## 2. Positive control (method validation, not a promoted fact)

Sampler address mode, byte3 mask `0xE0`: baseline created via API with
`address_s=clampToEdge`. **Control** run (empty patch) samples out-of-range UV and returns
the clamp-to-edge texel. **Test** run (same baseline, patched byte3 to the `repeat` code
`0x20`) returns a *different*, wrapped texel. **Reference** run (a *separately created* real
`address_s=repeat` sampler, no patch at all) returns **the bit-identical pixel** to the
patched **Test** run, and the **live descriptor bytes** the patched run wrote
(`...20800700...`) are byte-identical to what the real API-created repeat sampler's own
baseline bytes read as. This is the falsifier for the whole technique: if a patched
encoding ever failed to reproduce what the *same* encoding produced when Metal built it
natively via the public API, the technique would be rejected and this experiment would stop
before running the real matrix. It did not fail.

## 3. Hypotheses (falsifiable, one per family)

### H1 — Sampler anisotropy beyond Metal's 16× cap
**Claim:** the 3-bit `maxAnisotropy` log2 field (sampler byte2 bits[4:6], values 0..7 →
1×..128×) is read and acted on by the sampler hardware for encodings beyond Metal's public
cap of 16× (code 4), i.e. codes 5/6/7 (32×/64×/128×) are not silently clamped to the
code-4 behavior.
**Falsifier:** at an anisotropy ratio (`|dPdx_texels| / |dPdy_texels|`) exceeding 16:1
(e.g. 64:1), a directly-patched aniso-64 (code 6) sampler produces **the same** pixel value
as a *real, API-created* aniso-16 sampler at the identical ratio. (Equal → clamped/no native
effect; different, and specifically closer to the fully-resolved ideal established by a
ratio≤cap control case → native support beyond the cap.)
**Confounders:** mip-chain box-filter authoring must make higher mips genuinely uniform
(controlled by hand-authoring every mip level, not relying on `-generateMipmapsForTexture:`
semantics); LOD bias/clamp fields must be held fixed across the compared cases.

### H2 — Sampler address-mode codes beyond the documented 5
**Claim:** address-mode codes 4, 6, 7 (3-bit field, sampler byte3 bits[5:7]; 0/1/2/3/5 are
Metal-documented per EXP-0015) either alias one of the five documented codes' *full
multi-point signature* or exhibit a distinct, novel addressing behavior.
**Falsifier:** for each of codes {4,6,7}, sample at 4 distinct out-of-[0,1] UV values and
compare the resulting 4-value signature against every documented code's signature at the
same 4 points. A byte-for-byte matching signature to some documented code C is aliasing to
C; any point of divergence from all five is a distinct mode.

### H3 — Sampler border-color code beyond the 3 presets
**Claim:** the 2-bit border-color field (sampler byte7 bits[5:6]) — 3 documented presets
(0=transparent black, 1=opaque black, 2=opaque white) — has a genuine 4th behavior at code 3,
independent of which preset the sampler was actually created with.
**Falsifier:** code 3, tested against samplers *created* with each of the 3 different real
presets, returns the *same* pixel value as code 0 in all three cases (proving true hardware
aliasing to preset 0, not "ignores the patch and keeps the creation-time value" — which
would instead reproduce each case's own distinct creation-time preset).

### H4 — Texture-descriptor swizzle codes beyond the documented 6
**Claim:** the swizzle field (3 bits/component; codes 0..5 = R,G,B,A,One,Zero per EXP-0015)
has codes 6/7 that either silently alias one of the 6 or hard-fault the command buffer.
**Falsifier:** codes 0..5 must each reproduce the exact predicted channel-routing value
(a required internal positive control — this family has no external "real API" reference
since MSL's public swizzle surface, if any, does not reach this raw field); codes 6/7 must
be classified as OK-with-some-pixel (alias/novel) or CMDBUF_ERROR (hard fault) — not
silently dropped either way.

### H5 — Primitive restart is a fixed hardware sentinel, not a general comparand
**Claim:** matching `docs/cmdstream/README.md`'s DATA-TRACE-only finding ("restart
comparand @+0x68 ... Metal always uses all-ones"), the *hardware* itself restarts a
triangle-strip exactly and only at the all-ones index value (`0xFFFF` u16 / `0xFFFFFFFF`
u32), not at other large or out-of-range index values.
**Falsifier:** an indexed triangle-strip draw with a sentinel index placed between two
disjoint vertex groups leaves the "connector" region between them unlit (cut) for the
all-ones value and lit (or command-buffer-faulted) for at least one adjacent/other
out-of-range value (e.g. `0xFFFE`, or a small literal out-of-bounds index).
**Explicitly out of scope / not falsifiable this experiment:** whether the *raw* VDM
`restart comparand` field is genuinely programmable to an arbitrary (non-sentinel) value —
this would require direct VDM/command-stream byte patching. That is assessed **infeasible
to do safely in this session** (see §5, "Blocked probes") and is recorded as a bounded
`UNKNOWN`, not silently dropped.

### H6 — No native geometry-shader/stream-output hardware path
**Claim:** `rasterizationEnabled=NO` (a public, real Metal API path historically used for
vertex-only/stream-out-style pipelines) is implemented as "run the same VDM/tiler vertex
pipeline, elide the fragment stage" — not a structurally distinct native
stream-output/geometry-amplification hardware mechanism.
**Falsifier:** the set and approximate shape of GPU buffer objects (BOs) registered for a
`rasterizationEnabled=NO` draw differs *materially* from a matched `rasterizationEnabled=YES`
draw beyond the expected absence of a render-target texture BO (e.g. an extra dedicated
"stream-out target" BO, a different VDM opcode class, or additional TA-stage bindings).
**Supporting prior evidence (not re-derived here, cited):** the VDM draw-record field map is
already exhaustively decoded with no leftover/unknown bytes (`docs/cmdstream/README.md`,
"VDM draw record — full field map"); EXP-0098 explicitly left "native GS/streamout hardware"
and any "lower native hardware descriptor/atomic-slot limit" `UNKNOWN`/out of scope for its
own (compute-emulated) transform-feedback bundle, by explicit instruction not to search for
it there — this experiment is the search.

### H7 — `device_load`/`device_store` `reserved7`/`reserved13` are true inert padding
**Claim:** the two byte-wide fields the encoding tables list as `reserved7` (byte+7) and
`reserved13` (byte+13) in the 14-byte `device_load` (`0x67`) / `device_store` (`0xe7`)
encodings (`docs/isa/encoding-tables.md`) carry no semantic weight for correctness.
**Falsifier:** splicing any tested non-zero value into either field, individually or in
combination, on either device_load instance or the device_store instance in a simple
authored copy kernel changes the kernel's numeric output, faults the command buffer, or
hangs.

## 4. Frozen case matrix (generated by `harness/casematrix.py`; no changes after this point)

| family | mechanism | cases | purpose |
|---|---:|---:|---|
| `aniso` | descpatch | 16 | H1 |
| `addrmode` | descpatch | 32 | H2 |
| `border` | descpatch | 12 | H3 |
| `swizzle` | descpatch | 11 | H4 |
| `restart` | gfxprobe | 6 | H5 |
| `norender` | gfxprobe | 2 | H6 (paired with the standing VDM-field-map evidence) |
| `opcode` | agxtest | 18 | H7 |
| **total** | | **97** | |

Every family includes at least one Metal-API-reachable / previously-documented case as an
internal positive control (per-family detail in `harness/casematrix.py` docstrings) —
satisfying the "every null needs a positive control proving detectability" requirement.

## 5. Blocked probes (recorded, not silently dropped)

Two sub-questions from the dispatch are assessed **infeasible to probe safely in this
session** and are recorded as bounded `UNKNOWN`, not attempted:

- **Arbitrary (non-sentinel) primitive-restart comparand** and **a raw hardware bit for
  provoking-vertex or conservative-rasterization** would require writing into the raw
  VDM/tiler draw-stream or 3D fixed-function-state BOs (`docs/cmdstream/README.md`: GPU VA
  `0x18000`/`0x58000`, both `(fw ctx)` — firmware-context-relative, unlike the
  Metal-userspace-heap descriptor pool this experiment successfully patches). Unlike the
  descriptor pool (created once, read many dispatches later, patched in a fully GPU-idle
  window with a verified stable CPU address), the VDM/FF-state stream is written and
  consumed within a single command-buffer submission whose doorbell ring is, per EXP-0009,
  **invisible to `iotrace`** ("likely a store into a firmware-shared page + barrier,
  invisible to this interposer") — there is no established safe window to write into it
  without racing live GPU consumption, and getting that race wrong is a plausible host-wedge
  vector under this repo's explicit safety model (no out-of-band recovery). This is a
  deliberate, reasoned scope boundary, not an oversight — flagged here for a future
  experiment that first establishes a safe write window for firmware-context BOs (e.g. via
  kernel-driver coordination, out of scope for the userspace-only RE work this repo does).

## 6. Standing gates (frozen; `harness/verify.py`)

`--selftest` (offline, no device); `--seqtest` (`PRE_GPU` → `RUN01_PRESENT` →
`RUN02_PRESENT`, fabricated trees only); a **non-recorded smoke case** run once per binary
before any `raw/` capture (`work/smoke/`); the cross-run gate excludes exactly the
documented nondeterministic keys (`gputime_ns`-equivalent wall-timing fields, if any land in
`observed` — none of these probes are expected to be inherently racy the way EXP-0098's
producer/consumer synchronization tests were, but the gate schema still reserves the
capability per the standing contract) and fails on any other observed-field mismatch between
the two runs. Every JSONL record is appended with `fflush`+`fsync` immediately, per
CODEX/SUBAGENT_BRIEF kill-safety. Run ids are never reused; a partial/killed run directory is
retained and a fresh id used for the retry.

## 7. Clean-room provenance (attestation, restated per §7 requirement of CODEX)

```
Clean-room provenance: HW-PROBE + DATA-TRACE + OWN-SHADER
Inputs inspected: our own MSL (generated by harness/*.m string templates), the public Metal
  API surface (MTLSamplerDescriptor, MTLTextureDescriptor, MTLRenderPipelineDescriptor,
  MTLRenderCommandEncoder, MTLBuffer.gpuAddress/.contents), tools/iotrace (read-only,
  unmodified, hash-checked against the repo copy) as a DATA source only, and tools/agxtest
  (read-only, unmodified) for the opcode-splice family.
Apple binary introspection: NONE. No Apple binary is disassembled, decompiled, or otherwise
  introspected anywhere in this experiment. Descriptor and command-stream BYTES are DATA
  (call parameters / buffer contents), not code, per the Asahi clean-room policy already
  relied on throughout this repo (tools/iotrace/README.md, EXP-0015).
Reproduction: harness/run.py --run <id> --out raw/<id>  (x2), then
  harness/verify.py --captured <run_a> <run_b>.
Evidence: raw/<run>/{00_inputs.json,02_gated.jsonl,03_nongated.jsonl,04_manifest.json};
  work/spike/ (non-recorded method-validation spike, method only, no promoted facts).
```
