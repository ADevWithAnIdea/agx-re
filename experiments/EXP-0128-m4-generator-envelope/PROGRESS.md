# PROGRESS -- EXP-0128 M4 generator envelope

Append-only. One entry per milestone, timestamped, so a kill costs at most
one milestone.

## Milestone 0 -- setup (2026-08-28)

- Directory created: `experiments/EXP-0128-m4-generator-envelope/`.
- Pinned repository revision: `cf544b4dd1fb37047c7cfee6a70a0d1a87628666`
  (working tree had unrelated untracked files from other in-flight
  experiments -- not our concern per SUBAGENT_BRIEF.md's HEAD-drift rule).
- Read: CLAUDE.md, CODEX.md, SUBAGENT_BRIEF.md, EXP-0112 (generator.py,
  isa_helpers.py, families.py, cf.py, casematrix.py, RESULTS.md,
  PRE_REGISTRATION.md, run.py, verify.py, baseline.py, harness/,
  kernels/), EXP-0101 RESULTS.md (load-to-ALU bridge), EXP-0113 RESULTS.md
  (register-file model, reg_move_c9 negative), EXP-0115 RESULTS.md
  (branch-reach checkerboard, zero forward slack, non-determinism),
  EXP-0105 RESULTS.md (falu2/falu2i register aliasing), EXP-0090
  isa_helpers.py/programs.py/diagnostics/redecisive.py (device_load->
  device_store direct-forward addr_mode=0x56, finding_3), tools/agx-isa/
  db.json's iadd2 entry (scattered srcB note, "up to 96 regs" dst note).
- `work/pilot/` created inside this experiment dir (never outside the repo,
  never `/tmp`) for the disclosed pre-freeze pilot phase below.

## Milestone 1 -- pilot phase: iadd2 register-mode decoding (item c)

Built `work/pilot/bin/shdump` + `work/pilot/bin/agxrun` (our own read-only
tool sources, compiled fresh into this experiment's own work/ dir).

**Differential-compilation recon** (compile small int-add MSL kernels with
varying register pressure, disassemble with `tools/agx-isa`'s own
`isadb.disassemble`, correlate compiled iadd2 bytes against the
independently-known register assignment of each `device_load` via
EXP-0101's own `extmode/2 == target register` formula): found the
compiler-natural chain shapes are contaminated by (a) address-computation
adds sharing iadd2's own byte0/match bits, (b) a genuinely different
multiply-add tail shape (srcA=0x8c), and (c) at least 3 distinct
register-mode tail bytes depending on chain position (0xa8/0x17/0x05,
0xa8/0x15/0x01, 0xe8/0x16/0x05) -- differential compilation ALONE did not
cleanly isolate the register-encoding formula (matches db.json's own
hedge: "compiler reg-alloc prevents clean single-bit isolation").

**Decisive follow-up: independent HW construction bypassing device_load
entirely (`mov_imm`-seeded GPRs).** Built minimal splice programs:
`mov_imm(r0,V0); mov_imm(rN,V1); iadd2(dst=D, srcA=0xa8, srcB=(reg_hi=0,
imm=4*N,imm_hi=0,ext=0), tail=(0x17,0x05), opmode=2); device_store(D)`.
Result: for the ONE clean, natural byte pattern (srcA=0xa8 constant,
srcB_reg_hi=0, srcB_ext=0), **`srcB_imm = 4*N` selects register N as the
SECOND operand; the FIRST operand is ALWAYS register 0, regardless of
`dst`** -- decisively confirmed by 3 independent constructions
(testB: dst==one of the operands' own register, still reads r0+r2, not
self-add; testA: dst unrelated to either operand, r0 unwritten (~0) +
r2(decoy)=99 exactly) that individually refute the two live alternative
hypotheses ("srcA implicit = dst", "srcA hardwired = 0"). Swept N=0..15
(the full range `mov_imm`'s 4-bit `dst` field can directly populate),
**16/16 exact matches** (`r0+rN` for every N, both addsub polarities not
yet separately swept -- see RESULTS.md).

**Bounded negative, also decisive:** chaining 2+ such register-mode iadd2
instructions back-to-back (even targeting different `dst` registers, even
with an inserted `scoreboard_fence` between them) reproducibly ZEROES the
result. Isolated single instances are solid; sequences are not (yet)
understood -- reported as a first-class gap, not swept under.

Not yet explored / explicitly out of scope for this milestone: N>15 (no
validated way to seed r16+ except `device_load`, which reopens the
load-forwarding-vs-GPR ambiguity this pilot phase specifically bypassed);
whether a DIFFERENT `srcA` byte value unlocks a different fixed first
operand; `addsub=0` (subtraction) polarity.

## Milestone 2 -- pilot phase: load-direct-to-store (item a)

Located EXP-0090's own `finding_3` (`diagnostics/redecisive.py`): a
`device_load` (addr_mode=0x44) immediately followed by a `device_store`
with **`addr_mode=0x56`** (not the usual `0x54` ALU-forwarded form),
`extmode=0` fixed, is a validated direct load->store forward bypassing the
GPR file. Reproduced fresh (own construction) and then GENERALIZED: with
`idx_off=0` fixed on BOTH sides and the byte address instead conveyed via
the INDEX REGISTER's dynamic content (set via `mov_imm`), **load and store
can address INDEPENDENT offsets** (own construction: load index=2, store
index=5, correct value forwarded to the new location) and **multiple such
pairs CHAIN correctly** (unlike iadd2's chaining hazard -- two independent
load-store pairs in one program, both correct). `idx_off != 0` on either
side (with index register held at 0) was tested and FAILS (silent zero) --
a real, bounded field-boundary rule: this mechanism's byte offset must be
carried by the index register, not the `idx_off` immediate.

## Milestone 3 -- pilot phase: control-flow displacement generator (item d)
   -- INCONCLUSIVE, hardware-confounded, STOPPED per safety protocol

Reconstructed EXP-0090/EXP-0112's CF skeleton instruction-by-instruction
(own `isadb.assemble` calls, not a byte copy), confirmed via disassembly
that its two branch displacements match EXP-0115's own derived formula
(`target = jump_addr + offset`, no +4): backward `jump` at file offset
0x5a, offset=-30, target=0x3c (loop head, right after `if_push`); forward
`jump_cond` at 0x2a, offset=0x40, target=0x6a (loop-exit reconverge). Built
a generator that inserts N extra no-op `falu2i` instructions inside the
loop body and RECOMPUTES both displacements from measured instruction
lengths (not copied constants); the N=0 case reproduces the anchor's exact
offsets byte-for-byte, confirming the arithmetic itself.

**Hardware validation attempt was CONFOUNDED, not clean.** The first
padded carrier kernel (`kernels/carrier_cf_padded.metal`, v1: extra `a[]`
reads for padding) shifted the compiler's base_slot/argument mapping --
reproducing the EXACT "n read from garbage, trip count saturates to
2^26=67108864.0" signature `cf.py`'s own module docstring already
documents as a known trap, confirmed because even the UNMODIFIED (N=0,
offsets unchanged) skeleton FAILED identically on this carrier. Of 4
hardware dispatches on this confounded carrier: 2 HANGed (recovered
cleanly within the 15s hard timeout each, NO host wedge -- host remained
fully responsive throughout, confirmed by continued command execution),
1 completed with the base_slot-confounded wrong value, 1 (the N=0 control)
also completed with the SAME wrong-value signature. **Because the control
itself failed under the same confound, this experiment did NOT obtain a
clean signal on whether the RECOMPUTED (N>=1) displacements are themselves
correct or unsafe.** A v2 carrier (padding via extra arithmetic on `acc`
only, no new buffer reference) was authored to remove the confound but,
given CLAUDE.md's explicit safety directive on control-flow hangs and the
two real hangs already observed, further live-hardware iteration on this
SPECIFIC technique was deliberately STOPPED here rather than continued --
this is reported as UNKNOWN (not FALSIFIED), a bounded, honest gap, per
CODEX's stated preference for UNKNOWN over unjustified certainty. The
GATED corpus (below) therefore does NOT include a new CF-displacement
hardware case; CF's validated envelope remains EXP-0112's own
one-parameterized-skeleton result, unchanged.

## Milestone 4 -- item b (R>=64) and item e (reg_move): synthesis, no new
   experimentation needed

Both items are already extensively and decisively covered by prior
experiments + this experiment's own item (c) work:
- (b): db.json's own `falu2`/`falu2i` entry (updated 2026-08-28, citing
  EXP-0112/EXP-0119) already states the closed rule: "ALIASING RULE
  (EXP-0112, HW-VALIDATED...): a target register R resolves to r(R mod 64)
  for R in [64,112], and FAULTS the command buffer at R in {126,127}...
  r64-95 have NO validated ALU-source path." EXP-0113 independently
  refuted the one candidate "wider-field" mechanism (`iminmax`'s plain
  8-bit srcA, fed via a relocated device_load) as genuine addressing
  (non-reproducible cross-run). This experiment's OWN item (c) work adds a
  concrete, positive counterpoint on the WRITE/dst side: iadd2's `dst`
  field (a full 7-bit register selector, unlike falu2's 4-bit nibble) is
  independently confirmed reaching registers well past 63 in this
  experiment's own splice tests (dst=90 case, Milestone 1/5) -- consistent
  with db.json's own EXP-0020 citation ("up to 96 regs") -- so "R>=64" is
  NOT a uniform hardware wall: it specifically bounds ALU SOURCE-operand
  reads for the packed 6-bit-effective register field family
  (falu2/falu2i, and this experiment's own newly-decoded iadd2 srcB
  field -- see RESULTS.md for the N<=15 boundary that field was actually
  tested to), not destination/write-side addressing.
- (e): three independent experiments (EXP-0101, EXP-0090, EXP-0113) have
  now each tried and failed to find a genuine GPR-to-GPR move -- EXP-0113
  additionally closed EXP-0101's own named candidate (byte0=0x2b,
  `reg_move_c9`) with a decisive negative. No new hardware experimentation
  is added here; RESULTS.md synthesizes the existing bounded-negative
  verdict per the dispatch's own instruction ("only if time permits...
  a bounded negative is acceptable and already largely established").

## Milestone 5 -- a real bug found while formalizing the gated corpus:
   mov_imm's imm8 field boundary (2026-08-28)

While building the FIRST formal case matrix (`casematrix.py`), case 0
(`iadd_reg_N00_dst20`, self-add with `r0val=200`) HUNG on real hardware
(`kIOGPUCommandBufferCallbackErrorHang`, `agxrun`'s own 15s timeout fired
cleanly, host stayed fully responsive). Root-caused via a direct
readback sweep (`mov_imm(reg,V); device_store(...)`, no add): **`mov_imm`'s
8-bit `imm8` field is only 7 bits load-bearing** -- V=50/127 read back
exactly, V=128/200/255 all read back as a SILENT 0 (dense boundary sweep,
5 points). This alone does not explain a HANG (0+0=0 should be harmless)
-- but COMBINED with `iadd2` register-mode's own N=0 (self-read) encoding
specifically, an imm8>=128 write reproducibly triggered a real hang (4/4
retries with dst in {20,21,30}, r0val=200, N=0 all hung; the SAME
construction with r0val<128 or N!=0 never hung). **Fix (not a
root-cause characterization, a bounded safe-range rule):** `isa_helpers.
mov_imm` now hard-rejects `imm8>=128`; every seed value in the frozen
corpus is <128. Re-verified: case 0 with the corrected (in-range) seed
values runs `STATUS OK`, correct result, no hang, reproducibly.

**Two adjacent GPU-hang/recovery side effects observed, consistent with
EXP-0115's own documented pattern:** a dispatch run immediately after a
hang was misclassified `kIOGPUCommandBufferCallbackErrorInnocentVictim`
(collateral, not its own independent failure) even though it later
reproduced CLEANLY as a genuine, isolated fault once retried after the
recovery window passed (see item (c)'s own dst=110 boundary-probe case,
RESULTS.md) -- a real operational-noise source this experiment is
disclosing, not silently working around.

## Milestone 6 -- gated capture (2026-08-28)

Both `m4-20260828-run01` and `m4-20260828-run02` complete: 39/39 cases
each run, `STATUS OK` for 38/39 (the one `iadd_reg_dst_probe110`
EXPLORATORY boundary case cleanly `CMDBUF_ERROR`s, as its own
pre-registered cautious prediction allowed for). 34/39 matched, 5/39
mismatched, **0 unexpected mismatches** (every mismatch is a
pre-registered `expect_match=False` case behaving as predicted), **1
disclosed surprise** (`iadd_reg_adv_wrong_reghi` matches despite
`expect_match=False` -- the pre-registered "reg_hi corrupts" hypothesis is
REFUTED, not confirmed; kept exactly as pre-registered per SS6's
convention, not silently corrected). `01_results.jsonl` byte-identical
across both runs (sha256 `9be3990a762d1d5dedbb0aea3bdd6191c2dfd5670aeaeb17
08a050be66918b98`). `verify.py --selftest/--seqtest/--preflight/
--between-runs/--captured` all PASS. `make_manifest.py --check` PASS.
No STOP.json in either run. No further hangs during the gated capture
itself (both hangs and their root cause were fully resolved during the
pre-freeze pilot phase, per Milestone 5). See RESULTS.md for full
interpretation.
