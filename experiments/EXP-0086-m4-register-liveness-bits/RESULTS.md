# RESULTS — EXP-0086 M4 register-liveness / "cache" bit falsification

## Evidence status (read this first)

**Primary, promoted evidence: `raw/m4-20260828-run01`** — complete (135/135
cases), closed, and passed every pre-registered static/dynamic gate
(`verify.py --selftest` 16/16, `--seqtest` 14/14, `--between-runs` PASS,
confirmed live immediately after capture and logged in `PROGRESS.md`).

**The second contracted run (`m4-20260828-run02`) is INCOMPLETE** (113/135
cases; killed by a terminal-emulator problem on the user's side, unrelated to
the experiment). It is retained, untouched, append-only, and does **not**
formally close this experiment's `--captured` (two-run) gate — see
`QUARANTINE-run02-attempt1.md`. The 113 completed lines are **byte-identical**
to the corresponding first 113 lines of `run01` (0 diffs, direct comparison)
— informal, non-gated, but real independent-process confirmation of every
finding below that falls in that range (which includes every decisive CAND_A
and CAND_B case for every kernel; case ordering is `adjacent` first, so the
single-kernel CAND_B result was independently re-executed and matched).

All findings below are **HW-VALIDATED** (splice-and-observe on real M4
hardware, `run01`, 3 fresh-process repeats per case, 0/45 case-groups
intermittent) unless stated otherwise. Target: **M4/G16G only**; not
promoted to G17P without a recorded validation (per `CLAUDE.md`).

## Verdict on `docs/isa/README.md:770`

> **REFUTED as a general claim; REFINED into a narrower, correctly-scoped
> statement.** The claim's own evidence gap, exactly as the dispatch
> described, is real: `RT-1a-FIX` never tested a later, separate
> instruction's read, so it never could have detected a liveness bug. We
> built that missing test. Result: **at least one bit in the exact same
> conceptual position/role, in the exact same instruction family (float ALU,
> byte0 low-nibble `9`) that is home to the literal `0x54`/`0x56`-bearing
> instructions, DOES corrupt a later, separate instruction's read when
> flipped on the producer/earlier-reading instruction** — deterministically,
> reproducibly (3/3 in-run repeats, plus an independent second process launch
> in the partial run02), with **no fault, no hang, silently wrong data**.
> This is precisely the failure signature the external compiler engineer
> described, and precisely what `RT-1a-FIX`'s same-instruction self-check was
> structurally incapable of catching. The blanket phrase "NOT an op change"
> (i.e. "safe to treat as inert") is therefore **unsafe as a general
> principle** and must not be assumed for other same-family fields without a
> later-read test of their own.
>
> We could **not** directly re-test the *literal* bit named in the claim
> (instruction bit 17 / byte+2 bit 1) on a shared-read-twice scenario: in
> every instruction family we could get the compiler to naturally emit for
> this test (`falu2i`/`falu2`/`falu_srcmod12b`), bit 17 is **proven** (by
> direct splice) to be part of the **opcode** `opsel` field — flipping it
> changes `fadd`→`fmul`/`fma`, not a cache hint at all. The bit we found to
> be load-bearing (`opflags` bit 0, instruction bit 20) sits two bits away
> from the literal claimed bit, in the same tail-modifier region, in the same
> instruction family. **The literal `0x54`/`0x56` field itself, and its
> siblings in `simd_reduce`/`fspecial`/`cvt_*`/`ret`/`unpack_convert`/
> `if_push_pred`, remain UNTESTED by a later-read probe and must be
> downgraded from their current "confirmed inert" framing to UNKNOWN pending
> exactly this kind of test**, rather than left as stated. See §"Exact doc
> correction" below for the precise proposed wording.

## Decisive cases, verbatim

Kernel `adjacent` (`kernels/adjacent.metal`): `float v=a[0]; float x1=v+10.0f;
float x2=v+20.0f;` — compiled to `_agc.main` bytes with `v` in the register
whose low-6-bit selector is `1`; `x1` = `falu2i` at `_agc.main+0x12`
(`09e5048380c0`), `x2` = `falu2i` at `_agc.main+0x18` (`19f514038000`).
Input `a[0]=7.5`. Independent oracle: `x1=17.5, x2=27.5`.

| case | splice (main-relative) | `out[0],out[1]` (all 3 reps identical) | verdict |
|---|---|---|---|
| `baseline` (no splice) | — | `17.5, 27.5` | MATCH_EXPECTED |
| `candA_flip_c1` (top-bit of x1's srcA-reg field, `0x41→0x01`) | `@21=03` | `17.5, 27.5` | MATCH_EXPECTED |
| `candA_flip_c2` (top-bit of x2's srcA-reg field, `0x01→0x41`) | `@27=83` | `17.5, 27.5` | MATCH_EXPECTED |
| `candA_flip_both` | `@21=03,@27=83` | `17.5, 27.5` | MATCH_EXPECTED |
| **`candB_flip_c1`** (opflags bit0 on **x1**, `0x0→0x1`) | `@20=14` | **`17.5, 20`** | **MISMATCH_EXPECTED** |
| `candB_flip_c2` (opflags bit0 on **x2**, `0x1→0x0`) | `@26=04` | `17.5, 27.5` | MATCH_EXPECTED |
| **`candB_flip_both`** | `@20=14,@26=04` | **`17.5, 20`** | **MISMATCH_EXPECTED** |
| `inert_control_c1` (ctrl_lo bit0 on x1) | `@22=81` | fault | FAULT (`CMDBUF_ERROR`) |
| `positive_control_c2` (wrong register on x2) | `@27=05` | `17.5, 20` | MISMATCH_EXPECTED (detection proof) |

`x2`'s expected value is `27.5` (`v+20.0`); corrupted it reads `20` — i.e.
`x2` computed `0+20`, as if it read **zero instead of `v`**. This is not a
crash, not an obviously-garbage bit pattern, not a NaN: it is a plausible,
silently-wrong float that a real compiler's correctness test could easily
miss. Note `candB_flip_c1`'s wrong value (`20`) is numerically identical to
`positive_control_c2`'s (which deliberately redirected `x2`'s source register
to a different, effectively-zero register) — consistent with: `x1`'s `opflags`
bit is (at least partly) responsible for making `v` available to whatever `x2`
reads from when `x2`'s own bit says "reuse," and corrupting it makes `x2`
fall back to reading zero, not some `x1`-derived garbage. This is exactly a
producer→consumer *hand-off* failure mode, not a general "any wrong bit
corrupts everything" fault.

## Polarity

For the `adjacent` kernel the natural (compiler-emitted) values are:
`x1` (first/earlier reader of `v`) has `opflags`-bit0 = **0**; `x2` (second/
later reader) has `opflags`-bit0 = **1**. Flipping `x1`'s bit **0→1** (making
the earlier read look like a "later/reuse" read) is the case that corrupts
`x2`. This is the polarity direction predicted by H2 in `PRE_REGISTRATION.md`
§2: forcing an earlier occurrence to behave as if it were *not* establishing
a fresh value is the corruption-risk direction, not the reverse.

For CAND_A (the register-select-field top bit, the closest analog we could
construct to the literal claim, present in `falu2i`/`falu2`/
`falu_srcmod12b`): natural polarity is **SET (`|0x40`) on the first read
after the producer or after a control-flow reconverge, CLEAR on an
immediately-following same-register read** — confirmed across all 7 kernels,
and confirmed (by an immediate-constant A/B swap in the pilot phase, see
`PRE_REGISTRATION.md` §1) to track *temporal schedule position*, not the
specific operand value. However, **this candidate's polarity was never
observed to matter**: every flip (`c1`, `c2`, `both`), in every kernel/
condition, left the output unchanged (see table below).

## Corrupting conditions and determinism

| kernel | distance/condition | CAND_A flip_c1/c2/both | CAND_B (adjacent only) | positive control | inert control |
|---|---|---|---|---|---|
| adjacent | 0 intervening instrs | null (3/3) | **flip_c1, flip_both corrupt (3/3)**; flip_c2 null | detects (3/3) | FAULT (3/3) |
| near | 1 intervening instr | null (3/3) | n/a | detects (3/3) | FAULT (3/3) |
| far4 | 2 intervening instrs, non-adjacent scheduling | null (3/3) | n/a | detects (3/3) | **MISMATCH (3/3)** |
| far16 | ~25 intervening instrs | null (3/3) | n/a | detects (3/3) | FAULT (3/3) |
| pressure | ~40 live values, ~372 B / dozens of instrs incl. a real `falu_acc` reduction tree | null (3/3) | n/a | detects (3/3) | **MISMATCH (3/3)** |
| if_boundary | straddles a real runtime `if_push`/`pop_reconverge` | null (3/3) | n/a | detects (3/3) | FAULT (3/3) |
| loop_boundary | straddles a real runtime-bounded `for` loop's push/pop_reconverge | null (3/3) | n/a | detects (3/3) | **MISMATCH (3/3)** |

Every single one of the 45 case-groups (135 individual case executions) was
**fully deterministic**: all 3 fresh-process repeats within `run01` returned
the identical verdict, with **zero** intermittent cases
(`analysis.json::intermittent_cases == []`). The 113/135 cases independently
re-executed in the (incomplete) second run were byte-identical to `run01`'s
corresponding lines, giving informal cross-process confirmation beyond the
in-run triplicate. **We found no evidence of intermittency in anything we
tested** — every effect we observed (corruption or its absence) reproduced
100% of the time under the exact same splice.

**CAND_A was tested under real distance, real ~40-value register pressure,
and real control-flow boundaries — and stayed null in every single
configuration.** This was NOT assumed to be a valid negative result by
default: `positive_control_c2` — redirecting the exact same instruction's
operand register, under the exact same distance/pressure/control-flow
condition — produced a detectable value deviation in **7/7 kernels**
(`analysis.json::positive_control_detected_n/total_n == 7/7`), proving the
harness could have detected a CAND_A corruption in every one of those same
conditions had one existed.

**The `inert_control_c1` field (presumed-inert `ctrl`/`ctrl_lo` tail bits)
was NOT actually inert** — it faulted the GPU (`CMDBUF_ERROR`, contained, no
wedge) in 4/7 kernels and silently produced a wrong value in the other 3/7
(`far4`, `pressure`, `loop_boundary`). This is a **separate, unplanned
finding**: the presumed-null control field is itself load-bearing in some
capacity we did not investigate further (out of scope here). It does not
invalidate the CAND_A/CAND_B results — `positive_control_c2` remains the
methodologically clean detection-capability proof — but it does mean this
particular field cannot be cited as a validated "nothing happens when you
flip an unrelated bit" baseline; that claim is retracted for this specific
field and flagged as its own open question.

## Producer/consumer agreement

For CAND_B on `adjacent` (the only decisive corrupting case set): the
producer/earlier-instruction's bit **alone** determines the outcome.
`candB_flip_c1` (only the earlier instruction's bit flipped) and
`candB_flip_both` (both flipped) give the **identical** corrupted result
(`20`); `candB_flip_c2` (only the later instruction's bit flipped) is null.
**The two sides do not need to "agree" in a symmetric XOR sense — the
consumer's own bit was irrelevant in this test; only the producer/earlier
occurrence's bit mattered.** This should be treated as a single data point
(one kernel, one instruction pair), not a general rule; whether this
generalizes to other producer/consumer pairs and instruction families is an
open question for a follow-up experiment.

For CAND_A: since no configuration corrupted anything, no agreement question
arises for that candidate in this dataset.

## Falu_acc (the literal RT-1a-FIX evidence instruction)

We could **not** reproduce the compact 4-byte `falu_acc` form (byte+2 in
`{0x18,0x38}`, the exact descriptor RT-1a-FIX spliced) in a "value read by
`falu_acc` AND separately read again later" scenario, after three honest
attempts (with/without `--no-fast-math`, straight `a+b+c+...` reduction
phrasing matching RT-1a's own `a2+...+a7` kernel almost verbatim) — the
compiler always chose the 6/8-byte `falu2`/`falu2i` sibling forms instead for
our exact source shapes. This is recorded as an unresolved scope limitation,
not a result either way: **`falu_acc`'s own byte+2 bit5 cache field has still
never been tested against a later, separate read** — RT-1a-FIX's
same-instruction self-check is its only evidence, exactly as diagnosed by
the dispatch, and that gap remains open specifically for `falu_acc` itself
(our CAND_B result establishes the *general risk*, not a direct
`falu_acc`-specific re-validation).

## Exact doc correction proposed (text only — not applied)

**`docs/isa/README.md:770`**, replace:

> `0x54<->0x56` cache bit = byte+2 bit 1 (instr bit 17) = a source cache /
> last-use hint (NOT an op change)

with:

> **`0x54<->0x56`-family bits (byte+2 bit 1 in `simd_reduce`/`fspecial`/
> `cvt_i2f`/`cvt_f2i`/`unpack_convert`/`ret`/`if_push_pred`; the analogous
> bit-5 `0x18`/`0x38` field in the compact `falu_acc` form) are labeled a
> "source cache / last-use hint" on evidence that only ever re-checked the
> SAME spliced instruction's own result (`RT-1a-FIX`) — never a LATER,
> separate instruction's read of the same register. That test is
> structurally incapable of detecting a genuine liveness/cache bug.
> **EXP-0086 (M4, HW-VALIDATED) built and ran exactly that missing test on a
> closely related same-family field (`falu2i`/`falu2` `opflags` bit 0, the
> nearest analog reachable given bit 17 is opcode-determining in every
> instance we could compile) and found it DOES corrupt a later, separate
> read when flipped on the earlier/producer instruction — deterministically,
> silently, with no fault** (`experiments/EXP-0086-m4-register-liveness-bits/RESULTS.md`).
> The literal `0x54`/`0x56`/`0x18`/`0x38` fields listed above are therefore
> **UNKNOWN, not confirmed inert** — each needs its own later-read splice
> test (construct a value consumed by the specific op, read again by a
> separate later instruction, splice the field, check the LATER read) before
> a driver may treat it as a free scheduling hint. Until re-tested, a
> conservative NIR->Apple9 backend should treat these bits as **significant**
> and set them to match the compiler's own observed convention (fresh-read =
> `SET`/`0x56`/`0x38`-style value on an instruction not immediately preceded
> by a same-register producer or not immediately following another read of
> the same register or a control-flow boundary; reuse/`CLEAR`/`0x54`/`0x18`-style
> value only on an immediately-following same-register read with no
> intervening control flow) rather than leaving it at an arbitrary or
> zero value.

**`db.json` descriptors affected** (report only — not edited; every one
carries language descending from the same unproven RT-1a-FIX self-check and
should get an "UNKNOWN pending later-read test" annotation, not a fix):
`falu_acc` (`cache` field, "NOT an op change (RT-1a-FIX: ... leaves the
reduction result unchanged)"), the `0xbf/0x3f/0xb7 cache bit` note under
`isa` top-level notes, `fspecial` ("byte+2 = source-cache bit (0x56 fresh /
0x54 shared)"), `unpack_convert` ("cache (byte+2) bit1 ... EXP-0038"),
`shl_reg`/`ibfins`-family ("byte+2 bit1 (cache) = source last-use hint"),
the texture coordinate-projection/LOD-setup descriptor ("cache ... is a
source-cache/last-use scheduling hint"), `if_push_pred` ("byte+2 = CF marker
(0x54 outer / 0x56 last-use)"), `cvt_i2f`/`cvt_f2i`/`cvt_u2f` ("byte+2==0x54
result-consumed vs 0x56 standalone/last-use"), the `ret` LAST-USE variant
("bit17 is the source cache/last-use hint ... a scheduling hint, not an op
change"), and the residual compact-`falu2` note ("the 0x30/0x31 pair carries
the source cache/last-use hint bit"). None of these were re-tested by this
experiment; all inherit the same evidentiary gap and should be downgraded
from their current confident phrasing to `UNKNOWN / needs later-read
splice test` until individually re-validated.

## What this undermines elsewhere in the repository

- Any NIR->Apple9 backend guidance (internal or external) that currently
  treats the `0x54/0x56`-family "cache" bits as free/ignorable — this
  experiment is direct, deterministic, hardware evidence that bits in this
  same role/family are NOT safe to ignore, at least for one instance.
  `docs/isa/README.md`'s "compiler guidance" framing around EXP-0025's
  register-interlock note is not contradicted (that is a different
  mechanism — HW register-availability interlock, not this operand-cache
  bit), but any reader who inferred "and therefore the adjacent cache-bit
  fields are also free" from the same section should not.
- `PROVENANCE.md` rows citing `RT-1a-FIX` item 4 / `EXP-0038` as the basis
  for "cache bit = inert" should be annotated with this experiment as a
  partial correction (general principle refuted; specific literal fields
  still individually unproven either way).
- The `falu_acc` claim specifically (`docs/isa/README.md`'s EXP-0038
  wrap-up paragraph, and the `db.json` `cache` field on `falu_acc`) keeps
  its ORIGINAL evidentiary status (same-instruction self-check only, gap not
  closed for `falu_acc` itself — see "Falu_acc" section above) but now reads
  in the context of a proven-real sibling risk, so its confidence should
  drop from implied-settled to explicitly unproven.

## Limitations / honest gaps

- **Single fully-valid, gate-passing run** (`run01`), not the two
  independent full runs the frozen contract called for. The second run was
  killed at 113/135 cases by an external terminal issue (twice, across two
  session interruptions unrelated to the experiment — see
  `QUARANTINE-run02-attempt1.md`); its completed 113 lines are
  byte-identical to `run01`'s, which is strong informal corroboration but
  not the contracted formal cross-run gate. `verify.py --captured` and
  `--between-runs` (on the current, post-quarantine-note tree) correctly and
  intentionally FAIL for this reason — this is disclosed, not hidden or
  forced.
- CAND_B was only tested on the single `adjacent` kernel (the task's
  distance/pressure/control-flow sweep was applied to CAND_A, the field we
  judged the closer analog to the literal claim, before CAND_B's causal
  effect was discovered in the same pilot pass that located CAND_A). Whether
  CAND_B's corrupting behavior also depends on distance/pressure/control-flow
  the way CAND_A's null behavior was shown not to is an **open question** —
  the honest scope of this result is "CAND_B corrupts adjacent-schedule
  reads; untested at distance."
- `falu_acc`'s own literal field remains untested against a later read (see
  above) — this experiment closes the *general* evidentiary gap the dispatch
  identified, but not the *specific* `falu_acc` instance.
- The `inert_control` field turned out not to be inert (see above); no
  control field in this experiment can be cited as a validated inert
  baseline going forward.

## Clean-room provenance

```text
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: kernels/*.metal (our own MSL), compiled via tools/shdump
  (newLibraryWithSource:), decoded/spliced with tools/agx-isa (read-only),
  executed on the real M4 GPU via tools/agxtest. No Apple binary, archive,
  BO, or command-stream inspection.
Apple binary introspection: NONE
Reproduction: python3 -B verify.py --selftest / --seqtest (synthetic, no GPU);
  python3 -B run.py --execute --run-id <id> (real GPU, append-only);
  python3 -B analysis.py --run-a m4-20260828-run01 --run-b m4-20260828-run02 --write
Evidence: raw/m4-20260828-run01/ (complete, gate-passing), analysis.json,
  raw/m4-20260828-run02/ (partial, quarantined, informal corroboration only)
```
