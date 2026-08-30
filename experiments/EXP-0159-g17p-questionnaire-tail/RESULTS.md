# EXP-0159 results — the last six Part-II questionnaire items that needed hardware

## STATUS: 6 of 6 CLOSED on G17P

All six ran on the **A18 Pro / G17P**, the documentation target, so these are **direct** results,
not `INFERRED`. `SFU-04` (blocked by clean-room rule 5) was deliberately not touched.

| item | verdict |
|---|---|
| `P2-06` native FP64 | **No** — absent from the MSL surface *and* from the complete single-byte space of the only native 64-bit ALU op. Bounded negative. |
| `TEX-01` projective divide | **No** — and the premise is refuted: `tex_addr_setup.form=0x01` is not a projection. **db-defect** recorded. |
| `TEX-19` bindless texture to 1,000,000 | **Yes** — and past it; 1,000,000 is an API limit, not a hardware ceiling. |
| `TEX-21` bindless sampler to 499,999 | **Yes** — and past it, with resource IDs above 500,000. |
| `TEX-22` 500,001st sampler / destroyed ID | **Answered**, four parts. Allocation does *not* fail; exhaustion never reuses a live ID; **destruction does**, and a stale heap entry silently follows it. |
| `MEM-19` USC preload capacity | **Answered**, three parts. 31 slots populatable (a hard API cap), 7-bit selector confirmed on G17P, past-capacity is silent-zero/mirror, never a fault. |

The six answer blocks, with their verified-unique splice anchors, are
**`analysis/questionnaire_answers.md`**. This experiment does not edit
`APPLE9_RE_IMPLEMENTATION_GAPS.md`.

---

## Runs, gates and concurrency

| run id | what | outcome |
|---|---|---|
| `raw/prefreeze/` | pre-freeze feasibility probe, **not evidence** | 3 facts, retained verbatim |
| `g17p-20260829-run01` | gated run, all six families | complete |
| `g17p-20260829-run02` | gated run, all six families | complete except family FE (below) |
| `g17p-20260829-fe-iso01` | FE re-captured **under `gpulease.sh`** | complete, 256/256 |
| `g17p-20260829-adv01` | post-registration: complete 256-value `tex_addr_setup.form` sweep, 2D carrier | complete |
| `g17p-20260829-adv02` | the same sweep on the 2D-array carrier | complete |
| `g17p-20260829-fbc01` | post-registration: 217 doubly-faulting FB encodings re-run 5× | complete, 1,085 executions |

```
python3 analysis/verify.py --preflight                                     PASS (50 sources)
python3 analysis/verify.py --captured g17p-20260829-run01 g17p-20260829-run02
    fa  CONTROL FIRED/FIRED   2 x 49 records    disagree 0
    fb  CONTROL FIRED/FIRED   2645 common       disagree 20   (all one class, see below)
    fc  CONTROL FIRED/FIRED   62 common         disagree 0
    fd  CONTROL FIRED/FIRED   92 common         disagree 0
    fe  CONTROL FIRED/NOT-FIRED (run02 FE killed at its baseline; replaced by fe-iso01)
    ff  CONTROL FIRED/FIRED   2215 common       disagree 0
python3 analysis/verify.py --captured g17p-20260829-run01 g17p-20260829-fe-iso01
    fe  CONTROL FIRED/FIRED   281 common        disagree 5    (all contamination-class, see below)
```

**Concurrency (`FIELD-SWEEP-PROTOCOL.md` §7.4).** Every family except FD's out-of-table arm and the
FE re-capture ran **unlocked and concurrent with sibling GPU experiments**. At least EXP-0156 was
demonstrably driving the same device throughout (it held `gpulease.sh` during our confirmation
window). Contamination was continuously visible and continuously labelled: 157 FB cases and 7 FE
cases carry `kIOGPUCommandBufferCallbackErrorInnocentVictim` verbatim. **No promoted claim in this
experiment rests on a `fault` verdict**, which is what makes §7A's warning non-load-bearing here —
see "Why the faults do not matter" below.

**Two harness defects found and fixed before the gated runs, both by the poisoned read-back
buffer:** (1) a canary-value scheme that aliased at index 65536; (2) dispatches that report
`MTLCommandBufferStatusCompleted` yet leave the poisoned output untouched. The second is a real
device-level observation, not just a harness bug: under concurrent load a command buffer can
complete successfully having written nothing. All harnesses now retry on it.

---

## OBSERVED (directly, before interpretation)

### FA — the MSL surface for FP64 (P2-06)

98 gated compiles (49 per run), **0 unexpected outcomes, both runs identical**. Controls
`ctrl_f32`, `ctrl_f16`, **`ctrl_u64`** accept at all three language-version settings. All 13 FP64
spellings reject at all three. Verbatim diagnostics include
`'double' is not supported in Metal` (144 occurrences), `unknown type name '_Float64'`, and
`'double4' (aka '__Reserved_Name__Do_not_use_double4') is an incomplete type`.

### FB — the complete single-byte space of the native 64-bit ALU op (P2-06)

Carrier `kernels/u64op.metal` (`out[gid] = a[gid] - b[gid]` on `ulong`) compiles on G17P to
`get_sr, device_load, device_load, iadd2, device_store, stop`, with `iadd2` =
`1f 01 56 00 02 08 00 50 17 05` at `_agc.main+0x20`, **0 leftover bytes** — byte-identical to
EXP-0146's M4 carrier.

- 2,550 spliced encodings per run × 2 runs = **5,100 executions**; outcomes
  `ok` 4,420 / `fault` 523 / `victim` 157.
- **Strict FP64 hits: 0.** The verdict requires one binary64 operation (add/sub/mul/div) to
  reproduce **all four** input rows; per-row coincidences are attributed to the simpler hypothesis
  by construction (the oracle tests passthrough/int/f32×2 first, and `f64_min`/`f64_max` are
  excluded because on the `+inf` row they are indistinguishable from a passthrough).
- Positive control fired in both runs: byte0 `0x1f → 0x9f` yields `i64_add` exactly on all four
  rows.
- Baseline re-validated every 128 cases; no cascade in either run.

### FC — bindless argument-buffer textures (TEX-19)

62 records per run, **0 cross-run disagreements, 0 faults**. Argument buffers are Tier 2.

- `encodedLength` = **8 × CAP exactly** for declared CAP 1,000,000 / 1,000,001 / 2,000,000 /
  16,777,216 / 67,108,864 — all accepted by the runtime compiler (largest = 536,870,912 bytes).
- Each entry is the texture's `MTLResourceID._impl`: a **small dense sequential integer**
  (1, 2, 3, … in creation order), not a VA.
- `CAP = 1,000,000` arm — correct at indices
  **0, 1, 2, 7, 255, 256, 65535, 65536, 262143, 499999, 500000, 999998, 999999**;
  silent zero at 3, 4096, 499998, 500001, 999996, 999997, 1000000, 1000001, 2000000.
- `CAP = 2,000,000` arm — correct at **0, 999999, 1000000, 1000001, 1048576, 1999998, 1999999**;
  silent zero at 1500000, 2000000.
- Per-lane divergent selection (8 lanes, 8 different indices) correct in both arms.

### FD — bindless samplers (TEX-21, TEX-22)

99 records per run, **0 cross-run disagreements, 0 faults**.

- `maxArgumentBufferSamplerCount = 500000`. `array<sampler,N>` accepted at
  N = 500,000 / 500,001 / 1,000,000 / 2,000,000, `encodedLength = 8N`.
- Independent-path fingerprints (sampler bound directly at `[[sampler(0)]]`), six distinct non-zero
  values: **303, 300, 3, 1101, 1100, 1001**.
- **Ceiling walk: 2,000,002 distinct descriptors created, no `nil` ever, 2,000,002 unique IDs, no
  live-ID duplicate ever, ~900 MB, ~5.4 s.** Reproduced in both runs. IDs are dense and strictly
  increasing (250k→250,001 … 2M→2,000,001); the constant `+1` is one non-argument-buffer control
  sampler that also took a slot (ID 3), which is what the raw `first non-dense ID at n=3` records.
- Dedup: identical descriptors → the same ID (1, 1); a `magFilter`-only difference → 1, 2.
- Heap selection correct at 0, 1, 2, 255, 256, 65535, 65536, 262143, 499997, 499998, 499999,
  **500000, 500001, 524288, 999998, 999999**. Entries at index ≥ 499997 hold resource IDs
  **500,108–500,113** (e.g. index 500000 holds `000000000007a191` = 500,113).
- Unpopulated heap entry (raw zero) → fingerprint **303**, i.e. a zero-filled default sampler, at
  indices 3, 499996, 500002, 1000000, 2000000. Not zero, not a fault.
- Destroyed-ID: ID 4 released → the next distinct creation received **ID 4 again**; the unchanged
  heap entry then sampled as the **replacement** (`3`), not the released sampler (`1001`).
- Out-of-table raw IDs 0 / 499999 / 500000 / 500001 / 1000000 / 0xFFFFFFFF / 0xFFFFFFFFFFFFFFFF /
  0x8000000000000000 → all `303`, **no fault, no hang, no device loss**; ID 1 → `101`. Baseline
  re-validated afterwards → `1001`. Run under `gpulease.sh`.

### FE — the USC constant/uniform program and the base-slot selector (MEM-19)

- Declared buffer arguments: 1, 2, 4, 8, 16, 24, 28, 30 **accept**; 31, 32, 40, 64 **reject** with
  `'buffer' attribute parameter is out of bounds: must be between 0 and 30`.
- **Uniformly** read bindings put their loads in `_agc.main.constant_program`: length 64 → 832
  bytes as N goes 1 → 30, with 1, 2, 3, 7, 16, 23, 27, 29 `0x67` loads and `base_slot` values in
  **even steps of 2**, reaching **58** at N = 30.
- **Thread-varying** reads put **zero** loads in the constant program and one `device_load` per
  binding in `_agc.main`, `base_slot` = the Metal binding index, dense 1…30.
- Isolated 256-value `base_slot` sweep (31 buffers bound, under the lease):
  slots **1…30 each resolve to their own binding** (all 30); slot 0 resolves to binding 0 (the
  output buffer, so the probe reads back its own poison); slots 31…127 **silent zero** (94 cases);
  **128…255 mirror 0…127, 128/128 exact**. Outcomes: `ok` 60, `silent_zero` 191, `unwritten` 2,
  `fault` 2, `victim` 1.

### FF — `tex_addr_setup.form` (TEX-01)

2,215 records per run, **0 cross-run disagreements**.

- Carrier note worth recording: a carrier whose coordinates and LOD are loop-invariant compiles to
  a bare `tex_sample` with **no `tex_addr_setup` at all**. Making the inputs thread-varying is what
  makes the compiler emit the instruction under test (`17 05 54 06 00 0c 00 04 f0 d0 08 00` at
  `_agc.main+0x52`). A sweep on the first carrier would have measured nothing.
- Positive control: form 0x05, third operand 1 → 2 gives `1100 → 2000`; each coordinate pair gives
  its own texel.
- form **0x01**: invariant in the third operand over {1, 2, 4, 0.5, 0.25, +0, −0, −1, +inf, −inf,
  NaN, 1e−30, 1e+30} at all four coordinate pairs — `201 / 103 / 303 / 0`, the **unprojected**
  level-0 nearest texels. On the array carrier it also forces **layer 0**.
- form 0x00 == form 0x01; form 0x0d == form 0x05; form 0x07 leaves the destination **unwritten**
  on the 2D carrier (52/52) and forces **layer 1** on the array carrier.
- Operand hunt: form pinned to 0x01, bytes +2…+11 × 21 values = **210 encodings per carrier, 420 across the two carriers**,
  three different third-operand values each. **0 encodings made the result depend on the operand; all returned 201.**
- Full form-byte sweep, 256 values × 4 coordinate pairs × 3 operand values, on **both** carriers
  (`adv01` = 2D, `adv02` = 2D array), 3,331 records each: **32** values make the result
  operand-dependent on each carrier, exactly those with **`(form & 7) == 5`** (high five bits
  don't-care), and in all of them the operand is the LOD / array layer; on the 2D carrier **128**
  values give the unprojected texel; **0 of 256 match the projective oracle on either carrier**.

---

## INTERPRETED

1. **No native FP64 on Apple9 (P2-06).** Both an API-surface and an ISA-level negative, with a
   fired positive control on each. The MSL vector spellings resolving to
   `__Reserved_Name__Do_not_use_doubleN` show the type is *deliberately* excluded, not merely
   unimplemented. Structurally corroborated over our own committed database: all **14** float
   operand-size fields across the 171 `db.json` descriptors are **1 bit wide, `{b16, b32}`**;
   `fspecial.precsel` names only `f16 result` / `f32 result`; and no descriptor mentions a 64-bit
   floating-point concept at all — so there is no encodable third float width.
   *Driver consequence:* binary64 must be software-emulated or not exposed.

2. **`tex_addr_setup.form = 0x01` is not a projective divide (TEX-01), and the database says it is.**
   The corrected semantics is "third scalar operand ignored; sample level 0 / layer 0 at the raw
   coordinates". `db.json` / `validation.json` label it *"coord-projection (samples level 0)"* with
   a `hardware-run` label from EXP-M4-14 (A18) — but EXP-M4-14's single observation (`1100 → 201`)
   is exactly what "operand dropped, level 0 sampled" predicts and contains no coordinate evidence.
   Recorded as a **db-defect** per `FIELD-SWEEP-PROTOCOL.md` §6; `db.json` is not edited here.
   *Driver consequence:* `lower_txp` stays enabled.

3. **Bindless indexing is a plain `base + idx*8` load with no ceiling at the published limits
   (TEX-19, TEX-21).** Both texture and sampler heaps are stride-8 arrays of small dense integer
   resource IDs, and selection is exact at, and well past, 1,000,000 and 499,999 respectively,
   uniformly and per lane, including with sampler IDs above 500,000. The published limits are Metal
   specification limits.

4. **The 500,000 sampler limit is unenforced by the runtime (TEX-22).** 2,000,002 distinct sampler
   states were created with no failure and no live-ID collision. *A driver must enforce the limit
   itself; it will get no allocation error to detect the overflow with.*

5. **Two distinct silent hazards in the bindless sampler path (TEX-22).** An unpopulated entry
   samples with a **default** sampler (a plausible-looking wrong result), not zero — the opposite of
   the texture case. And a **destroyed** sampler's ID is recycled, so a heap entry that still holds
   it silently selects the new owner. *A bindless sampler heap entry is a weak reference; a driver
   must keep referenced samplers alive or rewrite entries on destruction.*

6. **MEM-19 is bounded by the API, not by the selector (MEM-19).** The base-slot selector is 7-bit
   with an exact 128→255 mirror (reproducing EXP-0083's M4 result on G17P for the first time), so
   128 slots are selectable; but `[[buffer(31)]]` is rejected, so at most 31 can be populated
   through the public path. The USC constant/uniform program is `_agc.main.constant_program`, its
   preload is performed by `0x67` `device_load`s in the program body (confirming the structural
   claim in the gap analysis), it addresses base slots in 2-unit steps up to 58, and it preloads
   exactly the uniform subset the compiler can hoist. Past capacity there is **no fault**: a silent
   zero below 128, a silent redirect to a real different binding above it.

---

## Why the faults do not matter here (`FIELD-SWEEP-PROTOCOL.md` §7A)

§7A warns that majority-of-3 under sibling load is insufficient to promote a `fault` verdict —
cross-run agreement did not defeat sustained contamination in EXP-0153; only isolation did.

**No claim in this experiment is a `fault` claim.** Every promoted statement is either a positive
selection result, a silent-zero/silent-default result, or a *negative existence* claim. The one
place a spurious fault could have mattered is P2-06: an encoding wrongly recorded as faulting could
in principle have hidden an FP64 result. That hole was closed directly — the **217 encodings that
faulted in both gated runs were re-run 5× each** (`raw/g17p-20260829-fbc01/`, 1,085 executions) and
**none produced a binary64 result on all four rows** in any repetition. That pass ran **unlocked**: three
attempts to repeat it under `gpulease.sh` all timed out waiting for the lease (EXP-0156 and
EXP-0158 held it continuously), and those attempts are recorded verbatim in
`raw/g17p-20260829-fbc01/LEASE_ATTEMPTS.txt`. Stated plainly: **the §7A isolated confirmation of
the FB fault set was not obtained.** It is not load-bearing — isolation can only turn a spurious
fault into a *readable* result, and every readable result across 5,100 + 1,085 executions was
non-binary64 — but a successor wanting a fully §7A-clean record should re-run
`harness/fbleaseconfirm.py` under the lease when the device is quieter.

Fault-class strings are recorded verbatim on every non-`ok` case, so a reader can separate
`...ErrorInnocentVictim` (machine state) from `...ErrorHang` / `...ErrorPageFault` (our encoding).

---

## Cross-run disagreements, itemised (nothing swept under the rug)

- **FB, 20 of 2,645 comparable cases (0.76%).** Every one is the same class: one run returned a
  value and the other returned the intact poison pattern — a dispatch that reported success and
  wrote nothing. In each case the value the other run returned was checked and **is not a binary64
  result**. `iadd2.b1=0x53` differs *between* the two runs with two different real values and is
  recorded as **nondeterministic**, not promoted.
- **FE, 5 of 281 (run01 vs the isolated re-capture).** Three are slots 32, 41 and 120, which read
  `00000000` in *both* captures and differ only in whether the command buffer errored (`fault` /
  `victim` under isolation, `silent_zero` unlocked) — per §7A the fault is not reproducible and is
  attributed to sibling load. Two are `probe_id@…` records whose ordering depends on which
  candidate load is identified first.
- **FA, FC, FD, FF: zero disagreements.**

## Retained partial capture

Gated `run02`'s FE arm was killed at its very first unmutated baseline dispatch by a concurrent GPU
error; `run.py` recorded `__probe_not_isolated` and stopped rather than sweeping against a broken
baseline. **That capture is retained unmodified under its own run id and was not reused, topped up
or deleted.** The replacement was captured under a **new** id (`g17p-20260829-fe-iso01`) under the
GPU lease, per `SUBAGENT_BRIEF.md`.

## Limitations and what remains open

- **P2-06** searched the complete *single-byte* space of one instruction plus the whole MSL surface.
  It does not exhaust the multi-byte opcode space and cannot see an FP64 unit reachable only from a
  stage or family the carrier never enters. The negative is bounded, and stated as such.
- **TEX-01** bounds `tex_addr_setup` only. A projective divide implemented by a *different*
  instruction in the coordinate-setup chain (e.g. a reciprocal-multiply in `tex_coord_setup`) is not
  excluded. Only the `texlod` carrier got the full 256-value form sweep; `texarr` got the five
  enumerated forms and the 420-encoding operand hunt.
- **TEX-19** never made 1,000,000 *real resident* textures (8 GiB host); it proves the index space
  and the descriptor representation, not simultaneous residency at that scale. TEX-20's
  nonresident-resource sub-question remains open.
- **TEX-22** did not test whether the 500,000 limit is enforced elsewhere (validation layer,
  residency sets), nor a dispatch genuinely referencing >500,000 *distinct* samplers.
- **MEM-19** cannot decide whether base slots 32…127 are populatable by a mechanism the public path
  does not expose. Recorded `UNKNOWN` with the exact tested range.
- One harness artifact worth flagging for a re-user: in `fd`'s `index_*` records the `heap_entry`
  field displays entry 0 when the probe index is outside the declared heap, so for
  `index_2000000` that field is not the address the shader read. The `observed` value is unaffected.
- `SFU-04` was not worked around and is untouched.

## Clean-room provenance

```
Clean-room provenance: HW-PROBE / OWN-SHADER / PUBLIC
Inputs inspected: authored MSL (kernels/*.metal, kernels/fa/*.metal), authored ObjC harnesses
  (harness/*.m), authored Python runners and analysis, and the AGX machine code the public runtime
  compiler produced from our own MSL. Public Metal/MSL API names were used as calling conventions
  only, never as a source of a hardware fact.
Apple binary introspection: NONE. No Apple binary, dylib, kext, firmware, system shader cache or
  Apple-authored precompiled shader was disassembled, decompiled, symbol-dumped, strings-scanned,
  debugged or otherwise introspected.
Reproduction: the command sequence in README.md.
Evidence: raw/g17p-20260829-run01, raw/g17p-20260829-run02, raw/g17p-20260829-fe-iso01,
  raw/g17p-20260829-adv01, raw/g17p-20260829-adv02, raw/g17p-20260829-fbc01,
  analysis/verdicts.json, manifest.json.
```
