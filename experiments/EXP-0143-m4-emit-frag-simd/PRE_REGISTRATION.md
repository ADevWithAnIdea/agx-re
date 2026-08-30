# EXP-0143 — PRE-REGISTRATION (FROZEN)

**Frozen with `CAPTURE_CONTRACT.json`; no clause below is revised after the first gated run.**
A successor experiment takes a new number rather than repairing this one in place.

Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: `kernels/*.metal` (our own MSL) and the AGX bytes compiled from them
Apple binary introspection: NONE
Reproduction: `python3 run.py --run-id <id>`; analysis `python3 analysis/verdicts.py <id> [<id2>]`
Evidence: `raw/<run_id>/sweep.jsonl` (append-only, fsynced per case)

## 1. Question

Twelve fragment/varying/SIMD instructions are **decodable but not emittable**: 64 of their
fields carry a label weaker than `hardware-run` / `isolated-byte-diff` in
`tools/agx-isa/validation.json`. For each field, can an emitter choose an arbitrary value in
its encodable range and get the documented behaviour on Apple9/G16G — and where it cannot,
what exactly bounds it?

Target fields (64), by instruction:
`vary_slot`(2) `frag_depth_store`(3) `frag_tile_setup`(4) `iter_flat`(4) `frag_color_store`(5)
`frag_color_pack`(6) `iter_at`(6) `simd_ballot`(6) `vary_store`(6) `iter`(7) `simd_shuffle`(7)
`simd_reduce`(8).

## 2. Falsifiable hypothesis

**H1 (per field).** For each target field `F` of width `w`, splicing each of its encodable
values into a live occurrence inside a program compiled from our own MSL, and executing on the
M4, partitions the value space into classes that are *stable and reproducible*: values that
reproduce the baseline observation, values that change it in a way a host oracle predicts or a
neighbouring-field control explains, values that silently zero, and values that reproducibly
fault. An emitter can then select from the documented classes.

**H2 (`vary_store` / 0x57 collision).** `byte0 == 0x57` is shared by an 8-byte **vertex**
varying store and a 6-byte **fragment** kill/target-mask op (EXP-0091, corrected by EXP-0093).
`db.json` discriminates on `byte+2 == 0x54`, but our own corpus shows `byte+2 == 0x54` in
*both*. H2: the discriminator is `byte+1`, and it is `byte+1` (not `byte+2`) that a
length rule must key on.

**H3 (`iter` interpolation mode).** EXP-0137 established that a fragment shader reading
`[[barycentric_coord]]` without `[[position]]` computes from **2 `iter` and zero `fspecial`** —
unnormalized perspective numerators with the third component derived as `1-b0-b1` — while
reading `[[position]]` pulls in the W-denominator `iter` + reciprocal + normalizing multiply,
and `[[barycentric_coord, center_perspective]]` is a byte-identical **no-op**. H3: a dense
sweep of `iter.mode` / `iter.loc` / `iter.coeff_sel` on a strongly-perspective carrier decides
whether normalization is selectable **from the `iter` encoding itself**, or is irreducibly a
multi-instruction lowering the backend must emit.

## 3. Refuters (pre-registered; each MUST fire or the method is reported as blind)

Listed in `harness/casematrix.py:FALSIFIERS`. Each is a splice that **must not** reproduce the
baseline. If a falsifier matches its baseline, the arm cannot detect a difference and **its
verdicts are withheld**, reported `untested` with `detection: INSUFFICIENT`.

- `iter@frag1 src_slot=0x08` and `=0x06` — must move colour channel 0 onto another varying.
- `fcs@iter0 rt_index=0x02` — must send the store to an absent RT, leaving the clear colour.
- `fcp@pack0 val=0x80` — must move a packed colour channel.
- `iter_at@cent1_0 lead=0x00`, `iter_at@cent1_1 lead=0x00` — must perturb the interpolated pixel.
- `sshuffle@simd1 lane=0x04` — must change the broadcast source lane.
- `sreduce@simd0 op=0x02` — must change the reduction operation.
- `iter_flat@flat1 sel=0x00` — must change which flat varying reaches its channel.

**H3 refuter.** If no value of `iter.mode`/`loc`/`coeff_sel` converts an unnormalized-numerator
read into a normalized one (or vice versa) on the strongly-perspective carrier, H3 is refuted
and normalization is reported as a multi-instruction lowering, not an encodable mode.

## 4. Liveness — the trap this family is pre-registered against

EXP-0129 lost an entire arm because two positive controls failed to prove its instruction was
on the rendered-pixel path. This experiment therefore requires **two independent liveness
statements per verdict**, and promotes on the second, not the first:

1. **Arm liveness** — a control splice on *this occurrence* changes the observation. Recorded
   per arm, but by itself it proves only that the *instruction* is live (EXP-0147's line:
   general sensitivity is not field-specific power).
2. **Field detection power** — at least one value of *this field's own* swept range changes the
   observation. This is the promoting condition.

A field whose entire range is indistinguishable from baseline on a **single** carrier is
**not** promoted to "inert": inert-looking and undetectable are not separable from one
observation point. It is promoted only when the full-range inertness reproduces on a **second,
independent occurrence or carrier**; otherwise it is `untested` with `detection: INSUFFICIENT`.

Every promoted field records, in `analysis/field_verdicts.json`, how the value was shown to
reach the observed pixel/lane.

## 5. Independent / controlled variables

- Independent: exactly one field of one instruction occurrence per case (`isadb.set_field`
  semantics — never a hand-computed byte offset).
- Controlled: carrier source, pipeline descriptor (colour format, sample count, depth, MRT
  count), geometry, viewport, probe pixels/lanes, clear colour, input buffer.
- Observation: exact RGBA32Float probe pixels (or exact 8-bit codes on the BGRA8 carrier),
  the depth probe on the depth carrier, per-lane u32 words on the compute carrier, plus a
  SHA-256 of the whole attachment so a change outside the probe set is never missed.

## 6. Oracles

- **Predictive** (host-computed, GPU-independent) where the field's meaning admits one:
  `iter.src_slot` (screen-space barycentric interpolation of the authored per-vertex values),
  `frag_color_store.rt_index` (store to an absent RT ⇒ clear colour), `simd_shuffle.lane`
  (broadcast source lane read straight from the authored input buffer).
- **Null/inert** elsewhere: expected observation == baseline; a deviation is the result.
- `interpolate_at_offset` **violates its documented contract on this hardware (EXP-0111)**, so
  the `c_at` carrier's oracle is derived from its own observed baseline, never from Apple's
  documentation. Stated again in `RESULTS.md`.

## 7. Coverage

Per FIELD-SWEEP-PROTOCOL §3: every field of width ≤ 8 is swept **densely over all 2^w values**;
wider fields (`frag_color_store.slice_addr` 32b, `simd_ballot.form_sig` 24b) get boundaries
{0,1,2,max-1,max}, every power of two, every 2^i−1, and 16 deterministic asymmetric interior
samples. `simd_shuffle.mode` is swept densely (0..255) per dispatch, to reach the three
out-of-band shuffle modes.

## 8. Confounders explicitly handled

- **Sibling GPU contamination (§7).** Other experiments sweep this GPU concurrently. A
  command buffer discarded as `kIOGPUCommandBufferCallbackErrorInnocentVictim` was faulted by
  another client, not by our splice: it is retried (8×, backoff), its OS classification string
  is recorded, and if it survives retry it is scored `foreign`, never `fault`.
- **Single-observation faults.** No `fault` verdict from one observation: majority-of-3
  (`CONFIRM_N=3`); a non-reproducing fault is scored `unreproduced`.
- **Error cascades.** The unmutated carrier is re-validated every 250 cases and at end of arm;
  4 attempts with backoff, and only an all-attempts failure counts as a cascade — which stops
  the arm rather than being recorded as data.
- **Silent success.** `MTLPipelineOptionFailOnBinaryArchiveMiss` makes pipeline creation fail
  rather than silently recompile from AIR, so an `OK` proves the *archived, spliced* code ran.
- **Silent write / stale cache.** Integrity sentinel: `frun.m` re-reads the patched archive off
  disk through a separate read and byte-compares every spliced window (`SENTINEL_FAIL`
  otherwise); every request gets a **unique** splice-archive path.
- **Unwritten readback.** Every read-back buffer is pre-filled with `0xDEADBEEF`; an all-poison
  read is reported `POISON`, never as zeros.
- **Compiler transformation.** We splice compiled bytes; we never re-compile between baseline
  and case.
- **Length/aliasing.** Every patched instruction is re-decoded with `isadb`; if it no longer
  decodes as the same mnemonic the case is marked `undecodable` (an encoding-space result,
  not an operand result).

## 9. Safety

One hypothesis per arm; 15 s per-request watchdog with kill+restart; **an arm stops after 2
genuine hangs** and is reported PARTIAL; every case is appended and `fsync`ed as it completes;
`PROGRESS.md` per milestone. Never `macvdmtool`; the A18 is never touched; nothing is written
outside this experiment directory.

## 10. Promotion rules (fixed before any run)

- `hardware-run` — arm liveness proven **and** field detection power proven **and** the full
  encodable range (or the §7 wide schedule) executed, **and** the classification reproduced in
  the independent gate run `run02`.
- `isolated-byte-diff` — an isolated, reproducible effect at specific points but the range not
  fully exercised (e.g. an arm stopped for hangs).
- `untested` + `detection: INSUFFICIENT` — the honest outcome where detection power was not
  established. **Not** rounded up on general sensitivity.
- `db_defects` — a field whose modelled boundaries do not match the hardware (a "field" that is
  really two, a live byte `db.json` does not expose, a length that swallows the next leader).
  `vary_store` stays **`emit_unsafe`** and is **not** reported emittable while the 0x57
  collision stands, whatever its field sweep shows.
