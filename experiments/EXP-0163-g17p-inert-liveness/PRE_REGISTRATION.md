# EXP-0163 — PRE-REGISTRATION (FROZEN)

**Frozen before any gated run.** The machine-readable form is
`CAPTURE_CONTRACT.json` (source hashes, arm list, value sets, protocol
constants, environment, repo revision). This file is the prose statement; where
the two could disagree the JSON is authoritative.

**Target: Apple A18 Pro / G17P** (`applegpu_g17p`, `AGXAcceleratorG17P`, 5 GPU
cores, macOS 26.6, Metal family Apple9), reached at `192.168.10.243`. Every
result in this experiment is labelled `target: G17P` and is **direct**
evidence, not `INFERRED`.

```
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: kernels/*.metal (ours) and the machine code the public
                  newLibraryWithSource: / MTLBinaryArchive API produced from them
Apple binary introspection: NONE
```

## 1. The question

`EXP-0155` swept 109 fields of the texture / fragment / SIMD instructions over
two independent gated runs. **22 of them moved nothing, on any carrier, in
either run.** The tempting reading is that those 22 are don't-cares.

The prior this experiment tests is the opposite, and it is a hardware-economics
argument: **encoding space is expensive, so a field that shows no effect is more
likely UNEXERCISED than meaningless.** EXP-0155's own data already supports it —
three fields it first read as inert turned out to be live once a different
carrier was picked (`tex_sample.samp_extra` inert on nine arms and live on 128
of 256 values on the explicit-LOD arm; `frag_color_store.flags` inert on one
colour-store arm and live on another; `tex_sample.coord` inert on three arms and
live on three).

**Question, per field.** Does there exist a compilable MSL carrier under which
at least one value in the field's dense range changes an observable — i.e. was
the EXP-0155 null a property of the carrier rather than of the silicon?

## 2. The target list (re-derived, not inherited)

Re-derived by `analysis/audit_0155.py` directly from
`experiments/EXP-0155-g17p-emit-tex-frag/raw/g17p_20260829_run03/sweep.jsonl`
and `..._run04/sweep.jsonl`: drop the `_`-prefixed pseudo-fields, then count per
`(instr, field, carrier)` how many swept values had `match == false`. `match`
takes only `true`/`false` in those files (49098 / 56840). **22 fields**, not the
20 in the dispatch; the two extra are `op57_vertex.byte2` and
`op57_fragment.byte2`, the raw-byte arms of EXP-0155's 0x57-collision probe.
`op57_vertex.byte2` *is* `vary_store.hint2`, so it is covered by this
experiment's `vary_store` arms; the fragment form is carried as a secondary
byte-probe target and is reported separately as a byte probe, not a field.

| instruction | fields |
|---|---|
| `tex_coord_setup` | `b5` `b6` `b8` `b9` `idx` |
| `vary_store` | `hint2` `hint6` `b7` |
| `frag_tile_setup` | `access` `sel` `b5` |
| `tex_write` | `amode` `rsv11` |
| `simd_shuffle` | `cache` `rsv9` |
| `simd_ballot` | `cache` |
| `frag_color_store` | `store_mode` |
| `imageblock_store` | `b4` |
| `iter_at` | `loc` |
| `iter` | `b9` |

## 3. Hypotheses and falsifiers

**H1 (per field, the main hypothesis).** For each listed field there exists a
compilable MSL carrier under which at least one value in `0..2^w-1` changes an
observable, and the EXP-0155 inertness was carrier-limited.

**Refuter for H1 (pre-registered).** A field that stays inert across **≥3
structurally different carriers each of which passed its own detection profile**
(§4) refutes H1 for that field and is reported `INERT-ROBUST` with the exact
envelope tested. Not "inert" in general — inert over a stated envelope.

**H2 (the mechanism, testable on its own).** The specific reason a field looked
inert is that the carrier could not put the field's function on the observed
path. The sharpest instance is `iter_at.loc` (db.json enum `1 = centroid`,
`3 = sample`): EXP-0155 swept it only on `c_cent1`, built at
`rasterSampleCount == 1`, where the centroid, the sample point and the pixel
centre are **the same point**, so no location selector can move anything.

**H2's controlled test.** `kernels/k_cent.metal` is built TWICE — as carrier
`cent1` (1 sample) and carrier `cent4` (4 samples, resolved). Identical MSL,
identical compiled bytes for the vertex stage, identical field values. The only
difference is the sample count. **Prediction:** `loc` inert on `cent1` and live
on `cent4`. **Refuter:** `loc` inert on both, or live on both.

**H3 (detection power is a precondition, not an afterthought).** A null result
from an arm that cannot be shown to move its observation is worthless. Every arm
therefore runs a **detection profile** before any sweep (§4), and an arm that
fails it is **discarded from inert verdicts** — not reported as evidence of
inertness. This is the EXP-0129 trap that EXP-0155 fell into pre-freeze and
fixed with its liveness ladder.

## 4. The detection profile (the binding methodological rule)

Before sweeping any target field, each arm runs, in frozen order, over **every
field the DB defines on that instruction**: the field's bitwise complement, then
zero, skipping values the field already holds. Every step is emitted to
`sweep.jsonl` as `field: "_detect"`, with whether the observation moved and
whether the patched bytes still decode as the arm's mnemonic.

Unlike EXP-0155's ladder this does **not stop at the first success**: the whole
profile is recorded, because the profile is the evidence, and it says *which
bytes of this instruction are live on this carrier*.

- **`detect_ok` (strict):** at least one step that STILL DECODES AS THE ARM'S
  MNEMONIC moved the observation. Only arms with `detect_ok` may support an
  `INERT-ROBUST` verdict.
- **`detect_any`:** at least one step moved the observation, including steps
  that changed the decode.
- An arm with neither is reported `STILL-UNDERPOWERED` and its sweeps are kept
  in `raw/` but excluded from every verdict.

## 5. Observation

Every surface the harness returns is SHA-256 hashed and the full hash set is the
comparison: colour attachments `PIX0..PIXn`, per-slice `PIXn_Sk` for layered
targets, `DEPTH`, the writable textures `TEXW` / `TEXWA<k>` / `TEXW3` / `TEXWH` /
`TEXWU`, the render `OUTBUF`, and the compute `OUT`. A change **anywhere** in
any surface is therefore detected, not only at the probe points; the probe
pixels/texels/lanes are recorded on top of that to make a difference readable.

`same as baseline` ⇔ identical hash set. Any difference is the observation.

**Poison.** Every read-back is pre-filled with `0xDEADBEEF` by the harness, so
"wrote a wrong value" and "never ran" are distinguishable
(FIELD-SWEEP-PROTOCOL §7.1). A surface that comes back all-poison is recorded as
`poison`; an observation where every surface is poison is `POISON`, not `ok`.

## 6. Variables

- **Independent:** one field at a time, swept **densely over all 2^w values**
  for `w ≤ 8` (every target field is `w ≤ 8` except `simd_shuffle.cache`, which
  is 1 bit and is swept over both values).
- **Controlled:** the carrier program, its exact pipeline descriptor (the same
  command line builds the archive and runs the sweep, so
  `MTLPipelineOptionFailOnBinaryArchiveMiss` cannot miss on a mismatch), the
  bound textures and buffers, and every other byte of the program — exactly one
  instruction's bytes are replaced.
- **Dependent:** the hash set of §5.

## 7. Carriers and why each exists

`harness/carriers.py` holds one `why` string per carrier and `harness/arms.py`
one per arm; both are reproduced in `RESULTS.md`. In summary, each carrier
exists to make a specific field's plausible function reachable:

| field(s) | the structural gap EXP-0155 had | carriers added |
|---|---|---|
| `iter_at.loc` | swept only at 1 sample, where centroid = sample = centre | `cent1` (control) / `cent4` (same MSL, 4 samples), `ms4cent`, `ms4out` (per-sample device-buffer observation), `atoff1` / `atoff4` (the `interpolant<>` pull model) |
| `frag_tile_setup.sel` `access` `b5` | one render target, no tile read | `mrt3` (3 RTs), `tileread` (`[[color(0)]]` programmable blending), `tilerw2` (2 RTs read AND written), `ibmrt`, `layer` |
| `frag_color_store.store_mode` | plain 2D single-RT attachment only | `mrt3`, `tileread`, `tilerw2`, `layer` (`texture2d_array` attachment + `[[render_target_array_index]]`), `cent4` (4 samples: the only stores in the repo with non-zero `slice_addr`), `ibhalf` (16-bit attachment) |
| `imageblock_store.b4` | single-sample single-RT store | `ibsamp` (reproduces EXP-0155's shape), `atoff4` and `ibms4` (the 4-sample store, tail `0x08000008`) |
| `tex_write.amode` `rsv11` | three writes to one 2D RGBA32Float texture | `twdim` (2D + 2D-array with a non-zero slice + 3D), `twtype` (contiguous vs scattered data, half and uint destinations) |
| `tex_coord_setup.b5 b6 b8 b9 idx` | one occurrence, one `form` | `fclass` / `bits` (`form 0x00`), `vsrc` / `vhalf` / `ms4out` (`form 0x42`, where db.json says `idx = dst<<2`), `sball` (`form 0x10`, the enumerated "bitfield/shift-prep") |
| `vary_store.hint2 hint6 b7` | four 32-bit scalar varyings, one data source | `vmany` (16 varyings, slots past 7), `vhalf` (half and vector components), `vflat` (flat integer / no-perspective / perspective), `vsrc` (memory / immediate / computed sources), `vclip` (`[[clip_distance]]`) |
| `simd_ballot.cache`, `simd_shuffle.cache` `rsv9` | one divergence-free kernel, each result stored once | `scache` (many consumers, long reuse distance, results feeding further SIMD ops), `stype` (quad, rotate/fill, dynamic-lane, 16-/64-bit operands — `rsv9` is non-zero there), `sdiv` (divergent branch, partial active mask), `sball` (every ballot/vote form) |
| `iter.b9` | three plain 32-bit scalar arms | `vmany`, `vhalf`, `vflat`, `cent4`, `atoff1`, `mrt3` |

## 8. Method (binding; FIELD-SWEEP-PROTOCOL §7 and §8)

1. Build every carrier archive from our own MSL with `gfrun2 --build-archive`
   using the EXACT command line the sweep runs.
2. Locate each target occurrence with `tools/agx-isa`: hits from the forward
   tokenization prefix where any exist, otherwise an anchored decode scan whose
   hits must have two cleanly decoding successors. **Never by hand-counted byte
   offsets.** `harness/arms.py` records the census bytes and offset for every
   arm and `run.py` REFUSES an arm whose located bytes differ — the pre-freeze
   smoke caught exactly this on three `cent4` arms and the arms were refused
   rather than swept at the wrong address.
3. Capture the arm's unmutated baseline first.
4. Run the detection profile of §4 in full.
5. Sweep each target field densely. Per case: integrity sentinel (the patched
   archive is re-read off disk and the spliced window byte-compared), poisoned
   read-back, and a unique splice-archive path per request.
6. Majority-of-3 before any `fault`; the OS fault-classification string recorded
   per trial; `InnocentVictim` retried (8×, backoff) then recorded as `foreign`,
   never as `fault`.
7. Baseline re-validation every 250 cases and at end of arm, 4 retries; an
   all-attempts failure is a cascade → stop, do not record the cascade as data.
8. A genuine hang is a confirmed watchdog timeout OR an OS `ErrorHang`. Two per
   field stops the field; six per arm stops the arm.
9. **Two independent gated runs.** A field is promoted to `LIVE` only on
   cross-run agreement; the per-field disagreement count is reported.

## 9. Verdict buckets (pre-registered, exhaustive, mutually exclusive)

Every one of the 22 fields lands in exactly one:

- **`LIVE`** — some arm with `detect_ok` shows ≥1 value that moves the
  observation, in **both** gated runs, on the same arm. Reported with the
  carrier, the moving-value set, and both runs' counts.
- **`INERT-ROBUST`** — inert across **≥3 structurally different carriers that
  each passed `detect_ok`**, in both runs, over the full dense range. Reported
  with the exact envelope. This is a real, useful negative.
- **`STILL-UNDERPOWERED`** — fewer than 3 `detect_ok` arms, or cross-run
  disagreement, or the arms available could not be shown to have detection
  power. Reported plainly as "could not be reached", never dressed up as inert.

## 10. Known confounders

- **Silent zeros.** A wrong field value on Apple9 usually yields a silent zero
  rather than a fault; a zero is an observation, never a skipped case.
- **Concurrent GPU clients.** Other agents share this GPU. Contamination
  surfaces as `InnocentVictim` and is handled by §8.6; the count is reported.
- **Compiler-chosen values.** A field whose baseline already equals the swept
  value is inert by construction; the dense sweep covers the whole range and the
  baseline value is recorded per arm.
- **Scan-located occurrences.** Where a carrier does not tokenize cleanly, the
  occurrence is anchored-scan located and is **not on a proven instruction
  boundary**. Such arms are usable only via their detection profile, and
  `located_via` is recorded per arm so a reviewer can weigh them.
- **`min_lod_clamp`** is kept out of every carrier (EXP-0106: it took
  `MTLCompilerService` down machine-wide on G16G — a host-software outage, not a
  re-runnable GPU fault).
- **Texture swizzle codes 6/7 hard-fault** (EXP-0136); no carrier emits them.

## 11. What would make this experiment fail honestly

- An arm that cannot show detection power → reported `STILL-UNDERPOWERED`, its
  sweeps retained and excluded from verdicts.
- A field that disagrees across the two gated runs → not promoted, reported
  `STILL-UNDERPOWERED` with the disagreement count.
- `iter_at.loc` inert on `cent4` as well as `cent1` → H2 refuted, and that is
  reported as the interesting negative it would be.

---

# ADDENDUM A (pre-registered after run01, before its own runs)

**Frozen 2026-08-30, after `raw/g17p_20260830_run01` and before any run of the
arms it adds.** It does not alter the main contract, the main arms, or the main
runs; it adds one carrier and its own paired gated runs.

## A.1 Why

Run01 found `tex_write.amode` and `tex_write.rsv11` inert on all six arms, but
those six arms come from only **two** source programs (`twdim`, `twtype`) — one
short of the §9 bar of "≥3 structurally different carriers", so the honest
verdict is `STILL-UNDERPOWERED`, not `INERT-ROBUST`.

Rather than relax the bar, this addendum adds the missing carrier. `twdim` and
`twtype` share a property that could itself be the limitation: **every write in
both uses a constant, compile-time coordinate, loaded straight from a uniform
buffer, with no control flow.** If `amode` is a data-source / addressing mode in
the sense db.json ascribes to the sibling `device_store`, that is exactly the
configuration in which one mode would always suffice.

## A.2 The carrier

`kernels/k_twrt.metal` (`carriers.py` entry `twrt`) differs in precisely that
dimension: a write with a **runtime-computed** coordinate; a write whose data has
**texture-unit provenance** (read from a texture, not loaded from a buffer); a
write executed inside a **loop**; and a 3D write with a **runtime depth**.

## A.3 Hypothesis and refuter

**H-A1.** `tex_write.amode` (and/or `rsv11`) moves at least one observable on
`twrt`, i.e. the run01 null was still carrier-limited.

**Refuter.** Inert over the full dense range on `twrt` as well, in both addendum
runs, with `twrt`'s arms passing the strict detection profile. That would take
`tex_write.amode` and `rsv11` to **three** structurally different carriers and
promote them from `STILL-UNDERPOWERED` to `INERT-ROBUST` over the stated envelope.

## A.4 Method

Identical to §8 in every respect. Two independent gated runs
(`g17p_20260830_run03`, `g17p_20260830_run04`), restricted with
`--mnem tex_write` so the addendum re-runs **every** `tex_write` arm — the six
existing ones and `twrt`'s — under one contract, and cross-run agreement is
required exactly as before.

## A.5 What this addendum may NOT do

It may not change any verdict for a field other than `tex_write.amode` and
`tex_write.rsv11`, and it may not be used to re-open run01/run02 for those two
fields: the addendum runs stand on their own and are reported separately in
`RESULTS.md` with their own run ids.
