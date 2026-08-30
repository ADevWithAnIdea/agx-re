# EXP-0159 — Part-II questionnaire answer blocks

Six items, all measured on the **documentation target itself** (A18 Pro / G17P), so every answer
below is **direct** evidence, not `INFERRED`.

Each block is preceded by `### ANCHOR: <line>`, an exact verbatim line from
`APPLE9_RE_IMPLEMENTATION_GAPS.md`. Every anchor was checked unique with
`grep -Fxc "<line>" APPLE9_RE_IMPLEMENTATION_GAPS.md` → `1`. Splice each block **immediately after
its anchor line**, indented as a `>` blockquote exactly as written. This experiment does **not**
edit `APPLE9_RE_IMPLEMENTATION_GAPS.md`.

| item | anchor line (verbatim) | `grep -Fxc` |
|---|---|---|
| P2-06 | `  and software emulation support?**` | 1 |
| TEX-01 | `  divide, including zero, signed-zero, infinity, NaN, and array-coordinate behavior?**` | 1 |
| TEX-19 | `  descriptor-pointer representation and its reuse/lifetime rules.` | 1 |
| TEX-21 | `  the final valid ID, descriptor duplication/deduplication, destruction, and ID reuse.` | 1 |
| TEX-22 | `  silently reuse a still-live ID.` | 1 |
| MEM-19 | `  when its declared preload count exceeds the supported capacity?**` | 1 |

---

### ANCHOR:   and software emulation support?**

  > **Answered 2026-08-30 (EXP-0159, A18 Pro/G17P — the documentation target) — P2-06 NO.**
  > **No native FP64 arithmetic exists on Apple9, in any form we could reach.** This is an
  > absence-of-capability result: a driver must emulate binary64 in software or refuse to expose it.
  > **(a) API surface — 48 gated compiles, 0 unexpected outcomes, reproduced in both runs.** Every
  > spelling of a 64-bit float we could write is rejected by the runtime compiler at *all three*
  > language-version settings (default, 3.1, 3.2): `double` as a buffer type / local / parameter,
  > `double2`, `double4`, `as_type<double>`, `_Float64`, `long double`,
  > `__attribute__((ext_vector_type))` of `double`, `atomic<double>`, `fma(double,…)`,
  > `simd_sum(double)`, a `double` struct member, and a `double` divide. The controls `float`,
  > `half` and **`ulong`** all compile — so it is *floating-point* 64-bit that is absent, not
  > 64-bit. Verbatim diagnostics: `'double' is not supported in Metal`, and — decisively — the
  > vector spellings resolve to reserved placeholder types:
  > `'double4' (aka '__Reserved_Name__Do_not_use_double4') is an incomplete type`. The type is
  > deliberately excluded from the language, not merely unimplemented.
  > **(b) ISA opcode space — the complete single-byte neighbourhood of the only known native
  > 64-bit ALU instruction, 2,550 encodings per run × 2 gated runs = 5,100 executions, 0 hits.**
  > Carrier: our own `ulong` subtract, which on G17P compiles to
  > `get_sr, device_load, device_load, iadd2, device_store, stop` with the single arithmetic
  > instruction `1f 01 56 00 02 08 00 50 17 05` at `_agc.main+0x20` — **byte-identical to
  > EXP-0146's M4 carrier**, the first G17P confirmation of that instruction. All 10 bytes × all
  > 256 values were spliced and executed against four input rows chosen so that binary64
  > add/sub/mul/div, int64 add/sub/and/or/xor, lane-wise f32x2 add/sub, passthrough, zero and the
  > poison pattern all give **different** 64-bit words. **Not one encoding reproduced a binary64
  > operation on all four rows.** Detection power is proved by the pre-registered positive control:
  > setting byte0 bit 7 turns the subtract into an exact 64-bit **integer** add on every row, in
  > both runs.
  > **(c) The faulting cases cannot be hiding an FP64 encoding.** A spurious fault could in
  > principle conceal an FP64-capable encoding, so the 217 encodings that faulted in *both* gated
  > runs were re-run **5× each** — 1,085 further executions — and **none produced a binary64 result
  > on all four rows** in any repetition (`raw/g17p-20260829-fbc01/`). That pass ran **unlocked**; three attempts to repeat it under
  > `gpulease.sh` (`FIELD-SWEEP-PROTOCOL.md` §7A) all timed out waiting for the lease under
  > sustained sibling contention and are recorded in
  > `raw/g17p-20260829-fbc01/LEASE_ATTEMPTS.txt`. Isolation can only convert a spurious fault into a *readable* result, and
  > every readable result in 5,100 + 1,085 executions was non-binary64, so it can strengthen but not
  > weaken this negative.
  > **(d) Structural corroboration (desk, over our own committed database).** Across all 171
  > `tools/agx-isa/db.json` descriptors there are **14 float operand-size fields**, on 8
  > instructions (`falu2`, `falu2_ext`, `falu2_srcmod10`, `falu2_uni`, `falu2i`, `falu3_srcmod12`,
  > `falu_srcmod12b`), and **every one of them is exactly 1 bit wide with the enum
  > `{b16, b32}`** — there is no encodable third float width. `fspecial.precsel`, the only other
  > float-precision selector, names `f16 result` and `f32 result` and nothing wider, and **no
  > descriptor in the database mentions a 64-bit floating-point concept at all**. EXP-0146's native
  > 64-bit ADD is integer register-pair machinery — exactly what this question excludes.
  > **Bound (stated in advance, not after the fact):** this searched the complete *single-byte*
  > space of one instruction plus the whole MSL surface. It does not exhaust the multi-byte opcode
  > space, and it cannot see an FP64 unit reachable only from a stage or instruction family our
  > carrier never enters. Within that bound the answer is a clean, reproduced **No**.
  > **Compiler consequence:** binary64 must be lowered to software emulation (or the feature not
  > exposed). No `has_fp64`-style option may be enabled, and no NIR 64-bit float op may survive to
  > the backend.
  > G17P target (direct, not inferred); no M4 claim.
  > Evidence: `experiments/EXP-0159-g17p-questionnaire-tail/` — `raw/g17p-20260829-run01/fa.jsonl`,
  > `fb.jsonl`, `raw/g17p-20260829-run02/` (same two), `raw/g17p-20260829-fbc01/fbconfirm.jsonl`,
  > `analysis/verdicts.json` (`P2-06.msl`, `P2-06.isa`), `kernels/fa/*.metal`, `kernels/u64op.metal`.

---

### ANCHOR:   divide, including zero, signed-zero, infinity, NaN, and array-coordinate behavior?**

  > **Answered 2026-08-30 (EXP-0159, A18 Pro/G17P — the documentation target) — TEX-01 NO, and the
  > premise of the question is itself refuted: `tex_addr_setup.form = 0x01` is NOT a coordinate
  > projection.** `lower_txp` must stay enabled.
  > **What form 0x01 actually does.** With a carrier that samples a 4×4×3-mip R32Float texture whose
  > texel is `1000*level + 100*y + x` (so a returned float *names* the texel and level), form 0x01's
  > result is the level-0 nearest texel of the **unmodified** `(u,v)` and is **completely invariant
  > in the third scalar operand** — over `{1, 2, 4, 0.5, 0.25, +0, −0, −1, +inf, −inf, NaN, 1e−30,
  > 1e+30}` at four coordinate pairs, in both gated runs, with zero disagreement:
  > `(0.375,0.625)→201`, `(0.75,0.25)→103`, `(0.9,0.9)→303`, `(0.125,0.125)→0`. A projective divide
  > by 2 would have given 100, 1, 101 and 0 respectively. Refuted at every discriminating point.
  > On a `texture2d_array` carrier form 0x01 additionally **discards the array-layer operand** and
  > samples layer 0 (`201` where the compiler's own encoding gives `1201`).
  > **Detection power (pre-registered positive control) fired:** with the compiler's own form 0x05,
  > changing the third operand 1→2 moves the result `1100 → 2000`, and each coordinate pair yields
  > its own distinct texel. The method can see a real change; there is none to see at form 0x01.
  > **Two adversarial refuter hunts, both negative.** (i) With form pinned to 0x01, **210 operand
  > encodings per carrier (420 across the 2D and array carriers)** — every byte of the instruction
  > from +2 to +11 crossed with 21 values (all the values EXP-M4-14 found live, plus boundaries) —
  > were executed at three different third-operand values. **Every one returned the unprojected
  > texel; not a single encoding made the result depend on that operand.**
  > (ii) A **complete 256-value sweep of the form byte itself, run on both carriers**: on each,
  > exactly **32** values make the sampled texel depend on the third operand, and they are precisely
  > those with **`(form & 7) == 5`** (the high five bits are don't-care); in all 32 the operand
  > behaves as the **LOD** (2D carrier) or the **array layer** (array carrier), never as a divisor.
  > On the 2D carrier **128 values give the unprojected level-0 texel and 0 of 256 match the
  > projective oracle**; the array carrier reproduces the same **0 of 256**. So the capability is
  > absent from the instruction, not merely absent from the value the database happens to label.
  > **db-defect (`FIELD-SWEEP-PROTOCOL.md` §6).** `tools/agx-isa/db.json` and `validation.json` name
  > `tex_addr_setup.form = 0x01` *"coord-projection (samples level 0)"*, labelled `hardware-run`
  > from EXP-M4-14 (A18). That label over-reads its own evidence: EXP-M4-14's single observation was
  > `1100 → 201`, i.e. the level-1 texel became the level-0 texel **at the same (u,v)** — which is
  > exactly "the operand is dropped and level 0 is sampled", with no coordinate change. The correct
  > semantics is **"third scalar operand ignored; sample level 0 / layer 0 at the raw coordinates"**.
  > The `coord-proj` name should be retired.
  > **Also observed on this carrier (recorded, not promoted):** form 0x07 leaves the destination
  > **unwritten** in all 52 2D cases (52/52, both runs) while on the array carrier it forces
  > **layer 1** and ignores the operand; form 0x00 behaves as form 0x01; form 0x0d matches 0x05.
  > **Not excluded:** a projective divide implemented by some *other* instruction (a reciprocal +
  > multiply in the coordinate setup chain, e.g. `tex_coord_setup`) rather than by this one. This
  > result bounds `tex_addr_setup` only.
  > **Compiler consequence:** `lower_txp` stays enabled; projective sampling must be lowered to an
  > explicit divide before the texture op.
  > G17P target (direct, not inferred); supersedes the A18 `coord-projection` naming from EXP-M4-14.
  > Evidence: `experiments/EXP-0159-g17p-questionnaire-tail/` — `raw/g17p-20260829-run01/ff.jsonl`,
  > `raw/g17p-20260829-run02/ff.jsonl` (2,215 records each, **0 cross-run disagreements**),
  > `raw/g17p-20260829-adv01/ffsweep.jsonl` and `raw/g17p-20260829-adv02/ffsweep.jsonl`
  > (the 256-value form sweeps, 2D and array carriers),
  > `analysis/verdicts.json` (`TEX-01`), `kernels/texlod.metal`, `kernels/texarr.metal`,
  > `harness/texrun.m`, `harness/ff_formsweep.py`.

---

### ANCHOR:   descriptor-pointer representation and its reuse/lifetime rules.

  > **Answered 2026-08-30 (EXP-0159, A18 Pro/G17P — the documentation target) — TEX-19 YES, and the
  > published 1,000,000 is an API limit, not a hardware indexing ceiling.**
  > **Representation.** Argument buffers are **Tier 2**. An `array<texture2d<uint>, CAP>` argument
  > buffer is a tightly packed array of **8-byte entries, stride exactly 8** (`encodedLength` is
  > `CAP*8` for every `CAP` tested). Each entry is the texture's `MTLResourceID._impl`, and that is a
  > **small dense sequential integer** (1, 2, 3, … in creation order) — **an index into a
  > device-global texture table, not a virtual address**. A driver can therefore build a bindless
  > texture heap by storing 8-byte resource IDs directly.
  > **Uniform selection.** With a genuine runtime `uint` index, every populated canary returned its
  > own distinguishing texel, at `CAP = 1,000,000`, at indices
  > **0, 1, 2, 7, 255, 256, 65535, 65536, 262143, 499999, 500000, 999998 and 999999** — including
  > the last legal entry of the published limit. Byte-identical in both gated runs.
  > **Non-uniform per lane.** One dispatch, 8 lanes, 8 *different* indices
  > (0, 1, 255, 65535, 262143, 499999, 999998, 999999): every lane read its own texture. Divergent
  > per-lane bindless selection works at those magnitudes.
  > **Past the published limit.** A second arm declared `CAP = 2,000,000` and repeated the test:
  > indices **1000000, 1000001, 1048576, 1999998 and 1999999** *also* selected correctly, uniformly
  > and per lane. The runtime compiler accepted declared arrays of **1,000,001 / 2,000,000 /
  > 16,777,216 / 67,108,864** entries (`encodedLength` = 8·CAP throughout, up to 536,870,912 bytes).
  > **So 1,000,000 is a Metal specification limit; the hardware's index arithmetic is an ordinary
  > `base + idx*8` load and shows no ceiling at that value.** A driver must still respect the API
  > limit, but need not fear a hardware cliff at it.
  > **Unpopulated / out-of-array entries.** Silent zero on a load, no fault, no aliasing, at
  > 3, 4096, 499998, 500001, 999996, 999997, 1000000, 1000001, 1500000 and 2000000 — reproducing
  > EXP-0095's M4 rule (`CAP=256`, `K=8`) **on G17P at four orders of magnitude larger index**, and
  > extending it past the declared array, where the read simply falls off the argument buffer and
  > returns zero (consistent with the out-of-allocation zero-fill of EXP-0076/0122).
  > **Lifetime/residency.** Only the canary textures exist; each is passed to `useResource:`. An
  > entry's validity is the referenced texture's lifetime — the ID is a table index, so the reuse
  > rules are the same class as the sampler case in TEX-22 below.
  > **Not tested:** one million *simultaneously resident real* textures (this host has 8 GiB); the
  > nonresident-resource sub-question of TEX-20 is still open.
  > G17P target (direct, not inferred).
  > Evidence: `experiments/EXP-0159-g17p-questionnaire-tail/` — `raw/g17p-20260829-run01/fc.jsonl`
  > and `raw/g17p-20260829-run02/fc.jsonl` (62 records each, **0 cross-run disagreements, 0 faults**),
  > `analysis/verdicts.json` (`TEX-19`), `kernels/bindtex.metal`, `harness/bindtex.m`.

---

### ANCHOR:   the final valid ID, descriptor duplication/deduplication, destruction, and ID reuse.

  > **Answered 2026-08-30 (EXP-0159, A18 Pro/G17P — the documentation target) — TEX-21 YES, at and
  > beyond index 499,999, uniformly and per lane, with sampler resource IDs above 500,000.**
  > **Representation.** `maxArgumentBufferSamplerCount = 500000`. A bindless sampler heap
  > (`array<sampler, SCAP>`) is a tightly packed array of **8-byte `gpuResourceID`s, stride exactly
  > 8** (`encodedLength = 8·SCAP` for SCAP = 500,000 / 500,001 / 1,000,000 / 2,000,000, all of which
  > the runtime compiler accepts). This reproduces EXP-O2B's A18 layout finding and extends it to
  > the ceiling and past it.
  > **Method — an independent-path oracle, not self-confirmation.** Six canary sampler classes were
  > built from (`lodMaxClamp` ∈ {0,1}) × (three s/t address-mode combinations) and sampled at the
  > deliberately out-of-range coordinate (1.2, 1.2) at explicit `level(2.0)` on a 4×4×3-mip texture
  > whose texel is `1000*L + 100*y + x`. Each class's **fingerprint was first measured through a
  > directly bound `[[sampler(0)]]`** — a different binding path entirely — giving six distinct
  > non-zero values **303, 300, 3, 1101, 1100, 1001**. The bindless heap then had to reproduce that
  > exact fingerprint at that index, so a returned float *names which sampler ran*.
  > **Uniform selection.** Correct at **0, 1, 2, 255, 256, 65535, 65536, 262143, 499997, 499998,
  > 499999** — the last legal entry — **and also at 500000, 500001, 524288, 999998 and 999999**, in a
  > heap declared at 1,000,000 entries. Identical in both gated runs.
  > **Non-uniform per lane.** One dispatch, 8 lanes, indices 0, 1, 2, 262143, 499999, **500000**,
  > **500001**, **999999**: every lane got its own sampler's fingerprint.
  > **Resource IDs above the ceiling work too.** Before placing the high-index canaries, 500,100
  > filler samplers were created so the ID watermark passed 500,000; the canaries at indices ≥ 499997
  > therefore carry `gpuResourceID`s of **500,108–500,113** (visible verbatim in the heap bytes:
  > index 499999 holds `000000000007a190` = 500,112 and index 500000 holds `000000000007a191`
  > = 500,113), and they select correctly. So neither the heap index nor the sampler
  > table index stops at 499,999.
  > **Dedup.** Two *identical* `MTLSamplerDescriptor`s return the **same** `gpuResourceID` (1 and 1);
  > a control pair differing only in `magFilter` returns 1 and 2. The published limit is therefore a
  > limit on **distinct sampler states**, not on API calls — a driver that creates the same sampler
  > repeatedly consumes one slot.
  > G17P target (direct, not inferred); supersedes/extends EXP-O2B, whose evidence stopped at K=64.
  > Evidence: `experiments/EXP-0159-g17p-questionnaire-tail/` — `raw/g17p-20260829-run01/fd.jsonl`
  > and `raw/g17p-20260829-run02/fd.jsonl` (99 records each, **0 cross-run disagreements, 0 faults**),
  > `analysis/verdicts.json` (`TEX-21`), `kernels/sampheap.metal`, `harness/sampheap.m`.

---

### ANCHOR:   silently reuse a still-live ID.

  > **Answered 2026-08-30 (EXP-0159, A18 Pro/G17P — the documentation target) — TEX-22, four
  > sub-answers. The headline: allocation does NOT fail at 500,001, exhaustion never reuses a live
  > ID, but a DESTROYED id is recycled and a stale bindless entry then silently selects the new
  > owner.**
  > **1. Allocating the 500,001st sampler — no failure.** `newSamplerStateWithDescriptor:` was
  > walked with **2,000,002 distinct descriptors**, four times the published ceiling, in both gated
  > runs: **no `nil` was ever returned** (`first nil at n=0`, i.e. never), and IDs came back as a
  > dense strictly-increasing sequence with **2,000,002 unique IDs for 2,000,002 states** —
  > checkpointed at n = 250k → 250,001, 500k → 500,001, 750k → 750,001, 1M → 1,000,001,
  > 1.25M → 1,250,001, 1.5M → 1,500,001, 1.75M → 1,750,001, 2M → 2,000,001. (The constant `+1`
  > offset is one non-argument-buffer sampler created as a control, which also consumed a table
  > slot — ID 3; the raw record's `first non-dense ID at n=3` is exactly that one-off shift, not a
  > gap.) **No ID was ever re-issued while its holder was alive** (`first live-ID duplicate at n=0`,
  > i.e. never). Cost: ~900 MB and
  > ~5.4 s. `maxArgumentBufferSamplerCount = 500000` is therefore **not** an allocation ceiling on
  > this OS build; it bounds what one argument buffer may reference, and userspace gets no
  > allocation failure to detect it with. **Driver consequence: a driver must enforce the 500,000
  > limit itself — the runtime will not.**
  > **2. Indexing entry 500,000 — works.** See TEX-21: a heap entry at index 500,000 holding a
  > sampler with `gpuResourceID` **500,113** selected that sampler exactly. Neither the index nor the ID
  > faults at the boundary.
  > **3. An unpopulated entry — a default sampler, NOT zero and NOT a fault.** A heap entry that was
  > never written (raw `0x0000000000000000`) samples as a **zero-filled sampler descriptor**:
  > nearest filtering, clamp-to-edge, LOD clamped to 0 — fingerprint `303` at indices 3, 499996,
  > 500002, 1000000 and 2000000, in both runs, with no fault. **This is the opposite of the bindless
  > *texture* case (TEX-19), where an unpopulated entry reads a silent zero.** A driver must not
  > assume "unbound sampler ⇒ zero result": it gets a real, plausible-looking sample from a default
  > sampler, which is a silent-wrong-result hazard rather than a detectable one.
  > **4. A destroyed sampler ID IS recycled, and a stale heap entry silently follows it.** A sampler
  > was created (ID 4), its ID stored in heap entry 0, and the sampler released; the next distinct
  > creation **received the same ID 4**, and sampling through the *unchanged* heap entry then
  > returned the **replacement** sampler's fingerprint (`3`) rather than the released one's
  > (`1001`). Reproduced in both gated runs. **Driver consequence: a bindless sampler heap entry is
  > a weak reference. A driver must keep every sampler referenced by a live heap alive, or rewrite
  > the entry on destruction — otherwise the entry silently aliases an unrelated sampler with no
  > fault and no zero.** Note this is *destruction*-driven recycling, not *exhaustion*-driven: the
  > question's specific worry ("exhaustion cannot silently reuse a still-live ID") is answered
  > **confirmed safe** — 2,000,002 live states, zero live-ID collisions.
  > **5. Raw out-of-table IDs — fault-free.** Writing arbitrary IDs directly into a heap entry
  > (EXP-O2B proved a hand-written ID array is byte-identical to the encoder's output) and sampling
  > through them: `0`, `499999`, `500000`, `500001`, `1000000`, `0xFFFFFFFF`,
  > `0xFFFFFFFFFFFFFFFF` and `0x8000000000000000` **all returned the default-sampler fingerprint
  > `303`, with no fault, no hang, no device loss and no aliasing to a live sampler**; ID `1`
  > returned a different real value (`101`), i.e. low IDs are live table entries. The baseline was
  > re-validated immediately afterwards and returned its own fingerprint (`1001`) — the device was
  > unharmed. Run under `gpulease.sh`, as pre-registered for the hang-prone arm.
  > **Not tested:** whether the 500,000 limit is enforced anywhere else (Metal validation layer,
  > `useResource`/residency-set paths), and the behaviour of a heap that genuinely references more
  > than 500,000 *distinct* samplers in one dispatch.
  > G17P target (direct, not inferred).
  > Evidence: `experiments/EXP-0159-g17p-questionnaire-tail/` — `raw/g17p-20260829-run01/fd.jsonl`
  > and `raw/g17p-20260829-run02/fd.jsonl` (`ceiling_walk`, `dedup_*`, `reuse_*`, `stale_id_sample`,
  > `id_*`, `oob_baseline_after`), `analysis/verdicts.json` (`TEX-22`), `harness/sampheap.m`.

---

### ANCHOR:   when its declared preload count exceeds the supported capacity?**

  > **Answered 2026-08-30 (EXP-0159, A18 Pro/G17P — the documentation target) — MEM-19 answered in
  > three parts: the USC constant/uniform program populates one base slot per *uniformly read*
  > binding and no more; the public path cannot declare more than 31 buffers; and every base slot
  > above the populated count is a silent zero, never a fault.**
  > **1. What the "USC constant/uniform program" physically is, measured.** On Apple9 the uniform
  > preload is performed by `0x67` `device_load`s inside **`_agc.main.constant_program`** — confirmed
  > directly here by compiling our own kernels with 1…30 buffer arguments read **uniformly** and
  > counting them. The constant program grows with the binding count and its loads carry
  > `base_slot` values in **even steps of 2**:
  > | bindings | `constant_program` bytes | `0x67` loads in it | its `base_slot` values |
  > |---|---|---|---|
  > | 1 | 64 | 1 | 0 |
  > | 2 | 64 | 2 | 0, 2 |
  > | 4 | 128 | 3 | 2, 4, 6 |
  > | 8 | 256 | 7 | 2…14 |
  > | 16 | 512 | 16 | 0…30 |
  > | 24 | 704 | 23 | …46 |
  > | 28 | 832 | 27 | …54 |
  > | 30 | 832 | 29 | …58 |
  > So the constant program addresses base slots in **2-unit steps** (a 64-bit base address occupies
  > two units) and reaches slot unit **58** for the maximum 30 non-output bindings. **It preloads
  > exactly the accesses it can hoist and no others:** the same kernels with *thread-varying* indices
  > put **zero** loads in the constant program (it stays at its 64-byte floor) and one
  > `device_load` per binding in `_agc.main`, with `base_slot` equal to the Metal binding index,
  > dense 1…30 with no holes. "Declared preload count" is therefore a compiler choice over the
  > uniform subset, not a fixed per-stage number.
  > **2. Can it populate *every* usable base slot? No — and the binding cap, not the selector, is
  > why.** The `base_slot` selector was swept over **all 256 values** on a spliced probe
  > `device_load` in a carrier with 31 buffers bound (buffer *k* filled with `0x51000000|k`), under
  > the GPU lease: slots **1…30 each resolve to their own binding** (all 30, exactly), slot **0**
  > resolves to binding 0 — the output buffer itself, so the probe reads back its own poisoned
  > destination — and **slots 31…127 read a silent zero** (94 of the 0…127 range under isolation).
  > **Only 31 of the 128 selectable slots can be populated through the public path**, and the reason
  > is a hard API ceiling: `[[buffer(31)]]` is rejected by the runtime compiler with
  > *"'buffer' attribute parameter is out of bounds: must be between 0 and 30"* (declared counts 1,
  > 2, 4, 8, 16, 24, 28, 30 accept; 31, 32, 40, 64 reject). Whether slots 32…127 can be populated by
  > a mechanism the public path does not expose is **UNKNOWN** and not decidable from userspace on
  > this target.
  > **3. What happens past capacity — silent, never a fault.** Across the full 256-value sweep, in
  > isolation and again unlocked in gated run01, **no value of the base-slot byte produced a
  > reproducible hardware fault**: out-of-range/unpopulated slots read zero, and the selector is
  > **7-bit — values 128…255 mirror 0…127 exactly, 128 of 128 matching pairs** under isolation.
  > This **reproduces EXP-0083's M4/G16G 7-bit-mirror finding on G17P**, the documentation target,
  > for the first time. Practical consequence: an out-of-range base slot does **not** fault — it
  > silently reads zero, or, for values ≥ 128, silently addresses a *real, different* binding. A
  > driver must never emit a slot it has not populated; the hardware will not tell it.
  > **Residual (honest):** 3 of 256 isolated sweep cases (slots 32, 41 and 120) returned a
  > command-buffer error rather than a clean silent zero; **all three read `00000000` (silent zero)
  > in gated run01**, so per `FIELD-SWEEP-PROTOCOL.md` §7A the fault is not reproducible and is
  > attributed to concurrent sibling load, not to the encoding. They are recorded, not promoted.
  > **Also recorded:** gated run02's FE arm was killed at its very first unmutated baseline by a
  > concurrent GPU error and produced no sweep; that partial capture is **retained unmodified**
  > under its own run id and was **not** reused — the replacement was captured under a new id
  > (`g17p-20260829-fe-iso01`) under the lease, which is the data cited above.
  > G17P target (direct, not inferred); cross-target confirmation of EXP-0083 (M4/G16G).
  > Evidence: `experiments/EXP-0159-g17p-questionnaire-tail/` —
  > `raw/g17p-20260829-fe-iso01/fe.jsonl` (isolated 256-value sweep),
  > `raw/g17p-20260829-run01/fe.jsonl` (unlocked sweep + the constant-program census),
  > `raw/g17p-20260829-run02/fe.jsonl` (retained partial), `analysis/verdicts.json` (`MEM-19`),
  > `kernels/slot31.metal`, `kernels/slotdecl_*.metal`, `kernels/slotdeclu_*.metal`,
  > `harness/fe_isolated.py`.
