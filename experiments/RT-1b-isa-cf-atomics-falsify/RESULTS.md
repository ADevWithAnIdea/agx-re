# RT-1b RESULTS — falsify control-flow / calls / memory / atomics (2nd overlapping pass)

All results are **HW-validated**: spliced bytes run on the real A18 Pro GPU via the **independent
one-shot** harness (`rt1b_run`, fresh `MTLDevice` per dispatch — a different code path from the
persistent runner both RT-1a passes used). Values are verbatim runtime outputs (`raw/`).

## Verdict summary

| # | Claim under test | Verdict |
|---|---|---|
| 1a | memory index register = **byte+5** | **CONFIRMED** (independent harness/ramp/indices) |
| 1b | byte+6 = inert padding | **CONFIRMED** |
| 1c | byte+1 = address-space (bit1 = threadgroup) | **CONFIRMED** (loads & stores) |
| 1d | immediate index-offset byte+9 bit7 (+1) / +10 (+2·v) / +11 (+512·v) | **CONFIRMED**; refinement: field is **signed**, compiler uses it for `a[i-1]` |
| 1e | vectors = one load moving N words; byte+5 ≠ "count" | **CONFIRMED** (width is byte+8/+12) |
| 2a | predication compare producers `0x0a`/`0x02`; **compare immediate = byte+3** | **CONFIRMED** (boundary moves +2 per +2) |
| 2b | select `0x05` (psel) / `0x16` (sel) | **CONFIRMED** (carry the select values) |
| 2c | "flipping `0x0a`↔`0x02` inverts the condition" | **DISCREPANCY (mechanism)** — naive byte0 swap → malformed output, not a clean invert |
| 2d | backward jump `0f 00 54 <off40>` signed LE PC-relative | **CONFIRMED** (off40=−262; zeroing → contained CMDBUF_ERROR) |
| 2e | adversarial CF: nested / break / continue / early-return | **CONFIRMED** (all match CPU) |
| 3a | CALL `0f 05 … 8f … 56 <off40>`, **target = call+4+off40** | **CONFIRMED** (two call sites → identical target −64) |
| 3b | off40 is the load-bearing target | **CONFIRMED** (corrupt → wrong result / HANG) |
| 3c | frame marker `43 00 00 01`; 3-level nested; recursion→loop; many-arg spill | **CONFIRMED** (all semantics correct) |
| 4a | atomic_rmw op selector at **byte+12** (12-op table) | **CONFIRMED** (10/10 ops exact) |
| 4b | cmpxchg = `0x24` | **CONFIRMED** (match & mismatch cases) |
| 4c | device vs threadgroup = byte+1 bit1 | **CONFIRMED** (tg atomic byte+1=0x02/0x03; splice device→tg breaks it) |
| 4d | contended atomics (1024 threads) | **CONFIRMED** (add→1024; op-splice add→max→32, matches EXP-0018) |
| 4e | barrier `0x07`, byte+3 = fenced memory scope (`0x61` tg) | **CONFIRMED** (splice `0x61`→`0x00` → 65 lanes read stale 0, STATUS OK) |
| 5 | large kernel tokenizes to ~0 leftover (DB README) | **DISCREPANCY** — strict tokenize halts @4th instr; ~86% named / ~91% resync; CF `0x0f` family + `0x07`(byte+2≠0x54) + `0x32` undecoded |
| 5' | large-kernel semantics | **CONFIRMED** (256/256 lanes == CPU ref; deterministic) |

**Net:** the memory byte+5 fix and the control-flow / call / atomic / barrier encodings all hold under
an independent 2nd pass. Two findings for the orchestrator: a small **mechanism** caveat on 2c, and a
re-confirmed **census/coverage** gap (item 5) — no *mis-decode* (wrong-field) regressions found.

---

## Item 1 — Memory (independent re-proof of the byte+5 fix) — CONFIRMED

Harness: `t_mem.py` / `t_memoff.py` / `t_memvec.py`. Ramp `a[j]=0xA000+j`, indices `{41,7,83,19}`
(different from RT-1a's `100·j+3`, `{40,3,77,12}`). Key gotcha reproduced: uniform (thread-invariant)
loads hoist into the constant/uniform program, so the index must be **gid-dependent** (`idx[gid*4+k]`)
to keep the load in `_agc.main`.

**byte+5 = INDEX REGISTER (CONFIRMED).** On the `bank` a-load (`6700460a02802000510100404600`),
sweeping byte+5 reads the *contents* of GPR r0..r4 as the index:
`0x00→a[41]=i0, 0x01→a[7]=i1, 0x02→a[83]=i2, 0x03→a[19]=i3, 0x04→a[0]`. bit7 (`0x80`) is a separate
flag (`0x80/81/82/83` == `0x00/01/02/03`) — low bits = register number. (`raw/t_mem.log`.)

**byte+6 = INERT (CONFIRMED).** Sweeping `0x00..0xff` never changes the loaded value.

**byte+1 = ADDRESS SPACE (CONFIRMED).** `0x00`/`0x04`→device (a[41]); `0x01`/`0x02`/`0x03`→0
(threadgroup/uninitialized). Threadgroup `tg` kernel: tile load byte+1=`0x02`, tile store byte+1=`0x02`,
device load/store byte+1=`0x00`/`0x10` (`raw/t_memvec.log`). Splicing a device load `0x00`→`0x02` returns 0.

**Immediate index-offset field (CONFIRMED + refinement).** On the single-index load with byte+5 pinned
to r0 (=41): byte+9 bit7 → +1 (a[42]); byte+10 → **+2 per unit** (`0x01→a[43], 0x02→a[45], 0x04→a[49],
0x08→a[57], 0x10→a[73]`); byte+11 → **+512 per unit** (`0x40→a[41], 0x41→a[553]`). **New refinement:** the
field is **signed** — replicating `minus1`'s bytes (`byte+9/10/11 = 89/ff/5f`) gives a[40] (delta **−1**),
and the compiler actually **uses** it for `a[gid-1]` (its load is `67104400010120005189ff5f4600`, offset
field populated), whereas `a[gid+1]` leaves it at baseline. So the doc's "compiler leaves idx_off=0" is
true only for positive offsets folded into a prior ALU op; for a **negative constant** the compiler
emits it in the load's signed offset field. (`raw/t_memoff.log`.)

**Vectors (CONFIRMED).** scalar/uint2/uint4 loads: byte+5 = `0x01/0x02/0x04`, byte+8 = `0x51/0x59/0x57`,
byte+12 = `0x46/0x48/0x40`. byte+5 tracks the index register (=rN, because the N-word destination occupies
r0..r(N-1) so `gid` lands at rN — proven a register selector by the bank sweep, **not** a count); the true
vector width lives in byte+8/byte+12. `float4` = **one** `0x67` load + **one** `0xe7` store move 4 words
([1..8] correct). (`raw/t_memvec.log`.)

## Item 2 — Control flow — CONFIRMED (one mechanism caveat)

Harness: `t_cf.py`.

**Compare immediate = byte+3 (CONFIRMED).** `thresh` (`gid<4?100:200`, grid=8) baseline `AAAABBBB`.
Sweeping the `0x02` compare byte+3 moves the active-lane boundary monotonically: `0x82→2, 0x84→4,
0x86→6, 0x88→8` (i.e. boundary = byte+3 & 0x7f, +2 per +2). Same on `ifdata`. byte+1/byte+2 are the source
operands (differ between kernels because one compares `gid`, the other a loaded reg); byte+4 is the
compare-mode/negate (a `0x22`→`0x26` splice inverts the pattern).

**Selects `0x05`/`0x16` (CONFIRMED).** `thresh` uses psel `0x05`, `ifdata` uses sel `0x16`. Splicing
psel byte+3 changes the "else" value (`0xc8=200`→`0x00→0`, `0xfe→254`).

**⚠ 2c mechanism caveat.** The doc says "flipping `0x0a`↔`0x02` inverts the condition." A **naive byte0
swap** `0x02`→`0x0a` on `thresh` produces **malformed output** (`????????`, not 100/200), because
`0x0a` (icmp_pred) and `0x02` (iminmax/cmpsel) have **different operand layouts** — swapping only byte0
yields an invalid instruction, not a cleanly-inverted condition. The two opcodes *are* the two compare
producers as documented, but "invert by swapping them" is not a reliable operation; condition inversion
is really via the byte+4 compare-mode / result-negate fields. Minor mechanism note, not a field error.

**Backward jump `0f 00 54 <off40>` (CONFIRMED).** `loopsum` (triangular sum) is **strength-reduced to a
closed form** (no loop) — expected. `loopbig` keeps a real loop: back-edge `0f 00 54 fa fe ff ff ff ff 00`
@+0x138, off40 = **−262** (signed LE), target ≈ +0x3c (loop head). Zeroing the offset → self-jump →
**contained `CMDBUF_ERROR`** (GPU watchdog), recovery OK — proving byte+3.. is the taken, load-bearing
back-edge. (Doc said "hang"; the watchdog-terminated contained error is the same phenomenon.)

**Adversarial (CONFIRMED).** nested if/else `[1..8]`, break `[0,0,3,10,45]`, continue `[0,0,2,6,20]`,
early-return `[7,7,7,7,0,0,0,0]` — all match the CPU reference. Data-dependent divergence works.

## Item 3 — Function calls — CONFIRMED

Harness: `t_call.py`, `dbg_call2.py`.

**CALL target = call+4+off40 (CONFIRMED, strong).** `twocall` has two sites to the *same* helper:
`@+0x24` (`…8f 00 56 98 ff ff ff ff`, off40=−104) and `@+0x38` (`…8f 00 54 84 ff ff ff ff`, off40=−124).
Both compute `call+4+off40 = −64` → **identical target**, and the off40 delta (20) equals the call-site
distance. (byte+6 differs `0x56`/`0x54` = the last-use/cache hint bit, EXP-0038.) (`raw/t_call_targets.log`.)

**off40 load-bearing (CONFIRMED).** Corrupting `one`'s off40 byte+7 `0x98`→`0x9a` → wrong result
`[0,0,0,0]`; `0x98`→`0xa8` → HANG. (`raw/t_call.log`.)

**ABI / structure (CONFIRMED via semantics).** frame marker `43 00 00 01` present; `chain` (3-level
`mid→leaf,leaf`) = `8A+2` `[10,18,26,34]`; recursion→loop `recur = A·1.1^N` `[2.0,2.2,3.221,5.1875]`;
many-arg spill `sum(A[0..11]) = 78`. All correct → the arg/return register convention (r10+/r10, doc-inferred)
is *consistent* end-to-end. (The standalone `RETURN 8f` lives in the callee region, outside `_agc.main`;
`0x8f` appears here only as byte+4 of the CALL, as the doc notes — not independently field-decoded this pass.)

## Item 4 — Atomics + barriers — CONFIRMED

Harness: `t_atom.py`.

**op selector @ byte+12 (CONFIRMED, 10/10).** Single-thread `rmw1`, `op(c=12, in=10)`:
`0x20 add→22, 0x36 sub→2, 0x22 and→8, 0x2c or→14, 0x3e xor→6, 0x3c xchg→10, 0x28 smax→12, 0x2a smin→10,
0x38 umax→12, 0x3a umin→10` — every code matches the doc's table exactly.

**cmpxchg `0x24` (CONFIRMED).** `c=5,desired=99`: expected=5→swap (c=99, ok=1); expected=7→no-swap
(observed=5, c=5).

**device vs threadgroup byte+1 bit1 (CONFIRMED).** device atomic byte+1=`0x11` (bit1=0); tg atomics
byte+1=`0x02`/`0x03` (bit1=1). Splicing `rmw1` byte+1 `0x11`→`0x13` (set bit1) redirects to tg space →
device counter no longer updates (`[10,12]` vs baseline `[12,22]`).

**contended (CONFIRMED).** 1024 threads add 1 → counter **1024**. op-splice add→umax/smax/xchg → **32**,
exactly reproducing EXP-0018 (per-simdgroup reduce = 32-lane sum, then one RMW; a spliced max leaves the
reduced 32 as the RMW operand).

**barrier byte+3 mem-scope (CONFIRMED).** `race` (grid=256): barrier `07 04 54 61 09 00` (byte+3=`0x61`).
Baseline 256/256 correct; splicing byte+3 `0x61`→`0x00` → **65 lanes read stale 0**, STATUS OK (silent
corruption) — the exact G-1 hazard; byte+3 is the load-bearing fenced scope.

## Item 5 — Stress kernel: census + semantics

Harness: `t_stress.py`, `t_census.py`. `big` = deep data-dependent CF + a noinline call + device & tg
atomics + 24 live regs (spill), 4052-byte `_agc.main`, grid 256.

**Semantics CONFIRMED.** GPU output matches a full CPU simulation (int32-wrapping, per-threadgroup atomic
sum, call, deep CF) on **256/256 lanes**; device counter = 256; deterministic across runs.

**⚠ DISCREPANCY — tokenization is NOT "~0 leftover" on a realistic kernel.**
- **Strict `isadb.disassemble` halts at the 4th instruction** (`@+0xa`, `0x07 22 02 00 …`): a `0x07`
  fence/barrier-family word with **byte+2 = `0x02`** (not `0x54`) that has **no length rule** →
  `instr_length` returns None → 0.2% "covered". (The DB's `0x07` handling gates on byte+2==`0x54`.)
- **Alignment-preserving census:** **86.3% descriptor-named**, **8.9% aligned-but-unnamed** (known length,
  no matching descriptor), **4.8% no-length-rule → resync**. So ~91% is structurally recognized, ~14% is
  not descriptor-decoded.
- **Real (aligned) DB gaps, not resync noise:** the control-flow / exec-mask **`0x0f` family** (13
  length-only + 3 no-length: the `0f 00` jump, `0f 05`/`0f 01` mask push/else, `0f 06` pop, `0f 80`
  indirect — a near-whole-family gap); the **`0x07` byte+2≠`0x54`** fence variant (15× no-length,
  incl. the first halt); **`0x32` carry-generate** (11× aligned-unnamed — EXP-0038 documents it but its
  descriptor is *staged, not merged*, so its instances don't match); plus smaller `0x17`/`0x03`/`0x22`.

This **re-confirms RT-1a's item-5 finding** (they measured 83.7%; fixes since bring it to ~86% named /
~91% resync) and refutes the DB README's "tokenizes all our shaders cleanly (0 leftover)" and the ISA
README's "no whole undecoded instruction family remaining" — the CF/exec-mask family is substantially
undecoded in the machine-readable DB (even though its prose semantics are documented). No *mis-decode*
(wrong-field) regressions were found — this is a **coverage** gap, not a correctness bug.

## Bottom line for the orchestrator
- **byte+5 memory fix HOLDS** under a fully independent harness (one-shot fresh device), fresh ramp/indices,
  and edge cases (multi-register bank, negative/signed offset, threadgroup space, uint4 vectors). byte+6
  inert, byte+1 space, and the signed immediate offset field all confirmed.
- **Control-flow, calls, atomics, barriers all CONFIRMED.** Strongest new evidence: two-call-site target
  identity (`call+4+off40`), the 10/10 atomic op table, and the 256/256 CPU-matched stress kernel.
- **Two things to fix in the tooling/docs (both already known / partially flagged):**
  1. Soften the ISA-README claim "flipping `0x0a`↔`0x02` inverts the condition" — a raw opcode swap is
     malformed; inversion is via the byte+4 compare-mode/negate.
  2. Reconcile the DB-README "tokenizes cleanly / 0 leftover" claim with reality: strict tokenize halts on
     a `0x07` byte+2=`0x02` fence variant; the `0x0f` CF/exec-mask family and `0x32` carry-gen (staged,
     unmerged) are the dominant undecoded leaders. Merge the CF-family + `0x32` + `0x07`-byte+2 length/desc
     rules if "0 leftover" is to be claimed.
