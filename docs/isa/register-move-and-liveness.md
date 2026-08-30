# Apple9 Register Move & Register-Liveness — Implementer Notes

**Status: URGENT CORRECTION (2026-08-28).** This chapter exists because an external compiler
engineer, building a NIR→Apple9 backend from this repository, reported two blocking problems: he
could not get a basic register-to-register move to work, and he believed the ISA carries a register
lifetime mechanism that our docs denied. **Both reports were correct.** Two experiments
(`EXP-0086`, `EXP-0087`) were run to check our own claims; both found our documentation wrong or
unproven in a way that would silently corrupt generated code.

Target: **Apple M4 / G16G**, local host, `HW-PROBE + OWN-SHADER` splice evidence — every fact in
this chapter is `target: G16G`. A18 Pro/G17P is `INFERRED`-by-family and is **not** relabelled.

> **Target status (2026-08-28).** All live testing has since moved to the **A18 Pro / G17P**, and
> **closure is measured against full G17P** (`../../CODEX.md`, "Target discipline"). This
> chapter's M4 evidence stays **valid on its own target** and is not retracted; **G17P
> revalidation is under way (`EXP-0153`)**. Cross-target promotion requires a recorded validation
> or an explicit `INFERRED` label — §2.8 shows why (a contradiction that looked like a device
> difference turned out to be operand provenance), and `memory-model.md` §2A.5 shows the opposite
> case (`tg_addr_compute`, a genuine live A18↔M4 divergence).

---

## 1. Emitting a register-to-register move

### 1.0 ⚠️ SCOPE CORRECTION (EXP-0090, 2026-08-28) — read before §1.1

The rule in §1.1 is **narrower than originally published here.** EXP-0090 tried to use it in a
hand-built whole program and found that **`reg_move` with this encoding failed to read a GPR that
had been written by `falu2`/`falu2i`.** Re-examining EXP-0087's validated cases showed they were
**entirely uniform-register-sourced**.

- **Validated scope:** moving from a **uniform-register / preloaded source**. `HW-VALIDATED`
  (EXP-0087, 5 source registers, zero cross-talk).
- **NOT established:** moving from a **GPR written by a preceding computation**. This is the case a
  register allocator needs most, and it **failed** in EXP-0090's P4 program. `UNKNOWN`, actively
  blocked.

Do not treat §1.1 as a general GPR→GPR move until that gap is closed.

### 1.1 The rule (use this, within the scope above)

For the compact move family (`byte0` low nibble `0xb`; `byte0` high nibble = destination register):

| field | value | status |
|---|---|---|
| `byte+2` | **`0x01`** | the only value proven to move a value (`HW-VALIDATED`, EXP-0087) |
| `byte+3` (`op_desc`) | **`0x08`** | proven with `byte+2=0x01` across 5 source registers, zero cross-talk |
| `src_flag` (`byte+1` bit 7) | **`0`** | GPR source |
| `dst` (`byte0` high nibble) | `r0`–`r15` | works across all reachable quads; **structurally capped at 4 bits** |
| `src_reg` (`byte+1` bits 0–6) | source GPR | validated over 5 distinct sources |

### 1.2 Why other encodings appear to "not work"

**Most other `byte+2` values are silent no-ops that deterministically ZERO the destination.**
EXP-0087's raw data shows 26 such zeroing cases spanning `byte+2` ∈ {`0x00`, `0x09`, `0x0b`,
`0x1b`, `0x20`, `0x22`–`0x2b`, `0x3b`, `0x49`, `0x60`, `0x61`, `0x69`, `0x89`, `0xa1`, `0xc1`,
`0xc9`, `0xe1`, `0xff`}. They do not fault. They do not warn. The destination simply becomes zero.
An implementer selecting a plausible-looking `byte+2` from the descriptor table gets a silent zero
rather than a move — the exact reported symptom. `HW-VALIDATED` (EXP-0087).

### 1.3 Hazards in the same encoding

- **`op_desc` bit 2 (`0x04`) is a live destination-corruption bit** — setting it redirects the
  write to a *different* register. `HW-VALIDATED` (EXP-0087).
- **`byte+2` = `0x26` and `0x0F` are nondeterministic** — they genuinely differed (fault vs.
  succeed) between two otherwise byte-identical runs. Do not emit them. `HW-VALIDATED` (EXP-0087).
- **`byte+2` = `0x21`** is the value most common in the corpus and *also* appears to work, but
  EXP-0087's design cannot distinguish "real move" from "lucky no-op that happened to leave the
  expected value in place". `UNKNOWN` — do not rely on it; prefer `0x01`/`0x08`.

### 1.4 Descriptor-table correction

`tools/agx-isa/db.json` currently models this family as **five separate opcodes**
(`reg_move_c0`, `reg_move_c1`, `reg_move_c9`, `reg_move_cb`, `reg_move_c2var`), discriminated by
`byte+2`'s low nibble. That is a misreading: **they are ONE instruction with a single 8-bit
`byte+2` field.** All five were derived from corpus byte-diff only (`reg_move_cb` is explicitly
"Not splice-validated"; `reg_move_c2var`'s field roles were "inherited"). `STRUCTURAL` → corrected
by EXP-0087; the DB collapse is a pending tool change, tracked as an open item.

### 1.5 What the compiler actually emits (census)

Of four authored contexts, **two emit zero instances of this family**: a simple variable
pass-through optimizes away entirely, and a `noinline` call-argument marshal uses a different
instruction. Only a genuine loop-carried control-flow-join phi produced real instances — and
neither emitted instance was a textbook plain-GPR-source move (one had an all-zero payload, the
other `src_flag=1`). **Consequence: our move descriptors were built almost entirely from contexts
that do not represent the move a compiler needs to emit.** `OWN-SHADER-DIFF` (EXP-0087).

---

## 2. Register liveness — the bits are NOT inert

### 2.1 What was claimed, and why it was wrong

`docs/isa/README.md` previously documented the `0x54↔0x56` bit (`byte+2` bit 1, instruction bit 17)
as "a source cache / last-use hint (**NOT an op change**)". The sole evidence was `RT-1a-FIX`,
which spliced an instruction and re-checked **that same instruction's own result**. A
register-liveness bit cannot fail there: its failure mode is a **later** instruction reading a value
that was marked dead. We tested the one case where the effect cannot appear.

### 2.2 What the hardware actually does

EXP-0086 ran the missing later-read test. Kernel: `v = a[0] = 7.5`; `x1 = v + 10`; `x2 = v + 20`;
oracle `(17.5, 27.5)`. All cases deterministic, 3 fresh-process repeats, no faults:

| case | splice | observed | verdict |
|---|---|---|---|
| baseline | — | `17.5, 27.5` | match |
| flip bit on the **earlier** (producer) instruction | `@20=14` | `17.5, **20**` | **CORRUPTED** |
| flip bit on the **later** instruction | `@26=04` | `17.5, 27.5` | match |
| flip on both | — | `17.5, **20**` | **CORRUPTED** |
| positive control (wrong register) | `@27=05` | `17.5, 20` | corrupted as designed |

The later read returned `20`, i.e. **`v` read as zero — the value was dropped.** `HW-VALIDATED`
(EXP-0086).

- **Polarity:** natural encoding is earlier-reader bit `0`, later-reader bit `1`. Forcing the
  *earlier* reader's bit to `1` is what corrupts.
- **Producer/consumer:** the **earlier** instruction's bit alone determines the outcome. The later
  instruction's own bit was irrelevant. No symmetric-agreement requirement observed.

### 2.3 The literal bit 17 IS load-bearing (EXP-0089)

EXP-0086 could not reach the literal bit; **EXP-0089 did**, in two independent families
(`unpack_convert`, `cvt_i2f`) where `db.json`'s own `match` table proves bit 17 is genuinely free
rather than opcode. Flipping it on the **earlier** instruction: `HW-VALIDATED`.

| kernel | baseline | flip on earlier insn | flip on later insn |
|---|---|---|---|
| `lit17_unpack` | `0.50000763, 6.0000305` | **`0, 5`** | `0.50000763, 6.0000305` (no-op) |
| `lit17_cvt` | `1244, 1254` | **`10, 20`** | `1244, 1254` (no-op) |

**New signature, stronger than `opflags` bit 0:** the flip corrupts **the flipped instruction's own
result as well as** a later reader's. `falu_acc` remains structurally opcode-fixed at bit 17 and
still cannot be tested there.

### 2.3b The mechanism — persistent producer-side writeback suppression

EXP-0089's `discrim3` kernel was built to *separate* candidate models rather than confirm one. The
evidence supports **persistent producer-side writeback suppression** over a one-shot bypass-cache
model: corruption reaches a **third, independent later reader**, and never an earlier one.
`HW-VALIDATED` (EXP-0089).

**Scope is condition-dependent.** The corrupting bit is universal across all 7 kernels, but
`loop_boundary` (12-byte extended form, real loop) uniquely corrupts a *third* value (the
accumulator) and is the only context where the **consumer's** own bit matters.

### 2.3c The `ctrl`/`ctrl_lo` field is not inert either

`HW-VALIDATED` (EXP-0089): bits **2/4 safe** in 13/14 compact-form contexts; bits **0/1/3/5/6
load-bearing** (fault or silent corruption); the **12-byte extended form is 0/8 safe, including a
genuine GPU hang**. Bits 0/1 are the only genuinely nondeterministic field observed across ~1200
executions in EXP-0086 + EXP-0089 combined. Treat the whole field as load-bearing.
- A different candidate (`CAND_A`, a register-select top bit that tracks first/second-read order
  across 7 independent compiles) was **null in every configuration** — adjacent/near/+4/+16
  instruction distance, ~40-value register pressure, and real `if`/`for` boundaries — across 7
  kernels, each with a positive control proving the harness *could* have detected corruption. A
  genuine negative result. `HW-VALIDATED` (EXP-0086).
- The field EXP-0086 chose as an inert control (`ctrl`/`ctrl_lo`) is **also not inert**: it faulted
  the GPU in 4/7 kernels and was silently wrong in 3/7. Own open question.

### 2.4 Implementer guidance

1. **Do not synthesize or normalize these bits.** Emit them exactly as they appear in a pattern you
   copied from compiler output for the same operand shape.
2. **Do not assume a wrong value is harmless.** The observed failure is silent, deterministic, and
   produces a zero — not a fault you can catch.
3. Treat every `db.json` descriptor whose text says "cache/last-use hint, NOT an op change" as
   `UNKNOWN` until that specific descriptor gets its own later-read test. The affected descriptors
   are listed in `EXP-0086/RESULTS.md`.

---

## 2.5 Other fields with the same silent-zero failure mode (EXP-0090)

The move encodings and the liveness bits are not the only fields that fail silently rather than
faulting. EXP-0090's hand-built programs surfaced two more:

- **`falu2` register-form requires `opflags=3`, not merely bit 0**, when BOTH operands are real
  computed values. **`opflags=1` silently zeroes `srcB`'s read.** `db.json` currently types this
  field as an opaque `mod`. `HW-VALIDATED` (EXP-0090).
- **`device_store`'s `extmode` byte = `2 x (source GPR)`** for ALU-forwarded stores — a concrete
  formula replacing EXP-0082's "implicitly supplied" note. `HW-VALIDATED` (EXP-0090).

**Pattern worth internalising: on this hardware, a wrong operand-field value usually produces a
silent zero, not a fault.** Assume nothing is inert until it has been tested with a later read.

## 2.6 What can and cannot be generated today (DRV-ISA-01 status)

`HW-VALIDATED` (EXP-0090, 3 of 4 hand-built whole programs, 24/24 cases, two byte-identical runs):
we can author and run non-trivial multi-instruction-family programs — an arithmetic dataflow chain
with immediate and integer operand sweeps, a memory round trip, and a control-flow program — each
matching an independent host-computed oracle.

**We cannot yet generate arbitrary programs.** Two concrete, named blockers:
1. **General load-to-ALU bridging** — `device_load`'s result could not be reliably fed into
   `falu2`/`falu2i` by independent construction (5+ falsified attempts). Only a direct
   store-forward and one verbatim `iadd2` anchor work.
2. **GPR-sourced moves** — see §1.0.

## 2.7 Both bit-level lifetime models are refuted (EXP-0099)

`HW-VALIDATED` (EXP-0099, commit `de4e4a81`, 35 cases, two runs, gates PASS). A pre-registered
adversarial test of **both** our database's model and the external engineer's model found each
wrong in a different way:

- **Our `db.json` 7-bit register-index model: REFUTED.** Encoding `falu2`'s register field as the
  literal value `67` (top bit set; low 6 bits = 3) still read **r3's** value, never the genuinely
  unwritten r67's zero — in all four decisive cases, both runs.
- **His `(bit15,bit19)` / `(bit31,bit20)` retention pairing: REFUTED.** With a later separate
  reader, the outcome depends **only** on `opflags` bit19/bit20 — identical whether the
  register-field top bit is 0 or 1.
- **Net:** the register field is **6 bits load-bearing, with a top bit that is HW-tested inert and
  whose role is `UNKNOWN`.** This reconfirms EXP-0086's `CAND_A` null result rather than explaining
  it away.
- **Registers 64–95 are `UNKNOWN` again** — removing the literal-index account leaves no validated
  addressing path for them in this family, despite EXP-0092's re-confirmed 96-GPR boundary.
- **`opflags` bit19/bit20 remain the genuine per-source control**, consistent with EXP-0090's
  `opflags` finding and with EXP-0086/0089's corruption results.

### UPDATE (EXP-0101, commit `2cf96b56`): blocker 1 SOLVED, blocker 2 re-characterized

**Load-to-ALU bridging works.** `HW-VALIDATED`, 29 cases, two byte-identical runs, every case
as pre-registered. The rule a compiler must follow:

| requirement | value |
|---|---|
| register a later `falu2`/`falu2i` references | **`device_load`'s `extmode` ÷ 2** (`extmode = 2 × target_register`) — the same formula EXP-0090 found for `device_store` |
| `dst_lo` / `dst_ext9` | **RULE ESTABLISHED (EXP-0141) — no longer "copy verbatim".** They carry **no register information**. `dst_lo = 1` **exactly**, and `dst_ext9` **bit 0 = 1**; that is three constrained bits across the nine the two fields span, the rest free. Correct: never derive them from the target register. Superseded: the old instruction to copy a compiler-observed `(1,1)` token — an emitter can now *choose* these |
| `falu2i` with a load-sourced operand | `mods` byte must be **`0xC0`** (bits 6+7 together; neither alone) |

Validated across target registers 3, 7, 16, 20 and both ALU forms, plus a compiler census where
11/11 emitted load→ALU pairs confirm the formula.

> **✅ EXP-0141 (2026-08-28) — `device_load`'s destination is now EMITTABLE, and the reachable
> range is bounded.** Exhaustive sweep of `extmode` at four target registers plus the full
> 512-value 2-D product, repeated under all 21 working `ld_format` codes:
>
> ```
> to land a load in register R:
>     extmode  = 2*R        bit 0 is a DON'T CARE
>     dst_lo   = 1          exact
>     dst_ext9 bit 0 = 1    upper bits ld_format-dependent
> ```
>
> **`extmode` values 0..127 all work and 128..255 all fail, exactly — so R is reachable only for
> R = 0..63. R ≥ 64 silently zeroes through this field** and must be reached another way. Two
> facts EXP-0101 could not establish: `extmode` bit 0 is free, and r64+ is unreachable here.
>
> One caveat, from a pre-registered refuter that *partially fired*: how many of `dst_ext9`'s
> **upper** bits are additionally don't-cares varies with `ld_format` (free for 16 codes, tighter
> for codes 3/7/9/13 and 39). `dst_ext9 = 1` is valid under all 21, so emit that.
>
> This is what took `device_load` and `device_store` from "decodable" to **emittable**, and it
> removes the last reason a generator had to copy compiled bytes rather than synthesize them.

> **⚠️ Correction with wide blast radius:** EXP-M4-13's `dst = dst_lo | (dst_ext9<<2)` formula —
> used by every prior experiment and by `tools/agx-isa/db.json` — **predicts the wrong register**.
> That, not the consumer route, was the real cause of EXP-0099's `ROUTE_LOAD` failure. Any claim
> resting on that formula needs re-examination.

**Blocker 2: we were probing the wrong instruction.** `reg_move`'s readback is completely
independent of the producer's value *and* of the producer's family: changing what is written to
the source register never changes what comes back. The content depends only on `src_reg`, is
register-pair-quantized (`reg` and `reg^1` read identically), and varies with the kernel's buffer
signature — the signature of a fixed per-kernel **preloaded/uniform-file slot**, not a corrupted
GPR read. `0x00000100` is simply that slot's content, not a sentinel. This also closes EXP-0087's
`byte+2=0x21` question: it reads the same uniform content and is **not** a real move. The candidate
real GPR move is EXP-0087's still-undecoded `byte0=0x2b`. `HW-VALIDATED` (EXP-0101).

### Original statement of the two blockers (superseded above)

`HW-VALIDATED` (EXP-0099): the consumer-route field does **not** explain the load-to-ALU blocker.
All 8 route values fail identically for a `device_load` → `falu2` consumer, while the paired
ALU-sourced control passes at all 8 — proving the harness and field wiring are sound. `opflags`
bit21 does not help either. GPR-sourced `reg_move` still fails, and now also fails to read a
`device_load`-written GPR. **New lead:** the failure returns an exact, reproducible `0x00000100`,
not literal zero as EXP-0090 reported.

## 2.8 The A18↔M4 lifetime contradiction is RESOLVED — it was operand PROVENANCE (EXP-0129) — `target: G16G`

`HW-VALIDATED` (EXP-0129, commit `873cb9c3`; two captures sha256-identical `9bcdb378…`; gates
re-run: `--selftest` 192 checks, `--seqtest` 4, `--captured` PASS). Source:
`experiments/EXP-0129-m4-lifecycle-boundary-probe/RESULTS.md`.

**The apparent A18↔M4 device difference was neither a device difference nor a dispatch-shape
effect. It was how the operand under test had been SEEDED.**

| operand seeded by | `cache = 1` | `cache = 0` | grid = 1 | grid = 4 |
|---|---|---|---|---|
| an **ALU** instruction | retains (`8.4078e-45`) | retains (`8.4078e-45`) | same | same |
| a **`device_load`** | `2.8026e-45` | **silent `0.0`** | same | same |

`EXP-M4-14`'s own literal anchor bytes break at **both** grid sizes. So `EXP-M4-14` (A18) and
`EXP-0119` (M4) differed by operand seeding, and **neither prior record was wrong.**
*(This supersedes the framing in `../evidence-classification.md` §3, which was written while the
contradiction was still open — see the correction note there.)*

**`ibitcount`'s release control is `srcdesc` bit 4** — bidirectional; bit 0 and bit 3 also break
the stored result; **all other free bits are inert over a 22-case sweep**. It is **NOT**
`cache`/bit 17, which stays independently inert even with bit 4 at its retaining setting.

**Both `falu2` signatures reproduce for `ibitcount`:** restore-on-rewrite (20.0 → 28.0) and
distance-invariance (0 / 1 / 4 intervening instructions).

> **Verdict: there is ONE underlying release concept, routed differently per instruction family.**
> An emitter must therefore look up the release control **per family** — `opflags` bit19/bit20 for
> the `falu2` family (§2.7), `srcdesc` bit 4 for `ibitcount` — and must not carry one family's bit
> position to another. EXP-0138 and EXP-0139 independently record the same warning for
> `falu_srcmod12b` and `iadd2.dst`.

**Bits 15/31 re-confirmed inert across four new axes:** real loop + if/else control flow, a
`device_load`-sourced operand, ~40-register pressure with highest live index r55, and b16/half
width.

⛔ **NEGATIVE, stated:** the **fragment stage is NOT reached** (two positive controls failed
within budget), and **the uniform-register operand class remains untested project-wide.**

## 3. Evidence status and open items

- **EXP-0087** (move synthesis): both runs closed, 49 cases each, 47/49 byte-identical across runs.
  `analysis.py` has a post-capture-discovered bug; per standing rule it was **not repaired in
  place** — a successor re-analyses the already-valid raw data with no recapture. See its
  `QUARANTINE.md`.
- **EXP-0086** (liveness): `run01` complete and gate-passing (135/135, selftest 16/16, seqtest
  14/14). `run02` was killed at 113/135 by a host interruption and is retained untouched under
  `QUARANTINE-run02-attempt1.md`; its 113 lines are byte-identical to `run01`, which is real but
  informal corroboration. **The formal two-run gate is NOT met** — `run01` alone is the promoted
  evidence and a successor must complete the pair.
- Open: literal bit-17 later-read test; `CAND_B` sweep across distance/pressure/control flow;
  `byte+2=0x21` disambiguation; the `ctrl`/`ctrl_lo` non-inertness; collapsing the five `reg_move`
  descriptors in `db.json`.
