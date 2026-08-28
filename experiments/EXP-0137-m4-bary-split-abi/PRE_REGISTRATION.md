# EXP-0129 Pre-registration — barycentric anomaly discrimination + split
# prolog/epilog ABI construction (DRV-ABI-01 / P0.8, last two open items)

**Target: Apple M4/G16G, local host only.** A18 Pro: hands-off, no data
collected. M5: not touched. Pinned repository revision at freeze:
`cf544b4dd1fb37047c7cfee6a70a0d1a87628666` (dirty=true at freeze time, per
the pinned-revision rule: the working tree carries OTHER, unrelated,
concurrently-running sibling experiments' untracked directories — this
experiment gates on its own authored-file sha256 set below, not on live
`HEAD` or a clean tree).

This experiment closes P0.8/DRV-ABI-01's last two open items, both flagged
explicitly by EXP-0109/EXP-0117:

- **H1 — barycentric VALUE correctness/convention.** EXP-0117 (§4)
  established `sum(b)==1` and internal self-consistency, but hit a
  disclosed, 4x-reproduced anomaly: adding an unrelated shader output
  changed the observed `barycentric_coord` value, blocking the
  vertex-order/perspective-convention determination.
- **H2 — split prolog/epilog linkage contract.** EXP-0109 (§5.1) established
  the load-bearing NEGATIVE that Metal's own compiler never produces a
  third code segment beyond preamble+main in the cases it tested (10
  spot-checked). DRV-ABI-01 still requires the prolog/main/epilog linkage
  contract (live-ins/outs, calls/branches, register allocation, resource
  merging) a driver must implement.

---

## H1 — barycentric anomaly: hypothesis and falsifiers

**Prior evidence (cited, not re-derived):** EXP-0117's official two-run
capture recorded, for the `bary_values` case (triangle
`p={(-0.6,-0.6),(0.6,-0.6),(0.0,0.6)}`, `w={1,2,4}`, sample pixel `(32.5,
32.5)` on a 64x64 target, tags `(10,20,30)`, 2-output fragment function
`f_bary` = `{raw=barycentric_coord, manual=recombination}`):
`b=(0.24348931,0.13476601,0.62174469)`. A single, non-frozen, disclosed
supplementary probe (`work/supplementary/bary_diag*.metal`, EXP-0117) found
that adding a THIRD output that echoes `[[position]]` back out (otherwise
identical) changes the reading to
`b=(0.48697862,0.26953202,0.24348938)`, close to this project's
perspective-corrected host oracle. This was reported as a genuine,
unresolved anomaly, explicitly flagged for "a dedicated follow-up
(structural byte-diff of the two fragment variants' compiled code would be
the natural next step)."

**Competing explanations to discriminate (from the dispatch):**
1. Real hardware behavior — barycentrics genuinely depend on output layout.
2. An interpolation-slot allocation effect — adding an output shifts which
   coefficient slot the barycentric read consumes.
3. A harness artifact (pipeline/attachment-count difference, not the
   shader).

**H1a (falsifiable).** The anomaly is triggered specifically by the
fragment shader **reading `[[position]]`**, independent of (a) whether
`[[position]]`'s value is ever emitted as a color OUTPUT, and (b)
independent of the total OUTPUT COUNT. **Falsifier:** if a 3-output variant
whose 3rd output is a compile-time constant or an unrelated, genuinely-new
interpolated varying (NOT position) ALSO reproduces the flipped value, H1a
is false (count, not position-content, is the trigger). If a 2-output
variant that reads position only to store it into a `device` buffer (never
a color output) does NOT reproduce the flip, H1a is false (must be an
*output*, not mere consumption).

**H1b (falsifiable, harness-artifact exclusion).** The unmodified 2-output
baseline shader (`f_base`), rendered through a pipeline configured with a
**3rd, shader-unwritten** color attachment, reads back IDENTICALLY to the
same shader with only 2 configured attachments. **Falsifier:** any observed
difference implicates the harness/pipeline-descriptor path, not the shader.

**H1c (mechanism, structural).** If H1a holds, the compiled fragment bytes
for the "flips" case contain instructions the "does not flip" case lacks
that are independently documented (`docs/isa/encoding-tables.md`'s `iter`
entry) as the missing half of Apple9's perspective-correction lowering: a
`mode=0x4` (perspective-W-denominator) `iter` plus an `fspecial` (rcp, byte0
`0xaf`) plus a normalizing multiply. **Falsifier:** the "flips" and
"does-not-flip" cases' `iter`/`fspecial` instruction counts and modes are
structurally indistinguishable (same set, same modes) despite different
numeric output — would mean the divergence is NOT in the interpolation
setup and a different explanation is needed.

**H1d (convention).** Once the trigger is isolated, the AUTHORITATIVE
(intended, hardware-supported) value is the one produced by the trigger
condition, and: `barycentric_coord.x/.y/.z` correspond to the primitive's
vertices in **emission/assembly order** (`vid%3==0,1,2`, the same order the
vertex shader emits them — consistent with EXP-0117's independently-derived
`primitive_id` assembly-order finding), and the semantics are
**perspective-correct** (not screen-space-linear). **Falsifier:** the
observed values under the trigger condition, tested against TWO
independent, asymmetric (distinct `w` ratios, distinct sample-relative
barycentric weights) triangle/tag configurations, do not simultaneously
match a single consistent vertex-order + perspective-correct model to
within float-interpolation precision (~1e-3 relative).

**Independent/controlled variables:** shader source text (which output
fields exist, whether `[[position]]` is read/output), triangle/w/tags
geometry (CONFIG1 = EXP-0117's exact geometry, CONFIG2 = an independent
asymmetric geometry designed in this pre-registration), sample pixel (held
fixed at the render target's center texel, matching EXP-0117). Controlled:
render target size/format (64x64 RGBA32Float), draw call shape (single
uninstanced triangle, `vertexCount=3`), toolchain/OS/target.

---

## H2 — split prolog/epilog: hypothesis and falsifiers

**Prior evidence (cited):** EXP-0109 §5.1/§5.2 found every one of 10
spot-checked render/compute pipelines compiles to exactly two regions
(`_agc.main.constant_program`, `_agc.main`); a `noinline`-attributed compute
helper called twice produces the documented CALL-family opcode pattern
inside `_agc.main`. EXP-0035/EXP-0109/EXP-0117 established the CALL/RETURN
ABI: args in consecutive GPRs from r10, return value in r10 (single-scalar
case only), `frame_marker` (`43 00 00 01`) before a call, `0f 06`
reconverge after, call depth 1-128 exact (EXP-0117), byte+6 uniformly
`0x54` on this M4/toolchain (EXP-0117, correcting a discrepancy against
EXP-0035's A18-only `0x56` record).

**H2a (falsifiable).** A `[[clang::noinline]]`-attributed MSL helper
function, given a genuinely resource-touching or multi-call-site body, CAN
be compiled by Metal's own toolchain as a genuinely separate, out-of-line
Mach-O local symbol distinct from `_agc.main` (refining, not necessarily
reversing, EXP-0109's "no third region ever appears" claim — that claim's
own tested cases may not have included a shape the compiler declines to
inline). **Falsifier:** every constructed `noinline` helper (fetch-style
vertex prolog, blend-style fragment epilog, 5-arg/float4-return compute
helper) compiles to exactly two regions with no genuine `call` opcode
(`byte0=0x0f,byte1=0x05,byte4=0x8f` per `tools/agx-isa`'s `call` descriptor)
anywhere in the disassembly — i.e., Metal always inlines regardless of the
attribute, in which case H2's contract is scoped entirely to the ISA-level
CALL/RETURN ABI as already decoded, with no observed present-day compiler
precedent for genuine reuse.

**H2b (falsifiable, numeric correctness of a genuine split).** A
fragment "epilog" split into a `noinline` callee that receives the
programmable-blend tilebuffer read (`[[color(0)]]`, only legal on the
entry function) as an ordinary forwarded argument, and performs a
data-dependent, BRANCHING blend computation, produces numerically correct
results (matching the standard blend-equation arithmetic, per EXP-0117's
already-closed blend spec) for BOTH branches of its internal control flow.
**Falsifier:** either branch's HW readback does not match the formula.

**H2c (falsifiable, numeric correctness of a genuine prolog).** A vertex
"prolog" split into a `noinline` callee performing a format-convert
attribute fetch (`UChar4Normalized`-style, extending EXP-0109 §1.3's inline
fetch model to a genuinely called function) returns EXACT in-range values
and reads back exactly ZERO for an out-of-range index (paired positive/
negative control, per EXP-0109's established OOB-reads-zero model).
**Falsifier:** either the in-range values are wrong, or the OOB read is
non-zero/faults.

**H2d (falsifiable, entry-only-attribute forwarding).** An entry-only MSL
attribute (`[[color(0)]]`) placed on a non-entry helper's parameter is
either (i) rejected at compile time, or (ii) accepted but semantically
INERT (the callee simply receives whatever ordinary value the caller
passes at the call site, not an independent re-invocation of the
tile-read mechanism). **Falsifier:** the helper's parameter receives a
value that is NEITHER the caller's forwarded argument NOR a compile
rejection (e.g. a silently different/uninitialized value) — would indicate
a genuinely unsafe, undefined-behavior-prone construction a driver must
avoid outright rather than merely "always forward."

**Confounders considered:** MSL's `[[clang::noinline]]` vs
`__attribute__((noinline))` spelling (both tested as a controlled check);
Apple's shader compiler is not obligated to honor `noinline` at all
(pre-registered as an explicit possible negative outcome, not assumed
away); struct/argument-buffer layout differences between a genuinely
compute vs. render pipeline.

---

## Method (both H1 and H2)

Two independently-generated, byte-comparable evidence types per
constructed variant, mirroring EXP-0109/EXP-0117's practice:

1. **Structural** (`tools/shdump/shdump.m` + this experiment's own
   `harness/struct_extract{,_vonly}.m`, `tools/shdump/agxparse.py` --
   compile OUR OWN MSL, extract the exact AGX bytes, list Mach-O local
   symbol/region names, disassemble with `tools/agx-isa/isadb.py`
   (imported, unmodified) via this experiment's own
   `analysis/isahelper.py` wrapper -- OWN-SHADER).
2. **HW-PROBE** (this experiment's own `harness/render.m` /
   `harness/compute_callret.m` -- real draws/dispatches on the real M4,
   real readbacks, no splicing).

No Apple binary is inspected at any point; `tools/agx-isa`'s database was
itself built entirely from clean-room sources (see its own README) and is
used here only via its published `disassemble()` API on bytes this
experiment extracted from its own compiled shaders.

## Raw-record schema (frozen, no-nondet)

Every case record: `{i, id, family, gated, meta}`. `gated` MUST NOT
contain any of `{duration_ms, pid, timestamp, started_utc, address,
elapsed}` (enforced by `run.py`'s `check_no_nondet`, statically, at capture
time, recursing into dicts and lists-of-dicts). All process/timing metadata
lives only in the separate, never-crossrun-compared `meta` field.

## Environment / timeouts

macOS 26.6.2, Metal 4 (Apple9), Apple clang 21.0.0 (`xcrun` 72), Python
3.14.6, Mac16,10 (M4, 10 GPU cores). Hard timeouts: 30s per case, 60s per
harness build. One process per case (no shared-state leakage between
cases). `raw/` run-directory creation refuses to overwrite/reuse an
existing directory (enforced in `run.py`).

## Evidence labels anticipated

- `OWN-SHADER` (structural extraction+disassembly) and `OWN-SHADER-DIFF`
  (variant-to-variant comparison) for the H1 mechanism.
- `HW-VALIDATED` for every real-hardware numeric readback (H1's raw `b`
  values against host oracles; H2's blend/fetch/call-return correctness).
- `STRUCTURAL` for facts established from length/framing/region-presence
  alone without a full semantic bit-decode (e.g. the exact physical
  register numbering of a multi-component CALL return, which remains
  DRV-ISA-01 territory, not re-derived here).

## Frozen authored-file set (sha256 pinned in `CAPTURE_CONTRACT.json`)

`kernels/{bary.metal,bary_qual_persp.metal,bary_qual_noperspective.metal,
split_negctrl.metal,split_epilog.metal,split_prolog.metal,
split_callret.metal}`, `harness/{struct_extract.m,struct_extract_vonly.m,
render.m,compute_callret.m}`, `analysis/isahelper.py`, `casematrix.py`,
`run.py`, `verify.py`, `README.md`, this file.

## What this experiment does NOT attempt

- It does not re-derive the exact bit-level encoding of every field in the
  `iter`/`fspecial`/`call`/`ret` instruction families beyond what
  `tools/agx-isa` already documents (DRV-ISA-01 territory).
- It does not attempt to determine WHY Apple's compiler chooses to inline
  vs. keep out-of-line a given `noinline`-attributed helper (a
  compiler-heuristic question, not a hardware-ABI question); it reports
  the observed cases honestly and specifies the contract a DRIVER (which
  controls its own code generation, not Apple's heuristic) must implement.
- Per DRV-ABI-01's own scope ("specify what a future epilog generator must
  emit; do not implement that generator"), this experiment specifies the
  seam contract; it does not build a general-purpose prolog/epilog
  generator.
