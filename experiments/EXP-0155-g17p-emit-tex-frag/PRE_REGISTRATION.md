# EXP-0155 — PRE-REGISTRATION (FROZEN)

**Frozen before any gated run.** The machine-readable form is
`CAPTURE_CONTRACT.json` (source hashes, per-arm case counts, value sets, oracle,
falsifiers, protocol constants, repo revision). This file is the prose
statement; where the two could disagree the JSON is authoritative.

**Target: Apple A18 Pro / G17P** (`applegpu_g17p`, `AGXAcceleratorG17P`, 5 GPU
cores, macOS 26.6, Metal family Apple9), reached at `192.168.10.243`. **Every
result in this experiment is labelled `target: G17P` and is DIRECT evidence**,
not `INFERRED` — that is the point of the pivot (`experiments/NEO-TARGET-BRIEF.md`).

```
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: kernels/*.metal (ours) and the machine code the public
                  newLibraryWithSource: / MTLBinaryArchive API produced from them
Apple binary introspection: NONE
```

## 1. The question

An emitter cannot today produce **any** texture or fragment-output instruction
from scratch. Of the 18 instructions in this experiment's scope, **110 fields**
are below emitter grade in `tools/agx-isa/validation.json`
(`corpus-correlation` / `tokenization-only` / `single-template-inference` /
`untested`), and not one of the 18 is `emittable` under the
`docs/evidence-classification.md` rule. `DOC-02` names `tex_sample`'s coordinate
and result registers among the top untested blockers in the whole ISA: a back
end currently cannot choose where a sample's coordinates come from or where its
result lands.

**Question.** For each of those fields, can an emitter choose an arbitrary value
and get documented behaviour on G17P — and for which instructions does that
clear the `emittable` bar?

## 2. Hypotheses and falsifiers

**H1 (per field).** Each blocking field has a value→behaviour map that is
*stable* and *host-predictable from the inert oracle*: splicing a value either
leaves the observed pixel/texel/lane identical to the arm's own unmutated
baseline, or moves it deterministically, or produces a reproducible fault.

**Refuter for H1.** A field whose values produce observations that differ
between the two independent gated runs, or between replicate trials inside a
run, is *not* emitter-grade and must stay below `hardware-run` regardless of how
clean the first run looked.

**H2 (liveness).** Each arm's instruction is on the observed output path. This
is the hypothesis EXP-0129 failed to establish and lost an arm to, so it is
tested *first* and *per arm*, by a frozen **liveness ladder** (§4). An arm whose
ladder produces no change is reported NOT LIVE and its field verdicts are
withheld — no field is promoted on general sensitivity.

**H3 (`vary_store` / 0x57).** `db.json` matches `vary_store` on byte0 alone and
always consumes 8 bytes, so it mis-lengths the 6-byte fragment kill/target-mask
op that shares byte0 = 0x57 (the EXP-0091 collision, still unresolved and flagged
`emit_unsafe`). H3: the discriminator is byte+1 (or byte+2), and it controls the
hardware's instruction **length**. Refuter: if sweeping byte+1 and byte+2 across
all 256 values in both stages never changes the program's output in a way an
operand change cannot explain, the length is not encoded there and H3 is false.

**H4 (negative, pre-registered).** `imageblock_load` is **not attempted**: no
carrier we can compile emits it (the explicit-layout fragment imageblock does
not compile — EXP-0142 — and the programmable-blending route compiles to
`tile_read`, which EXP-0147 already closed). Its five blocking fields stay
`untested`. This is recorded here so its absence from the results is a
pre-registered negative, not a silent omission.

## 3. Variables

- **Independent:** one instruction field at a time, swept over the frozen value
  set (width ≤ 8 → **all 2^w values, dense**; width > 8 → boundaries
  {0,1,2,max−1,max} + all powers of two + all (2^i)−1 + 16 deterministic
  asymmetric interior samples).
- **Controlled:** the carrier program, its pipeline descriptor, the bound
  textures and buffer(0) contents, the probe pixels/texels/lanes, and every
  other byte of the program (exactly one instruction's bytes are replaced).
- **Dependent:** the read-back RGBA32Float pixel at three probe pixels inside
  the triangle; where applicable the depth attachment, the writable texture at
  five probe texels, and the compute output buffer at five probe lanes.

## 4. Liveness — how each field's value is proven to reach the observation

The pre-freeze smoke (`raw/prefreeze/smoke02_liveness.json`) exposed exactly the
EXP-0129 trap in its first form: the single named control for every texture arm
was `coord = 0x00`, and our compiled `tex_sample` bytes **already hold
`coord = 0`**, so a control that changed nothing was being read as "the
instruction is not live". A byte-by-byte diagnostic
(`raw/prefreeze/probe_live_t_sample.txt`) showed the splice was landing and the
pixel *did* move for other bytes.

The frozen replacement is a **liveness ladder**: the arm's named control first,
then, for each swept field in order, that field's bitwise complement and then
zero, skipping any value the field already holds, capped at 14 steps. **Every
step is emitted to `sweep.jsonl`**, so the reader sees which control did the
work and how many were inert. All 40 arms passed with the ladder.

Per-arm liveness statements (why the value reaches the observed pixel) are the
`note` field of each arm in `harness/casematrix.py`, and are reproduced in
`RESULTS.md`. In summary:

| family | how the value reaches the observation |
|---|---|
| `vary_slot`, `vary_store` | the vertex program feeds all four fragment varyings and the fragment program writes them straight to the observed pixel |
| `tex_sample`, `tex_coord_setup` | each sample's result is one colour channel and nothing else reaches it; the source texture is `texel(x,y) = x + 100*y`, so a baseline of (1, 203, 405) names its own texels exactly, and channel 3 is an ALU-only sentinel (6*7 = 42) that separates a dead texture unit from a dead shader |
| `tex_write` | the writable texture is reset to (−1,−2,−3,−4) before every render and read back after, so "wrote here", "did not write" and "wrote somewhere else" are three distinguishable read-backs, with two control texels that must keep the sentinel |
| `tex_deriv` | each of the four partial derivatives goes to its own channel, with the alpha channel carrying derivative + ALU sentinel |
| `iter`, `iter_at`, `iter_flat` | the interpolated value IS the observed channel |
| `frag_color_store/pack`, `frag_tile_setup`, `imageblock_store` | they are the store that writes the observed pixel |
| `frag_depth_store` | the depth attachment is read back directly and the written depth is an interpolated gradient |
| SIMD | every lane writes its result to the output buffer, read back at five probe lanes |

## 5. Method (binding, FIELD-SWEEP-PROTOCOL §7 and §8)

1. Build every carrier archive from our own MSL with the **exact** pipeline
   descriptor the sweep runs (`gfrun --build-archive`), so
   `MTLPipelineOptionFailOnBinaryArchiveMiss` can never miss on a descriptor
   mismatch.
2. Locate each target occurrence with `tools/agx-isa` — by clean forward
   tokenization where the program tokenizes, otherwise by an anchored decode
   scan whose every hit is recorded in `00_inputs.json`. **Never by
   hand-counted byte offsets.**
3. Capture the arm's unmutated **baseline** first; every later case is a delta
   against it.
4. Run the frozen liveness ladder.
5. Sweep each field. Per case: **integrity sentinel** (the patched archive is
   re-read off disk through an independent `NSData` read and every spliced
   window byte-compared), **poisoned read-back** (`0xDEADBEEF`), and a **unique
   splice-archive path per request**.
6. **Majority-of-3 before any `fault`**: a non-OK case is re-run to 3 trials and
   the verdict is the majority. The **OS fault-classification string** is
   recorded per trial; `InnocentVictim` is retried (up to 8×, with backoff) and
   then recorded as `foreign`, never as `fault`.
7. **Baseline re-validation** every 250 cases and at end of arm, with 4 retries;
   an all-attempts failure is a cascade → stop, do not record the cascade as
   data.
8. A genuine hang is a confirmed watchdog timeout **or** an OS `ErrorHang`.
   Two per field stops the field; six per arm stops the arm (§8).
9. Two **independent gated runs**. A field is promoted only on cross-run
   agreement; the per-field disagreement count is reported.

**Arms run in the frozen priority order** of `casematrix.ARMS` — `vary_slot`
first, then `tex_sample`, then the rest — so a wall-clock deadline or a crash
truncates the low-priority tail, and every unswept field is emitted explicitly
as `not_run` rather than silently omitted.

## 6. Known confounders

- **Silent zeros.** On Apple9 a wrong field value usually yields a silent zero,
  not a fault (EXP-0114: all 14 unused texture-selector nibble values zero
  silently). A zero is recorded as `silent_zero`, an observation, never a
  skipped case.
- **Concurrent GPU clients.** Five other agents share this GPU. Contamination is
  detectable, never silent: it surfaces as `InnocentVictim`. Handled by §5.6.
  The count of concurrent experiments is reported in `RESULTS.md`.
- **Compiler-chosen values.** A field whose baseline value already equals the
  control is inert by construction — the trap of §4.
- **Scan-located occurrences.** Where a carrier does not tokenize cleanly the
  occurrence is anchored-scan located; all hits are recorded and at least one
  known-spurious hit exists (`t_write` fragment offset 334). Only occurrences
  whose liveness ladder passes are swept.
- **`min_lod_clamp`** is kept out of every carrier: on G16G it took
  `MTLCompilerService` down machine-wide (EXP-0106), and that is a host-software
  outage, not a re-runnable GPU fault.
- **Swizzle codes 6/7 hard-fault** (EXP-0136). No carrier emits them; if a
  sweep reaches an equivalent state the §8 hang budget stops the field.

## 7. What would make this experiment fail honestly

- An arm that is not live → its fields stay `untested` with an explicit
  `INSUFFICIENT detection proof` note, as EXP-0147 did for its six fence fields.
- A field that disagrees across the two gated runs → not promoted.
- A falsifier that comes back `ok` → that arm could not detect a difference on
  the day and its verdicts are withheld.
