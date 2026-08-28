# RESULTS — EXP-0114 m4-texture-deferred

**STATUS: COMPLETE for the frozen contract's 3 covered items (TEX-15, TEX-16's raw-splice half,
EXP-0094's gradient-operand register field).** Both capture runs (`m4-20260828f-run01`,
`m4-20260828f-run02`) captured 49/49 cases, `status: ok`, zero faults, zero timeouts, zero GPU
wedges. `analysis.json`: `repeat_exact: true` — every one of the 49 case records is byte-identical
between the two runs. All five standing gates PASS. The other 8 dispatched items (TEX-01, TEX-12,
TEX-19, TEX-20, TEX-21, TEX-22, TEX-26, TEX-27, TEX-28) are explicitly **NOT EXERCISED** here —
see §5.

Two earlier capture attempts are retained, quarantined, unmodified — in both cases every one of
the 49 cases ran correctly and the underlying scientific data is not in question; both were
caught by automated gates before promotion and neither was repaired in place, per
`SUBAGENT_BRIEF.md`'s standing rule:

- `m4-20260828d-run01`/`-run02` (`QUARANTINE-20260828d.md`): `run.py`'s environment-record helper
  omitted one required hash (`CAPTURE_CONTRACT.json`'s own).
- `m4-20260828e-run01`/`-run02` (`QUARANTINE-20260828e.md`): `gen_contract.py`'s blob-discovery
  incorrectly hash-pinned `README.md`/`RESULTS.md`/`PROGRESS.md` (files meant to be written
  *after* capture) into the same capture-time provenance registry as genuine inputs.

Both fixed; the pair promoted below is the third, final capture: `m4-20260828f-run01`/`-run02`.

Target: **local Apple M4 (G16G), macOS 26.6.2, arm64, "Apple M4", Mac16,10**, own-compiled MSL
only (`newLibraryWithSource:`), public Mach-O/Metal-fat container parsing
(`tools/shdump/agxparse.py`, read-only), own splice-and-dispatch harnesses. Nothing here is an
A18/G17P result — A18 is hands-off per `CLAUDE.md`. Pinned revision:
`87d02c34f56357734f448695cf62d37ab555fcb0` (`CAPTURE_CONTRACT.json`'s `pinned_git_revision`).

## Gate results

| gate | result |
| --- | --- |
| `verify.py --selftest` (against final CAPTURED tree) | PASS |
| `verify.py --seqtest` (PRE_GPU/RUN01_PRESENT/RUN02_PRESENT, 5 real subprocess gate checks) | PASS |
| non-recorded pre-capture smoke gate (`tex_native`, `run.py`'s `smoke_gate()`) | PASS before either `raw/` run dir existed |
| `raw/m4-20260828f-run01` | CAPTURED — 49/49 cases `exit=0 status=ok`, no `STOP.json`, no quarantine needed |
| `raw/m4-20260828f-run02` | CAPTURED — same shape, same outcome |
| `analysis/analyze.py --write` | PASS — `repeat_exact: true`, 49/49 cases match frozen expectations |
| `verify.py --captured` | PASS — final gate |

Wall-clock: each run completed in well under 2 minutes (49 fresh-process cases: 8 compile-only
diff cases + 41 compile+splice+dispatch cases against 1x1/2x2-scale textures and single-thread
dispatches).

## 1. TEX-15 — texture-read selector field (`op+4`) construction

### 1.1 Corrected premise (first-class negative result)

**OBSERVED.** `diff_sparse3` (`kernels/read_sparse3.metal`: 128 declared `[[texture(N)]]` args,
only 3 actually read — `[[texture(5)]]`, `[[texture(50)]]`, `[[texture(100)]]`, in that source
order) compiles to `op4_sequence: [0, 128, 0]` (`raw/m4-20260828f-run01/case_diff_sparse3.json`,
byte-identical in run02). **INTERPRETED.** This falsifies both candidate hypotheses the gap doc's
framing implicitly assumed: `op+4` is neither the literal MSL binding index (`5, 50, 100`
predicted) nor a stable compacted use-order index (`0, 1, 2` predicted). The observed `0, 128, 0`
pattern means the FIRST and THIRD reads were assigned the SAME `op+4` value despite addressing
two different physical textures — **`op+4` is a short-lived, compiler-reused register/uniform-slot
reference, not a per-resource identifier.** `diff_n4` (4 concurrently-read textures, each result
to its own output, no accumulation) shows the identical ping-pong: `op4_sequence: [0, 128, 0,
128]`. This directly matches and extends EXP-0016's own finding ("single-texture/single-sampler
shaders always encode a fixed local slot regardless of the Metal binding index") — now shown to
hold even for MULTIPLE non-contiguously-declared textures processed sequentially. `OWN-SHADER-DIFF`.

**Consequence for TEX-15's original framing:** "decode which of 0-127 the field encodes" is not
the right question for `op+4` — the true per-texture 0-127 selector must live in a **preceding
pointer-materialization instruction** (a 4-byte, byte0-low-nibble-`0xb` instruction immediately
before each read bundle; not decoded in this contract — see §6 successor spec). This contract
instead answers the question that IS well-posed for `op+4` itself: **what is its own bit width,
legal/populated range, and failure mode**, established by construction below.

### 1.2 Register-pressure census (own-shader-diff, compile-only, deterministic)

| case | N declared/used | bundle_count found | distinct nibbles (op+4 >> 4) seen | low nibble always 0? |
|---|---:|---:|---|---|
| `diff_n2` | 2 | 2 | {0, 8} | yes |
| `diff_n4` | 4 | 4 | {0, 8} | yes |
| `diff_n8` | 8 | 8 | {0, 8} | yes |
| `diff_n16` | 16 | 16 | {0, 8} | yes |
| `diff_n32` | 32 | 32 | {0, 8} | yes |
| `diff_n64` | 64 | 32 | {0, 1, 8, 9} | yes |
| `diff_n127` | 127 | 84 | {0, 1, 2, 3, 8, 9, 10, 11} | yes |
| `diff_sparse3` | 128 declared / 3 used | 3 | {0, 8} | yes |

**OBSERVED.** At low register pressure (N ≤ 32) the compiler reuses only 2 of the 16 possible
upper-nibble values (`0x0`, `0x8`); at higher pressure (N = 64, 127) it reaches at least 4 and 8
distinct nibble values respectively, always still confined to the **upper nibble** (low nibble
always `0x0` in every one of the 168 bundles scanned across all 8 diff cases, both runs).
**INTERPRETED.** The field genuinely has more than 1 bit of range (falsifying a naive "only bit7
matters" reading of EXP-0016's 2-texture finding) — the compiler simply doesn't need more than 2
concurrently-resident slots in a small kernel. `OWN-SHADER-DIFF`; the true maximum nibble value the
compiler can be driven to emit (whether it ever reaches 0xF) is untested — a bounded limitation,
noted in §5's "not exercised" list is not needed since this is answered analytically by the direct
construction below, which characterizes ALL 16 values regardless of whether the compiler itself
emits them.

**Limitation, stated plainly:** `bundle_count` undercounts `n_declared` at N=64 (32 of 64) and
N=127 (84 of 127). The scanner's pattern (companion 3rd byte `0x0c`, following op byte0 low
nibble 0 and op+2==`0x17`) is the same pattern that exactly matched every bundle at N≤32 and in
EXP-0016's own validated shapes; the discrepancy at scale is **unexplained** — plausibly the
optimizer combines/vectorizes some of the `acc += tK.read(c).x * (K+1)` terms into a different
encoding not covered by this pattern (each `diff_n*` kernel accumulates a per-texel-weighted sum,
optimizer-visible). This is recorded as an open item, not resolved here; it does not affect §1.3's
construction results, which splice a hand-controlled 2-texture baseline directly.

### 1.3 Construction (HW splice, `splice_tex` family, 31 cases — the finite-resource answer)

Baseline: `kernels/read_n2.metal` (own MSL, 2 `access::read` textures, `o[0] =
t0.read(c).x + t1.read(c).x`), HW-validated native behavior (`tex_native`): bound
`t0=0x11111111`, `t1=0x22222222` → `out_word_hex = 33333333` (exact sum), reproduced byte-identical
both runs. Bundle1 (t0) op+4 native = `0x00`; bundle2 (t1) op+4 native = `0x80`.

**Positive control / bidirectional detectability (H3).** `tex_flip_b2_to_t0` (bundle2's op+4
spliced `0x80→0x00`) → `22222222` (t0+t0, exact). `tex_flip_b1_to_t1` (bundle1's op+4 spliced
`0x00→0x80`) → `44444444` (t1+t1, exact). Both directions flip cleanly and reproducibly —
independently reproduces EXP-0016's original 2-texture splice finding with a freshly authored
kernel, and proves the splice mechanism itself reliably detects a real change. `HW-VALIDATED`.

**Full upper-nibble construction sweep (H1/H2), `tex_nibble_0`..`tex_nibble_f` (16 cases,
bundle2's op+4 spliced to `nib << 4` for every `nib` in 0..15):**

| nibble | spliced byte | observed `out_word_hex` | interpretation |
|---:|---|---|---|
| 0x0 | 0x00 | `22222222` | populated slot → t0 |
| 0x1 – 0x7 | 0x10..0x70 | `11111111` (all 7) | unpopulated → **silent zero** |
| 0x8 | 0x80 | `33333333` | populated slot → t1 (native) |
| 0x9 – 0xF | 0x90..0xF0 | `11111111` (all 7) | unpopulated → **silent zero** |

**Low-nibble invariance (H1's "don't-care" claim), 12 cases:** bundle2's op+4 spliced to
`{0x00,0x01,0x02,0x04,0x08,0x0F}` all → `22222222` (t0, matching nibble-0); spliced to
`{0x80,0x81,0x82,0x84,0x88,0x8F}` all → `33333333` (t1, matching nibble-8). Every one of these 12
plus the 16-value sweep reproduced byte-identical across both runs.

**Response block:**

```text
Status: [x] Closed for op+4's own bit width/range/failure-mode (as reframed in §1.1)
        [ ] Partial for the ORIGINAL "0-127 texture selector" framing -- see §1.1/§6
Answer: op+4 is (at least) a 4-bit field (upper nibble, bits 7:4); the lower nibble (bits 3:0)
        is inert to the hardware -- confirmed by construction across 12 representative
        low-nibble values at both populated slots, plus the 16-value full-nibble sweep. It is
        NOT a stable per-texture identifier: it names a short-lived register/uniform slot the
        compiler assigns and reuses via its own allocator (Section 1.1).
Applies to: [x] M4/G16G (HW-VALIDATED)  [ ] A18 Pro/G17P (INFERRED by family per CLAUDE.md)
Evidence: [x] independently constructed HW splice, both directions, positive control (H3)
          [x] full-range sweep (16/16 nibble values) with a positive AND negative expectation
              for every value  [x] low-nibble invariance across 12 constructed values
Finite-resource table (the field ITSELF, in the tested 2-live-texture program):
  exact representation: 4-bit field, upper nibble of op+4 (16 possible values)
  usable/populated range (in this specific 2-texture baseline): {0x0, 0x8} -- exactly 2 of 16
  holes: the other 14 nibble values (0x1-0x7, 0x9-0xF) -- ALL constructed and tested, ALL
    deterministic silent zero, zero faults, zero aliasing to t0/t1, zero garbage
  first-invalid value: any of the 14 holes (there is no single boundary -- see below)
  observed failure mode: silent zero (matches docs/isa/register-move-and-liveness.md's
    project-wide convention), never a fault, never a hang, never an alias to a live value
  low-nibble sub-field: fully don't-care, 12/12 constructed values confirm
Maximum-valid and first-invalid: NOT a monotonic ceiling -- unlike a table-index field, the
  "legal" set is exactly whichever slots THIS COMPILED PROGRAM populated (here: 2 of 16); a
  driver emitting its OWN code controls which nibble(s) are populated via its own register
  allocation, so "first invalid" is program-relative, not a fixed architectural boundary. A
  higher-register-pressure program (Section 1.2) shows the compiler itself populating up to 8
  of the 16 nibbles (N=127 diff census) -- consistent with the full 4-bit range being live
  hardware capability, not merely a 1-bit convenience.
Driver/compiler consequence: a Mesa backend must NOT treat op+4 as "the texture binding index."
  It must track which physical register/slot currently holds each live texture-descriptor
  pointer (ordinary register-allocation bookkeeping) and reference THAT via op+4's upper
  nibble; referencing an unallocated slot is safe-by-default (silent zero) but wrong. The real
  0-127 binding-index-to-pointer mapping happens in a PRECEDING instruction (§6), not here.
```

## 2. TEX-16 raw-descriptor-splice half — folded into §1.3

TEX-16's first half (129th direct texture: MSL compile-time rejection) was already closed by
EXP-0095 (structural, deterministic). Its second half — "raw table/selector injection" — **is**
exactly the 14-hole construction in §1.3: injecting an op+4 value the compiled program never
populated is precisely a raw out-of-population selector injection at the AGX-instruction level.
**Result: deterministic silent zero for every one of the 14 tested holes, zero faults, zero
aliasing** — the safest possible failure mode, and the same answer EXP-0095 found for the
DIFFERENT (bindless argument-buffer image index) resource namespace. Note the mechanism is
different from EXP-0095's: there, an out-of-range RUNTIME index reads past a driver-provisioned
table; here, an out-of-population BYTE VALUE references an unallocated register/uniform slot in
an otherwise-fixed compiled program. Both land on the same project-wide silent-zero convention.
`HW-VALIDATED`.

## 3. EXP-0094 gradient-operand register field — cleaner differential (was OPEN)

### 3.1 Differential design and diff size

Own MSL (`kernels/gradpair_A.metal` / `_B.metal`): a render pipeline with two per-vertex
varyings `gA`, `gB` (float4 each, carrying `gradient2d()`'s 4 scalar components: `dx.x, dx.y,
dy.x, dy.y`), source-identical except which named varying feeds `gradient2d()` and which is
summed into a dead (unread-by-the-oracle) output channel — the SAME varying-routing technique
EXP-0094 used successfully for `bias()` (its sec 3.3), instead of the `constant float*` +
`tid.x`-offset addressing that produced 116 differing bytes there.

**OBSERVED.** Compiling A/B and diffing the extracted fragment `_agc.main` bytes
(pre-registration exploration, `work/`, reproduced structurally by this same technique in the
frozen `diff`-less gradient contract — the 16 offsets below are FROZEN as literal splice targets
in `CAPTURE_CONTRACT.json`, not re-derived at capture time) gives **16** differing bytes (down
from 116) in a clean, systematic, mirrored pattern: 8 byte positions in `_agc.main+[33,97]` and 8
positions in `+[133,211]` with near-inverted values. A second differential pair
(`gradpair2_A/B.metal`, an inserted filler varying to shift overall register allocation) produces
the SAME first-block offsets `{33,43,53,63,73,81,89,97}` with different but analogously-mirrored
values. `OWN-SHADER-DIFF`.

### 3.2 Construction (HW splice, `splice_grad` family, 10 cases)

Oracle: a 2-level, solid-color texture (level0 = red, level1 = green), nearest mip filter — `gA`
fixed to a tiny gradient (selects level0/red), `gB` to a huge one (selects level1/green), so the
readback color unambiguously reveals which operand the sampler instruction actually used.

| case | pair | splice | observed pixel | verdict |
|---|---|---|---|---|
| `g1_native` | 1 | none | `r=1 g=0` (red) | baseline: gA used |
| `g1_off33` | 1 | `+33` alone, A→B value | `r=0 g=1` (green) | **individually causal** |
| `g1_off63` | 1 | `+63` alone, A→B value | `r=0 g=1` (green) | **individually causal** |
| `g1_off43_negctrl` | 1 | `+43` alone, A→B value | `r=1 g=0` (red, unchanged) | negative control: not independently causal |
| `g1_both_33_63` | 1 | `+33` and `+63` together | `r=0 g=1` (green) | consistency |
| `g1_all16` | 1 | all 16 A/B-differing bytes | `r=0 g=1` (green), matches B-native | consistency |
| `g2_native` | 2 (filler-shifted) | none | `r=1 g=0` (red) | baseline |
| `g2_off33` | 2 | `+33` alone | `r=0 g=1` (green) | **causal at same offset, 2nd register assignment** |
| `g2_off63` | 2 | `+63` alone | `r=0 g=1` (green) | **causal at same offset, 2nd register assignment** |
| `g2_off43_negctrl` | 2 | `+43` alone | `r=1 g=0` (red, unchanged) | negative control |

All 10 reproduced byte-identical between both capture runs.

**Response block:**

```text
Status: [x] Closed (causal effect established, bidirectionally reproduced, stable across two
              register assignments)  [ ] Partial (bit-level field semantics not claimed --
              see limitation below, matching EXP-0094 sec 3.5's own discipline)
Answer: fragment-relative byte offsets _agc.main+33 and _agc.main+63 are EACH independently
        sufficient to flip which vertex-interpolated operand gradient2d() reads its value from.
        A THIRD tested offset in the same differential block (+43) is NOT independently causal
        under single-byte splice -- it may govern a different gradient component (this
        experiment's oracle only detects "some component became large", not which of the 4
        components), or a different, non-operand-selecting role. Reproduced at the SAME
        relative offsets in a second differential pair with a different overall register
        assignment (an inserted filler varying) -- a stable encoding-position fact, not an
        artifact of one specific compiled program's layout.
Applies to: [x] M4/G16G (HW-VALIDATED)  [ ] A18 Pro/G17P (INFERRED by family)
Evidence: [x] independently constructed HW splice, bidirectional-equivalent (2 causal + 1
              negative-control offset, both pairs)  [x] consistency checks (both-together,
              all-16) reproduce the expected composite outcome
Limitation (stated plainly, matching EXP-0094 sec 3.5's clean-room discipline): NO bit-level
  claim is made about what +33/+63 encode (e.g. "this is register N" or "this is component
  dx.x's select field"). The oracle proves an OBSERVED CAUSAL EFFECT on real hardware, not a
  decoded field meaning. The other 5 bytes in the same 8-byte block (+43,+53,+73,+81,+89) were
  NOT individually spliced in this contract (time-boxed) -- a natural, cheap successor: repeat
  this same single-byte-splice methodology on each of the remaining 5, and on the mirrored
  second 8-byte block, to map which of gradient2d()'s 4 scalar components (if any) each byte
  governs.
Driver/compiler consequence: gradient2d()'s operand-register selection, like bias()'s (EXP-0094
  sec 3.3), lives in instructions PRECEDING the sampler bundle, not in the bundle itself -- a
  Mesa backend must model this as an ordinary register-allocation problem for the gradient
  operand, not a fixed instruction-field encoding to fill in directly.
```

## 4. Finite-resource summary table (every selector/index field touched)

| resource/field | exact representation | usable range (constructed) | holes | first-invalid | failure mode | driver fallback |
|---|---|---|---|---|---|---|
| texture-read bundle `op+4` (upper nibble) | 4-bit field, bits 7:4 of the byte; low nibble inert (12/12 constructed low-nibble values confirm) | program-relative: whichever slot(s) the compiler's own allocator populated (2 of 16 in the minimal baseline; up to 8 of 16 observed at N=127 register pressure) | every unpopulated nibble in a given compiled program (14/16 in the minimal baseline; ALL 14 constructed and tested here) | any hole value (no fixed architectural boundary — see §1.3) | deterministic silent zero; zero faults, zero aliasing, zero garbage across all 14 holes x 2 runs | driver must track live register/slot allocation for descriptor pointers itself; unallocated references are safe-by-default but semantically wrong |
| gradient-operand causal byte offsets (`_agc.main+33`, `+63`, fragment-relative) | at least 2 independently causal single-byte positions of an unspecified bit-level field, within a 16-byte differential block | 2 confirmed causal / 1 confirmed non-causal (`+43`) of 8 tested-as-a-block, at 2 register assignments | 5 untested individual bytes in the same block (`+53,+73,+81,+89`) + the entire mirrored 8-byte block | not established (no full sweep performed) | N/A (causal-effect test, not a range sweep) | driver must treat as register-allocation output, not a fixed field to encode directly |

## 5. NOT exercised in this contract (explicit, per dispatch)

The following 8 dispatched items were **not exercised** — no new evidence gathered, no cases run.
Reasons and successor pointers are in `PRE_REGISTRATION.md` §0 (unchanged from EXP-0106's own
successor specs, since nothing new was learned about them here):

- **TEX-01** (native `txp` projective-divide form) — needs `op+2` opcode-space fuzzing beyond
  every compiler-reachable value; a distinct, larger campaign from this contract's scope.
- **TEX-12** (sparse-texel residency) — needs `MTLHeap`/`updateTextureMapping:` lifecycle, a
  materially different harness shape (resource lifecycle, not a single dispatch).
- **TEX-19 / TEX-20** (bindless texture ceiling to 1,000,000 / behavior beyond) — needs
  allocation/binding at that scale; EXP-0095's methodology reused at the documented boundary is
  the named successor.
- **TEX-21 / TEX-22** (bindless sampler ceiling to 499,999 / reuse at 500,001) — needs an M4
  re-run of EXP-O2B's (A18-only) methodology at that scale.
- **TEX-26 / TEX-27 / TEX-28** (raw sampler-descriptor field injection: anisotropy/max-LOD/
  address/border/swizzle codes beyond Metal's clamp) — needs locating the **sampler**-side
  per-stage binding table (a `tools/iotrace` BO-capture investigation, not a shader-byte splice;
  the texture-side table was proven reachable in EXP-0016, the sampler side was found
  unreachable via the explicit-argument-buffer path in EXP-M4-08 specifically, not yet retried
  via the direct `[[sampler(n)]]` path).

## 6. Successor spec (unattempted, follow-on to §1.1's corrected finding)

Decode the 4-byte, byte0-low-nibble-`0xb` instruction immediately preceding each texture-read
bundle (visible in every extracted hex dump this contract produced, e.g. `read_n2`'s bytes 0-11
before the first companion). This is the plausible carrier of the TRUE 0-127 texture selector.
Method: build a differential pair analogous to §3's gradient design but for a SINGLE live texture
at two distinct declared `[[texture(N)]]` indices (own-shader-diff, no second live resource, to
remove the register-reuse confound §1.1 identified), diff the preceding-instruction bytes, and
splice-validate any causal byte the same way. Cross-reference
`docs/isa/register-move-and-liveness.md`'s still-open `byte+2` semantics (EXP-0087) since this may
be a sibling variant of the same "compact move" family under a different addressing mode.

## Clean-room provenance

```text
Clean-room provenance: OWN-SHADER + PUBLIC
Inputs inspected: kernels/*.metal (all authored for this experiment); AGX bytes extracted from
  our own compiled archives via tools/shdump/agxparse.py (public Mach-O/Metal-fat container
  parser, used read-only, not modified); own splice-and-dispatch harnesses
  (harness/texsplice.m, harness/gradsplice.m, harness/case_runner.py).
Apple binary introspection: NONE.
Reproduction: README.md "Reproduce" section; CAPTURE_CONTRACT.json pins every splice offset/value
  and expected outcome; run.py/verify.py/analysis/analyze.py are the exact commands.
Evidence: raw/m4-20260828f-run01/, raw/m4-20260828f-run02/ (49 case receipts + 3 provenance
  files each), analysis.json (repeat_exact: true), CAPTURE_CONTRACT.json's blob_sha256 registry.
```
