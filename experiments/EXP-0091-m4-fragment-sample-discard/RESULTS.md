# RESULTS — EXP-0091 M4 fragment sample/coverage/discard/demote/helper state machine

**Target:** Apple M4/G16G, this host only. macOS 26.6.2 (25G82), Metal 4, Apple clang
21.0.0. A18 Pro/G17P is `INFERRED`-by-family per `CLAUDE.md` target discipline; no A18
evidence exists or is claimed here.

**Two-run gate:** `raw/m4_20260827_run01/` and `raw/m4_20260827_run02/`, 78 cases each,
every case `STATUS OK` or `SCANNED` (no fault, hang, or command-buffer error in either
run). `python3 verify.py --crossrun raw/m4_20260827_run01 raw/m4_20260827_run02` →
**PASS**: every `*.gated.json` record is byte-identical between the two runs.
`python3 verify.py --selftest` and `--seqtest` → **PASS** (see §8).

One supplementary, **single-run** probe (`d_helper_relay`, §4.3) was added after the
frozen two-run capture to close a gap the frozen matrix's own suppression finding
revealed; it is explicitly flagged wherever cited and is not part of the cross-run gate.

---

## 1. GLFS-A01 — Exact fragment sample-state operation and finite mask capacity

```text
Status: [x] Closed (existence, location, presence/absence rule, mask-width contract) /
        [ ] Partial (full bit-level operand decode of the submission op)
Answer, where Yes/No: a DEDICATED instruction pair exists (Yes, a separate op does
  exist; it is NOT folded into frag_color_store/frag_tile_setup/frag_end).
Applies to: [x] M4/G16G   [ ] A18 Pro/G17P (not tested)  [ ] both
Evidence: [x] independently assembled HW execution (splice)
          [x] HW splice (byte-level field flip, 3-channel readback)
          [x] API create/submit/exhaustion test (MSAA mask-width sweep)
          [ ] Linux end-to-end UAPI test
          [ ] captured userspace/command memory
          [x] encode/decode round trip (own-shader differential compile)
          [ ] own-MSL byte diff only (stronger evidence obtained, see below)
          [ ] corpus inference only
Test/artifact: kernels/loc_*.metal (9 differential-compile probes), kernels/
  s_kill_probe.metal (splice target), kernels/f_persample_mask_resolve.metal (MSAA
  sweep); raw/m4_20260827_run0{1,2}/{loc_*,splice_*,msaa_*}.gated.json
Exact observed semantics or field mapping: see below.
Finite namespace: sample-coverage mask, scope = one fragment invocation's tilebuffer/
  depth/stencil submission; encoding = a 32-bit value (as exposed through MSL's
  [[sample_mask]] uint) whose EFFECTIVE width is exactly N = the pipeline's
  rasterSampleCount; exact usable range = bits [0,N); holes/reserved = none within
  [0,N) (every bit combination in range is legal and independently observable via the
  resolve-fraction technique, §1.3).
Maximum-valid and first-invalid tests: bit N is the first "invalid" (inert, not
  rejected) bit at sample count N; tested up to bit 31 (0x80000000) and all-ones
  (0xFFFFFFFF) at N=4 with no fault and exactly the low-4-bit-masked behavior.
Failure/overflow behavior: [x] zero/discard (silently masked, NOT rejected, NOT
  aliased/wrapped, NOT faulting) for out-of-range bits. [ ] reject [ ] fault/device loss.
Correct behavior when the compiler/driver needs more: not applicable (there is no
  "need more than N" case at the ISA level; N tops out at the Metal/hardware-advertised
  rasterSampleCount, itself capped at 4 -- see EXP-M4-09's independently-established
  "8x MSAA is Metal-rejected at both texture- and pipeline-creation" finding, which this
  experiment did not need to re-test).
Lifetime, destruction, and reuse semantics: the mask is submitted once per fragment
  invocation by this op; GLFS-A01 also asks about "already-killed samples" and "samples
  already submitted" repetition -- see Counterexamples.
Counterexamples and untested cases: repeated/overlapping submissions from the SAME
  invocation (calling discard_fragment() twice, or writing [[sample_mask]] twice) were
  NOT executed as separate cases in this experiment (MSL permits at most one
  [[sample_mask]] stage-out per invocation, and a double discard_fragment() call was
  not included in the frozen matrix); flagged as an open follow-up. Full bit-level
  decode of the submission op's byte+1 (0x14 vs 0x1c) and its companion op's fields
  beyond byte+4 remains STRUCTURAL/UNKNOWN (see below) -- several splice probes on
  those bytes were null (no observable effect), which is itself recorded, not
  discarded, but does not by itself prove those bits inert in all contexts.
Driver/compiler consequence: a compiler backend can and should model fragment kill /
  explicit sample-mask output as ONE physical instruction family, register-sourced (the
  value must be materialized into an ordinary GPR by a preceding instruction, then
  submitted), always followed by a fixed companion "commit" op before any subsequent
  tile-access-dependent instruction. This unifies discard_fragment() and
  [[sample_mask]] lowering into a single ISA-level pattern -- the "independent target
  and live masks like the current Asahi model" question is answered NEGATIVELY at the
  instruction-count level: there is one submission op, not two.
```

### Observed semantics (detail)

**Localization (differential compile, host-side, no GPU dispatch, `tools/agx-isa`
tokenizer as an independent structural check):** a plain fragment shader
(`loc_base`) and a fragment shader with a divergent `if`/reconverge that does
**neither** discard nor writes a sample mask (`loc_if_nodiscard`) both tokenize
**CLEAN** (0 leftover bytes) and contain **zero** occurrences of any `byte0==0x57,
byte2==0x54` instruction. Every kernel that calls `discard_fragment()` and/or writes
`[[sample_mask]]` — constant or runtime-valued, alone or combined — emits exactly this
6-byte op (`57 <B1> 54 <B3> <B4> <B5>`) immediately followed by a 6-byte companion
(`07 02 54 01 <B4'> <B5'>`), distinct from the ordinary end-of-program epilog `07 02 54
0c 02 00` that still unconditionally follows later in every fragment main. This is a
clean presence/absence result across 9 controlled source variants (`loc_loc_base`
through `loc_loc_mask_const_A`, `raw/m4_20260827_run01/loc_*.gated.json`).

`B1` (byte+1 of the submission op) takes exactly two values across the tested corpus:
`0x1c` for the one fully compile-time-provable, unconditional, straight-line case
(`discard_fragment()` with no enclosing branch, and `[[sample_mask]]=0` unconditional —
these two DIFFERENT source constructs compile to **byte-identical** 32-byte fragment
mains, `loc_loc_discard_unconditional` and `loc_loc_mask_const_zero`); `0x14` for every
branch-computed or buffer/runtime-sourced case, and also for a compile-time *nonzero*
constant mask (`loc_loc_mask_const_full`/`loc_loc_mask_const_A`, mask=0xF/0xA) — MSL
does not const-fold the explicit `[[sample_mask]]` stage output the way it folds
`discard_fragment()`.

The submission op **never carries the mask value as a literal immediate**:
`loc_mask_const_full` (mask=0xF) and `loc_mask_const_A` (mask=0xA) differ at exactly one
byte, and that byte is in an *earlier*, ordinary ALU immediate-load instruction (value =
`mask<<1`), not in the submission op itself. This is consistent with (not yet a complete
bit-level proof of) a register-sourced operand model: the op consumes a fixed slot; an
ordinary preceding instruction produces the value.

**db.json correction (informational, not applied — `tools/agx-isa` is read-only per
dispatch):** this exact byte pattern currently decodes, via `tools/agx-isa`'s existing
`vary_store` descriptor (an 8-byte **vertex**-stage varying-output op sharing byte0=
`0x57`), as an over-length 8-byte instruction, consuming 2 bytes that belong to the
companion op and leaving the rest of the fragment main as tokenizer "leftover" — visible
directly in this experiment's own tokenizer output (`loc_loc_if_discard.gated.json`:
`"tokenize_clean": false`). This is the same class of opcode-byte collision between
vertex- and fragment-stage instruction families that EXP-0029 already found and fixed
for a different byte0 group (`0x9f 11 54`). Recommended follow-up: `tools/agx-isa/
db.json` needs a fragment-context-gated descriptor for this 6-byte op family, separate
from `vary_store`.

**Splice validation (HW-VALIDATED, later-effect discipline per `docs/isa/register-
move-and-liveness.md`):** `kernels/s_kill_probe.metal` (runtime buffer-sourced
`[[sample_mask]]`, sampleCount=1, fixed-function depth, `depthCompare=Always` so
occlusion/depth are gated purely by the kill mechanism) located the candidate op at
absolute file offset 13798 (`57 14 54 00 00 01`) and companion at 13804 (`07 02 54 01 00
00`) in `s_kill_probe.bin`. Baseline: `mask=1` (bit0 set) survives on all three
channels (color visible, fixed-function depth written =0.1, occlusion=4/4); `mask=0`
killed on all three (color clear, depth unchanged =0.5, occlusion=0/4) — reproduced
identically via plain compile and via the unspliced archive.

Byte+4 of the candidate op (`57 14 54 00 [B4] 01`) sweep, mask=1 baseline (every value
its own frozen case, `raw/m4_20260827_run0{1,2}/splice_B4own_*_m1.gated.json`,
byte-identical across both runs):

| B4 | color | depth | occlusion | verdict |
|---|---|---|---:|---|
| `0x00` (baseline) | `4080bfff` | `0.1` | 4 | survive |
| `0x01,0x02,0x04,0x08,0x10` | `00000000` | `0.5` | 0 | **killed** |
| `0x20,0x40,0x80` | `4080bfff` | `0.1` | 4 | survive (matches baseline) |
| `0xFE,0xFF` | `00000000` | `0.5` | 0 | **killed** |

Every tested value that has any bit set in `[4:0]` kills; every tested value with only
bits in `[7:5]` set survives identically to baseline — consistent with bits[4:0] being
(at least) a 5-bit source-register-select field, where `0x00` selects the register the
compiler routed the real computed mask into, and any other tested value in that range
redirects the read to a different register that behaves as always-zero (an
uninitialized-register-reads-zero pattern consistent with prior findings elsewhere in
this ISA). **All three channels (color, depth, occlusion) moved together in every
case** — the addendum's explicitly flagged falsifier (a killed sample that still reaches
depth/stencil, or a demoted-but-covered lane's write reaching a buffer/image) was
**not observed** for this op. Own byte+1 (`0x14→0x1c`), own byte+3 (`0x00→0x01`),
own byte+5 (`0x01→0x00`), and companion byte+3/+4/+5 splices were **null** (no
observable change on any channel) in this configuration — recorded as genuine negative
results (bit not load-bearing IN THIS CONTEXT), not re-tried speculatively; full
compiler-ready bit decode of the whole family remains open. Positive control (corrupting
one byte of the unrelated `frag_color_pack` op) changed the color channel, confirming
the splice mechanism itself is capable of producing an observable difference — the null
results above are not a dead harness.

**MSAA mask-width/hole sweep (HW-VALIDATED, plain compile, no splice, 22 cases,
`raw/m4_20260827_run0{1,2}/msaa_*.gated.json`):** using the resolve-fraction technique
(`f_persample_mask_resolve.metal`: per-sample write of `color = (mask>>sid)&1`,
`[[sample_mask]]=mask`, MSAA box-filter resolve → `resolved.r ≈ popcount(mask &
((1<<N)-1))/N`), swept at N=1,2,4:

| N | tested masks | resolved.r pattern |
|---|---|---|
| 4 | 0,1,5,10,15,16,32,240,255,65535,4294967295(=2^32-1),2147483648(=2^31) | `0,1,5,10,15` → `0,0.25,0.50,0.50,1.0` exactly (popcount/4); `16,32,240,2147483648` (all bits ≥ bit4 only) → **0.0** (fully inert); `255,65535,4294967295` (any bits-[3:0] set, plus arbitrary high garbage) → **1.0** |
| 2 | 0,1,2,3,4,12 | `0,1,2,3` → `0,0.5,0.5,1.0`; `4,12` (bits ≥ bit2 only) → **0.0** |
| 1 | 0,1,2,3 | `0,2` → 0.0 (bit0 clear); `1,3` → 1.0 (bit0 set) |

No fault, hang, alias, or wrap at any tested value including `0xFFFFFFFF` and
`0x80000000` at N=4. **Exact rule: the effective mask is exactly the low N bits of the
32-bit value; all higher bits are silently, uniformly inert.** This directly answers
the "finite mask width," "maximum hardware sample count" (N ∈ {1,2,4}, confirmed
independently against `EXP-M4-09`'s "8x Metal-rejected" finding, not re-derived here),
and "inactive high-bit behavior" clauses of GLFS-A01 without needing a splice.

**Verdict: GLFS-A01 is a POSITIVE result, not the negative one the triage flagged as a
real possibility.** A dedicated instruction pair exists, is present if and only if the
source uses discard or an explicit sample-mask write, and is register-sourced with a
partially-decoded (bits[4:0] of byte+4 = source-register-select, HW-validated) operand.
Full compiler-ready decode of every remaining bit (byte+1's two observed values, the
companion op's full field set) is **PARTIAL/STRUCTURAL**, an honest open item, not
claimed closed.

---

## 2. GLFS-A02 / OPT-09 — Demote, discard, terminate, and helper-lane state transitions

```text
Status: [x] Closed for the tested channels (ALU/register continuation, derivative
  sharing, implicit-LOD sharing, quad-op relay, buffer/atomic/color/depth side effects)
  [ ] Partial (true-termination-vs-demote for EVERY NIR operation category; loop/
  subgroup-op forward-progress under demotion not exercised)
Answer, where Yes/No: [x] Yes -- Apple9 fragment discard has SPIR-V demote semantics.
Applies to: [x] M4/G16G   [ ] A18 Pro/G17P (not tested)  [ ] both
Evidence: [x] independently assembled HW execution  [ ] HW splice (not needed --
  decisive via ordinary compiled execution)  [x] API create/submit/exhaustion test
  [ ] Linux end-to-end UAPI test  [ ] captured userspace/command memory
  [x] encode/decode round trip (n/a, behavioral)  [ ] own-MSL byte diff only
  [ ] corpus inference only
Test/artifact: kernels/d_demote_before.metal, d_demote_after.metal,
  d_control_nodiscard.metal, d_quad_shuffle.metal, d_tex_implicit_lod.metal,
  d_control_tex.metal; raw/m4_20260827_run0{1,2}/{d_control_nodiscard,d_demote_before,
  d_demote_after,d_quad_shuffle,d_tex_implicit_lod,d_control_tex}.gated.json
Exact observed semantics or field mapping: see below.
Finite namespace: not applicable (behavioral state machine, not a resource table).
Maximum-valid and first-invalid tests: n/a.
Failure/overflow behavior: n/a.
Correct behavior when the compiler/driver needs more: a compiler MAY set
  discard_is_demote = true for portable-NIR lowering purposes (see verdict), subject to
  the GLFS-A06 caveat that side-effect suppression is automatic and must not be
  re-synthesized as extra predication.
Lifetime, destruction, and reuse semantics: a demoted lane's helper status (queried via
  simd_is_helper_thread()) reads TRUE after discard for every one of 8 tested
  quad-relayed lanes (§4.3, supplementary single-run); it never reads FALSE again in any
  tested case (no "later operation makes a demoted invocation live again" case was
  observed, though none was specifically attempted either -- open).
Counterexamples and untested cases: true BRANCH/HALT termination (a hypothetical
  separate "terminate" instruction, as opposed to discard_fragment()) was not located or
  tested -- this experiment establishes that discard_fragment() itself is demote-like,
  not that no separate true-terminate mechanism exists elsewhere in the ISA. Nested/
  divergent loops after discard, and killing-the-last-live-sample-changes-helper-state,
  were not separately isolated (partially covered by GLFS-A03's supplementary probe).
Driver/compiler consequence: Yes permits .discard_is_demote = true (OPT-09's own stated
  consequence). A compiler backend does NOT need a separate lowering for NIR demote vs.
  Apple9 discard_fragment() for the tested operation categories (ALU, derivatives,
  implicit-LOD sampling, quad shuffle). It DOES need to know (GLFS-A06, below) that
  memory/attachment side effects from the demoted lane are automatically suppressed by
  hardware and must not be additionally predicated by the compiler.
```

### Decisive test and exact numbers

`d_demote_before.metal`: even-x lanes call `discard_fragment()` then, only in that
taken branch, add `(1000,1000)` to a local copy of the fragment's screen coordinate
(`pos.xy`, whose true per-pixel step is exactly 1.0 in x for this geometry).
`fwidth()` of that value is computed **after** the branch merge, by every lane, and
written to a per-pixel buffer record (only the surviving lane's write reaches memory —
see §3). Observed (`raw/m4_20260827_run01/d_demote_before.gated.json`, byte-identical in
run02): every surviving (odd-x) lane's `fwidth` reads **exactly `999.0`** — the exact
value predicted by "the discarded neighbor continued executing the `+1000` mutation
before the quad-shared derivative was computed" (`|x_survivor − (x_discarded+1000)| =
|1 − 1000| = 999`). The no-discard control (`d_control_nodiscard`) reads exactly `1.0`
for every lane. The statement-order control (`d_demote_after.metal`, discard placed
**after** the `fwidth()` read) reads exactly `1.0` for every surviving lane — proving
the `999.0` result in the `_before` variant is genuinely caused by the discarded lane's
**continued execution of a later instruction**, not a harness artifact or a property of
`discard_fragment()` alone regardless of placement.

`d_quad_shuffle.metal` independently cross-validates via `quad_shuffle_xor`, retrieving
a distinctive marker computed **after** the discard by the discarded lane itself
directly into the surviving neighbor's register: for the quad `(px=0,py=0)`
discarded / `(px=1,py=0)` survivor, `quad_shuffle_xor(own, 1)` on the survivor returned
`7777` — **exactly** `px*1000+py+7777` evaluated at the discarded lane's own
`(px,py)=(0,0)`, i.e. the demoted lane's own live post-discard register state, not a
frozen pre-discard value, not zero, not garbage. Reproduced identically for the
`(2,0)`/`(3,0)` pair (`9777`, matching `2*1000+0+7777`).

`d_tex_implicit_lod.metal` vs `d_control_tex.metal` (implicit-LOD sample after a
partial-quad discard, per OPT-09's explicit derivative/implicit-LOD clause): the
surviving lanes' sampled checker-texture value at row y=0 changed from the control's
`0.8627` to `0.1569` when the discarded neighbor's post-discard-perturbed coordinate
(`uv*37`) entered the shared quad derivative computation that drives implicit-LOD
selection — a real, decisive change attributable only to the demoted lane's continued
participation in derivative computation (row y=1, where the neighbor's contribution
happened not to move the sampled texel, is unchanged in both variants — an internal
consistency check, not a null result).

**Verdict:** all four tested channels (ALU continuation via `fwidth`, quad-op register
relay, implicit-LOD sample dependency, statement-order sensitivity) agree: Apple9
`discard_fragment()` **is** a demote, not a true terminate, for M4/G16G. `OPT-09`
closes **Yes**.

---

## 3. GLFS-A03 — Helper-status source and changes during an invocation

```text
Status: [ ] Partial
Answer, where Yes/No: not a yes/no item; helper-status IS dynamically queryable and
  responsive to discard (see below), but the complete get_sr 0x84 raw-bit-pattern
  encoding was NOT independently validated (MSL's simd_is_helper_thread() canonicalizes
  through a language bool, so only the MSL-visible 0/1 semantic, not the hardware's raw
  representation, is established here).
Applies to: [x] M4/G16G   [ ] A18 Pro/G17P (not tested)  [ ] both
Evidence: [ ] independently assembled HW execution (raw get_sr splice not attempted --
  see below)  [ ] HW splice  [x] API create/submit/exhaustion test
  [ ] Linux end-to-end UAPI test  [ ] captured userspace/command memory
  [ ] encode/decode round trip  [x] own-MSL byte diff only (behavioral, MSL-level)
  [ ] corpus inference only
Test/artifact: kernels/d_control_nodiscard.metal, d_orig_helper.metal,
  d_helper_relay.metal (supplementary, single-run); raw/m4_20260827_run0{1,2}/
  {d_control_nodiscard,d_orig_helper}.gated.json + work/ single-run capture of
  d_helper_relay (not in the frozen gate, see §4.3)
Exact observed semantics or field mapping: covered live invocations read helper=false
  both before and after ordinary execution (d_control_nodiscard, all 16 lanes,
  helper_pre=helper_post=0). A demoted (post-discard_fragment()) lane's own helper
  status, relayed via quad_shuffle_xor into a surviving neighbor because the demoted
  lane's OWN buffer write is suppressed (GLFS-A06): helper_post reads TRUE (1) for
  every one of 8 tested relayed lanes, deterministic across 3 repeats on this single-run
  supplementary probe. helper_pre (read BEFORE the discard call, same lane) read FALSE
  (0) for 6 of 8 relayed lanes and TRUE (1) for 2 of 8 -- deterministic across repeats
  of the SAME probe, but not spatially uniform; see Counterexamples.
Finite namespace: not applicable (single boolean-shaped SR value as exposed through
  MSL).
Maximum-valid and first-invalid tests: n/a.
Failure/overflow behavior: n/a.
Correct behavior when the compiler/driver needs more: n/a -- this is a query, not a
  resource.
Lifetime, destruction, and reuse semantics: helper status transitions false->true at
  (at latest) the point discard_fragment() executes for that lane; no case observed a
  true->false transition.
Counterexamples and untested cases: the "helper_pre reads true for 2 of 8 lanes"
  anomaly (§4.3) is UNEXPLAINED -- both anomalous lanes are diagonal-opposite quad
  positions in a 4x4 grid of otherwise-identical quads, suggesting a possible
  quad-reconvergence-boundary or scheduling interaction rather than a stable semantic
  "helper before discard" answer, but this experiment did not isolate the cause and does
  not claim one. This whole probe is SINGLE-RUN (not cross-run gated) -- flagged
  explicitly as needing a second run and, ideally, splice-level get_sr 0x84
  raw-bit-pattern validation (assembler-authored, not MSL-bool-canonicalized) before
  promotion beyond PARTIAL. Original (never-covered) helper invocations' OWN helper
  status was NOT observed: d_orig_helper's partial-coverage geometry produced only
  interior fully-live pixels whose writes landed (all correctly helper=false); the
  genuinely-uncovered edge-adjacent original-helper pixels' writes are suppressed by the
  same GLFS-A06 mechanism as demoted lanes, and this experiment did not build a
  quad-shuffle relay for the original-helper case (only for the demoted case) --
  deferred as follow-up. Per-sample helper status under per-sample killing (the
  f_persample_discard cross-check) recorded helper_pre/post via the SAME suppressed-
  write limitation and consequently shows all-zero (uninformative) in the frozen matrix
  (raw/m4_20260827_run01/f_persample_discard_N4.gated.json, buffer 1) -- also deferred.
Driver/compiler consequence: a compiler can rely on helper status becoming true
  immediately upon a lane's own discard (supports treating discard as demote for
  purposes of subsequent helper-status queries), but should NOT assume the
  pre-discard read is a stable, uniform false in every scheduling context until the
  2-lane anomaly above is explained by a dedicated follow-up experiment.
```

---

## 4. GLFS-A06 — Suppression of helper and demoted-lane side effects

```text
Status: [x] Closed for the four tested channels (device buffer store, global atomic
  increment, color output, explicit depth output); [ ] Partial for image store, stencil
  output, dual-source output, sample-mask output from a demoted lane (not exercised),
  and for whether a demoted lane's own load/fault behavior can be observed.
Answer, where Yes/No: suppression is INHERENT (hardware-automatic) for all four tested
  channels; the compiler does NOT need to synthesize explicit predication for them.
Applies to: [x] M4/G16G   [ ] A18 Pro/G17P (not tested)  [ ] both
Evidence: [x] independently assembled HW execution  [ ] HW splice (not needed)
  [x] API create/submit/exhaustion test  [ ] Linux end-to-end UAPI test
  [ ] captured userspace/command memory  [ ] encode/decode round trip
  [ ] own-MSL byte diff only  [ ] corpus inference only
Test/artifact: kernels/g6_suppress.metal, g6_suppress_control.metal;
  raw/m4_20260827_run0{1,2}/{g6_suppress,g6_suppress_control}.gated.json
Exact observed semantics or field mapping: see table below.
Finite namespace: not applicable.
Maximum-valid and first-invalid tests: n/a.
Failure/overflow behavior: [x] zero/discard (the write/increment simply does not
  happen; no fault, no partial write observed) for a demoted lane's writes on all four
  tested channels.
Correct behavior when the compiler/driver needs more: none needed -- this is a hardware
  guarantee the compiler can rely on rather than something it must implement.
Lifetime, destruction, and reuse semantics: n/a.
Counterexamples and untested cases: image store, stencil output, dual-source output,
  sample-mask output FROM a demoted lane, and whether an out-of-bounds/faulting load
  performed by a demoted lane can itself produce an observable command-buffer fault
  despite its write being suppressed, were NOT exercised in this experiment (explicitly
  flagged, not silently dropped -- an OOB-read probe was considered and deferred as a
  higher-risk follow-up requiring its own isolated single-change dispatch per the
  device-safety rules).
Driver/compiler consequence: extends FS-12 (which only established color suppression):
  a compiler backend can treat discard-suppression as automatic for buffer stores,
  atomics, color output, AND depth output, and does not need extra masking/predication
  around any of these four operation kinds following a discard. This also directly
  answers the GLFS-A01 falsifier concern: the addendum's feared "killed sample that
  still reaches depth/stencil, or a demoted-but-covered lane's write reaching a
  buffer/image" was NOT observed for any of the four tested channels.
```

### Exact numbers

`g6_suppress.metal`: even-x lanes discard, then ALL lanes unconditionally execute (in
program order, after the branch merge): a per-lane-unique device buffer store into a
pre-poisoned (`0xEE` fill) slot, a global atomic increment, a color write, and an
explicit `[[depth(any)]]` write. `g6_suppress_control.metal` is identical minus the
discard. Observed (`raw/m4_20260827_run01`, identical run02):

| channel | control (no discard) | test (even-x discarded) |
|---|---|---|
| device buffer slot (even-x lanes) | written (`0xc0ffee`+idx) | **stays poisoned** (`0xEEEEEEEE`) |
| device buffer slot (odd-x lanes) | written | written (unaffected) |
| global atomic counter | 16 (every lane incremented) | **8** (only surviving lanes incremented) |
| color (even-x) | visible | clear |
| depth (even-x) | written (0.1) | unchanged (clear=0.9) |

All four channels move together, deterministically, for **every** even-x lane (16/16 in
control all written; 8/16 in test, exactly the surviving half) — a complete, clean,
reproducible (byte-identical across both runs) negative result for every discarded
lane's ability to produce ANY of these four side effects, despite the shader placing
those instructions unconditionally, in program order, after the point (established in
§2) where the demoted lane is proven to still be executing ordinary ALU instructions.

---

## 5. GLFS-A05 — Early/late depth-stencil ordering and fragment side effects

```text
Status: [x] Closed for the tested factorial ({no attribute, [[early_fragment_tests]]} x
  {no discard, y<H/2 discard} x {fixed-function depth, explicit [[depth(any)]] output}).
Answer, where Yes/No: n/a (multi-valued, see table).
Applies to: [x] M4/G16G   [ ] A18 Pro/G17P (not tested)  [ ] both
Evidence: [x] independently assembled HW execution  [ ] HW splice (not needed)
  [x] API create/submit/exhaustion test  [ ] Linux end-to-end UAPI test
  [ ] captured userspace/command memory  [ ] encode/decode round trip
  [ ] own-MSL byte diff only  [ ] corpus inference only
Test/artifact: analysis/gen_e_kernels.py -> kernels/e_*.metal (6 generated variants);
  raw/m4_20260827_run0{1,2}/e_*.gated.json
Exact observed semantics or field mapping: see table.
Finite namespace: not applicable (behavioral ordering, not a resource table). No finite
  temporary/attachment/per-sample state exhaustion was found or tested at this small
  scale (8x8 target, sampleCount=1 for this group).
Maximum-valid and first-invalid tests: n/a.
Failure/overflow behavior: n/a.
Correct behavior when the compiler/driver needs more: a compiler emitting
  [[early_fragment_tests]] can rely on true pre-shader-launch rejection (not merely a
  post-hoc write-suppression) for the depth-fail region; this is the correctness basis
  for using early-Z as a genuine performance optimization, not just a semantic no-op.
Lifetime, destruction, and reuse semantics: n/a.
Counterexamples and untested cases: stencil output, conservative-depth qualifiers, and
  MSAA depth-attachment interaction (this group ran at sampleCount=1 only) were not
  exercised -- explicitly deferred.
Driver/compiler consequence: "which effects a later discard can and cannot undo" now
  has a concrete, tested answer for the depth/occlusion pair: under ORDINARY (late)
  testing, a later discard DOES retroactively cancel the occlusion-query contribution
  (32->16 pass count when a discard removes half of the already-passing region); under
  [[early_fragment_tests]], a later discard inside the (launched) shader does NOT
  retroactively cancel the occlusion count already committed by the early test (stayed
  at 32, matching the no-discard-early case exactly) even though color/buffer/atomic
  writes for THAT lane are still suppressed per GLFS-A06. A compiler must therefore
  treat "occlusion/visibility counting" as committed at the EARLY test point when
  [[early_fragment_tests]] is declared, distinct from and NOT reversible by a
  subsequent discard -- this is a genuine, non-obvious ordering fact a driver
  implementer cannot get right by guessing.
```

### Exact numbers (8x8 target, W=8 gives a clean 4-column pass / 4-column fail split
against `clearDepth=0.5`, `compare=Less`; "ran" = an atomic fired as the shader's very
first statement, so it fires regardless of any later discard)

| variant | occlusion (of 64) | ran, pass region (of 32) | ran, fail region (of 32) |
|---|---:|---:|---:|
| `e_late_nodiscard` (no attribute) | 32 | 32 | **32** |
| `e_early_nodiscard` (`[[early_fragment_tests]]`) | 32 | 32 | **0** |
| `e_late_discard` (no attribute + y<H/2 discard) | **16** | 32 | 32 |
| `e_early_discard` (`[[early_fragment_tests]]` + y<H/2 discard) | **32** (unchanged) | 32 | **0** |
| `e_shaderdepth_nodiscard` (explicit `[[depth(any)]]` output) | 32 | 32 | 32 |
| `e_shaderdepth_discard` (explicit depth output + y<H/2 discard) | **16** | 32 | 32 |

**Reading the table:** ordinary and shader-depth-output testing are **LATE** — the
shader always launches (ran=32/32 in both regions) regardless of eventual pass/fail; a
discard placed inside always reduces the occlusion count proportionally (32→16 when it
removes half the passing region). `[[early_fragment_tests]]` is **EARLY** — the
depth-fail region's shader launch is skipped entirely (ran=0/32), a direct, decisive
proof of true pre-shader-launch rejection, not just late write suppression; and,
critically, a discard placed inside the (launched) pass-region shader does **not**
reduce the occlusion count that the early test already committed (32, not 16) — the
asymmetry the addendum specifically asked for ("which effects a later discard can and
cannot undo").

---

## 6. GLFS-A07 — Sample shading invocation and liveness model

```text
Status: [x] Closed for invocation-frequency-vs-[[sample_id]] and per-sample kill
  granularity's aggregate reproducibility; [ ] Partial for the exact per-lane pattern
  of one sub-probe (see Counterexamples) and for MinSampleShading-style fractional
  rates (closed as a documented ABSENCE, not a hardware measurement).
Answer, where Yes/No: n/a (multi-valued).
Applies to: [x] M4/G16G   [ ] A18 Pro/G17P (not tested)  [ ] both
Evidence: [x] independently assembled HW execution  [ ] HW splice
  [x] API create/submit/exhaustion test  [ ] Linux end-to-end UAPI test
  [ ] captured userspace/command memory  [ ] encode/decode round trip
  [ ] own-MSL byte diff only  [x] PUBLIC (Metal Shading Language spec surface check,
  for the MinSampleShading-absence finding only)
Test/artifact: kernels/f_persample_count.metal, f_perpixel_count.metal,
  f_persample_discard.metal; raw/m4_20260827_run0{1,2}/f_*.gated.json
Exact observed semantics or field mapping: see below.
Finite namespace: invocation-frequency "rate" namespace = exactly 2 states (per-pixel /
  per-sample), gated solely by [[sample_id]] presence in the fragment function
  signature; MSL exposes NO third (fractional/MinSampleShading-style) state -- checked
  against the public Metal Shading Language specification surface (PUBLIC source, not a
  hardware absence-of-capability test, since there is no API surface to even attempt to
  invoke).
Maximum-valid and first-invalid tests: n/a (binary namespace).
Failure/overflow behavior: n/a.
Correct behavior when the compiler/driver needs more: a driver asked to honor an
  OpenGL MinSampleShading value must round it to one of the two available Metal-exposed
  rates (typically: any value > 0 -> declare/consume [[sample_id]] to force full
  per-sample shading; value == 0 -> ordinary per-pixel path) -- there is no partial-rate
  hardware path reachable through Metal to spill into instead.
Lifetime, destruction, and reuse semantics: n/a.
Counterexamples and untested cases: f_persample_discard_N4 (per-sample-id-conditioned
  discard, odd sample_id discards) produced a DETERMINISTIC (byte-identical across both
  runs) but SPATIALLY NON-UNIFORM atomic-suppression pattern: of the 4 pixels x 2
  odd-sample-IDs = 8 "should be suppressed" slots, only 2 (both in the SAME two of 4
  pixels, at sample_id=1 only, never sample_id=3) actually read as suppressed (ctr=0);
  the other 6 read as NOT suppressed (ctr=1), unlike the uniform, complete suppression
  g6_suppress found for WHOLE-fragment discard. This is recorded exactly as observed,
  flagged PARTIAL/OPEN, and explicitly NOT generalized into a "per-sample discard only
  partially suppresses atomics" rule -- it needs an adversarial follow-up (different
  target size, different sample-id parity pattern, and ideally an independent probe
  design) before promotion. It does not contradict or weaken the whole-fragment-discard
  finding in GLFS-A06, which is complete and uniform.
Driver/compiler consequence: [[sample_id]] presence is the ONLY Metal-level control
  over per-sample vs per-pixel shading; a compiler backend gets no free per-pixel-
  broadcast fast path once MSAA is enabled and per-sample behavior is requested. The
  per-sample-discard suppression anomaly above means a compiler MUST NOT yet assume
  per-sample kill uniformly suppresses side effects the same way whole-fragment kill
  does, pending the follow-up.
```

### Exact numbers

`f_persample_count.metal` ([[sample_id]] declared) vs `f_perpixel_count.metal` (not
declared), 2x2 target, atomic increment into a `(pixel,sample)`-indexed counter,
sampleCount N∈{1,2,4} (`raw/m4_20260827_run01/f_{persample,perpixel}_count_N{1,2,4}.
gated.json`):

| N | `f_persample_count` per-(pixel,sample) slot | `f_perpixel_count` slot0 value | total invocations (either kernel) |
|---|---|---|---:|
| 1 | every slot = 1 | 1 | 4 |
| 2 | every slot = 1 (2 distinct samples/pixel, each exactly once) | **2** | 8 |
| 4 | every slot = 1 (4 distinct samples/pixel, each exactly once) | **4** | 16 |

Per-sample shading launches **exactly one invocation per covered `(pixel,sample)`
pair** — clean, exhaustive (every one of 4/8/16 slots hit exactly once, zero
double-counts, zero misses). The per-pixel (no `[[sample_id]]`) kernel's single
output slot accumulates to **N**, not 1 — the fragment shader body is genuinely
re-executed N times per covered pixel at sample count N even without `[[sample_id]]`;
there is no observed single-invocation-broadcast fast path for "ordinary" MSAA
shading on this hardware. This scales exactly N-for-N across N=1,2,4 (ruling out a
fixed off-by-something artifact), and the N=1 case (where per-sample and per-pixel are
definitionally identical) correctly gives 4 in both, which is the internal control
proving the counting method itself is sound.

---

## 7. GLFS-A04 note (not a Bundle A closure target — GLIO-A04/other-bundle territory
per the addendum's own text, mentioned here only because the g6/msaa evidence bears on
it): "shader output replaces... prior coverage" is confirmed structurally: writing
`[[sample_mask]]` is the SAME submission mechanism as `discard_fragment()` (§1), and its
value is read back exactly via the resolve-fraction technique with no combination/
intersection with any prior fixed-function coverage observed in this single-primitive,
full-coverage geometry (no separate API sample mask or alpha-to-coverage was configured
in any case here — genuinely out of this bundle's scope, flagged for whichever bundle
owns GLFS-A04).

---

## 8. Gate results

```
$ python3 verify.py --selftest   -> RESULT: PASS (10/10 checks)
$ python3 verify.py --seqtest    -> RESULT: PASS (8/8 checks; the two intentional
                                     [FAIL] lines printed mid-run are `smoke()`'s own
                                     internal diagnostic showing it correctly refuses
                                     once raw/run01 exists -- not counted, see the
                                     seqtest[RUN01_PRESENT]/[RUN02_PRESENT] PASS lines
                                     that assert `not smoke(...)`)
$ python3 verify.py --smoke      -> RESULT: PASS (run BEFORE raw/m4_20260827_run01
                                     existed; wrote nothing to raw/)
$ python3 run.py --run run01 --out raw/m4_20260827_run01   -> 78/78 cases, all OK/SCANNED
$ python3 run.py --run run02 --out raw/m4_20260827_run02   -> 78/78 cases, all OK/SCANNED
$ python3 verify.py --crossrun raw/m4_20260827_run01 raw/m4_20260827_run02
                                  -> RESULT: PASS (78/78 gated records byte-identical)
```

No GPU fault, hang, command-buffer error, or host wedge occurred in either run or in
any pilot dispatch across this experiment's full lifetime (well over 150 individual GPU
dispatches including pilot exploration). No `macvdmtool` invocation, no A18/M5 contact.

## 9. Finite-resource-mandate summary table

| Namespace/resource | Scope | Encoding | Exact usable range/count | Holes/reserved | First invalid value | Observed failure | Correct "need more" fallback | Evidence |
|---|---|---|---:|---|---:|---|---|---|
| Fragment sample-coverage mask (GLFS-A01) | one fragment invocation's tilebuffer/depth/stencil submission | 32-bit value as exposed via MSL `[[sample_mask]]`; hardware-effective width = N=rasterSampleCount | bits [0,N), N∈{1,2,4} | none within [0,N) | bit N (first inert, not first rejected) | silently masked to low N bits, no fault/alias/wrap | driver advertises exactly N=rasterSampleCount as the mask width; never emit/rely on bits ≥N | `msaa_*` cases, §1 |
| Fragment kill-op source-register field (GLFS-A01, byte+4 bits[4:0] of the `57 14 54` op) | one instruction operand | 5 tested bits of an 8-bit byte | `0x00`=correct register; every other tested value in [4:0] behaves as reading a zero-valued register | bits[7:5] untested beyond single-bit values, no observed effect | not established (no value tested faulted) | silent "reads zero" (kill), not a fault | compiler must always emit `0x00`/whatever the compiler's own register allocator routes there; do not treat as a free field | `splice_B4own_*` cases, §1 |
| Per-sample shading invocation rate (GLFS-A07) | one Metal render pipeline/fragment function | binary: `[[sample_id]]` declared or not | 2 states only | n/a | n/a (not a numeric range) | n/a | round any fractional OpenGL MinSampleShading request to one of the 2 states; no third hardware path reachable via Metal | `f_persample_count`/`f_perpixel_count`, §6 |

## 10. Clean-room attestation

```text
Clean-room provenance: OWN-SHADER + HW-PROBE (+ PUBLIC for the MSL-spec-surface check
  in §6)
Inputs inspected: every kernels/*.metal file listed in work/pre_reg_hashes.txt /
  CAPTURE_CONTRACT.json (all authored by this experiment); harness/fsrun.m (authored,
  models tools/agxtest/agxrender.m's public-Metal-API splice technique); tools/shdump,
  tools/agx-isa, tools/agxtest used read-only, exactly as documented in their own
  READMEs (agxparse.py --locate SYMBOL --stage STAGE returns only an (offset,length)
  pair, never a materialized byte blob of any other region -- the EXP-0050 quarantine's
  lesson was applied: no whole-archive byte-array read, no other-stage/other-region
  extraction, ever, in this experiment's own code)
Apple binary introspection: NONE. Every inspected/spliced byte is the compiled output
  of MSL source we wrote (`kernels/*.metal`), compiled by the public
  `newLibraryWithSource:`/`shdump` runtime path.
Reproduction: python3 run.py --run runNN --out raw/m4_<date>_runNN ;
  python3 verify.py --crossrun raw/m4_<date>_run01 raw/m4_<date>_run02 ;
  python3 verify.py --selftest ; python3 verify.py --seqtest
Evidence: raw/m4_20260827_run01/, raw/m4_20260827_run02/ (78 gated+78 nongated JSON
  pairs each); work/pre_reg_hashes.txt / CAPTURE_CONTRACT.json (authored-input hashes);
  manifest.json
```
