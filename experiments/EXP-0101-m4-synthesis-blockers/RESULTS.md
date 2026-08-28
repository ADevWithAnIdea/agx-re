# RESULTS — EXP-0101 M4 synthesis blockers

**STATUS: CAPTURED / GATE-CLOSED.** Both contracted runs
(`m4-20260827-run01`, `m4-20260827-run02`) complete, 29/29 cases each,
`01_results.jsonl` **byte-identical** across both independent runs (sha256
`dd8ff10b2c5dce29d15a50365329d996d9df04fd9ac3ca65c128da2f224521ab`).
21/29 matched their oracle, 8/29 mismatched — **every single one of the 8
mismatches is a case whose `expect_match` was pre-registered `False`
before this matrix's one informal pilot-verification run, and zero cases
disagreed with their prediction in either gated run** (`PRE_REGISTRATION.md`
§3 for the full, frozen confirm/refute table). `verify.py --selftest`
(13 checks), `--seqtest`, `--preflight`, `--between-runs`, `--captured`
all PASS. Target: **local Apple M4 / G16G only** (macOS 26.6.2/25G82,
`Mac16,10`, arm64). No A18 Pro replication (hands-off). No M5 evidence
used anywhere.

---

## 0. Headline verdicts

**BLOCKER 1 — RESOLVED.** `device_load`'s result CAN now be independently
constructed to feed `falu2`/`falu2i`. The rule: **the register a
subsequent ALU instruction must reference is `device_load`'s `extmode`
field divided by 2 (`extmode = 2 * target_register`) — NOT the
`dst_lo`/`dst_ext9`-derived value EXP-M4-13's own formula predicted.**
`dst_lo`/`dst_ext9` remain a real, independently-required field, but must
be **copied verbatim from a compiler-observed value for the same
addr_mode/ld_format shape**, never derived from the target register. A
third field, `falu2i`'s own `mods` byte, must additionally be `0xC0` (not
the naive default `0`) when the operand it modifies is load-sourced.
`HW-VALIDATED`, two independent gated runs, 6 positive constructions (4
distinct target registers via 2 ALU forms) and 6 adversarial falsifications
of the 3 next-most-plausible wrong repairs, plus an OWN-SHADER compiler
census (11/11 compiler-emitted load→ALU pairs independently confirm the
formula; 2/2 census kernels functionally verified unspliced).

**BLOCKER 2 — NOT RESOLVED, mechanism CHARACTERIZED.** No construction in
this experiment (or any prior one) reads a GPR written by
`falu2`/`falu2i`/`device_load` through `reg_move`. What IS now established,
`HW-VALIDATED`: the instruction's output at `src_flag=0` ("GPR mode" per
its own `db.json` label) is **completely independent of what any GPR
actually holds** — changing the producer's VALUE, and separately changing
the producer's FAMILY (ALU vs. load), leaves the output byte-identical.
The output depends only on `src_reg`, quantized in register PAIRS. This is
the signature of reading a **fixed, per-kernel PRELOADED/uniform-file
slot**, not a corrupted or partial GPR read. `0x00000100` (register pair
2,3) is simply whatever that slot holds for the tested carriers — not a
special sentinel with independent meaning. EXP-0087's own open question
about `byte+2=0x21` is resolved as "reads the same uniform content, not a
real move." **Next discriminating experiment, precisely bounded below.**

---

## 1. BLOCKER 1 — device_load → falu2/falu2i

### 1.1 OBSERVED: compiler census (OWN-SHADER, `analysis/census.py`)

Compiled two kernels we authored (`kernels/census_load_add.metal`: one
load, one `+10.0`, one store; `kernels/census_multiload.metal`: ten
independent loads, each kept live to its own later `+K` use) and
disassembled the result with `tools/agx-isa`. Both kernels were run
**unmodified** (no field mutation whatsoever) and are **functionally
verified correct**: `census_load_add` gives `mem[0]=42.5 → out[0]=52.5`;
`census_multiload` gives all 10 of `mem[i]=i·10+0.25 → out[i]=mem[i]+(i+1)`
exactly (`analysis/census_report.json`, both `functional_check_unspliced.
match = true`).

Across these two kernels' 11 compiler-emitted `device_load`-then-
`falu2`/`falu2i` pairs, `analysis/census.py` finds:

| quantity | matches |
|---|---|
| `extmode / 2 == consumer's srcA_reg` | **11/11** |
| `(dst_lo \| (dst_ext9<<2)) == consumer's srcA_reg` (EXP-M4-13's own formula) | **1/11** (coincidental, when both happen to be 0) |

The single cleanest data point: `census_load_add`'s compiled program loads
`mem[tid]` with `dst_lo=1, dst_ext9=1` (EXP-M4-13's formula predicts
register **5**) yet the immediately-following, functionally-verified-
correct `falu2i` reads it via `srcA_reg=0` — the naive formula's own
prediction never appears anywhere in the working program. This is
`OWN-SHADER-DIFF` evidence, gathered by pure compile-and-disassemble, no
splicing.

### 1.2 OBSERVED: hardware splice validation (HW-PROBE, two gated runs)

Every one of the following is an independently hand-assembled program
(`tools/agx-isa isadb.assemble()`), spliced over the SAME compiled carrier,
run in its own fresh process, and cross-checked byte-identically across
both gated runs.

**Positive (`LOAD_FIX` group, all 4 `expect_match=True`, all MATCHED both
runs):** relocating the consumer register via `extmode` alone — holding
`dst_lo`/`dst_ext9` at the one HW-confirmed-valid token `(1,1)` — works for
target registers **3, 7, 16, and 20** (`fix_extmode_reg3/_reg7_falu2/
_reg16/_reg20`), each reading `mem[1]=-8.5` exactly via `falu2`
(register-register). `fix_extmode_reg7_falu2i` additionally validates the
`falu2i` (register+immediate) form, requiring one MORE field
(`mods=0xC0`, see §1.4) on top of the `extmode`/`dst_lo`/`dst_ext9` rule.

**Negative / falsification (`LOAD_REPLICATE` + `LOAD_ADVERSARIAL` groups,
6 cases, all `expect_match=False`, all MISMATCHED as predicted, both
runs):**

| case | what it disturbs | observed | oracle |
|---|---|---|---|
| `route_load_replicate_fail_route6` | EXACT EXP-0099 ROUTE_LOAD shape: `extmode=0` (its old default), `dst_lo`/`dst_ext9` derived from register 7 via the naive formula | `0.0` | `-8.5` |
| `adversarial_extmode_unchanged_srcA_mismatch` | `extmode` correct for r0, but consumer `srcA_reg=3` (mismatched) | `0.0` | `-8.5` |
| `adversarial_dstfields_naive_formula` | `extmode` CORRECTLY set (`2*3=6`), but `dst_lo`/`dst_ext9` computed from the target register (3,0) instead of copied | `0.0` | `-8.5` |
| `adversarial_dstfields_zero_extmode_correct` | `extmode` correct (`2*3=6`), `dst_lo`/`dst_ext9=(0,0)` (arbitrary) | `0.0` | `-8.5` |
| `adversarial_dstfields_zero_extmode_unchanged` | `extmode` UNCHANGED at its already-correct value (0, target r0); ONLY `dst_lo`/`dst_ext9` disturbed to `(0,0)` | `0.0` | `-8.5` |
| `adversarial_falu2i_mods_naive_default` | IDENTICAL to `fix_extmode_reg7_falu2i` except `mods=0` | `1.5` (K_SMALL alone; srcA read as 0) | `-7.0` |

**Control (`control_dst_nibble_independent_of_srcA`, `expect_match=True`,
MATCHED):** relocates the consumer to r16 (low 4 bits = 0) while the ALU's
own `dst` nibble is set to an unrelated 8 — reads `-8.5` correctly,
falsifying an early pilot-phase over-theory that `dst` must alias
`srcA_reg`'s low bits (see §1.5).

### 1.3 INTERPRETED — the rule

A driver backend synthesizing a `device_load` whose result must be
consumed by a later `falu2`/`falu2i` must:

1. Set `extmode = 2 × R` where `R` is the register the consuming
   instruction's `srcA_reg`/`srcB_reg` field will use. `R` may be any
   value the ALU's own 7-bit register field can represent (0–127);
   validated 0, 3, 7, 16, 20.
2. Set `dst_lo`/`dst_ext9` to a value **copied from a compiler-observed
   `device_load` of the same `addr_mode`/`ld_format` shape** — this
   experiment validates `(dst_lo=1, dst_ext9=1)` for the terminal,
   scalar-32-bit shape (`addr_mode=0x44`, `ld_format=0x11`). **Do not**
   derive this pair from `R` via any formula; every tested attempt to do
   so fails, including leaving `extmode` correct and disturbing only
   `dst_lo`/`dst_ext9`.
3. If the consumer is `falu2i` (register + immediate, rather than
   `falu2`'s register-register form) and the register operand is
   load-sourced, ALSO set `falu2i`'s `mods` byte (offset +5, bits 40–47)
   to `0xC0` — the value the compiler itself emits for this shape. Neither
   bit 6 nor bit 7 alone suffices; both must be set (structurally the same
   shape as EXP-0090's own "`falu2`'s two-real-operand `opflags` must be 3,
   not 1" finding — a required PAIR of bits, not a single flag).

This directly explains EXP-0099's own `ROUTE_LOAD` failure: it always used
`isa_helpers.device_load()`'s old default `extmode=0` while pointing the
consuming instruction's `srcA_reg` at 7 — a plain field mismatch that has
nothing to do with the "consumer route" (`mod_hi`) field EXP-0099
correctly found to be irrelevant. That negative conclusion **stands**
(route genuinely does not matter); this experiment identifies the actual
mechanism EXP-0099's own design could not reach because its
`device_load()` helper conflated two independent fields into one.

### 1.4 The `mods=0xC0` finding, in detail

Discovered when the first attempt at `fix_extmode_reg7_falu2i` (built with
`isa_helpers`'s naive `mods=0` default) failed a pre-freeze smoke check. A
direct one-field-at-a-time sweep (`mods ∈ {0, 0xC0, 0x80, 0x40, 0x08, 0x04,
0x02, 0x01}`, same carrier/mem, everything else identical) found **only
`0xC0` works**; every other value, including EACH of the two component
bits (`0x40`, `0x80`) alone, fails identically to `mods=0`
(`PROGRESS.md` Milestone 4). `0xC0` is exactly the compiler's own emitted
value for this field shape (§1.1). This was folded into the frozen matrix
before the formal gate (`fix_extmode_reg7_falu2i` now uses `mods=0xC0`;
`adversarial_falu2i_mods_naive_default` captures the `mods=0` negative
under the same gate).

### 1.5 A resolved false lead

An early pilot-phase reading of the compiler census (§1.1) noticed that,
in a self-updating accumulate pattern (`v += K`), the compiler always set
`falu2i`'s 4-bit `dst` nibble equal to `srcA_reg`'s low 4 bits — suggesting
`dst`'s true address might inherit high bits from `srcA_reg`. This is
**falsified**: `control_dst_nibble_independent_of_srcA` reads a register-16
source with an UNRELATED `dst=8` and works correctly. The actual
explanation for the earlier confusing result was simpler and unrelated: a
downstream `device_store`'s own `extmode` (data-register selector, EXP-0090's
`extmode=2*data_reg`) must be kept consistent with whatever register the
ALU op's `dst` really wrote — an adversarial test that changed `dst`
without updating the paired store's `extmode` was reading a stale/wrong
register, not exposing a `dst`-addressing defect.

### 1.6 What remains open (Blocker 1)

`dst_lo`/`dst_ext9`'s own legality rule is **not** fully characterized:
`(0,0)` fails at least once (`addr_mode=0x44`, this experiment's carrier)
but was separately observed to work fine in a DIFFERENT context (a
non-terminal, `addr_mode=0x54` load inside the compiler's own
10-load census program, §1.1) — legality appears to depend on
`addr_mode`/context in a way this experiment did not fully map (an
informal pilot-phase finding, `PROGRESS.md` Milestone 3, not independently
gated). The safe driver rule remains "copy verbatim from a real compile of
the matching shape," which is sufficient for synthesis even though the
underlying hardware semantics of `dst_lo`/`dst_ext9` (candidate: an
internal load-queue/cache-slot tag, unrelated to the GPR file) remain
`UNKNOWN`.

---

## 2. BLOCKER 2 — reg_move / 0x00000100

### 2.1 OBSERVED: producer independence (decisive, two gated runs)

| case | producer | src_reg | observed (all 4 rows byte-identical, both runs) |
|---|---|---|---|
| `move_replicate_baseline` | `falu2i` writes `30.0` to r2 | 2 | `0x00000100` |
| `move_producer_independence_altvalue` | `falu2i` writes `2.0` to r2 (SAME register, DIFFERENT value) | 2 | `0x00000100` |
| `move_loadsourced_independence` | `device_load` (this experiment's own H1-FIXED, functional path) writes `-8.5` to r2 | 2 | `0x00000100` |
| `move_srcclass_0x21_alu_sourced` | `falu2i` writes `30.0` to r2; `byte+2=0x21` (EXP-0087's own open question) instead of `0x01` | 2 | `0x00000100` |

**The output is byte-identical across three different producer VALUES and
two different producer FAMILIES (ALU vs. load), and across two different
`byte+2` encodings that both nominally "read something".** If `reg_move`
were reading register 2 in any of these constructions, at least one of
these rows would differ from the others — none does.

### 2.2 OBSERVED: register-pair quantization and slot diversity

| src_reg | observed (both runs) | as hex u32 |
|---|---|---|
| 0, 1 | `1.6286451271768754e-40` (both identical) | `0x0001C600` |
| 2, 3 | `3.587324068671532e-43` (both identical) | `0x00000100` |
| 4, 5 | `1.6250578031082039e-40` (both identical) | `0x0001C500` |
| 8 | `0.0` | `0x00000000` |

`src_reg` and `src_reg XOR 1` always read identical content; different
pairs read genuinely different, non-zero content (i.e. this is not simply
"everything reads the same garbage") up to `src_reg=8`, beyond which
content reads exactly zero for this carrier. An informal (not gated —
different, ungated carrier file, see `PROGRESS.md` Milestone 5) cross-check
found the `(2,3)` pair's `0x00000100` value STABLE across a 3-buffer
carrier and two different dispatch sizes, while the `(0,1)` pair's value
CHANGED with the carrier's buffer signature — consistent with `src_reg`
addressing a per-kernel preloaded/uniform region whose content is
partly kernel-specific and partly (at least at this one slot) stable.

### 2.3 OBSERVED: `src_flag=1` positive control

| src_reg | src_flag | observed (both runs) |
|---|---|---|
| 1 | 1 | `1.401298464324817e-45` (= raw bits `0x00000001`) |
| 2 | 1 | `2.802596928649634e-45` (= raw bits `0x00000002`) |
| 3 | 1 | `4.203895392974451e-45` (= raw bits `0x00000003`) |

At `src_flag=1` (the field's own documented "uniform/class" label), the
SAME instruction reads back the literal small integers 1, 2, 3 — a clean,
easily distinguished signal. This is the decisive **positive control**:
the harness, the splice mechanism, and this instruction family ARE
capable of reading genuinely different content as addressing changes. The
`src_flag=0` producer-independence findings above are therefore a real
hardware fact about THIS specific addressing mode, not an artifact of a
broken or insensitive test.

### 2.4 OBSERVED: extended silent-zero boundary

`move_srcreg_8_reads_zero` (`0.0`) and `move_opdesc_sweep_zero` (`op_desc=0`
instead of the one documented-working `8`; `0.0`) both match the standing
`docs/isa/register-move-and-liveness.md` §2.5 pattern ("most fields fail
silently to zero, not by faulting"), extending EXP-0087's own byte+2/
op_desc sweep (done on a uniform-sourced carrier) to this experiment's
ALU-sourced one with the same conclusion.

### 2.5 INTERPRETED

**The compact-move family, at `byte+2=0x01` (or `=0x21`, `op_desc=0x08`),
never addresses the live general-purpose register file when `src_flag=0`,
regardless of that field's documented "gpr" label.** Its `src_reg`
operand instead selects a register-pair-quantized slot in what is most
plausibly a per-kernel PRELOADED/uniform-register region — the SAME
region `src_flag=1` more legibly addresses, though evidently not via an
identical index mapping (flipping `src_flag` at the same `src_reg` value
changes the content, so `src_flag` is not purely cosmetic; its exact
addressing relationship to `src_flag=0`'s slot numbering is `UNKNOWN`).
`0x00000100` is not a special sentinel or an error code — it is simply
whatever that particular preloaded slot happens to hold for the tested
carriers, which is why it reproduces exactly regardless of what the
"intended" source register was computed to be.

This resolves EXP-0099's own open lead ("a concrete lead for whoever
continues this investigation") with a specific, falsifiable answer: the
lead is not a corrupted-address bug that happens to always land on the
same spot; it is the instruction correctly performing the operation it was
ALWAYS designed to perform (a uniform/preload-file read) at an operand
value a compiler never has reason to point at live GPR content, because —
per EXP-0087's own census — the compiler only emits this specific family
in a genuine loop-carried control-flow join, and even then sources it from
either an all-zero "const-zero/scope-prep" form or a `src_flag=1`
uniform-class value, never a `src_flag=0` plain-GPR value with a nonzero
source (`docs/isa/register-move-and-liveness.md` §1.5).

### 2.6 Hypotheses falsified (Blocker 2, cumulative with EXP-0099)

- Destination-publication bit (`opflags` bit21) — **falsified**, EXP-0099.
- Pipeline-timing / padding instructions — **falsified**, EXP-0099.
- Both combined — **falsified**, EXP-0099.
- Producer family specificity (works for one of falu2i/device_load but not
  the other) — **falsified**, EXP-0099 AND this experiment (independently,
  on a now-genuinely-functional load path via this experiment's own H1
  fix, strengthening EXP-0099's own analogous case which used the
  pre-fix, non-functional load).
- **NEW, this experiment:** dependence on the producer's actual VALUE —
  **falsified** (§2.1).
- **NEW, this experiment:** `byte+2=0x21` is a genuine, different "real
  move" encoding (EXP-0087's own explicitly left-open question) —
  **falsified** (§2.1, §2.5).
- **NEW, this experiment:** the addressing is simply broken/random rather
  than a real, structured read of SOME resource — **falsified** by §2.2's
  clean pair-quantization and by §2.3's positive control (a broken/random
  read would not reproduce byte-identically across two independent
  hardware runs, nor would it correlate cleanly with `src_flag`).

### 2.7 Next discriminating experiment

The mechanism is now well enough characterized to make a sharp, falsifiable
next step: **determine the exact addressing relationship between this
family's `src_flag=0` slot numbering and either (a) the SAME kernel's own
argument-buffer/uniform-table layout** (probe: vary buffer COUNT and TYPE
systematically — not just 2-vs-3 buffers as this experiment's informal
check did — and see whether `src_reg`'s content shifts in lockstep with a
specific buffer's pointer or a specific `[[buffer(N)]]` argument slot;
compare against what `tools/iotrace` observes crossing the userspace→kernel
boundary for the SAME kernel's uniform/push-constant region) or **(b) a
genuinely different, not-yet-decoded instruction family that IS the real
GPR-to-GPR move** — EXP-0087's own census left one byte0=`0x2b`-class
instruction (encountered mid-way through a hand-authored register-swap
kernel) completely undecoded by `tools/agx-isa`; that gap was out of scope
for EXP-0087 and remains out of scope here, but is the most concrete
un-chased lead for finding an actual working GPR move, since (per §2.5) the
compiler's own use of the CURRENTLY-decoded compact-move family has never
been observed sourcing a genuine, nonzero, `src_flag=0` GPR value.

---

## 3. Gate results

- `verify.py --selftest`: **PASS**, 13 checks (recorded-reality fixture:
  `harness/recorded_fixture_case0.json`, a REAL hardware record of case 0
  captured during this experiment's own pilot phase — CODEX gate (e);
  round-trips all 29 cases through `isadb.disassemble`+`assemble`).
- `verify.py --seqtest`: **PASS** in all three tree states (`PRE_GPU`,
  `RUN01_PRESENT`, `RUN02_PRESENT`).
- `make_manifest.py --check` / `--write`: **PASS** (15 authored files).
- `verify.py --preflight`: **PASS**.
- `verify.py --between-runs`: **PASS** — gated ONLY on
  `authored_{code,kernel,doc}_sha256` and the pinned revision recorded in
  `PRE_REGISTRATION.md`/`CAPTURE_CONTRACT.json`; never live git `HEAD`.
- `verify.py --captured`: **PASS** — `01_results.jsonl` byte-identical
  across both runs (sha256 above); `01_timing.jsonl` correctly NOT
  required to match.
- No `STOP.json` in either run.
- **21/29 matched, 8/29 mismatched, in BOTH runs, and every one of the 8
  mismatches is a pre-registered `expect_match=False` case — zero
  unexpected results in either gated run.**
- **Positive controls:** `positive_control_deliberate_mismatch` (SEED_CHECK)
  and `positive_control_deliberate_mismatch_move` (MOVE_UNIFORM) both read
  their correct underlying value (`30.0` and `0x00000100` respectively)
  against a deliberately unreachable oracle (`999.0`) — MISMATCH as
  designed, in both runs, proving match-detection is not a rubber stamp
  for BOTH blockers' evidence.
- **OWN-SHADER census** (`analysis/census.py`, not part of the two-run
  splice gate — see PRE_REGISTRATION.md §4 for why): 11/11 compiler-emitted
  load→ALU pairs confirm `extmode/2==srcA_reg`; both census kernels
  functionally correct unspliced. Independently re-runnable
  (`python3 -B analysis/census.py --write`); its own internal assertions
  are a hard fail if the formula or functional correctness does not hold.

---

## 4. Limitations / honest gaps

- **Blocker 1's `dst_lo`/`dst_ext9` field is not fully characterized**
  (§1.6) — a working, sufficient DRIVER RULE is established (copy from a
  compiler-observed value of the matching shape), but the field's own
  hardware semantics remain `UNKNOWN`, and its legality boundary
  (`addr_mode`-dependent, per one informal, ungated pilot observation) is
  not mapped.
- **Blocker 1's fix is validated only for `addr_mode=0x44`/`ld_format=0x11`
  (terminal, scalar 32-bit loads).** Non-terminal (`addr_mode=0x54`, part
  of a base-sharing group) and non-scalar (`ld_format` vector) shapes were
  observed in the compiler census (§1.1, multiload uses `addr_mode=0x54`
  for 9 of its 10 loads, all consistent with the SAME `extmode` formula)
  but NOT independently splice-validated under this experiment's own gate
  — only the `addr_mode=0x44` shape was.
- **Blocker 2 is NOT resolved.** No construction found in this experiment
  (or EXP-0087/EXP-0090/EXP-0099 before it) successfully reads a GPR
  written by `falu2`/`falu2i`/`device_load` via `reg_move`. §2.7's next
  step is a genuine, unstarted follow-up, not a near-miss.
- **The cross-carrier / cross-dispatch-size stability check for the
  `(2,3)`-pair `0x00000100` value (§2.2) is INFORMAL/pilot-phase only** —
  observed on real hardware but with a different, ungated carrier file, not
  captured under this experiment's own formal two-run gate (same
  disclosure convention EXP-0099 used for its own analogous informal
  finding). A follow-up experiment should formalize it if it becomes
  load-bearing for further work.
- **`src_flag=0`'s exact relationship to `src_flag=1`'s addressing is
  `UNKNOWN`** — both plausibly address "the uniform file" in some sense,
  but flipping the bit at the same `src_reg` value changes the content, so
  they are not the same index into the same table without translation; no
  translation was determined.

---

## 5. Clean-room provenance

```text
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: kernels/carrier.metal, kernels/census_load_add.metal,
  kernels/census_multiload.metal (all our own MSL), tools/agx-isa's
  isadb.assemble()/disassemble()/imm_encode()/imm_decode() (read-only),
  tools/agxtest (read-only, splice-and-run), tools/shdump (read-only,
  compile+extract). No external document or third party's example bytes
  were used as a hypothesis source anywhere in this experiment (unlike
  EXP-0099, whose H1-H6 partly tested an external engineer's own claims) —
  every hypothesis here originates from this experiment's own OWN-SHADER
  compiler census (analysis/census.py) and field-mutation splice pilot.
Apple binary introspection: NONE.
Reproduction: python3 -B verify.py --selftest/--seqtest (no GPU);
  python3 -B baseline.py / analysis/census.py --write (GPU, compile +
  unspliced dispatch only); python3 -B run.py --execute --run-id <id>
  (real GPU, splice, append-only); python3 -B verify.py --captured.
Evidence: raw/m4-20260827-run01/, raw/m4-20260827-run02/ (byte-identical
  01_results.jsonl, sha256 above), analysis/census_report.json,
  manifest.json.
```
