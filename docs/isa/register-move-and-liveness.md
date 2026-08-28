# Apple9 Register Move & Register-Liveness — Implementer Notes

**Status: URGENT CORRECTION (2026-08-28).** This chapter exists because an external compiler
engineer, building a NIR→Apple9 backend from this repository, reported two blocking problems: he
could not get a basic register-to-register move to work, and he believed the ISA carries a register
lifetime mechanism that our docs denied. **Both reports were correct.** Two experiments
(`EXP-0086`, `EXP-0087`) were run to check our own claims; both found our documentation wrong or
unproven in a way that would silently corrupt generated code.

Target: **Apple M4 / G16G**, local host, `HW-PROBE + OWN-SHADER` splice evidence. A18 Pro/G17P is
`INFERRED`-by-family; its validation is deferred until the device is available.

---

## 1. Emitting a register-to-register move

### 1.1 The rule (use this)

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

### 2.3 Exact scope — read before generalizing

- The bit proven to corrupt is a bit **in the same conceptual role and the same float-ALU family**
  as the literal `0x54/0x56` field — it is **not** the literal bit 17.
- **The literal bit 17 could not be tested**: in every family it could be compiled into, splicing
  proved bit 17 is part of the **opcode** (`opsel`), not a free bit. `0x54`/`0x56`/`0x18`/`0x38`
  are therefore **`UNKNOWN`**, pending their own later-read test — **not** confirmed inert.
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
