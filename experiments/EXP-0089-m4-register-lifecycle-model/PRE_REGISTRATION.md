# PRE_REGISTRATION — EXP-0089 M4 register-lifecycle model (successor to EXP-0086)

Filed BEFORE any splice/GPU capture. Host-side pilot OWN-SHADER compiles (no
splicing, no GPU dispatch) were used to locate the two NEW literal-bit-17
candidate families and the discrim3 kernel and to freeze the anchors below —
the standard "characterize the compiler's own output" step that precedes
every splice experiment in this repo (EXP-0036/EXP-0038/RT-1a/EXP-0086).

## 0. Why this experiment exists

This is a **successor** to `experiments/EXP-0086-m4-register-liveness-bits`,
dispatched to close five open items from that experiment's `RESULTS.md` and
`docs/isa/register-move-and-liveness.md`:

1. **Complete the formal two-run gate.** EXP-0086's `run02` died at 113/135
   from a host interruption and is quarantined, untouched, under
   `EXP-0086.../QUARANTINE-run02-attempt1.md`. Its finding (CAND_B corrupts a
   later read) rests on `run01` alone. This experiment re-runs the SAME
   frozen case DESIGN (CAND_A/CAND_B/positive-control on the 7 original
   kernels are carried over verbatim) to a clean, closed, two-run gate under
   a NEW experiment number, NEW run ids, and a fresh contract — EXP-0086's
   files are not touched, reused, or repaired in place.
2. **The literal bit 17.** EXP-0086 could not test the actual `0x54`/`0x56`
   field: in every family it could compile into (`falu2i`/`falu2`/
   `falu_srcmod12b`), splicing proved bit 17 is part of the **opcode**
   (`opsel`), not a free bit. This experiment locates TWO independent
   families where db.json's own `match` table proves bit 17 is genuinely
   free, and runs the missing later-read test on the LITERAL bit in both.
3. **Sweep CAND_B** (the bit EXP-0086 found corrupts) across the distance/
   pressure/control-flow conditions it was only tested under for CAND_A.
4. **Characterize `ctrl`/`ctrl_lo`** (EXP-0086's presumed-inert control field,
   which turned out to fault 4/7 kernels and silently corrupt 3/7): which
   VALUES fault, which corrupt, which are safe.
5. **A producer/consumer discriminating case**: does the mechanism behave
   like a last-use/discard hint, a register-cache residency flag, or
   something else — via a THIRD, even-later reader.

## 1. What is carried over verbatim vs. new

**Carried over verbatim** (byte-identical; re-verified by a fresh compile on
THIS session's toolchain before reuse, see `analysis`/`baseline.py`'s
frozen-anchor check, 0 diffs across all 7 kernels' `c1`/`c2` anchors):

- `kernels/{adjacent,near,far4,far16,pressure,if_boundary,loop_boundary}.metal`
  — identical file content to `EXP-0086-m4-register-liveness-bits/kernels/*`.
- `casematrix.ANCHORS` (offsets/mnemonics/hex) for those 7 kernels, and
  `casematrix.INPUTS`/`OUT_N`/`EXPECTED` (the independent host-side float32
  oracle), and `casematrix.INERT_FIELD`.
- The CAND_A case design (`candA_flip_c1/c2/both`: top-bit of the
  `falu2i`/`falu2`/`falu_srcmod12b` 7-bit register-select field) and the
  `positive_control_c2` detection-capability design (redirect c2's operand
  register, low6+1).
- The `_decode`/`_splice_field`/round-trip-assert splice machinery, and the
  overall standing-gate architecture (selftest/seqtest/preflight/
  between-runs/captured, GATED-vs-NONGATED record split, append-only raw,
  smoke gate, single-threaded harness) — same design as EXP-0086, adapted to
  this experiment's file names/paths/case matrix.

**New in this experiment**:

- CAND_B (`opflags` bit0) cases (`candB_flip_c1/c2/both`), extended from
  EXP-0086's "adjacent kernel only" scope to ALL 7 original kernels (item 3).
- A `ctrl`/`ctrl_lo` VALUE SWEEP: 8 bit-pattern masks
  (`0x01,0x02,0x04,0x08,0x10,0x20,0x40,0x7f`) applied via XOR against the
  kernel's actual natural value, on BOTH `c1` and `c2`, for all 7 original
  kernels (item 4; EXP-0086 only ever flipped bit0 on `c1`).
- Two new kernels, `lit17_unpack.metal` and `lit17_cvt.metal`, each a
  genuinely independent literal-bit-17 test family (item 2, detailed in §2).
- A new kernel, `discrim3.metal`, a 3-reader extension of `adjacent`
  (`x1=v+10, x2=v+20, x3=v+30`), used as the producer/consumer discriminating
  case (item 5, detailed in §5).
- `_splice_raw` (a new, minimal raw-byte splice primitive alongside the
  existing field-based `_splice_field`), needed because `lit17_unpack`'s
  presumed source-register byte is embedded in db.json's opaque 32-bit
  `convert_desc` raw field with no independently named sub-field to target.

## 2. Literal bit 17: two new candidate families

Instruction bit 17 = byte+2 bit 1 = the literal bit named in
`docs/isa/README.md:770` (`0x54<->0x56`). The dispatch's candidate list
(`0xbf/0x3f/0xb7` reduce family, `0x17 unpack_convert`, the `0x37`
derivative/quad-reduce split, `ret` `8f .. 54/56`, `if_push_pred`,
`cvt_i2f/f2i/u2f`, the compact `falu_acc 0x18/0x38` pair) was checked against
`tools/agx-isa/db.json`'s own `match` tables (read-only; the tables encode
which bits are opcode-fixed vs. free — this is analysis of our OWN db.json,
not Apple code):

- **`falu_acc`**: its `match` fixes bits 17-20 to `0b1100` — bit 17 is
  opcode-determining here too (this is a NEW finding: EXP-0086 never checked
  `falu_acc` structurally, only reported it could not compile a
  shared-read-twice case into this form). `falu_acc`'s own `cache` field is
  bit 21, not bit 17. Confirms this family cannot test the literal bit either
  way — recorded, not pursued further.
- **`ret`/`ret_luse`**: byte+2 (`0x54`/`0x56`) is entirely inside `match` —
  it is the field that SELECTS which of the two mnemonics an instruction IS,
  not a free bit within one instruction. Not testable this way.
- **`if_push_pred`**: byte+2 (`scope`) is free of `match`, but semantically
  encodes control-flow nesting, not a source-register read; no natural
  "shared source read twice" shape. Not pursued (recorded as untested).
- **`unpack_convert`** (byte0 `0x17`): `match = [[0,8,23],[8,4,4],[16,1,0],
  [18,6,21]]` — bit 16 and bits 18-23 of byte+2 are FIXED by match; only bit
  17 is free. The `cache` field can therefore ONLY ever be `0x54` or `0x56`
  — this is, structurally, the single free bit the original claim describes,
  on the nose.
- **`cvt_i2f`** (byte0 `0xa7`, byte+1 `0x07`): `match = [[0,8,167],[8,8,7]]`
  — byte+2 (`mode`) is entirely free of any match constraint (a full 8-bit
  field), so a bit-17-only flip (`XOR 0x02`) leaves every other bit exactly
  as the compiler emitted it.

**Pilot compiles** (this session's toolchain; OWN-SHADER, no splice, no GPU):
a single MSL expression evaluated twice (`unpack_unorm2x16_to_float(p)` twice,
or `float(v)` twice) gets common-subexpression-eliminated into ONE
instruction (confirmed by pilot decode) — the same CSE behavior EXP-0086
diagnosed for `falu_acc`. Using two DIFFERENT MSL builtins/casts on the SAME
source value (`unpack_unorm2x16_to_float(p)` + `unpack_snorm2x16_to_float(p)`;
`float(v)` + `float((uint)v)`) defeats CSE while still reading the identical
physical source register, confirmed by decode:

```
lit17_unpack (kernels/lit17_unpack.metal), _agc.main:
  +0x12 unpack_convert 1704560401000eaa   cache=0x56 (bit17=1)  <- c1 (unorm, first)
  +0x1a unpack_convert 1704540001001cca   cache=0x54 (bit17=0)  <- c2 (snorm, second)
  byte+4 of BOTH instructions = 0x01 (presumed shared source-register byte,
  located by pilot byte-diff: matches the preceding device_load's dst_lo=1)

lit17_cvt (kernels/lit17_cvt.metal), _agc.main:
  +0x12 cvt_i2f a707560003048e60          mode=0x56 (bit17=1), src=4  <- c1 (signed, first)
  +0x1a cvt_i2f a70754020304ac20          mode=0x54 (bit17=0), src=4  <- c2 (unsigned, second)
```

Both families reproduce the doc's claimed NATURAL polarity exactly: the
FIRST/earlier-scheduled reader is `0x56` (bit17=1), the SECOND/later reader
is `0x54` (bit17=0) — matching EXP-0086's CAND_A/CAND_B "earlier=fresh(1),
later=reuse(0)"-style convention, now on the literal named field, in two
independent instruction families, with an independently-computable oracle
(unorm/snorm formulas and int/uint-to-float are public MSL Shading Language
spec behavior — PUBLIC source, not learned from any Apple binary; see
`casematrix.expected_lit17_unpack`/`expected_lit17_cvt` docstrings).

**Pilot dry-run observation (informal, PRE-registration only, NOT part of the
gated evidence — the gated capture below is what this experiment promotes)**:
flipping `c1`'s literal bit 17 (`0x56->0x54`, i.e. the FIRST reader wrongly
claims "reuse a cached predecessor" when none exists) on a real M4 dispatch
changed `lit17_unpack`'s output from `(0.500008, 6.00003)` to `(0, 5)` and
`lit17_cvt`'s from `(1244, 1254)` to `(10, 20)` — i.e. **both** the flipped
instruction's OWN result and the separate LATER instruction's result read as
if their shared source were zero. Flipping ONLY `c2`'s bit (natural
`0x54`->forced `0x56`, "treat as fresh" when it already reads correctly) was
a no-op in both families. This pilot observation is what the frozen case
matrix below (`lit17_flip_c1/c2/both`) re-tests under the full gated
protocol (3 in-run repeats, two independent runs, positive control).

**Positive controls**: `lit17_cvt` has a named `src` field (redirect it,
`XOR 0x1`, field-based). `lit17_unpack` has no named source-register field —
its positive control is a `_splice_raw` byte flip at the located byte+4
(`+1`, wrapped mod 256) — the detection-capability proof for this specific
kernel therefore ALSO tests our byte-diff-located "byte+4 = source register"
hypothesis: if the redirect does NOT change the output, that hypothesis, not
just the detection method, is in question, and RESULTS.md will say so.

## 3. CAND_B sweep

Unchanged case shapes from EXP-0086 (`candB_flip_c1/c2/both`, flipping
`opflags` bit0 on the falu-family instruction identified as `c1`/`c2`),
applied to ALL 7 original kernels instead of only `adjacent`. `adjacent`'s
own re-run (byte-identical case design) doubles as the direct EXP-0086
reproduction/independent-process check this dispatch also asks for.

## 4. `ctrl`/`ctrl_lo` value sweep

For each of the 7 original kernels, the same `INERT_FIELD` used by EXP-0086
(`ctrl_lo` on `falu2i`, `ctrl` on `falu2`/`falu_srcmod12b`) is swept through 8
values (`natural XOR mask`, `mask` in `{0x01,0x02,0x04,0x08,0x10,0x20,0x40,
0x7f}` — the 7 individual bit positions of the 7-bit field plus the all-ones
boundary) on BOTH `c1` and `c2` independently (EXP-0086 only ever touched
`c1`, and only bit0). One value change per case (still change-one-variable);
`0x7f` is the one case that changes all 7 bits simultaneously as the explicit
boundary/worst-case probe. This directly answers "which values fault, which
corrupt, which are safe" (dispatch item 4) and, as a side effect, gives a
producer-side-vs-consumer-side comparison for this field too.

## 5. Producer/consumer discriminating case: `discrim3`

`kernels/discrim3.metal`: `v=a[0]; x1=v+10; x2=v+20; x3=v+30;` — THREE
separate later readers of the same `v`, instead of EXP-0086's two. Pilot
decode (this session, OWN-SHADER, no GPU) found the compiler's natural
`opflags`-bit0 (CAND_B) pattern is **`x1=0, x2=0, x3=1`** — NOT the simple
alternating `0,1` EXP-0086 saw with only two readers. This is reported
honestly as a genuine, non-simplified scheduling difference (see
`casematrix.make_discrim_cases` docstring), not smoothed over: it means the
"natural" corrupting pair by CAND_B's own convention is actually `(x2,x3)`
(x2=0="fresh", x3=1="reuse", exactly EXP-0086's `adjacent` shape), with `x1`
available as a bonus third data point (scheduled BEFORE the flipped
instruction in both `flip_x1`/`flip_x2` cases).

Cases: `discrim_flip_x1`, `discrim_flip_x2`, `discrim_flip_x3` (each flips
ONE reader's own bit in isolation — `flip_x3`, the last reader's own bit
alone, is a predicted-null adversarial control per EXP-0086's "consumer's own
bit is irrelevant" finding), `discrim_flip_x1_x2` (both `x1` and `x2`
flipped, `x3` untouched).

**What this discriminates.** The dispatch asks for (a) last-use/discard hint
the hardware acts on, (b) a register-cache residency flag, or (c) something
else. `discrim3` gives three independent readings per splice, letting the
data speak to two separable questions the two-reader `adjacent` kernel
cannot separate:

- **Causality/directionality**: does corruption ever reach a reader
  SCHEDULED BEFORE the flipped instruction? (Any such result would be
  physically remarkable and flagged as such, not just fit into a model.)
- **Persistence vs. one-shot**: when `x2` (playing `adjacent`'s "c1"/producer
  role toward `x3`) is flipped, is ONLY `x3` (the immediate next differently-
  marked reader) corrupted, or does the corruption look like it would persist
  to still-later readers too (as a "producer skipped writing the value back
  to the register file" model predicts) vs. a one-shot forwarding-path glitch
  local to the immediately following consumer (as a bypass-cache model
  predicts) — `x1`, `x2`'s BEFORE-executed sibling, additionally lets us
  check whether a "sibling" read that shares the SAME natural CAND_B value as
  the flipped instruction (both naturally 0) is at any risk, which
  the two-reader design could never separate from "later distinct-natural-
  value reader."

H(a) last-use/discard: predicts `x2`-flip corrupts `x3` (later, differently-
marked reader) but leaves `x1` (earlier) untouched, REGARDLESS of what `x1`'s
own natural marking is.
H(b) residency/bypass-cache: predicts the same directional signature as (a)
for THIS specific kernel (a bypass-cache model does not obviously predict a
different outcome from a discard-hint model on a single flip in a
single-thread, no-reuse kernel — the dispatch's own framing already
anticipates this experiment may not cleanly separate (a) from (b), and
RESULTS.md will say so rather than force a false distinction) but is
falsified by any observation where `x1` (temporally BEFORE the flip) is
affected, or where flipping `x2` leaves `x3` correct while leaving some OTHER
signature (e.g. a fault) instead of the same "reads zero" pattern EXP-0086
established, which would instead point to (c).

## 6. Falsifiable hypotheses (per item)

- **H1 (EXP-0086's finding replicates)**: `candB_flip_c1`/`candB_flip_both`
  on `adjacent` reproduce EXP-0086's exact result (`x2: 27.5 -> 20`,
  deterministic, no fault) in BOTH new runs. Refuter: any deviation
  (different value, fault, or non-determinism) on `adjacent` specifically.
- **H2 (literal bit 17 is NOT a free scheduling hint, matching CAND_B's
  general risk)**: `lit17_flip_c1` on `lit17_unpack` AND `lit17_cvt` BOTH
  reproducibly corrupt (their pilot-observed `(0,5)`/`(10,20)` outputs, or a
  clearly analogous "reads-as-zero-source" pattern), while `lit17_flip_c2`
  alone is null in both. Refuter: either family's `lit17_flip_c1` case
  matches the UNSPLICED baseline (i.e. the flip turns out to be truly inert
  for that family) — a genuinely possible outcome this pre-registration does
  NOT assume away, since the two families test structurally different
  instructions (a format-unpack vs. an int/float convert) and could behave
  differently.
- **H3 (CAND_B corruption is condition-independent, i.e. "universal" within
  this bit's scope)**: `candB_flip_c1`/`candB_flip_both` on ALL 7 original
  kernels show the SAME qualitative corruption (a later target-index
  mismatch, no fault) as `adjacent`. Refuter: any kernel where
  `candB_flip_c1` is null (matches baseline) or produces a FAULT instead of a
  silent mismatch — either would show the effect IS condition-dependent,
  which is reported as a first-class, not a disappointing, result.
- **H4 (`ctrl`/`ctrl_lo` has a mixed, bit-position-dependent effect map, not
  a single "the field is dangerous" story)**: the 8-mask sweep across 7
  kernels x {c1,c2} produces a heterogeneous mix of `FAULT`/`MISMATCH`/`safe`
  outcomes (not all-fault, not all-safe, not all-mismatch) that RESULTS.md
  will tabulate exactly, without asserting a bit-by-bit semantic map beyond
  what 3x-repeated, 2-run-confirmed data supports.
- **H5 (discrim3 causality)**: no case ever shows corruption reaching a
  reader scheduled BEFORE the flipped instruction. Refuter: `discrim_flip_x2`
  or `discrim_flip_x1_x2` showing `x1` (scheduled first) mismatched.

**Detection-capability proof (required for every corrupting-or-null claim)**:
`positive_control_c2` (7 original kernels + 2 lit17 kernels, one case each)
deliberately redirects the read to a WRONG register/byte and is REQUIRED to
show `MISMATCH_EXPECTED` for that kernel's other results (CAND_A/CAND_B/
ctrl-sweep/LIT17 nulls) to be interpretable as genuine negatives rather than
"the harness couldn't have detected a change here." A `positive_control_c2`
that unexpectedly matches baseline downgrades every null result for that
kernel to `UNKNOWN`, not `PASS` — stated explicitly in RESULTS.md if it
occurs.

## 7. Independent / controlled variables

- **Independent**: (a) which item/candidate (CAND_A/CAND_B/LIT17/CTRL_SWEEP/
  DISCRIM); (b) which site is spliced (`c1`/`c2`/`both`, or `x1`/`x2`/`x3`/
  `x1_x2` for discrim3); (c) kernel (distance/pressure/control-flow condition
  for the 7 original kernels; family identity for the 2 lit17 kernels);
  (d) for `ctrl`/`ctrl_lo`, the 8-value mask.
- **Controlled**: identical splice mechanism (`tools/agx-isa` decode/
  assemble round-trip, or the new `_splice_raw` same-length byte patch —
  field/byte WIDTH never changes, only its value); identical toolchain/
  target (M4/G16G, this host); identical `--no-fast-math` compile flag;
  identical grid=1/tg=1 single-thread dispatch; fixed, distinct,
  non-degenerate input values per kernel (`casematrix.INPUTS`) so a corrupted
  read cannot coincidentally equal the correct value.
- **Paired controls**: `positive_control_c2` (all 9 c1/c2-shaped kernels,
  detection-capability proof, §6).

## 8. Determinism / intermittency protocol

Every case template is executed `REPEAT_N=3` times, each repeat its own
fresh process (fresh `agxtest.py` invocation, fresh Metal library load, fresh
command buffer). A case is **deterministic** if all 3 repeats within a run
return the identical `verdict`. Both runs (`m4-lifecycle-20260828-run01`,
`m4-lifecycle-20260828-run02`) execute the FULL identical case matrix a
second time end to end, and `verify.py`'s cross-run gate requires the GATED
result file (`04_results.jsonl`, which excludes all timing) to be
byte-identical between the two runs. Total case count: `python3 -B
casematrix.py` reports **549** cases per run (183 templates x REPEAT_N=3):
168 from the 7 original kernels (24 templates each: 1 baseline + 3 CAND_A +
3 CAND_B + 1 positive_control_c2 + 16 ctrl_sweep), 10 from the 2 lit17
kernels (5 templates each), 5 from `discrim3` (5 templates: baseline + 3
single-flip + 1 double-flip) — see `casematrix.full_case_list()`, the
executable copy of this table.

## 9. Environment (frozen)

- Git revision at filing: `1e0c481a96eb595b5b1f41b19d07a911a43c75a2` (working
  tree dirty — pre-existing unrelated untracked files from other in-flight
  experiments per `git status`, none touched by this experiment; also note
  per `../SUBAGENT_BRIEF.md`, this revision is PINNED for reference only —
  the run02 gate does NOT require live `HEAD` to still equal this value,
  only that the AUTHORED SOURCE HASHES recorded in run01 and run02 match;
  the orchestrator may commit other experiments' work between the two runs).
- Host: this machine (Apple M4, G16G, 10 GPU cores) — the sole test target
  per `CLAUDE.md`/`CODEX.md`; A18 Pro is hands-off, no claim here is promoted
  to G17P without a recorded validation or `INFERRED` label.
- macOS: 26.6.2 (build 25G82). `xcrun version 72`. Captured verbatim into
  `00_inputs.json` for both runs.
- Python: 3.14.6 (host analysis/harness scripts only; no Metal shader
  toolchain dependency — compilation is `newLibraryWithSource:` at runtime
  via `tools/shdump/shdump.m`, no `metal` CLI).
- Toolchain for the splice/assemble step: `tools/agx-isa/isadb.py`
  (unmodified, read-only) — `decode_one`/`assemble` round-trip asserted on
  every anchor at case-generation time (`casematrix._decode`).

## 10. Raw-tree schema (frozen; `run.py`/`verify.py` are the executable copy)

Identical schema to EXP-0086: `raw/<run-id>/{00_inputs.json,01_cases.json,
02_build.json,03_dispatch.json,04_results.jsonl,04_results_raw.jsonl,
05_run_manifest.json}`. `04_results.jsonl` is the GATED, cross-run
byte-compared record and contains **no** timing/duration/pid/address field.
`04_results_raw.jsonl` is the append-only, NON-gated per-repeat record
carrying timing, never byte-compared across runs. `verify.py --selftest`
proves this distinction AND (new in this experiment) that live
`git_revision` divergence between runs does NOT break the cross-run gate
(only authored-hash equality is contracted). `verify.py --seqtest` proves the
contracted gate ORDER (PRE_GPU -> RUN01_PRESENT -> RUN02_PRESENT) is walkable
end to end. Both are required (and re-run) immediately before every capture.

## 11. Timeouts

`env_command`=10s, `host_build`=60s, `baseline`(host compile+tokenize, 10
kernels)=180s, `case_process`=60s (per `agxtest.py` invocation), `smoke_process`=60s.

## 12. Known confounders

- Compiler scheduling is **not** source order (established by EXP-0086,
  re-confirmed here for `discrim3`'s non-alternating opflags pattern) — every
  anchor below is a FROZEN byte offset from the actual compiled output,
  verified fresh by `baseline.py` before every capture.
- `lit17_cvt`'s test input (`1234`, positive) makes the signed/unsigned
  reinterpretation numerically identical — this experiment does not exercise
  sign-extension behavior, only the literal-bit-17 splice on two separate
  same-source-register converts (explicitly scoped in
  `casematrix.expected_lit17_cvt`'s docstring).
- `lit17_unpack`'s presumed "byte+4 = source register" role is LOCATED by
  pilot byte-diff (both `c1`/`c2` share byte+4=`0x01`, matching the load's
  destination register), not by an independently named db.json field; its
  positive control is designed to ALSO validate this hypothesis, not just
  detection capability (see §2).
- A splice that faults the whole command buffer (`CMDBUF_ERROR`/`HANG`)
  produces NO output for that case — `run.py` records this as `verdict=FAULT`,
  distinct from `MISMATCH_EXPECTED`; both are evidence, neither is dropped.
- `falu_srcmod12b` (loop_boundary's `c1`) has an undecoded 48-bit
  `ext_srcmod` tail; only named fields (`srcA_reg`, `ctrl`, `opflags`) are
  ever touched via `isadb.assemble`, never the raw tail (carried over from
  EXP-0086, unchanged).

## 13. Clean-room provenance (this filing)

```text
Clean-room provenance: OWN-SHADER
Inputs inspected: our own kernels/*.metal (7 carried over verbatim from
  EXP-0086, 3 new), compiled via tools/shdump (newLibraryWithSource:),
  decoded with tools/agx-isa (read-only). unorm/snorm/int-float conversion
  formulas are PUBLIC MSL Shading Language spec behavior (documented public
  Metal builtin semantics), independently re-implemented in Python, not
  learned from any Apple binary. No Apple binary, archive, BO, or
  command-stream inspection.
Apple binary introspection: NONE
Reproduction: python3 -B baseline.py --bin-dir <bindir> --out <report.json>
  (host-only, no GPU); python3 -B casematrix.py (case matrix summary, 549
  cases/run)
Evidence: casematrix.py::ANCHORS/DISCRIM_ANCHORS (frozen anchors), this file
  (hypotheses)
```
