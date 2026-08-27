# EXP-0076 results — M4 owned-buffer robustness matrix (MEM-06..MEM-10)

**Headline verdict (tested configuration).** For authored MSL accessing an
owned 64-byte device buffer at controlled byte offsets through the frozen
pointer idioms, this Apple M4 / G16G (macOS 26.6.2 build 25G82, Metal 4,
runtime compile, `fastMathEnabled = NO`, `mathMode = MTLMathModeSafe`):

1. **No fault, no hang, no command-buffer error, and no guard corruption
   anywhere in the matrix** — including reads and stores a full KiB past the
   end of the allocation and an out-of-allocation atomic exchange. All
   106 cases x 2 runs completed with status `ok`.
2. **Out-of-allocation reads return 0x00 for every tested width**
   (MEM-08 = Yes), and **out-of-allocation stores are discarded** —
   allocation, both guard allocations, and all result guards unchanged
   (MEM-10 = Yes, for the tested offsets).
3. **Unaligned accesses do not fault and never corrupt neighbors — but they
   do NOT access the bytes at the requested address.** The effective address
   of every access unit is its address **aligned down to the unit's natural
   width** (8/16-bit: one unit; 64-bit: two 32-bit units; 128-bit: four
   32-bit units, each aligned down to 4). One single model of this form
   predicts **108/108 load-side and 108/108 store-side observations** across
   both runs (212 case records, zero exceptions) — including all 26
   boundary-straddling reads and all 26 straddling stores.
4. The pre-registered per-component **mix model for straddling reads (H4) is
   refuted**: a read that starts in-bounds does not return the bytes at its
   start offset; it returns the aligned-down window's bytes, and only the
   components whose aligned-down window begins at/after the allocation end
   read as zero.
5. Everything is **deterministic**: the two runs' 106-case result files are
   byte-identical, including every out-of-allocation value.

---

## OBSERVED (directly, from `raw/`, before any interpretation)

- Two contracted runs, `raw/m4-20260827-run01` and `raw/m4-20260827-run02`,
  each 106 cases, one fresh process per case (fresh device, library,
  pipeline, buffers, queue, command buffer). Per run: 52 loads, 52 stores,
  2 atomic-exchange stretch cases; widths 8/16/32/64/128 bits; offset
  classes `align_in`(32), `mis1`(33), `mishalf`(35 @64-bit, 39 @128-bit),
  `last`(64-W), `oob1`(64), `far`(1088), `straddle_c` (cross the end by
  c = 1..W-1 bytes, offset 64-W+c).
- Status counts (both runs identical): `ok` 106, `cb_error` 0, `watchdog` 0,
  `proc_fail` 0, `proc_timeout` 0. No STOP. No case was retried.
- Environment (recorded at capture, identical in both runs): git revision
  `203c3138ab883dcc29385227a3781bb1fefe1d23` (repo dirty: this untracked
  experiment dir), python 3.14.6, `sw_vers` macOS 26.6.2 (25G82), device
  `Apple M4`, registryID 4294968259, `fast_math=false`, `math_mode_raw=0`
  (`MTLMathModeSafe`), `language_version_raw=262144` (default, not pinned).
  Median per-case library compile 0.0008 s; median dispatch 0.0014 s; max
  dispatch 0.0034 s.
- Cross-run: `raw/*/04_results.jsonl` are **byte-identical** (`cmp` clean);
  all guard-integrity flags true in every case; `pre_ok` true in every case;
  no load mutated the buffer (`load_buffer_mutations`: empty).

### MEM-06 — in-bounds loads (aligned and misaligned), verbatim

Aligned/last-element loads: byte-exact against the fill-derived expectation,
all 10 cases (e.g. `load_w32_align_in` @32 exp `05203b56` obs `05203b56`;
`load_w128_last` @48 exp `b5d0eb06213c57728da8c3def9142f4a` obs identical).

Misaligned loads: **all 6 cases diverge from the bytes at the requested
offset**; each returns the window at the address rounded DOWN:

| case | off | expected @off | observed | observed equals bytes at |
| --- | ---: | --- | --- | --- |
| load_w16_mis1 | 33 | `203b` | `0520` | 32 (2-align down) |
| load_w32_mis1 | 33 | `203b5671` | `05203b56` | 32 (4-align down) |
| load_w64_mis1 | 33 | `203b56718ca7c2dd` | `05203b56718ca7c2` | 32..39 |
| load_w64_mishalf | 35 | `56718ca7c2ddf813` | `05203b56718ca7c2` | 32..39 |
| load_w128_mis1 | 33 | `203b56718ca7c2ddf8132e49647f9ab5` | `05203b56718ca7c2ddf8132e49647f9a` | 32..47 |
| load_w128_mishalf | 39 | `c2ddf8132e49647f9ab5d0eb06213c57` | `718ca7c2ddf8132e49647f9ab5d0eb06` | **36..51** (per-32-bit align-down, not 32) |

The `load_w128_mishalf` row is decisive: a single 128-bit align-down would
return bytes 32..47; observed bytes 36..51 is exactly what four independent
32-bit units at 39/43/47/51 each aligned down to 36/40/44/48 produce. No
misaligned load faulted, and no load changed the buffer.

### MEM-07 — in-bounds stores (aligned and misaligned), verbatim

All 16 in-bounds stores completed with command-buffer status 4 and wrote
exactly W bytes; the bytes changed per case are exactly the aligned-down
windows, and **no byte outside the window changed** in any case:

| case | off | bytes changed | notes |
| --- | ---: | --- | --- |
| store_w8_align_in / _last | 32 / 63 | {32} / {63} | exact |
| store_w16_align_in / _mis1 / _last | 32/33/62 | {32,33} in all three | mis1 writes 32..33 (2-align down) |
| store_w32_align_in / _mis1 / _last | 32/33/60 | {32..35} / {32..35} / {60..63} | mis1 writes 32..35 |
| store_w64 (all four classes) | 32..56 | 8 bytes at the 4-aligned-down window of each 32-bit unit | mis1@33 and mishalf@35 both write 32..39 |
| store_w128_mis1 @33 / _mishalf @39 | | 32..47 / **36..51** | per-32-bit-unit align-down, mirroring loads |

The written value bytes are `ca c9 c8 c7 ...` rather than the registered
pattern image `c7 c8 c9 ca ...`: the harness uploaded the frozen pattern as
big-endian-read 32-bit words, so the little-endian memory image of the
uploaded words is per-4-byte reversed. The hardware wrote **exactly the
words it was given** — every one of the 16 in-bounds store windows matches
the uploaded-words image byte-for-byte — so store *value* fidelity, width,
addressing, and adjacency integrity are all fully determined by this data;
only the intended-vs-uploaded byte order was a harness-side encoding slip
(see Errata). The registered H2 byte-image check in `analysis.json` flags
16/16 divergent for exactly this reason; the per-window comparison above
(e.g. `cac9c8c7` = uploaded word `0xC7C8C9CA` little-endian) shows the
divergence is the encoding, not the hardware.

### MEM-08 — out-of-allocation reads (oob1 @64, far @1088), verbatim

Every OOB read returned all-zero bytes, at every width and both offsets
(10/10 cases): `load_w8_oob1`=`00`, `load_w16_oob1`=`0000`,
`load_w32_oob1`=`00000000`, `load_w64_oob1`=`0000000000000000`,
`load_w128_oob1`=`00000000000000000000000000000000`, and identically for all
five `*_far` cases at offset 1088 (+1 KiB past the end). No fault, no error
string, identical in both runs.

### MEM-09 — boundary-straddling reads, verbatim

26 cases (start in-bounds, cross the end by 1..W-1 bytes). Observed values
are NOT the registered mix model (in-bounds fill + zero tail at the
requested offset); they are the aligned-down-window bytes, with zero only in
the components whose aligned-down window starts at/after offset 64.
Representative rows (fill bytes: F(60)=f9, F(61)=14, F(62)=2f, F(63)=4a):

| case | off | mix model (H4) | observed | equals |
| --- | ---: | --- | --- | --- |
| load_w16_straddle_1 | 63 | `4a00` | `2f4a` | bytes 62..63 (2-align down) |
| load_w32_straddle_1 | 61 | `472f4a00` | `f9142f4a` | bytes 60..63 |
| load_w32_straddle_3 | 63 | `4a000000` | `f9142f4a` | bytes 60..63 |
| load_w64_straddle_5 | 61 | `142f4a`+5x`00` | `f9142f4a00000000` | low unit @61→60 (bytes 60..63) + high unit @65→64 OOB → `00000000` |
| load_w128_straddle_5 | 53 | `2f4a`+12x`00` | `213c57728da8c3def9142f4a00000000` | units 53→52, 57→56, 61→60 in-bounds; 65→64 OOB → zero |
| load_w64_straddle_4 | 60 | `f9142f4a00000000` | `f9142f4a00000000` | start already 4-aligned: align-down == offset, mix model coincides |

`analysis.json` counts 22/26 straddle reads divergent from the mix model;
the 4 "matching" cases are exactly those whose start offset was already
4-aligned (w64@60; w128@52/56/60), where the aligned-down window IS the
requested window and the two models coincide — consistent with, and
predicted by, the same single model.

### MEM-10 — out-of-allocation stores, verbatim

All 10 OOB store cases (`oob1` and `far` at all five widths): the 64-byte
allocation is **unchanged** (byte-identical to the fill), both 256-byte
guard allocations unchanged (`g1_ok`/`g2_ok` true), both result guards
unchanged, command-buffer status 4, no fault. `analysis.json`: 10/10
`oob_store_discarded`. Straddling stores (26 cases): the components whose
aligned-down 4-byte window lies inside the allocation were written (at the
aligned-down addresses), the components at/past the end were discarded, and
no guard changed — e.g. `store_w32_straddle_3`@63 wrote bytes 60..63 only;
`store_w128_straddle_15`@63 wrote bytes 60..63 only.

### Atomic exchange stretch, verbatim

- `axch_w32_align_in`@32: exchanged-out word = `05203b56` (exactly fill
  bytes 32..35 as a little-endian word); buffer bytes 32..35 replaced by the
  uploaded word image; no other byte changed.
- `axch_w32_oob1`@64: exchanged-out word = `00000000`; the allocation and
  all guards unchanged; no fault, no command-buffer error.

## INTERPRETED (supported by the observations, not itself observed)

A single behavioral model accounts for every observation with zero
residuals: every access through the frozen idioms is performed as
independent **units** — one unit for 8/16-bit accesses, two 32-bit units for
64-bit, four for 128-bit — and each unit's effective address is the
requested address **rounded down to the unit's natural alignment** (1/2/4
bytes). A load unit whose aligned-down window lies inside the allocation
returns exactly those bytes; a unit whose window begins at or past the end
returns zero. A store unit whose window lies inside the allocation writes
exactly the given word bits; a unit at/past the end is discarded. Nothing
faults, nothing leaks into neighboring allocations (as placed by the
allocator in these runs), and the behavior is deterministic. Validated:
this model predicts 108/108 load-side and 108/108 store-side observations
across both runs (the atomic case counts on both sides), 0 exceptions.

What this does and does not establish:

- The observations fix the **userspace-visible behavior** of these frozen
  MSL idioms on this machine in this configuration. They do NOT locate the
  align-down (compiler-emitted address masking vs. hardware/TLU behavior),
  do not establish any native encoding, and do not bind any other compiler
  version, OS, or API surface.
- The OOB-read zero and OOB-store discard are consistent with either a
  bound/clamp mechanism, zero-filled slack in the driver's sub-allocation,
  or per-access masking — public-Metal behavioral evidence cannot
  distinguish these (MEM-11 adjacent). What matters for an implementer is
  that in this configuration the robust semantics are already exactly
  "OOB reads zero, OOB writes discarded, per-unit" — the same semantics
  Vulkan's `robustBufferAccess` / NIR `load_global_bounded` requires
  (MEM-12 input).
- Failure to observe guard corruption does not prove allocation isolation:
  the guard allocations are separate `MTLBuffer`s whose placement relative
  to the case buffer is chosen by the driver and was not observable through
  the public API.
- The misaligned-in-bounds behavior is the load-bearing negative result for
  a compiler: byte-exact unaligned device accesses must be decomposed by
  the compiler (e.g. to byte loads), because a monolithic unaligned load
  here returns the wrong window's bytes.

## Exact tested range

- Hardware/software: one Apple M4 (G16G), 10 GPU cores, macOS 26.6.2
  (25G82), Metal 4, runtime `newLibraryWithSource:` with
  `fastMathEnabled = NO` and `mathMode = MTLMathModeSafe`; MSL language
  version default (raw 262144).
- Operation: exactly the frozen idioms in `kernels/robustness_matrix.metal`
  (`*(device uint *)p`-style loads/stores; element-index atomic exchange,
  relaxed), byte offset from a device `uint` uniform, one compute thread per
  case, one case per process.
- Allocation: one 64-byte owned shared `MTLBuffer` per case, CPU-filled
  `F(i)=(0xA5+0x1B*i) mod 256`, bracketed by 256-byte guard allocations
  (0x5A before, 0xC3 after) and a guarded 32-byte result buffer; guards
  checked after every case.
- Offsets exercised: 32, 33, 35, 39, 48, 56, 57..63, 60, 61, 62, 63, 64,
  1088 — i.e. aligned in-bounds, misaligned by 1 and by W/2-1 (64/128-bit),
  last full element, first fully-OOB element, +1 KiB, and every
  straddle-by-c (c=1..W-1) at 16/32/64/128 bits. Widths 1/2/4/8/16 bytes.
- Two runs, fresh process tree each; results byte-identical.

Not tested (explicitly): any offset beyond 1088; negative offsets; offsets
larger than 2^32; other allocation sizes (the align-down and OOB-zero
behavior was probed only around a 64-byte allocation); buffers placed
adjacent to guard allocations by explicit placement; `fastMathEnabled=YES`;
64-bit atomics; fragment/vertex stages; concurrent accesses; any Linux/UAPI
path; any A18 (G17P) hardware; and any claim about the instruction encoding
actually emitted.

## Target and scope label

**M4 / G16G, local host, public Metal API only — behavioral evidence.**
No native-encoding or ISA claim is made or implied. No Linux/UAPI claim. No
A18 (G17P) inference: the A18 is hands-off for this work, nothing was run on
it, and this result must not be promoted to an A18 fact without its own
recorded experiment. M5 is a separate, deferred workstream and is not
touched.

---

## Required response block — MEM-06 (unaligned loads)

```text
Status: [ ] Open  [ ] Partial  [x] Closed  [ ] Not applicable
Answer, where Yes/No: [ ] Yes  [x] No  [ ] Unknown
Applies to: [ ] A18 Pro/G17P  [x] M4/G16G  [ ] both tested independently
Evidence: [x] independently assembled HW execution  [ ] HW splice
          [ ] API create/submit/exhaustion test       [ ] Linux end-to-end UAPI test
          [ ] captured userspace/command memory      [ ] encode/decode round trip
          [ ] own-MSL byte diff only                 [ ] corpus inference only
Test/artifact: experiments/EXP-0076-m4-buffer-robustness-matrix/
    raw/m4-20260827-run01/04_results.jsonl, raw/m4-20260827-run02/04_results.jsonl
    (byte-identical), analysis.json, manifest.json; matrix and gates in
    run.py/verify.py (--selftest/--preflight/--between-runs/--captured).
    Evidence qualification: our own MSL idioms compiled at runtime through
    the public API (OWN-SHADER / HW-PROBE class); no bytes spliced, no
    encoding inspected, no native instruction claimed.
Exact observed semantics or field mapping:
    M4/G16G, macOS 26.6.2 (25G82), Metal 4, runtime compile,
    fastMathEnabled=NO, mathMode=MTLMathModeSafe, 64-byte owned shared
    buffer, offset from a device uint uniform, one compute thread:
      * unaligned loads of every tested width (8/16/32/64/128-bit) complete
        with no fault and no buffer mutation;
      * they do NOT return the bytes at the requested offset: the effective
        address is rounded DOWN to the access unit's natural width
        (8/16-bit: one unit; 64-bit: two 32-bit units; 128-bit: four 32-bit
        units, each rounded down to 4) and those bytes are returned;
      * aligned loads and last-element loads are byte-exact (10/10).
    Counterexamples verbatim: load_w16_mis1@33 -> 0520 (bytes 32..33,
    expected 203b); load_w32_mis1@33 -> 05203b56; load_w64_mis1@33 ->
    05203b56718ca7c2; load_w64_mishalf@35 -> 05203b56718ca7c2;
    load_w128_mis1@33 -> bytes 32..47; load_w128_mishalf@39 -> bytes 36..51
    (per-unit align-down, decisive against a single 128-bit align-down).
Finite namespace: scope / encoding / exact usable count or range / holes and reservations:
    Not a finite-resource item. Enumerated: all five widths x {misaligned
    by 1, misaligned by W/2-1 where distinct} in-bounds offsets on a 64-byte
    allocation, plus aligned controls and last-element controls.
Maximum-valid and first-invalid tests:
    Misalignment is not a validity axis here: no tested misalignment (1, 3,
    7 bytes) is rejected or faults. The first "invalid" access in the
    offset axis is the first fully-OOB element (offset 64), which reads as
    zero rather than faulting (see MEM-08).
Failure/overflow behavior: [ ] reject  [ ] zero/discard  [ ] alias/wrap  [x] fault/device loss
    NONE of these: no fault, no device loss, no rejection, no corruption;
    the access silently uses the aligned-down address (an alias of the
    intended semantics, not of another allocation).
Correct behavior when the compiler/driver needs more:
    A compiler needing byte-exact unaligned loads must decompose them (e.g.
    to byte loads / `ldg` per byte) or mask the address itself before the
    memory op; it must NOT emit a monolithic unaligned device load and
    expect the bytes at the given offset. (Behavioral fact of this
    configuration; the mechanism -- compiler masking vs hardware -- is not
    identified here.)
Lifetime, destruction, and reuse semantics:
    Not applicable (stateless per-case accesses on owned buffers).
Counterexamples and untested cases:
    6 directed counterexamples listed above (all misaligned in-bounds load
    cases). Untested: other allocation sizes, offsets > 1088, negative
    offsets, fastMath arm, fragment/vertex stages, A18/G17P, Linux/UAPI,
    native encodings.
Driver/compiler consequence:
    Treat unaligned `nir_load_global` as NOT byte-exact on this path:
    either the frontend guarantees alignment, or the compiler lowers
    unaligned accesses to byte/aligned decompositions. Robustness-wise the
    misaligned path is safe (no fault), just semantically address-rounded.
```

## Required response block — MEM-07 (unaligned stores)

```text
Status: [ ] Open  [ ] Partial  [x] Closed  [ ] Not applicable
Answer, where Yes/No: [x] Yes  [ ] No  [ ] Unknown
Applies to: [ ] A18 Pro/G17P  [x] M4/G16G  [ ] both tested independently
Evidence: [x] independently assembled HW execution  [ ] HW splice
          [ ] API create/submit/exhaustion test       [ ] Linux end-to-end UAPI test
          [ ] captured userspace/command memory      [ ] encode/decode round trip
          [ ] own-MSL byte diff only                 [ ] corpus inference only
Test/artifact: experiments/EXP-0076-m4-buffer-robustness-matrix/
    raw/*/04_results.jsonl (both runs), analysis.json; per-window comparison
    in RESULTS.md "MEM-07" table.
Exact observed semantics or field mapping:
    M4/G16G, macOS 26.6.2 (25G82), Metal 4, runtime compile, precise mode:
      * unaligned stores of every tested width complete with no fault and
        NO adjacent-byte corruption: in every case exactly the aligned-down
        unit windows changed and every other byte of the allocation was
        untouched (full 64-byte readback compared);
      * addressing mirrors loads exactly (per-unit align-down; 128-bit =
        four 32-bit units, e.g. store_w128_mishalf@39 writes bytes 36..51);
      * the stored bits equal exactly the 32-bit words supplied to the
        kernel (little-endian memory image), proven byte-for-byte in all 16
        in-bounds cases;
      * straddling stores write only the in-allocation units and discard
        the rest (26/26 cases match this model).
Finite namespace: scope / encoding / exact usable count or range / holes and reservations:
    Not a finite-resource item. Enumerated: all five widths x {align_in,
    mis1, mishalf, last} + all straddle offsets, on a 64-byte allocation.
Maximum-valid and first-invalid tests:
    No misalignment is rejected. First invalid offset axis point = 64
    (fully OOB), whose store is discarded (see MEM-10).
Failure/overflow behavior: [ ] reject  [x] zero/discard  [ ] alias/wrap  [ ] fault/device loss
    OOB units are discarded silently. No fault, no wrap, no visible aliasing
    into neighbors in any tested case.
Correct behavior when the compiler/driver needs more:
    Same consequence as MEM-06: byte-exact unaligned stores require
    compiler-side decomposition; the monolithic unaligned store silently
    writes the aligned-down window. No corruption risk beyond the intended
    window was observed at any tested width/offset.
Lifetime, destruction, and reuse semantics:
    Not applicable.
Counterexamples and untested cases:
    No counterexample to the no-adjacent-corruption claim in 16 in-bounds +
    26 straddling cases. Registered H2 byte-image check flags all 16
    in-bounds stores divergent due to a harness value-encoding slip (the
    uploaded words' LE image is ca c9 c8 c7.. instead of c7 c8 c9 ca..);
    the hardware wrote exactly the words given, so value fidelity, width,
    addressing, and adjacency are fully determined; only the intended
    byte-order image was never landed. Untested as for MEM-06.
Driver/compiler consequence:
    Unaligned global stores may be emitted without corruption or fault
    risk on this path (aligned-down addressing), but byte-exact unaligned
    stores again require decomposition. The MEM-06/07 pair means the
    compiler must handle misalignment uniformly for loads and stores.
```

## Required response block — MEM-08 (out-of-allocation reads)

```text
Status: [ ] Open  [ ] Partial  [x] Closed  [ ] Not applicable
Answer, where Yes/No: [x] Yes  [ ] No  [ ] Unknown
Applies to: [ ] A18 Pro/G17P  [x] M4/G16G  [ ] both tested independently
Evidence: [x] independently assembled HW execution  [ ] HW splice
          [ ] API create/submit/exhaustion test       [ ] Linux end-to-end UAPI test
          [ ] captured userspace/command memory      [ ] encode/decode round trip
          [ ] own-MSL byte diff only                 [ ] corpus inference only
Test/artifact: experiments/EXP-0076-m4-buffer-robustness-matrix/
    raw/*/04_results.jsonl; analysis.json hypotheses.H3_MEM08_oob_reads_zero.
Exact observed semantics or field mapping:
    M4/G16G, macOS 26.6.2 (25G82), Metal 4, runtime compile, precise mode:
    reads whose (aligned-down) unit window starts at or past the end of the
    64-byte owned allocation return 0x00 for every byte, at every tested
    width (8/16/32/64/128-bit) and both tested distances (first fully-OOB
    element at +0..+15 bytes; +1 KiB at offset 1088). 10/10 cases all-zero;
    no fault, no command-buffer error; identical in both runs
    (deterministic). The OOB atomic exchange also reads 0x00000000.
Finite namespace: scope / encoding / exact usable count or range / holes and reservations:
    Not a finite-resource item. Distances probed: offsets 64..79 (via the
    five widths) and 1088. Distances between ~80 and 1088, beyond 1088, and
    negative offsets are untested.
Maximum-valid and first-invalid tests:
    Last valid byte = 63 (load_w*_last byte-exact); first invalid offset =
    64 -> zero fill, no fault. +1 KiB -> zero fill.
Failure/overflow behavior: [x] zero/discard  [ ] reject  [ ] alias/wrap  [ ] fault/device loss
    OOB reads are zero-filled, not rejected, not aliased to another
    allocation's data (in these runs), and do not fault.
Correct behavior when the compiler/driver needs more:
    For Vulkan robustBufferAccess on this configuration, OOB reads already
    return zero through the plain access path; an explicit clamp
    (load_global_bounded) is needed only to control WHICH in-bounds address
    is read (see MEM-06 align-down) and for widths/offsets not tested here.
Lifetime, destruction, and reuse semantics:
    Not applicable.
Counterexamples and untested cases:
    Zero counterexamples in 10 cases x 2 runs. Mechanism (bound check vs
    zero-filled slack) not identified; other allocation sizes, larger
    offsets, and other storage modes untested; A18/Linux untested.
Driver/compiler consequence:
    OOB reads on this path are already robust (zero) -- but note the
    align-down caveat from MEM-06 applies to the address computation, and
    MEM-09 shows straddling reads zero per 32-bit unit, per component.
```

## Required response block — MEM-09 (boundary-straddling reads)

```text
Status: [ ] Open  [ ] Partial  [x] Closed  [ ] Not applicable
Answer, where Yes/No: [ ] Yes  [x] No  [ ] Unknown
    (the registered per-component mix model is refuted; the actual rule is
    stricter and simpler)
Applies to: [ ] A18 Pro/G17P  [x] M4/G16G  [ ] both tested independently
Evidence: [x] independently assembled HW execution  [ ] HW splice
          [ ] API create/submit/exhaustion test       [ ] Linux end-to-end UAPI test
          [ ] captured userspace/command memory      [ ] encode/decode round trip
          [ ] own-MSL byte diff only                 [ ] corpus inference only
Test/artifact: experiments/EXP-0076-m4-buffer-robustness-matrix/
    raw/*/04_results.jsonl; analysis.json mem09_straddle_reads; the
    representative table in RESULTS.md "MEM-09".
Exact observed semantics or field mapping:
    M4/G16G, macOS 26.6.2 (25G82), Metal 4, runtime compile, precise mode:
    a read that starts in-bounds and crosses the end does NOT return
    (in-bounds bytes at the start offset + zero tail). It returns the bytes
    of each 32-bit (or narrower) unit at that unit's address rounded down;
    units whose rounded-down window starts at/past the allocation end read
    zero. Examples: load_w32_straddle_1@61 -> f9142f4a (bytes 60..63);
    load_w64_straddle_5@61 -> f9142f4a00000000 (low unit @61->60 in-bounds,
    high unit @65->64 zero); load_w128_straddle_5@53 ->
    213c57728da8c3def9142f4a00000000 (three in-bounds units + one zero
    unit). All 26 straddle cases x 2 runs match this rule; 22/26 differ
    from the registered mix model, and the 4 coinciding cases are exactly
    those already 4-aligned at the start (w64@60, w128@52/56/60), where the
    two rules agree.
Finite namespace: scope / encoding / exact usable count or range / holes and reservations:
    Not a finite-resource item. Enumerated: every crossing amount c=1..W-1
    at 16/32/64/128 bits.
Maximum-valid and first-invalid tests:
    The whole straddle range was exercised; the boundary case c=W-1 (one
    byte in-bounds) still reads the aligned-down in-bounds unit, never
    faults.
Failure/overflow behavior: [x] zero/discard  [ ] reject  [ ] alias/wrap  [ ] fault/device loss
    No fault at any crossing amount; the out-of-allocation units read zero.
Correct behavior when the compiler/driver needs more:
    `load_global_bounded`-style semantics must clamp per component before
    the access if byte-exact straddling behavior is required; the native
    path already provides zero for fully-OOB components (which is the
    Vulkan-required result), just not the requested in-bounds bytes when
    the start is unaligned.
Lifetime, destruction, and reuse semantics:
    Not applicable.
Counterexamples and untested cases:
    22 directed counterexamples to the mix model (all unaligned-start
    straddle cases). Untested: straddling at larger allocations, negative
    starts, atomic straddles.
Driver/compiler consequence:
    MEM-12 (load_global_bounded synthesis): the hardware/compiler path
    already gives per-32-bit-unit zero-fill past the end, so a bounded load
    can be synthesized as align/clamp the address per component then a
    plain load ONLY if the clamp also fixes the align-down effect; for
    byte-exact semantics the clamp must be computed on the byte address
    before any unit decomposition the compiler performs.
```

## Required response block — MEM-10 (out-of-allocation stores)

```text
Status: [ ] Open  [ ] Partial  [x] Closed  [ ] Not applicable
Answer, where Yes/No: [x] Yes  [ ] No  [ ] Unknown
Applies to: [ ] A18 Pro/G17P  [x] M4/G16G  [ ] both tested independently
Evidence: [x] independently assembled HW execution  [ ] HW splice
          [ ] API create/submit/exhaustion test       [ ] Linux end-to-end UAPI test
          [ ] captured userspace/command memory      [ ] encode/decode round trip
          [ ] own-MSL byte diff only                 [ ] corpus inference only
Test/artifact: experiments/EXP-0076-m4-buffer-robustness-matrix/
    raw/*/04_results.jsonl; analysis.json hypotheses.H5_MEM10_oob_stores_discarded.
Exact observed semantics or field mapping:
    M4/G16G, macOS 26.6.2 (25G82), Metal 4, runtime compile, precise mode:
    stores whose (aligned-down) unit windows lie entirely at/past the end of
    the 64-byte allocation are discarded: the allocation is byte-identical
    to its pre-store state, both adjacent 256-byte guard allocations are
    unchanged, both result guards unchanged, command-buffer status 4, no
    fault -- at every tested width and at both distances (offset 64 and
    +1 KiB). 10/10 cases. Straddling stores write the in-allocation units
    (at aligned-down addresses) and discard the rest (26/26). The OOB
    32-bit atomic exchange likewise discards (old value read as zero).
Finite namespace: scope / encoding / exact usable count or range / holes and reservations:
    Not a finite-resource item. Distances probed: offsets 64..79 and 1088;
    see MEM-08 for untested distances.
Maximum-valid and first-invalid tests:
    Last valid store target = bytes 56..63 / 48..63 etc. (last-element
    stores, all byte-exact); first invalid = offset 64 -> discarded.
Failure/overflow behavior: [x] zero/discard  [ ] reject  [ ] alias/wrap  [ ] fault/device loss
    Discarded silently; no corruption of the owning allocation, no observed
    corruption of the guard allocations, no fault, deterministic across
    runs.
Correct behavior when the compiler/driver needs more:
    Robust write behavior (OOB stores dropped) is already native on this
    path for the tested offsets; a driver implementing robustBufferAccess
    write semantics may rely on it for this configuration but must still
    handle the align-down addressing (MEM-07) for byte-exactness.
Lifetime, destruction, and reuse semantics:
    Not applicable.
Counterexamples and untested cases:
    None in 10 OOB + 26 straddling + 1 OOB-atomic cases x 2 runs. Caveat:
    guard non-corruption is placement-dependent evidence, not proof of
    isolation (guards are separate MTLBuffers whose placement is chosen by
    the driver); larger offsets and other allocation sizes untested.
Driver/compiler consequence:
    No write-side robustness emulation is needed for the tested offsets on
    this configuration; the store path is fault-free and discard-on-OOB.
    Combined with MEM-08, robustness on this path is symmetric: reads zero,
    writes dropped, per 32-bit unit.
```

## Required response block — MEM-11-adjacent / MEM-12-input (recorded observations)

```text
Status: [ ] Open  [x] Partial  [ ] Closed  [ ] Not applicable
Answer, where Yes/No: [ ] Yes  [ ] No  [x] Unknown
    (MEM-11 is an ISA/descriptor question; this behavioral experiment
    records adjacent observations only and closes nothing on MEM-11.)
Applies to: [ ] A18 Pro/G17P  [x] M4/G16G  [ ] both tested independently
Evidence: [x] independently assembled HW execution  [ ] HW splice
          [ ] API create/submit/exhaustion test       [ ] Linux end-to-end UAPI test
          [ ] captured userspace/command memory      [ ] encode/decode round trip
          [ ] own-MSL byte diff only                 [ ] corpus inference only
Test/artifact: experiments/EXP-0076-m4-buffer-robustness-matrix/ (whole tree)
Exact observed semantics or field mapping:
    Adjacent observations for MEM-11: through the public API, a plain
    device access past a 64-byte owned buffer already behaves as if bounded
    (reads zero, writes discarded, per 32-bit unit, deterministic, no
    fault). Whether that comes from a descriptor-level bound, address
    masking, or zero-filled allocator slack is NOT identifiable from this
    evidence. For MEM-12: the observed semantics coincide with
    load_global_bounded's required results for fully-OOB components; the
    two gaps a synthesis must close are (a) the align-down of unaligned
    in-bounds starts (MEM-06/07) and (b) which in-bounds bytes a straddling
    access returns (MEM-09) -- both are properties of the un-clamped path,
    so the clamp must operate on byte addresses per component before the
    compiler's unit decomposition.
Finite namespace / Maximum-valid and first-invalid tests:
    See MEM-08/MEM-10 blocks.
Failure/overflow behavior: [x] zero/discard (see MEM-08/MEM-10 blocks)
Correct behavior when the compiler/driver needs more:
    MEM-11 needs ISA/descriptor-level evidence (a separate splice/native
    experiment); MEM-12 synthesis rules are now constrained by this data.
Lifetime, destruction, and reuse semantics: not applicable.
Counterexamples and untested cases: mechanism untested by design (public
    API only).
Driver/compiler consequence:
    Do not assume a descriptor bound exists from this data; do use the
    observed zero/discard semantics when choosing where to place
    robustness clamps.
```

---

## Errata and process notes

- **First run01 attempt stopped pre-capture** (smoke gate): the harness
  printed the `obs` hex field without JSON string quotes, so the record did
  not parse. `raw/` was never created; the failure record was retained under
  `work/` and is preserved verbatim in `PROGRESS.md` (2026-08-27T23:47Z
  entry), after which the retained tree was removed per the pre-capture
  repair protocol. The one-line harness fix preceded any capture; no frozen
  matrix entry or expectation changed after it. Disclosure: the smoke
  invocation itself dispatched one real GPU case (the in-bounds aligned
  control), whose observed value (`05203b56`) was seen during diagnosis and
  happens to match the frozen expectation; the capture re-observed it like
  every other case.
- **Store-value word packing slip (does not affect any conclusion):** the
  harness uploaded the frozen store pattern as big-endian-read 32-bit words,
  so the intended in-memory image `c7 c8 c9 ca ...` was uploaded as words
  whose little-endian image is `ca c9 c8 c7 ...`. The hardware wrote exactly
  the words supplied (proven byte-for-byte in all 16 in-bounds cases), so
  store value fidelity, width, aligned-down addressing, adjacency
  integrity, OOB discard, and determinism are all fully determined by the
  capture; the registered H2 byte-image check in `analysis.json` flags
  16/16 divergent purely due to this encoding. A successor wanting the
  `c7..` image landed literally needs only a corrected packing line (no new
  information about the hardware is expected).
- `analysis.json`'s registered H1..H5 divergence counts are reported as
  computed by the frozen `analysis.py`; the unified per-unit align-down
  model validation (108/108 + 108/108, zero exceptions) was performed
  post-hoc and is documented in INTERPRETED above.
- Manifest order: the hash-frozen README lists `verify.py --captured`
  before `make_manifest.py --write`; the executable order is the reverse
  (the manifest must cover the full captured tree first). Same erratum
  class as EXP-0074; the final on-disk state was regenerated in the
  executable order and re-verified.
- Git HEAD moved during the session (orchestrator commits); both captures
  record the identical revision `203c3138ab88...` and the authored blobs
  are bound by `CAPTURE_CONTRACT.json` hashes, not by revision.
- EXP-0068's superseded scaffold was read for scope only; nothing was
  captured there and nothing from it is evidence. No Apple binary,
  archive, BO, command stream, or compiled-shader byte was inspected at any
  point; no remote target was contacted; no `macvdmtool` was run.

```text
Clean-room provenance: HW-PROBE / OWN-SHADER / PUBLIC API
Inputs inspected: authored MSL (kernels/robustness_matrix.metal), authored
  harness (harness/probe.m), authored runner/verifier/analysis, and the raw
  byte readbacks of our own dispatches. No Apple binary, archive, BO,
  command stream, or compiled-shader byte was inspected.
Apple binary introspection: NONE
Reproduction: python3 -B verify.py --selftest && python3 -B verify.py --captured
  && python3 -B analysis.py --run-a m4-20260827-run01 --run-b m4-20260827-run02
  (fresh capture requires python3 -B run.py --execute --run-id <id>)
Evidence: raw/m4-20260827-run01, raw/m4-20260827-run02, analysis.json,
  manifest.json (hashes every artifact except itself)
```
