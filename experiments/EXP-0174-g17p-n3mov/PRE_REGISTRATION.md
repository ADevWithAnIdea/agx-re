# EXP-0174 — PRE-REGISTRATION (frozen before the gated runs)

**Frozen:** 2026-08-30, before any case in `raw/g17p_20260830_run*` was dispatched.
**Target:** Apple A18 Pro / G17P, `users-MacBook-Neo.local`. Device identity is read from
the live device into `00_env.json` on every run and is never taken from a literal.

```
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: kernels/*.metal (authored by us) and the AGX machine code the public
  newLibraryWithSource: / MTLBinaryArchive API compiled FROM THEM; plus this repository's
  own committed evidence from EXP-0013/0086/0089/0090/0099/0101/0112/0128/0138/0140/
  0146/0157/0161/0165/0166/0168/0169/0170/0173.
Apple binary introspection: NONE
```

> **The instruction under test is GENERATED, not spliced.** Every one of its four bytes is
> computed by `harness/isa_helpers.n3_bytes()` from the bit positions `tools/agx-isa/db.json`
> declares for `n3_mov`, cross-checked against `isadb.assemble()` by `assert_geometry()`.
> No byte of it comes from a compiled shader. `kernels/probes.metal` exists only to provide
> compiled positive controls and is not on the path of any verdict below.

---

## 1. The question

`docs/compiler-readiness.md` and EXP-0173 §7.1 both name the same first blocker:

> **No emittable descriptor moves one GPR to a DIFFERENT GPR.**

`mov_zext16` is an in-place narrow of one register used as both source and destination.
`n2_op6` calls itself a catch-all bucket and is not HW-dispatch validated. `n3_mov` is the
candidate, and its three operand fields — `dst`, `srcA_reg`, `srcA_uni` — are all
`corpus-correlation` from EXP-M4-13, which is compile-only.

**Can this ISA move one GPR to a different GPR, and can we GENERATE that encoding without a
captured template?**

## 2. Hypotheses (falsifiable), and the frozen model

**H1 — `dst` is a destination-register selector.** `n3_mov` byte0 bits 4..7 select the GPR
written, over r0..r15.
*Refuter:* a dense `dst` sweep in which the written value lands in a slot other than the one
`dst` names, or in no slot at all, in a carrier whose ladder passes.

**H2 — byte+1 selects a 16-bit SOURCE HALF, not a 7-bit register plus a uniform flag.**
Frozen model: byte+1 = `2*S + hs`, where `S` (bits 1..7) is the source register with
**aliasing period 64**, and `hs` (bit 0) selects the source's low (0) or high (1) 16 bits.
This CONTRADICTS `db.json`, which declares `srcA_reg` = bits 0..6 and `srcA_uni` = bit 7.
*Refuter:* byte+1 = 0x13 not yielding the HIGH half of r9, or byte+1 = 128+2k not aliasing
to register k, or bit 7 behaving as a file selector rather than as source-register bit 6.

**H3 — byte+2 (`subform`) is an OP selector and byte+2 bit 3 releases the source.**
Frozen model: the MOVE op is `(b2 & 0x03) == 0x01` with `(b2 & 0xE0) == 0x00`; bit 3 (0x08)
additionally releases (zeroes) the source register; bits 2 and 4 are don't-care for the move.
*Refuter:* a value satisfying the mask that does not move, or a value outside it that does;
or bit 3 leaving the source intact.

**H4 — byte+3 (`companion`) selects the DESTINATION half, and the other half is PRESERVED.**
Frozen model: `hd = b3 & 1`; `b3 == 0x00` writes the destination's low half, `b3 == 0x01`
its high half, and in both cases the *other* half of the destination keeps its previous value.
Other `b3` values do not write.
*Refuter:* a destination half write that clobbers the other half, or `b3 >= 2` writing.

**H5 — a full 32-bit `r[i] = r[j]`, i != j, is GENERATABLE as two `n3` instructions.**
`X3 (2S+1) 01 01` followed by `X3 (2S+0) 01 00`, in either order.
*Refuter:* any (i, j) pair for which the host-computed 16-register prediction fails.

**THE FROZEN ORACLE.** For `X3 b1 b2 b3` with `(b2 & 0x03) == 1`, `(b2 & 0xE0) == 0`,
`b3 ∈ {0x00, 0x01}`:

```
S  = (b1 >> 1) mod 64        hs = b1 & 1        hd = b3 & 1
v  = (state[S] >> (16*hs)) & 0xFFFF
state[dst] = (state[dst] & ~(0xFFFF << (16*hd))) | (v << (16*hd))
if (b2 & 0x08) and S != dst: state[S] = 0
```
`state` is the HOST-KNOWN register state at block time. Cases outside the mask carry
`predicts = "no_model"` and are recorded structurally; they can only ever falsify, never
confirm.

## 3. Independent / controlled variables

| | |
|---|---|
| independent | exactly one of `dst`, byte+1, byte+2, byte+3 per case (the generation arm varies the (dst, src) PAIR, which is the point of that arm) |
| controlled | carrier kernel, its `_agc.main` length, the seed table, the sentinel and dump code, `extmode`, grid/threadgroup, the pinned `db.json`/`isadb.py` snapshot |
| observable | the full 16-GPR dump + PRE sentinel + POST sentinel + a 28-word tail poison region, out of a buffer pre-filled with `0xDEADBEEF` |

**Rule 3(a) compliance — the observable does not co-vary with the field under test.** The
read-back is a FIXED list of 16 stores, `store_word(W_REG0 + 4r, r)` for r = 0..15, identical
in every case of every arm. No store's `data_reg`, `index_reg` or `idx_off` is a function of
any swept value. This is the specific defect EXP-0168 found in EXP-0140 and it cannot occur
here: for a destination-register field the whole effect is *where* the value lands, so the
observable must be the set of slots, and it is.

**Rule 3(b) compliance.** `rt_ok` is recorded per case and is used for NOTHING. No verdict
cites a round trip.

## 4. Carriers

Two register plans, which are two genuine carriers because they differ **in the dimension
`dst` controls** — the register plan itself:

| plan | read-back index reg (BLIND slot) | pad reg (MASKED slot) | sentinel | pre-scratch |
|---|---|---|---|---|
| `idx15` | r15 | r13 | r12 | r11 |
| `idx7`  | r7  | r6  | r12 | r11 |

The blind slot is destroyed by the read-back path (`store_word` re-zeroes its index register
before every store, so a write the block made to it cannot relocate the dump). The masked
slot is rewritten with its own seed by the post-block padding. **The two plans are disjoint
in both**, so every one of the 16 slots is truly observed in at least one carrier, and no
verdict may be drawn from a blind or masked slot — every case records `blind` and
`pad_masked` and the analysis excludes them explicitly.

This directly re-tests EXP-0168's claim that "a write whose 4-bit destination nibble is 15 is
discarded": in `idx7`, r15 is not touched by the read-back path.

## 5. Arms (frozen)

| arm | field / question | coverage |
|---|---|---|
| `A/dstmap` | `n3_mov.dst` | dense 0..15, both plans, at the move form |
| `B/srcmap` | byte+1 (`srcA_reg` + `srcA_uni`) | dense 0..255, both plans — 7-bit register x half-select x the alias band |
| `C/half` | source half + destination half | 4 combos x wide source x wide destination, both plans |
| `D/subform` | `n3_mov.subform` (byte+2) | dense 0..255 x b3 in {0x00, 0x01}, both plans |
| `E/companion` | `n3_mov.companion` (byte+3) | dense 0..255 x b2 in {0x01, 0x09}, both plans |
| `F/gen32` | H5 — GENERATED full 32-bit copy | all 240 ordered (dst != src) pairs, both plans, both instruction orders |
| `G/genhalf` | GENERATED half moves | dst 0..15 x src 0..15 x hs x hd, both plans |
| `H/release` | byte+2 bit 3 | release with a wide source, with S == dst, both plans |
| `X/falsify` | see below | |

## 6. Falsifiers (pre-registered to FAIL)

1. **`X/lownib`** — byte0's LOW nibble set to each of 0x0..0xF except 3, with byte+1/+2/+3
   unchanged. Only nibble 3 may produce the predicted move. This falsifier is chosen AWAY
   from every swept field: `dst` lives in byte0's HIGH nibble, so the low nibble carries no
   field under test. (EXP-0168 defect #2 was a falsifier that clobbered a byte carrying both
   the opcode and the swept field, making it confounded.)
2. **`X/narrow`** — byte+2 := 0x00 at an otherwise valid move encoding. Must NOT move the
   source; must perform the in-place narrow `r[dst] &= 0xFFFF` (reproducing EXP-0161).
3. **`X/b3hi`** — byte+3 := 0x02, 0x04, 0x08, 0x10 at the move form. Must NOT write.
4. **`X/b2hi`** — byte+2 := 0x21, 0x41, 0x81 (mask bit set). Must NOT move.
5. **`X/selfmove`** — dst == src. Declared UNDECIDABLE in advance: a correct self-move and a
   no-op are indistinguishable in this observable. It is scored `undecidable`, never `ok`.

If every case passes, the sweep proves nothing about its own detection power; the gate below
requires the falsifiers to FIRE in every run.

## 7. Known confounders and how each is handled

| confounder | handling |
|---|---|
| **`device_load` is ASYNCHRONOUS on G17P (DEF-0169-1)** — with no wait it landed 0,0,0,0,2,5,8,8 of 8 seed registers depending only on filler length, which FABRICATES movement | **there is no `device_load` anywhere in this experiment.** Every register is seeded with `mov_imm` / `falu2i` immediates |
| the read-back buffer cannot distinguish "wrote 0" from "did not run" | poisoned with `0xDEADBEEF` before every dispatch; an all-poison read-back is `invalid_poison` and is re-run, never a silent zero |
| a contaminated dispatch reporting `STATUS OK` and writing nothing (EXP-0160 saw 25) | PRE sentinel (memory, written before the block), POST sentinel (materialized after the block by `mov_imm`, a path the instruction cannot influence), and a 28-word tail poison region; any failure is `invalid_*` |
| a sibling agent's GPU reset splashing in | `InnocentVictim`-class strings segregated and re-run; the OS fault-classification string recorded on every non-`ok` case |
| an unknown byte+2/byte+3 selecting a LONGER instruction that eats the dump | 8 bytes of self-restoring padding (`mov_imm(pad, SEED[pad])`) after the block; an over-consumption that reaches the dump shows as a corrupted/poisoned read-back and is `invalid_*` |
| the pinned toolchain drifting | `work/frozen/{db.json,isadb.py}` sha256-pinned in `CAPTURE_CONTRACT.json`; `isa_helpers._find_isadb()` has **no path-search fallback** and raises if the pin is absent. The neo's shared `~/agxre/tools/agx-isa/db.json` is stale (1036 fields vs 1062) |
| the carrier's own blind/masked slots | recorded per case and excluded explicitly; the second plan covers them |
| register aliasing (mod 64 on the ALU, EXP-0112; period 16 on the fragment stage, EXP-0172) | measured here rather than assumed — arm `B/srcmap` sweeps byte+1 over its whole 0..255 range, which spans two alias bands |

## 8. Gate for promotion

Two gated runs, `run01` forward order and `run02` reverse order.

- **≥ 99% per-value cross-run agreement** on the observed 16-register dump, AND
- **movement ≥ 2x the disagreement count**, AND
- dense coverage for every w ≤ 8 field, AND
- every falsifier FIRING in every run, AND
- no case counted whose `validity != "valid"`, AND
- for `hardware-run`: at least two carriers differing in the dimension the field controls.

`fault` is never concluded from a single observation: majority-of-3 minimum, and adjudicated
offline from the poisoned buffer and sentinels where possible.

Verdict labels come from `docs/evidence-classification.md` and nothing else. A field whose
sweep is inconclusive is reported `corpus-correlation` or `untested`, never rounded up.

## 9. What would make this experiment report a NEGATIVE

If no `(byte+1, byte+2, byte+3)` combination moved a value from one GPR to a different GPR,
or if the movement could not be generated without copying bytes from a compiled shader, the
result is a documented negative on the register-allocator blocker and is reported as the
headline. The pre-freeze calibration already indicates otherwise, and the gated runs exist to
test the frozen model above rather than to look for a form.
