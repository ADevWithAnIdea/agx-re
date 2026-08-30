# EXP-0159 — Pre-registration (FROZEN before any gated build/run)

**Frozen:** 2026-08-29. **Target: A18 Pro / G17P** (`users-MacBook-Neo.local`, `192.168.10.243`),
`AGXAcceleratorG17P`, `applegpu_g17p`, 5 GPU cores, macOS 26.6 (build `25G5043d`), Metal family
Apple9, 8 GiB unified memory. **All results are direct G17P evidence, not `INFERRED`.**

Repo revision at freeze: `7dc67d768ada3c016771923bffd5b9647dd14813` (dirty: 16 uncommitted
sibling-experiment paths, expected — per `SUBAGENT_BRIEF.md` the gate is authored-blob hashes,
not live `HEAD`).

## 0. Question set

Six Part-II questionnaire items that the desk pass could not settle without hardware. **Note the
numbering trap:** Part-II `P2-01..06` are NOT Part-I `DRV-P2-01..05`. Here `P2-06` = native FP64.

| id | question (abbreviated; exact wording in `APPLE9_RE_IMPLEMENTATION_GAPS.md`) |
|---|---|
| `P2-06` | Is any native FP64 arithmetic operation present beyond integer register-pair machinery and software emulation support? |
| `TEX-01` | Does the Apple9 coordinate-projection setup form implement exactly NIR's projective divide, incl. zero, signed-zero, inf, NaN, array-coordinate behaviour? |
| `TEX-19` | Can Apple9 dynamically select every argument-buffer texture entry through the published limit of 1,000,000, uniformly and non-uniformly per lane? |
| `TEX-21` | Can Apple9 dynamically select every bindless sampler entry through index 499,999, uniformly and non-uniformly per lane? |
| `TEX-22` | What exactly happens when allocating the 500,001st sampler or indexing entry 500,000, an unpopulated entry, or a destroyed sampler ID? |
| `MEM-19` | Can the USC constant/uniform program populate every usable base slot, and what happens when its declared preload count exceeds the supported capacity? |

## 1. Pre-freeze feasibility probe (NOT evidence; retained in `raw/prefreeze/`)

Three facts were established before freezing, solely to make the contract specifiable. They are
retained verbatim and are **not** promoted as results; every claim below is re-measured inside a
gated run.

1. `device double*` in MSL is **rejected** by `newLibraryWithSource:` on G17P
   (`error: 'double' is not supported in Metal`). → FA is a diagnostic-capture family, not a
   dispatch family.
2. `struct AB { array<texture2d<uint>, 1000001> tex [[id(0)]]; };` **compiles**. → FC can declare
   the published-ceiling array directly rather than indexing past a small one.
3. 20,000 `MTLSamplerState`s with distinct descriptors are created in 0.01 s, IDs are dense
   sequential integers from 1, and two *identical* descriptors return the **same** `gpuResourceID`.
   → FD's ceiling walk to >500,000 is feasible; distinct descriptors are required to reach it.

## 2. Probe families, hypotheses, refuters

### FA — `fp64_msl` (P2-06): API-surface rejection census
- **H-FA:** no MSL spelling of a 64-bit floating-point type is accepted by the Apple9 runtime
  compiler on G17P.
- **Independent variable:** the FP64 spelling (16 authored sources, one construct each).
- **Controls:** `ctrl_f32`, `ctrl_f16`, `ctrl_u64` (must all **accept**) — they prove the harness
  can compile and that 64-bit *integers* are fine, isolating "64-bit" from "floating-point".
- **Expected if true:** 3 accepts, 13 rejects, each reject carrying a verbatim diagnostic.
- **Refuter:** any FP64 spelling accepts → H-FA false; that source is then dispatched.
- **Confounder:** `MTLLanguageVersion`. Each source is compiled at default and at 3.1 and 3.2.

### FB — `fp64_isa` (P2-06): exhaustive single-byte search of the only known native 64-bit ALU op
- **H-FB:** no single-byte mutation of the native 64-bit register-pair ALU instruction produces
  IEEE-754 binary64 arithmetic.
- **Carrier:** authored `kernels/u64op.metal`, `out[gid] = a[gid] - b[gid]` on `ulong`. EXP-0146
  (M4) showed this compiles to exactly one arithmetic instruction, `iadd2`, 10 bytes, and that
  byte0 bit 7 flips subtract→**native 64-bit add**. The carrier is re-compiled here on G17P and
  the instruction re-located from our own bytes; the M4 byte string is a starting point only.
- **Independent variable:** byte offset 0..9 within the located `iadd2`, value 0x00..0xFF
  → **2,560 encodings, the complete single-byte space of the instruction**.
- **Inputs (chosen to separate every hypothesis):** row0 `a=0x3FF0000000000000` (1.0 binary64),
  `b=0x3E45798EE2308C3A` (1e-8 binary64); row1 `a=0x4000000000000000` (2.0), `b=0x3FF0000000000000`
  (1.0); row2 `a=0x7FF0000000000000` (+inf), `b=0x3FF0000000000000`; row3
  `a=0xBFF0000000000000` (-1.0), `b=0x3FF0000000000000`.
- **Oracle (host-computed, GPU-independent):** for each row, the exact 64-bit result under each of
  `f64_add, f64_sub, f64_mul, f64_div, f64_min, f64_max, i64_add, i64_sub, i64_and, i64_or,
  i64_xor, f32x2_add, f32x2_sub, passthrough_a, passthrough_b, zero, poison`. Each observed
  8-byte word is classified against that closed set; `other` is recorded verbatim.
- **Poisoned readback:** the output buffer is supplied as an *input* filled with `0xA5` so an
  unwritten or half-written destination is distinguishable from a real zero.
- **Positive control / detection power:** the case `byte0 = 0x9F` must classify as `i64_add` on
  every row. If it does not, the family is void and reported so.
- **Falsifier:** any case classifying as `f64_add`/`f64_sub`/`f64_mul`/`f64_div` on **all four**
  rows → native FP64 exists; H-FB refuted.
- **Bound stated in advance:** this searches the single-byte neighbourhood of one instruction, not
  the whole opcode space. A negative is reported as bounded, with the exact swept set.
- **Desk companion (no GPU):** a census of every float-typed instruction in `tools/agx-isa/db.json`
  and the width of its operand-size fields.

### FC — `bindless_tex` (TEX-19)
- **H-FC1:** a runtime-computed `uint` index selects the correct argument-buffer texture entry at
  every tested index up to and including 999,999 (the last entry of a 1,000,000-entry array).
- **H-FC2:** per-lane divergent indices in one SIMD group each select their own entry at those
  magnitudes.
- **Canary indices (populated with distinct 1x1 R32Uint textures whose texel is `0xC0DE0000|k`):**
  `0, 1, 2, 7, 255, 256, 65535, 65536, 262143, 499999, 500000, 999998, 999999`.
- **Probe indices (unpopulated / out of range):** `3, 4096, 999997, 1000000, 1000001, 2000000`.
- **Declared array size `CAP` = 1000000**, argument buffer `CAP*8` bytes.
- **Expected if true:** every canary read returns its own `0xC0DE0000|k`; unpopulated returns 0
  (EXP-0095's M4 rule); no fault anywhere.
- **Refuter:** a canary at a large index returns 0 or another canary's value → the usable ceiling
  is below the published limit, or entries mirror.
- **Also recorded:** `MTLArgumentEncoder.encodedLength` for `CAP`; the raw 8 bytes the encoder
  writes for a texture (resource-ID representation); accept/reject of declared `CAP` in
  `{1000000, 1000001, 2000000, 16777216}`.
- **Confounder:** residency. Only the ~13 real canary textures exist; each is passed to
  `useResource:`. A canary failing *for residency reasons* would show as 0 at **every** index, not
  only large ones, which the small-index canaries detect.

### FD — `bindless_samp` (TEX-21, TEX-22)
- **H-FD1 (ceiling):** `newSamplerStateWithDescriptor:` succeeds for exactly
  `maxArgumentBufferSamplerCount` distinct descriptors and fails on the next.
- **H-FD2 (dedup):** two identical descriptors return the same `gpuResourceID`, so the ceiling is
  on *distinct* sampler states, not on API calls.
- **H-FD3 (density):** the n-th distinct sampler's `gpuResourceID._impl` equals `n` (+1 offset).
- **H-FD4 (no live-ID reuse):** at no point does a newly created sampler receive the ID of a
  still-live sampler. Checked by keeping every ID in a set and asserting insertion.
- **H-FD5 (indexing):** a shader-computed index into a heap of 8-byte `gpuResourceID`s selects the
  right sampler at index 0, 1, 255, 65535, 499998 and 499999.
- **H-FD6 (destroyed ID):** after releasing a sampler, its ID is either retired or re-issued to a
  later creation; if re-issued, a heap entry still holding it selects the new sampler.
- **Discriminator for FD5/FD6:** samplers alternate `magFilter` nearest/linear; sampling a 2x2
  R32Float texture (`0,2,4,6`) at the exact centre returns `3.0` for nearest and a distinct
  interpolated value for linear, so the returned float *names which sampler ran*.
- **Out-of-table IDs (hang-prone; run under `gpulease.sh`):** raw heap entries
  `0, 499999, 500000, 500001, 0xFFFFFFFF, 0xFFFFFFFFFFFFFFFF` written directly into the heap
  (EXP-O2B proved a hand-written ID array is byte-identical to the encoder's output).
- **Refuter:** the ceiling differs from 500,000; or an ID is re-issued while its holder is alive;
  or a large-index selection returns the wrong sampler's value.
- **Safety:** the out-of-table arm is isolated in its own process, one ID per dispatch, under the
  lease, with a hard timeout; a fault is recorded and the walk continues.

### FE — `usc_slots` (MEM-19)
- **H-FE1 (population):** with the maximum number of buffers the public path allows bound, the
  number of *populated* base slots equals that number, and every remaining slot in the selector
  space is unpopulated.
- **H-FE2 (selector space):** the base-slot selector is 7-bit on G17P — values 128..255 mirror
  0..127 — reproducing EXP-0083's M4 finding on the documentation target.
- **H-FE3 (past capacity):** an out-of-range/unpopulated slot is silent zero (load) or silent
  discard (store), never a fault.
- **H-FE4 (API ceiling):** the public path cannot declare more than 31 buffer arguments; the
  32nd is rejected, and this — not the 7-bit selector — is what bounds the populated count.
- **Method:** authored `kernels/slot31.metal` binds 31 buffers, buffer *k* filled with the
  distinctive word `0x5100_0000|k`; the single probe `device_load`'s `base_slot` byte is spliced
  across **all 256 values**, and the read word identifies which binding it landed on.
  A second carrier additionally binds 16 textures/samplers to test whether *non-buffer* resources
  populate slots above the buffer count.
  An API arm compiles kernels declaring 30/31/32/64 buffer arguments and records accept/reject.
- **Refuter:** a slot above the bound count returns a nonzero, non-mirror word → something other
  than a bound buffer populates it; or any slot faults.

### FF — `texproj` (TEX-01)
- **H-FF (the DB's claim, stated so it can be refuted):** `tex_addr_setup.form = 0x01` performs a
  projective divide of the coordinates by a third operand.
- **Provenance of the claim:** `tools/agx-isa/db.json` and `validation.json` label form `0x01`
  "coord-projection (samples level 0)". The sole evidence (EXP-M4-14, A18) is a single case:
  with `uv=(0.375,0.625)`, `lod=1` the result changed 1100 → 201, i.e. the level-1 texel became
  the level-0 texel **at the same (u,v)**. That is equally consistent with "the LOD operand is
  dropped and level 0 is sampled", with **no** coordinate change. The naming is therefore an
  untested inference and this family tests it.
- **Carrier:** authored `kernels/texlod.metal`,
  `out[gid] = tex.sample(smp, float2(cin[0], cin[1]), level(cin[2])).x`, bound to an authored
  4x4x3-mip R32Float texture whose texel is `1000*level + 100*y + x` — so a returned value
  *names the exact texel and mip level sampled*.
- **Independent variables:** (i) `form` in `{0x05 (baseline), 0x01, 0x07, 0x00, 0x0d}`;
  (ii) the third input `cin[2]`, which is the LOD under form 0x05 and the *candidate divisor*
  under the projective hypothesis, over
  `{1.0, 2.0, 4.0, 0.5, 0.25, 0.0, -0.0, -1.0, INF, -INF, NaN, 1e-30, 1e30}`;
  (iii) the coordinate pair over `{(0.375,0.625), (0.75,0.25), (0.9,0.9), (0.125,0.125)}`.
- **Oracle:** host-computed. Under `proj`, the expected texel is the level-0 nearest texel of
  `(u/w, v/w)`; under `noproj`, the level-0 nearest texel of `(u, v)`. The two disagree for every
  `w != 1.0` in the set, which is what makes the family decisive.
- **Expected if H-FF true:** with `form=0x01`, results track `proj`.
- **Refuter (and the outcome the prior evidence actually predicts):** with `form=0x01`, results are
  **invariant** in `cin[2]` and equal the `noproj` oracle → form 0x01 is an implicit-LOD level-0
  sample, not a projective divide, and the DB enum label is a **db-defect** under
  `FIELD-SWEEP-PROTOCOL.md` §6.
- **Positive control / detection power:** with `form=0x05` (baseline), changing `cin[2]` from 1 to
  2 must change the result 1100 → 2000. If it does not, the family is void.
- **Array-coordinate sub-question:** a second carrier samples a `texture2d_array` so the third
  coordinate is a real array layer, and the same `form` sweep is applied.

## 3. Controlled variables (all families)

One G17P device; one authored source per carrier, hash-frozen in `CAPTURE_CONTRACT.json`; fresh
`MTLDevice` per harness process; `fast_math` recorded per case, not assumed; every case's raw
record appended and `fflush`ed immediately.

## 4. Confounders explicitly tracked

- **Cross-agent GPU contamination** (`FIELD-SWEEP-PROTOCOL.md` §7). Runs are concurrent and
  UNLOCKED except the FD out-of-table arm. Every non-`ok` case records the OS fault-classification
  string verbatim. **No case is classified `fault` from one observation:** every non-`ok` case is
  re-run to a majority of 3, and `...ErrorInnocentVictim` results are segregated from the gated
  comparison.
- **Baseline drift.** Each family re-runs its unmutated baseline every 128 cases; a baseline
  failure means a cascade — the run stops, the position is recorded, and the remainder resumes in
  a fresh process under a new run id.
- **Compiler variation.** The compiled carrier bytes are hashed per run; a byte change invalidates
  cross-run comparison and is reported rather than absorbed.
- **Residency (FC/FD).** Only real, `useResource:`-ed textures are canaries; small-index canaries
  detect a residency failure mode that would otherwise be misread as a ceiling.
- **`min_lod_clamp` is NOT touched.** EXP-0106 took the compiler service down machine-wide with
  the MSL `min_lod_clamp()` sample option on G16G. No source in this experiment uses it. The
  `MTLSamplerDescriptor.lodMaxClamp` *property* used in FD to make descriptors distinct is a
  different, plain API property; `lodMinClamp` is left at its default.

## 5. Timeouts and safety

Every remote call wrapped in `perl -e 'alarm N; exec @ARGV'`. Per-dispatch watchdog 8 s
(`persistrun.py`); per-family process timeout 900 s; whole-run timeout 3600 s. FD's out-of-table
arm and every re-validation batch take `~/agxre/gpulease.sh EXP-0159 900`. After two genuine
(majority-of-3) hangs in one arm, that arm STOPS and is reported PARTIAL.
If the neo stops answering: STOP, report BLOCKED. `macvdmtool` is never used.

## 6. Raw-record schema (append-only, one JSON object per line)

`raw/<run_id>/<family>.jsonl`:

```json
{"family":"fb","case":"iadd2.b0=0x9f","instr":"iadd2","field":"byte0","value":159,
 "bytes":"9f0156000208005017 05","row":0,"observed":"a5a5a5a5a5a5a5a5",
 "oracle_class":"i64_add","match":true,"outcome":"ok","fault_class":"",
 "reruns":1,"target":"G17P","note":""}
```

`outcome` ∈ `ok | silent_zero | wrong_value | reject | fault | hang | victim | undecodable`.
Per-run metadata in `raw/<run_id>/00_meta.json` (device identity, OS build, compiler version,
carrier hashes, git revision, concurrent-experiment note).

## 7. Gates (all must pass before any answer block is written)

1. `analysis/verify.py --preflight` — carrier sources hash-match `CAPTURE_CONTRACT.json`.
2. Two independent runs, `g17p-<date>-run01` and `-run02`, each in a fresh process.
3. Every FA/FC/FD/FE/FF case, and every FB case except those recorded `victim`, must agree
   between runs. Disagreements are listed, not averaged.
4. Every family's positive control fired.
5. Every non-`ok` case has a recorded fault-classification string and a majority-of-3 verdict.

An item whose gates do not pass is reported as a bounded `UNKNOWN` with the exact tested range.
**No answer is invented.**

## 8. Clean-room provenance

Clean-room provenance: HW-PROBE / OWN-SHADER / PUBLIC
Inputs inspected: authored MSL (`kernels/*.metal`), authored ObjC harnesses (`harness/*.m`),
authored Python runners/analysis, and the machine code compiled from our own MSL. Public Metal /
MSL API names and the public `MTLSamplerDescriptor` / `MTLArgumentEncoder` surfaces are used as
calling conventions only, never as a source of a hardware fact.
Apple binary introspection: NONE.
