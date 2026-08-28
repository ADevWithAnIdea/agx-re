# EXP-0129 Results — barycentric anomaly discrimination + split
# prolog/epilog ABI construction (DRV-ABI-01 / P0.8, closing the last two open items)

**Target: Apple M4/G16G, local host only** (Mac16,10, 10 GPU cores). macOS
26.6.2 (25G82), Metal 4 (Apple9), Apple clang 21.0.0, `xcrun` 72, Python
3.14.6. **A18 Pro: no data collected** (hands-off per `CLAUDE.md`); every
fact below is `INFERRED`-by-family for A18/G17P per `docs/m4-deltas.md`'s
ISA-identity finding, not independently confirmed on A18. M5: not touched.

**Two official captures**, `raw/m4-20260828-run01/` and
`raw/m4-20260828-run02/`, **29 cases each, all `OK`**, each a fully
separate `run.py` process invocation. `python3 verify.py --crossrun
raw/m4-20260828-run01 raw/m4-20260828-run02` → **29/29 byte-identical, 0
mismatches.** Zero faults, zero `CMDBUF_ERROR`, zero hangs, zero host
instability anywhere in this experiment.

---

## Standing-gate results

| Gate | Result |
|---|---|
| `--selftest` | **11/11 PASS** (runnable with zero `raw/` captures present; re-run and still passing after both official captures) |
| `--seqtest` | **3/3 PASS** — `PRE_GPU → RUN01_PRESENT → RUN02_PRESENT` all correctly detected |
| Non-recorded smoke gate | `verify.py --smoke` (wraps `run.py --smoke-only`, writes only to `work/`) — 2/2 real cases OK, run **before** either official capture and before `raw/` existed |
| No-nondeterministic-field | `run.py`'s `check_no_nondet()` statically forbids `{duration_ms, pid, timestamp, started_utc, address, elapsed}` inside any case's `gated` record, recursing into nested dicts and lists of dicts (needed for the `iters[]`/`records[]` array shapes); enforced at capture time |
| Fixtures from recorded reality | `harness/fixtures/recorded_reality.json` — 2 records built from real M4 GPU/compiler calls made via the FINAL frozen backends (`barystruct_base`, `baryrender_base`), used by `--selftest` |
| Cross-run byte-exact gate | **29/29 PASS**, 0 mismatches |

Other CODEX/SUBAGENT_BRIEF discipline followed: append+`fsync` after every
case record (`run.py`); `PROGRESS.md` per milestone (including two
disclosed pilot bugs and two disclosed structural discoveries, with exact
evidence, found and fixed/investigated BEFORE freezing); a full 29-case
dry run into `work/dryrun1/` (never `raw/`) before spending either
official run id; one process per case; hard 30s per-case / 60s per-build
timeouts; `raw/` run-directory creation refuses to overwrite/reuse an
existing dir; `CAPTURE_CONTRACT.json` pins authored-file sha256 hashes
(verified unchanged from `PRE_GPU` freeze through `RUN02_PRESENT` — all 17
authored files bit-identical to their frozen hashes) rather than live
`HEAD` (`HEAD` moved once, `cf544b4d…`→`6987e19e…`, purely because the
orchestrator committed sibling experiments between pre-registration and
capture — not a gate failure, per the pinned-revision rule).

---

## TL;DR — per-item verdicts

1. **H1, barycentric anomaly — RESOLVED, mechanism identified,
   convention pinned.** The anomaly is **specifically triggered by the
   fragment shader reading `[[position]]`** — independent of output
   count and independent of whether position is ever emitted as a color
   output. A genuinely new, correctly-connected interpolated varying
   (`count3_vary`) and a compile-time-constant 3rd output
   (`count3_const`) do **not** trigger it; a pipeline configured with an
   extra unwritten attachment (`attach3ctrl`) does **not** trigger it
   (rules out the harness-artifact explanation outright). Structurally,
   the baseline (no `[[position]]`) compiles `barycentric_coord` to only
   **2 `iter` ops and 0 `fspecial`** — i.e. it computes two raw
   perspective-*numerators* (`l_i/w_i`) and derives the third component
   as the sum-to-one complement, **never applying the shared
   normalize-by-sum-of-numerators step**. Reading `[[position]]`
   (regardless of whether its value is used) adds the missing
   **perspective-W-denominator `iter` + `fspecial` (rcp) + normalizing
   multiply** machinery, and `barycentric_coord`'s own numerators get
   swept up in it. Numerically: the baseline matches a
   **"perspective-numerator + sum-to-one-complement"** model
   (`Model B`) exactly, in **two independent, asymmetric triangle/`w`
   geometries**; the position-touching cases match the standard,
   fully-**normalized, perspective-correct** model (`Model C`) exactly,
   in both geometries. **Verdict: `CLOSED`, `HW-VALIDATED` +
   `OWN-SHADER-DIFF` (structural).** Convention:
   `barycentric_coord.x/.y/.z` correspond to the primitive's vertices in
   **emission/assembly order** (`vid%3==0,1,2`); the intended/correct
   semantics are **perspective-correct**. **Driver consequence:** a
   compiler backend targeting AGX directly must **always** emit the full
   perspective-numerator + W-denominator + reciprocal + normalize
   sequence for `barycentric_coord`, unconditionally — it must not infer
   "does this shader need perspective correction" from unrelated
   shader content the way Apple's MSL compiler evidently does on this
   toolchain, because that inference is demonstrably incomplete
   (`barycentric_coord`'s own perspective need is not counted by
   whatever heuristic decides to emit the W-denominator machinery; only
   an accidental, indirect one from `[[position]]` is).
2. **H2, split prolog/epilog contract — CONSTRUCTED, both regimes
   observed and validated.** Genuine, `noinline`-attributed, out-of-line
   CALL-boundary "prolog" (vertex attribute fetch) and multi-argument/
   multi-component-return ("epilog"-shaped) helper functions were built,
   compiled, and run correctly on real hardware. **Two distinct compiler
   regimes were observed and are both reported, refining (not reversing)
   EXP-0109's "no third region ever appears" claim**: (a) a single-call-
   site fragment "epilog" (`do_blend_epilog`) got **inlined** despite
   `[[clang::noinline]]` (confirmed unaffected by attribute spelling) —
   still exactly 2 Mach-O regions, 0 `call` opcodes; (b) a single-call-
   site vertex "prolog" (`fetch_attr`) and a 2-call-site compute helper
   (`mk4`) were **kept genuinely out-of-line** — **3 Mach-O regions**
   (a real, separately-named local symbol,
   e.g. `l__Z10fetch_attrPU9MTLdeviceKDv4_hj` / `l__Z3mk4fffff`), real
   `call`/`frame_marker`/`pop_reconverge` instructions, and — **both
   numerically HW-VALIDATED** — correct results end to end (blend
   arithmetic exact for both a branching add- and mul-shaped epilog body;
   fetch exact in-range and exactly zero out-of-range, extending
   EXP-0109's OOB-reads-zero model to a genuinely called fetch; a 5-scalar-
   argument, float4-return, 2-call-site compute case exact for all
   tested inputs). **Verdict: `CLOSED` (contract specified and validated
   by construction), `HW-VALIDATED` + `STRUCTURAL`.** See §2 for the full
   seam contract (live-ins/outs, resource merging, what a driver must
   guarantee).
3. **Own-compiler correction, disclosed:** an entry-only MSL attribute
   (`[[color(0)]]`) placed on a non-entry helper function's parameter is
   **syntactically accepted, not rejected** — contrary to this
   experiment's own pre-registered H2d expectation of either outright
   rejection or an unsafe silent-garbage outcome — and is **semantically
   INERT**: the parameter simply receives whatever ordinary value the
   caller forwards at the call site (`HW-VALIDATED`, exact). Driver
   consequence unchanged: values must still be explicitly forwarded as
   plain arguments; the attribute does nothing useful on a callee and
   must not be relied upon.
4. **Grammar probe (new, disclosed negative):** MSL syntactically accepts
   an explicit interpolation qualifier on `[[barycentric_coord]]`
   (`center_perspective`/`center_no_perspective`, the same syntax used
   for ordinary varyings) — but it is a **complete no-op**: both
   qualified forms compile to a byte-for-byte identical instruction
   sequence to the unqualified baseline (2 `iter`, 0 `fspecial` — the
   *incomplete*/`Model B` shape). **There is no MSL-level escape hatch**
   a shader author could use to force correct perspective-corrected
   `barycentric_coord` on this toolchain; only the indirect
   `[[position]]`-consumption trigger does.
5. **P0.8 / DRV-ABI-01 — all nine constituent items are now addressed.**
   See §3.

---

## §1 H1 — Barycentric anomaly: discriminating evidence and convention

### 1.1 The discriminating factorial (OFFICIAL, both runs byte-identical)

CONFIG1 geometry (identical to EXP-0117's): triangle
`p={(-0.6,-0.6),(0.6,-0.6),(0.0,0.6)}`, `w={1.0,2.0,4.0}`, sample pixel
`(32.5,32.5)` on a 64×64 `RGBA32Float` target, tags `(10,20,30)`. Observed
`barycentric_coord` (`c0`, first 3 components) for every constructed
variant:

| variant | what changed vs. baseline | `[[position]]` touched? | output count | observed `b` |
|---|---|---|---:|---|
| `base` | — (baseline) | no | 2 | `(0.24348931, 0.13476601, 0.62174469)` |
| `count3_const` | +1 output, compile-time constant | no | 3 | `(0.24348931, 0.13476601, 0.62174469)` — **identical to base** |
| `count3_vary` | +1 output, genuinely new interpolated varying | no | 3 | `(0.24348931, 0.13476601, 0.62174469)` — **identical to base** |
| `attach3ctrl` | `base`'s UNCHANGED shader, pipeline configured with a 3rd, shader-unwritten attachment | no | 2 (shader) / 3 (pipeline) | `(0.24348931, 0.13476601, 0.62174469)` — **identical to base** |
| `pos2` | `[[position]]` read AND emitted as the 2nd (of 2) outputs | yes (output) | 2 | `(0.48697862, 0.26953202, 0.24348938)` — **flips** |
| `posread_noout` | `[[position]]` read and stored to a `device` buffer, never a color output | yes (side-effect only) | 2 | `(0.48697862, 0.26953202, 0.24348938)` — **flips** |
| `pos3` | `[[position]]` read AND emitted as a 3rd output (EXP-0117's exact anomaly recipe) | yes (output) | 3 | `(0.48697862, 0.26953202, 0.24348938)` — **flips** |

`analysis/summary.json`'s `h1.discrimination` block (machine-checked from
the official capture):

```json
{
  "count_alone_triggers": false,
  "any_extra_interpolant_triggers": false,
  "position_output_at_count2_triggers": true,
  "position_readonly_noout_triggers": true,
  "harness_attach3_alone_triggers": false,
  "pos3_matches_pos2": true,
  "pos3_matches_posread_noout": true
}
```

**OBSERVED, HW-VALIDATED, both runs byte-identical.** This directly
answers the dispatch's three competing explanations:

- **(iii) harness artifact — REFUTED.** `attach3ctrl` (the exact `base`
  shader, unchanged, rendered through a pipeline with an extra
  shader-unwritten attachment configured) reads back **byte-identical**
  to `base`. Whatever drives the anomaly, it is not the pipeline
  descriptor's attachment count.
- **(ii, restricted form) "any extra output/interpolant" — REFUTED.**
  `count3_const` (a 3rd output that's a bare compile-time constant, no
  new interpolation at all) and `count3_vary` (a 3rd output that
  genuinely echoes a NEW, correctly `[[stage_in]]`-connected, default-
  perspective interpolated varying) both read back **byte-identical** to
  `base`. Neither output count nor the mere presence of additional
  interpolated data triggers the flip.
- **(ii, refined) "an interpolation-setup allocation effect keyed
  specifically to `[[position]]`" — CONFIRMED.** `pos2` (2 outputs,
  position emitted) and `posread_noout` (2 outputs, position read but
  NEVER emitted — only stored to an ordinary `device` buffer) both flip
  to the **same** value as `pos3`. The trigger is **consuming
  `[[position]]`**, full stop — not whether it becomes an output, not
  output count.
- **(i) "real, content-independent hardware behavior" — not the right
  frame**, per §1.2's structural evidence: this is a **compiled-code**
  difference (different instruction *sequences*, not the same sequence
  producing different results), i.e. a **compiler code-generation
  effect**, not raw silicon nondeterminism.

### 1.2 Structural mechanism — decisive, `OWN-SHADER-DIFF`

`docs/isa/encoding-tables.md`'s `iter` entry already documents Apple9's
perspective-correct interpolation as a **multi-instruction lowering**:
linear/numerator component `iter`s (`mode=0x0`) + a **W-denominator**
`iter` (`mode=0x4`) + an `fspecial` **reciprocal** (byte0 `0xaf`) + a
per-component normalizing multiply. This experiment's own
`harness/struct_extract.m` (generalized to N configurable color
attachments — **not** `tools/shdump/shdump.m`'s `--render` mode, which
hardcodes a single attachment and would have silently produced WRONG
structural bytes for every multi-output variant here, see
`PROGRESS.md`) + `tools/agx-isa/isadb.py` (imported, unmodified)
disassembly of every variant's compiled fragment bytes:

| variant | `iter` count | `iter` modes/slots (raw) | `fspecial` count |
|---|---:|---|---:|
| `base` | 2 | `(dst=0,slot=0,mode=0)`, `(dst=2,slot=2,mode=0)` | 0 |
| `count3_const` | 2 | identical to `base` | 0 |
| `pos2` | 4 | 2 new slots appear (`slot=4`,`slot=6`) | 2 |
| `posread_noout` | 5 | 2 new slots appear | 1 |
| `pos3` | 4 | 2 new slots appear | 1 |
| `count3_vary` | 6 | vtag's own 4-component perspective interpolation (`mode=4` W-denom + 3 more) plus `base`'s own 2 (unchanged) | 1 |

**OBSERVED, both runs byte-identical.** `base`/`count3_const` share the
**identical** 2-instruction `iter` pair and have **zero** `fspecial`
instructions anywhere in the compiled fragment program — `barycentric_coord`
is computed from exactly 2 interpolated numerators with **no reciprocal,
no normalization**. Every position-touching variant (`pos2`,
`posread_noout`, `pos3`) gains **2 new coefficient slots and at least one
`fspecial`** — the missing W-denominator + reciprocal machinery.
`count3_vary`'s 4 EXTRA `iter`s (for `vtag`, a real, independently-
verified, correctly perspective-interpolated `float4` varying — its
readback matches the same `Model C` formula applied to per-vertex tag
values, `8.5651064` observed vs. `8.56511` independently recomputed) are
entirely separate from `barycentric_coord`'s own unchanged 2-`iter`/
0-`fspecial` shape — confirming an ordinary varying gets its OWN correct
perspective machinery regardless of `barycentric_coord`, while
`barycentric_coord`'s own lowering does not request that machinery for
itself.

**INTERPRETED.** This is a genuine **compiler code-generation
gap specific to `barycentric_coord`**: whatever whole-shader analysis
decides "this fragment program needs the W-denominator/reciprocal
machinery" evidently does not count `barycentric_coord`'s own use as
justification on its own, but a `[[position]]` read (which the docs
independently establish lowers through `get_sr` + `iter`, and needs the
same reciprocal-W value Metal exposes as `[[position]].w`) does — and once
that machinery exists for `[[position]]`'s sake, `barycentric_coord`'s
numerators get normalized "for free" by whatever downstream pass reuses
already-computed values. **Grammar exploration (own-compiler, disclosed
negative):** `[[barycentric_coord, center_perspective]]` and
`[[barycentric_coord, center_no_perspective]]` are BOTH syntactically
ACCEPTED (compile cleanly) but compile to a **byte-for-byte, instruction-
sequence-identical** program to the unqualified `base` (2 `iter`, 0
`fspecial` — the *incomplete* shape) — confirming there is **no MSL-level
way to force the correct behavior**; only the indirect `[[position]]`-
consumption side effect does.

### 1.3 Numeric convention — HW-VALIDATED, two independent geometries

Host oracle models (`analysis/decode.py::models()`), CONFIG1 (EXP-0117's
geometry) and an independent CONFIG2 (`p={(-0.5,-0.3),(0.55,-0.2),
(0.0925,0.6975)}`, `w={1.0,3.0,2.5}`, tags `(100,-50,7)`, same fixed
sample texel), assuming `barycentric_coord[i]` corresponds to vertex `i`
in the vertex shader's literal emission order (`vid%3==i`):

| model | formula | CONFIG1 prediction | CONFIG2 prediction |
|---|---|---|---|
| `Model B` (this experiment's mechanism finding) | `b_i = l_i/w_i` for `i=0,1`; `b_2 = 1-b_0-b_1` | `(0.243490, 0.134766, 0.621745)` | `(0.400000, 0.116667, 0.483333)` |
| `Model C` (standard, fully-normalized perspective-correct) | `b_i = (l_i/w_i) / Σ(l_j/w_j)` | `(0.486979, 0.269531, 0.243490)` | `(0.648649, 0.189189, 0.162162)` |

| case | CONFIG1 observed | matches `Model B`? | matches `Model C`? |
|---|---|---|---|
| `base` | `(0.24348931, 0.13476601, 0.62174469)` | **YES**, exact | no |
| `pos3` | `(0.48697862, 0.26953202, 0.24348938)` | no | **YES**, exact |

| case | CONFIG2 observed | matches `Model B`? | matches `Model C`? |
|---|---|---|---|
| `base2` | `(0.40002215, 0.11665846, 0.4833194)` | **YES** (~2e-4 abs, float-interpolation precision) | no |
| `pos3_2` | `(0.64866889, 0.1891713, 0.1621598)` | no | **YES** (~2e-4 abs) |

**OBSERVED, HW-VALIDATED, both runs byte-identical, two independent
triangle/`w`/tag geometries.** Both configurations independently confirm
the SAME model assignment (no-position → `Model B`; position-touching →
`Model C`) under the SAME assumed vertex-order convention — an asymmetric
triangle with 3 numerically distinct `l_i`/`w_i` values matching a
specific ASSUMED order to 3-4 significant figures, twice independently,
is not plausible under a wrong-order coincidence. **Driver consequence /
convention, established:** `barycentric_coord.x/.y/.z` correspond to the
primitive's vertices in **emission (assembly) order**
(`vid%3==0,1,2` — the same convention already independently established
for `primitive_id` in EXP-0117 §5.1, a nice cross-check), and the
**intended/correct** semantics — the ones a compiler backend targeting
AGX directly must always produce — are **perspective-correct**
(`Model C`), matching the standard SPIR-V/Vulkan
`gl_BaryCoord`/`FragmentShaderBarycentric`-class convention. `Model B`
(the MSL-compiler default when `[[position]]` is absent) is **not** a
legitimate alternate hardware mode; it is an incomplete lowering that a
clean-room backend must not reproduce.

---

## §2 H2 — Split prolog/epilog: the linkage contract, given no native split

### 2.1 What Metal's own compiler actually does (both regimes, disclosed)

Region names from `tools/shdump/agxparse.py --json`'s `agx.regions` field,
OFFICIAL capture, both runs byte-identical:

| kernel | call sites | regions | `call` opcodes present? |
|---|---:|---|---|
| `do_blend_epilog` (fragment, `[[clang::noinline]]`) | 1 | `["_agc.main.constant_program", "_agc.main"]` (2) | **no** (INLINED) |
| `fetch_attr` (vertex, `[[clang::noinline]]`) | 1 | `["_agc.main.constant_program", "l__Z10fetch_attrPU9MTLdeviceKDv4_hj", "_agc.main"]` (3) | **yes**, 1 |
| `mk4` (compute, `[[clang::noinline]]`) | 2 | `["_agc.main.constant_program", "l__Z3mk4fffff", "_agc.main"]` (3) | **yes**, 2 |

A supplementary, non-frozen re-check (`work/scratch_debug/
epilog_attr_test.metal`, disclosed in `PROGRESS.md`) confirms the epilog
inlining is **not** an attribute-spelling artifact: switching to the exact
`static float4 __attribute__((noinline))` spelling EXP-0109/EXP-0117 used
successfully elsewhere gives the identical 2-region, 0-`call` result.

**OBSERVED.** This **refines** (does not reverse) EXP-0109 §5.1's "no
third region ever appears" claim: every one of EXP-0109's own 10
spot-checked cases happened to land in the regime Metal's compiler
chooses to inline. Given the right shape (here: a vertex-stage helper
performing a genuine memory load, and a multi-call-site compute helper),
Metal's **own** toolchain DOES emit a real, separately-Mach-O-symbol-named,
out-of-line code object reached by the ordinary CALL/RETURN ABI. **This
project does not attempt to characterize Apple's inlining heuristic**
(explicitly out of scope, `PRE_REGISTRATION.md`) — it is not a hardware
fact and a driver's own backend controls its own out-of-lining
unconditionally regardless of what Apple's compiler happens to choose.

### 2.2 The seam contract a driver must implement

**Numerically validated, both runs byte-identical, real hardware:**

- **Epilog seam** (`epilog_struct`/`epilog_render_mode{0,1}`): the entry
  fragment function reads the tilebuffer via `[[color(0)]]` (the ONLY
  place that attribute is meaningful — see §2.3) and the "shader main"-
  computed source color via an ordinary buffer, then forwards BOTH as
  plain value arguments into a `noinline` callee that performs a
  **branching** blend computation (`mode==0` → `src*sf + dst*df`;
  `mode==1` → `(src*sf) * (dst*df)`) and returns the blended `float4`.
  Both branches match the standard blend-equation arithmetic **exactly**
  (`mode0_add_matches`/`mode1_mul_matches`: true, tolerance well under
  1e-3, both runs).
- **Prolog seam** (`prolog_struct`/`prolog_render`): the entry vertex
  function forwards a `device const uchar4*` buffer pointer and an index
  into a `noinline` callee (`fetch_attr`) performing a
  `UChar4Normalized`-style fetch+normalize (extending EXP-0109 §1.3's
  INLINE fetch-robustness model to a genuinely CALLED fetch function),
  which returns a `float4`. In-range fetches (indices 0-5) are **exact**
  to 4 decimal places; the deliberate out-of-range index (56, against a
  6-element buffer) reads back **exactly zero** — the same
  zero-fill-on-OOB policy EXP-0109/EXP-0076 established for inline
  device loads now confirmed for a call-boundary-crossing fetch.
- **Multi-value crossing** (`callret_struct`/`callret_render`): a
  `noinline` compute callee (`mk4`) taking **5 scalar arguments**
  (generalizing EXP-0035's original 2-argument case) and returning a
  **float4** (generalizing EXP-0035's single-scalar `r10`-only case) is
  called from TWO distinct call sites in the same kernel; every tested
  input (4 threads) produces the exact expected value from BOTH calls
  combined. Structurally: each call site is bracketed by a `frame_marker`
  (`43 00 00 01`) immediately before and a `pop_reconverge` (`0f 06 04 02
  00 00`) immediately after — exactly matching `tools/agx-isa`'s `call`
  descriptor's documented framing — and the caller retrieves the callee's
  float4 result via **4 distinct register-move-class operations**
  post-call (vs. the single move a scalar return needs per EXP-0035),
  scaling with the return's component count. **The exact physical
  register numbering of the multi-component return path is NOT
  independently re-derived here** (the retrieval uses a different
  move-instruction class, `reg_move_c9`/`rtq_state_move`, than the
  argument-setup path's plain `falu2i`/`reg_move_c1` — flagged
  `STRUCTURAL`, open for DRV-ISA-01, not asserted as a specific `r10-r13`
  claim without a dedicated splice). The **argument** side, by contrast,
  is fully confirmed: the 5 arguments land in raw destination registers
  `0xa,0xb,0xc,0xd,0xe` (decimal 10-14) — an exact, direct extension of
  EXP-0035's "consecutive from r10" finding to 5 arguments, using the
  identical raw-value convention EXP-0035's own splice established.
- **Entry-only-attribute forwarding** (`negctrl_struct`/`negctrl_render`):
  `[[color(0)]]` on a non-entry helper parameter compiles (not rejected)
  and is semantically **inert** — the callee's readback exactly equals
  the caller's forwarded clear-color value in every tested case, never a
  re-invoked tile-read or garbage.

### 2.3 The contract, stated for a driver backend (per DRV-ABI-01's "specify, do not implement" scope)

Given there is no native fixed-function prolog/epilog unit and no
guaranteed compiler out-of-lining, a driver implementing a **software**
programmable prolog (attribute fetch, EXP-0031/EXP-0109) and epilog
(programmable blend, EXP-0117) has exactly two legitimate implementation
strategies, and this experiment characterizes both:

1. **IR-level (NIR) concatenation, no real CALL boundary at all** — the
   strategy Apple's own compiler demonstrably prefers when it inlines
   (§2.1's `do_blend_epilog` case, and EXP-0031/EXP-0109/EXP-0117's own
   finding that Metal's compiler NEVER produces a native, separately-
   addressed segment for these roles): the driver's compiler backend
   splices the prolog's and epilog's NIR (or equivalent IR) as an
   ordinary prefix/suffix of the vertex/fragment "main" body BEFORE final
   code generation, so the emitted AGX code is a single flat `_agc.main`-
   shaped object exactly like every case this project has ever observed
   from Metal. Live-in/live-out "crossing" at this seam is then just
   ordinary SSA/register-allocator def-use — no ABI is needed because
   there is no real call. This is the strategy that avoids any of §2.2's
   open questions and matches 100% of Apple's own observed fragment-
   epilog behavior.
2. **A genuine out-of-line object via the CALL/RETURN ABI** — for a
   driver that wants to compile ONE prolog/epilog object and reuse it
   across many "main" variants (the Mesa-M1/M2-style variant-reduction
   motivation DRV-ABI-01 is ultimately in service of), this experiment
   constructs and HW-validates the seam:
   - **Live-ins (prolog→main, main→epilog):** ordinary CALL arguments,
     consecutive GPRs from `r10` (confirmed to at least 5 scalar
     arguments here; EXP-0035 confirmed 2). A driver must lay out its
     prolog/epilog's parameter list to fit the argument-register budget
     it has validated, and spill anything beyond it via the same
     per-thread scratch mechanism EXP-0035 documented for register
     pressure generally (`h_pressure`) — not independently re-tested at
     the call boundary specifically in this experiment (cited, not
     re-derived).
   - **Live-outs:** a scalar return lands in `r10` (EXP-0035); a
     multi-component (vector) return generalizes by using more registers
     one-per-component (confirmed structurally here for a float4 — 4
     post-call retrieval ops vs. 1 for scalar), but the EXACT physical
     numbering of that path is unresolved (flagged, §2.2) — a driver
     backend generating its OWN AGX bytes directly does not need to
     replicate Apple's specific register choice, only to define its OWN
     consistent convention (e.g. literally `r10-r13` per the argument
     convention's own pattern) and honor it symmetrically at both the
     callee's return-value store and the caller's retrieval.
   - **Calls/branches:** the CALL/RETURN ABI (EXP-0035/EXP-0109/EXP-0117)
     — `frame_marker` (`43 00 00 01`) before, `call` (`0f 05 54 1a 8f 00
     54 <off40> 00`, byte+6 uniformly `0x54` per EXP-0117, now confirmed
     again on two more kernel shapes) at the site, `pop_reconverge` (`0f
     06 04 02 00 00`) after, `ret` (`8f <linkmode> 54 <scoreboard>`) at
     the callee's end. Control flow INSIDE a called epilog (this
     experiment's branching `add`-vs-`mul` blend body) works correctly —
     a driver's epilog generator may use ordinary conditional branches
     inside a genuinely out-of-line epilog object, not just straight-line
     code.
   - **Resource merging:** **not a real problem.** Every resource a
     prolog/epilog body touches (device buffers, the tilebuffer via
     `[[color(n)]]`) is resolved by the ENTRY function's own declared
     argument list — a property of the WHOLE pipeline/shader-container
     object (DRV-SHADER-01 territory), not of any individual code
     segment — and is simply FORWARDED into the callee as an ordinary
     value argument (a raw pointer, or an already-tile-read `float4`).
     **A genuinely out-of-line callee cannot and must not attempt to
     declare its own resource/stage-IO bindings**: MSL syntactically
     tolerates writing `[[color(0)]]` on a non-entry parameter but it is
     PROVEN inert (§2.2's negctrl finding) — a driver's own AGX backend
     must therefore treat "which buffer/texture/tile is bound to which
     index" as a single, pipeline-wide table fixed BEFORE generating any
     of prolog/main/epilog, with each piece referencing already-agreed
     slot numbers; no runtime relocation or re-binding happens at the
     CALL boundary itself.
   - **What the driver must GUARANTEE:** (a) the callee is compiled with
     the SAME argument-register layout convention the caller assumes
     (since there is no descriptor negotiating this — it is a pure
     compile-time contract between the driver's own prolog/epilog
     generator and its own main-body generator); (b) any resource the
     callee touches is already resolved to a concrete binding slot in the
     whole pipeline's argument table before the callee is generated —
     there is no notion of a callee "requesting" a resource independently
     of its caller; (c) if the callee's own register pressure exceeds the
     GPR file, it must use the ordinary per-thread scratch spill
     mechanism (EXP-0035), which composes correctly with the CALL
     boundary (not independently re-stress-tested here, but no
     evidence contradicts it and EXP-0035's own `h_pressure` case
     dispatches correctly under exactly this condition for an ordinary,
     non-prolog/epilog-labeled call).

---

## §3 P0.8 / DRV-ABI-01 — all nine items now addressed

Per EXP-0117's own enumeration (RESULTS.md TL;DR, items 1-9):

| # | item | status before EXP-0129 | status after EXP-0129 |
|---|---|---|---|
| 1 | Programmable-blend-epilog spec | CLOSED (EXP-0117) | unchanged, CLOSED |
| 2 | CS sysvals beyond dynamic shared memory | CLOSED BY CITATION (EXP-0092) | unchanged, CLOSED |
| 3 | FS output ordering | CLOSED (EXP-0117) | unchanged, CLOSED |
| 4 | Barycentric VALUE correctness/convention | **PARTIAL**, disclosed anomaly | **CLOSED** (this experiment, §1) |
| 5 | `primitive_id` VALUE correctness | CLOSED (EXP-0117) | unchanged, CLOSED |
| 6 | MSAA centroid-vs-sample | CLOSED (EXP-0117) | unchanged, CLOSED |
| 7 | Full CALL-ABI byte decode | CLOSED (EXP-0117) | unchanged, CLOSED (independently re-confirmed on 2 more kernel shapes, §2.2) |
| 8 | Stencil-value overflow | CLOSED (EXP-0117) | unchanged, CLOSED |
| 9 | Split prolog/epilog register-crossing mechanics | **DEFERRED** | **CLOSED** (this experiment, §2) |

**All nine items are now addressed.** This does not by itself flip
`docs/P0-P1-CLOSURE.md`'s P0.8 row from `OPEN` to `CLOSED` — that row's
six closure rules (per `docs/P0-P1-CLOSURE.md`'s closure rules) require an
orchestrator-level audit across the full evidence set (this experiment
plus EXP-0109/EXP-0117/EXP-0029/EXP-0031/EXP-0035/EXP-0092) and a
`PROVENANCE.md` update, which is the orchestrator's job per
`SUBAGENT_BRIEF.md`, not this experiment's. What this experiment
establishes is: **no named DRV-ABI-01 sub-item remains open or deferred**
as of this capture.

---

## Finite-resource / range rows

| Namespace/resource | Scope | Tested range | Failure mode outside range | Evidence |
|---|---|---|---|---|
| `barycentric_coord` output-count sensitivity | per fragment function | 2 vs. 3 declared color outputs, both with/without position, both with/without an extra genuine varying | n/a (no failure — this IS the discriminated non-effect) | `barystruct_*`/`baryrender_*` (9/9 variants, both runs) |
| `[[position]]`-consumption trigger | per fragment function | consumed-and-output, consumed-and-buffer-stored, both vs. never-consumed | n/a (binary trigger, both positive forms confirmed identical) | `baryrender_pos2`/`posread_noout`/`pos3` (3/3, both runs) |
| CALL-ABI scalar-argument count | per call site | 5 arguments (this experiment) vs. 2 (EXP-0035) | not tested past 5 | `callret_struct`/`callret_render` (both runs) |
| CALL-ABI return width | per call site | float4 (this experiment) vs. scalar (EXP-0035) | not tested past float4 (e.g. a struct return spanning >4 registers) | `callret_struct`/`callret_render` (both runs) |
| Vertex-fetch OOB (call-boundary-crossing) | per fetch | in-range 0-5, OOB index 56 vs. a 6-element buffer | reads exactly zero, no fault (matches EXP-0109's inline model) | `prolog_render` (both runs) |

---

## OBSERVED vs. INTERPRETED (explicit)

**OBSERVED, both runs byte-identical:** every numeric readback table in
§1.1/§1.3/§2.2; every `iter`/`fspecial`/`call`/`frame_marker`/
`pop_reconverge` count and region-name list in §1.2/§2.1/§2.2; the
grammar-probe byte-for-byte instruction-sequence equality (§1.2); the
negctrl value-forwarding equality (§2.2).

**INTERPRETED:** the causal claim that `[[position]]`-consumption
specifically (not count, not "any interpolant") is the mechanism (§1.1,
supported by the full factorial, not merely the two original EXP-0117
cases); the characterization of `Model B` as "incomplete" rather than "an
alternate valid hardware mode" (§1.3, a judgment call grounded in the
structural absence of the normalize step and the standard graphics
convention, not a directly observed hardware fact by itself); the
driver-consequence prescriptions in §2.3 (a synthesis of the observed ABI
facts into an actionable contract, per DRV-ABI-01's own "specify, do not
implement" scope).

**Explicitly NOT established here (flagged, not silently assumed):** the
exact physical register numbering of a multi-component CALL return
(§2.2); WHY Apple's compiler inlines `do_blend_epilog` but not
`fetch_attr`/`mk4` (out of scope, §2.1); whether the CALL boundary
composes correctly under genuine register-pressure/spill conditions
SPECIFICALLY for a prolog/epilog-shaped callee (cited from EXP-0035's
general case, not independently re-stress-tested); per-sample depth/
stencil MSAA suppression under a split epilog (not this experiment's
scope — EXP-0117 §3.3 already flagged the general case `PARTIAL`).

---

## Clean-room provenance

```text
Clean-room provenance: OWN-SHADER (kernels/*.metal, all authored here;
  structural extraction via this experiment's own harness/struct_extract.m,
  harness/struct_extract_vonly.m, and the unmodified tools/shdump/shdump.m
  + tools/shdump/agxparse.py, rebuilt fresh from committed source;
  disassembly via tools/agx-isa/isadb.py's published disassemble() API,
  imported unmodified through this experiment's own analysis/isahelper.py)
  + HW-PROBE (harness/render.m, harness/compute_callret.m: real draws/
  dispatches, no splicing) + PUBLIC (MSL grammar accepted/rejected by the
  public newLibraryWithSource: API for OUR OWN source; public Metal API
  types only).
Inputs inspected: kernels/{bary.metal,bary_qual_persp.metal,
  bary_qual_noperspective.metal,split_negctrl.metal,split_epilog.metal,
  split_prolog.metal,split_callret.metal} (all authored here);
  docs/isa/encoding-tables.md and docs/isa/README.md (this project's own
  prior clean-room documentation, PUBLIC-internal, cited for the `iter`/
  `call`/`ret`/`frame_marker` semantics, not re-derived from any Apple
  binary); EXP-0109/EXP-0117/EXP-0035/EXP-0031/EXP-0097/EXP-0111
  RESULTS.md (this project's own prior experiments, cited per CODEX §8).
Apple binary introspection: NONE. No disassembler, decompiler, or binary-
  inspection tool was run on any Apple framework, dylib, kext, firmware,
  or compiler binary. tools/agx-isa/ and tools/shdump/ were used
  read-only and unmodified throughout (imported/invoked via their
  published APIs, never edited).
Reproduction: python3 run.py --run <id> --out raw/<id> (×2); python3
  verify.py --crossrun raw/m4-20260828-run01 raw/m4-20260828-run02;
  python3 analysis/decode.py raw/m4-20260828-run01; python3 verify.py
  --selftest; python3 verify.py --seqtest; python3 verify.py --smoke.
Evidence: raw/m4-20260828-run01/, raw/m4-20260828-run02/ (00_inputs.json,
  01_cases.json, 04_results.jsonl, 05_run_manifest.json each),
  analysis/summary.json, harness/fixtures/recorded_reality.json,
  CAPTURE_CONTRACT.json (authored sha256 set, state RUN02_PRESENT).
```

## Files

- `PRE_REGISTRATION.md`, `CAPTURE_CONTRACT.json`, `PROGRESS.md` — frozen
  contract and milestone log (2 disclosed pilot bugs, 2 disclosed
  structural discoveries).
- `casematrix.py` — the 29-case frozen matrix (single source of truth for
  `run.py` and `verify.py`).
- `kernels/bary.metal` — the H1 factorial (9 variants sharing 2
  geometries); `kernels/bary_qual_{persp,noperspective}.metal` — the
  grammar probe.
- `kernels/split_negctrl.metal`, `kernels/split_epilog.metal`,
  `kernels/split_prolog.metal`, `kernels/split_callret.metal` — the H2
  constructions.
- `harness/struct_extract.m` (generalized to N attachments, fixing a real
  `shdump.m --render` single-attachment limitation for this experiment's
  multi-output shapes), `harness/struct_extract_vonly.m` (rasterization-
  disabled vertex-only pipelines), `harness/render.m`,
  `harness/compute_callret.m` — authored probes.
- `analysis/isahelper.py` — shared disassembly-summary wrapper around
  `tools/agx-isa/isadb.py` (imported, unmodified).
- `run.py`, `verify.py` — capture driver + standing-gate verifier.
- `raw/m4-20260828-run01/`, `raw/m4-20260828-run02/` — the two official
  captures.
- `analysis/decode.py`, `analysis/summary.json` — post-capture arithmetic
  (host-oracle models, blend/fetch/callret formula checks), no new GPU
  calls.
- `harness/fixtures/recorded_reality.json` — real-GPU-call-derived
  selftest fixture.

## STOPs

No `BLOCKED` state was entered; no host wedge, reboot, or `macvdmtool` use
occurred. Two pilot bugs and two structural discoveries were disclosed
above and in `PROGRESS.md`, not silently fixed/smoothed over. No excursion
outside `/Users/user/asahi_re/public/agx-re` occurred at any point in this
experiment.
