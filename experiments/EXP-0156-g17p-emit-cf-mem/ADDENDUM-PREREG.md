# ADDENDUM PRE-REGISTRATION — EXP-0156, arm `tgac141`
## Removing the carrier confound from the `tg_addr_compute` cross-target claim

**Frozen 2026-08-30, BEFORE this arm was dispatched to the GPU, and after — and only
because of — what the primary `tgac` arm found.** It is an adversarial test in the sense of
`CODEX.md` §8 ("falsify before promoting"), added because the primary result is
load-bearing.

## Why this arm exists

The primary `tgac` arm ran **EXP-M4-14's own `k_thr.metal`, byte-for-byte**, and gated
cleanly on G17P (two runs, 100.0% exact cross-run agreement, 0 hangs, 0 baseline
failures). It found byte0 accepting **104 of 256 values, including both `0x1c` and
`0xfc`** — i.e. **EXP-M4-14's A18 record reproduces**.

The M4 record that contradicts it, **EXP-0141 H5** ("of all 256 values only `0x1c` … leaves
the tile dataflow correct; `0xfc` does not reproduce"), was **not measured on that
kernel**. `experiments/EXP-0141-m4-emit-mem/kernels/tg_tile.metal` is a *different*
carrier: lane 0 fills the whole 256-entry tile in a loop and every lane then reads
`tile[(li+128)&255] + tile[(li+37)&255]`, with the op at **+422** rather than +46.

So the two disagreeing records differ in **both the target and the carrier**. Reporting a
G16G↔G17P hardware divergence from them would be **confounded**, and this experiment will
not do that without removing the confound.

## The one direction still available

The M4 is retired for GPU work, so re-running `k_thr.metal` there is out of scope. The
symmetric move is available: **run EXP-0141's own carrier, byte-for-byte, here on the
G17P.**

`kernels/tg_tile_141.metal` is `experiments/EXP-0141-m4-emit-mem/kernels/tg_tile.metal`
copied unchanged. A compile-only pilot on the neo (no GPU dispatch) shows it produces
`_agc.main` of **494 bytes** with `tg_addr_compute` at **+422** (`1c 02 00 00 00 00`) and
`threadgroup_barrier` at **+428** — **exactly the offsets EXP-0141's `sweepdefs.py`
records for the M4**, so the two are the same program.

## Hypotheses, decided now

**HA (target-driven).** byte0's accepted set on G17P is wide on this carrier too
(materially more than the single value `0x1c`), and in particular `0xfc` reproduces.
⇒ the difference is the **TARGET**: G17P accepts byte0 forms that G16G rejects, and the
corpus's only live cross-target contradiction is real.

**HB (carrier-driven).** byte0's accepted set on G17P is on this carrier essentially
`{0x1c}` (or a small neighbourhood of it), matching EXP-0141's M4 result.
⇒ the difference is the **CARRIER**, not the target; EXP-0141's M4 measurement and
EXP-M4-14's A18 measurement are both correct on their own programs, and the claimed
divergence **dissolves**. This would be the more valuable outcome, because it retires a
standing contradiction.

**Both are pre-registered. Neither is the "hoped-for" answer**, and whichever way it falls
the primary arm's numbers stand unchanged — only their *interpretation* moves.

*Refuter for the arm as a whole:* the unmutated carrier failing its own host oracle, or
its falsifier matching. Either means the carrier is not live here and nothing is concluded.

## Method

Identical machinery to the primary arm: same-length in-place single-byte splices at +422,
dense over all 256 values of byte0 and of byte+1, plus the two adjudicated values `0x1c`
and `0xfc` called out as their own cases. Host-computed oracle recomputed from the MSL
(`tile[i] = a[i]+1`, `o[li] = tile[(li+128)&255] + tile[(li+37)&255]`, `a[i] = i`),
never read off a GPU run. **This carrier does carry an integrity sentinel** (`o[256] =
0xA5A5A5A5`), which `k_thr.metal` cannot — so the addendum is, in that one respect,
*stronger* evidence than the primary arm.

Two gated runs, new run ids (`g17p-20260830-t141a` / `t141b`), never reused, **held under
the GPU lease** (the orchestrator's directive for this specific test), gated on identical
accepted-value sets.

## Clean-room

```
Clean-room provenance: HW-PROBE + OWN-SHADER
Inputs inspected: our own MSL (kernels/tg_tile_141.metal, authored by this project as
                  EXP-0141's carrier and reused byte-for-byte) and the machine code
                  compiled from it
Apple binary introspection: NONE
```

---

# ADDENDUM PRE-REGISTRATION §2 — arm `jump_cond.*@NAT`
## Measuring `jump_cond`'s scope bytes in a program that still computes the right answer

**Frozen 2026-08-30, BEFORE this arm was dispatched**, after the primary `jump_cond` arms
gated.

## Why

`a09` sweeps `jump_cond.cf_scope` and `.reserved` densely at the two **poison** offsets.
That worked — the liveness gate fired, and every one of the 1024 cases behaved the same
way (branch taken ⇒ the output store never runs) — but the only observable there is
**taken vs not-taken**. "Inert" against that observable is a weaker statement than
EXP-0140's promotion of `jump.branch_ctrl`, which was inert in a program that produced its
**exact correct output**.

## Arm

Sweep the same two bytes densely (all 256 values each) at the **natural** offset `0x40`
under `n = 0`, where the guard is uniformly true, the branch **is** taken, and it lands
where the compiler intended — so the program produces the exact host-computed fall-through
oracle `a[tid] − 3 = [7,17,27,37,47,57,67,77]`.

**Prediction:** every value reproduces the fall-through oracle exactly.
**Refuter:** any value that changes the output, or that makes the store vanish.

Appended after every existing arm so **no frozen case index moves**; the already-captured
runs remain joinable. Two gated runs, new ids (`g17p-20260830-jcn1` / `jcn2`), under the
GPU lease (CF arms are the hang-prone class).
