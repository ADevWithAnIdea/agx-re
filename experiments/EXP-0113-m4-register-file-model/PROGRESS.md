# PROGRESS -- EXP-0113

## Milestone 0 -- setup

Read CLAUDE.md, CODEX.md, SUBAGENT_BRIEF.md, and the four prerequisite
RESULTS.md files (EXP-0099, EXP-0105, EXP-0101, EXP-0092). Confirmed via
`tools/agx-isa` static analysis that `2b0009c0` (EXP-0087's own
"undecoded" instance) reproduces byte-for-byte via
`isadb.assemble('reg_move_c9', {dst:2,src_reg:0,src_flag:0,src_class:0,
op_desc:0xC0})` -- db.json's field table already covers this shape;
`instr_length()`'s byte0=0xNb length rule has no branch for byte+2
low-nibble==9, which is why the disassembler still calls it "undecoded."

## Milestone 1 -- pilot phase, H1 seeding technique exploration

All work in `work/` (never committed as `raw/` evidence; ad hoc, no gate).
Explored several candidate techniques for seeding a distinguishable value
into r64+ for an H1 test:

1. `get_sr(dst=6,sr_sel=thread_position_in_grid.x)` (small dispatch,
   tid 0-4) + `falu2i(srcA=6,K=0.0)` readback: reads back exactly 0.0 for
   ALL tested tid (0-4), even though a DIRECT `device_store` readback of
   the same register (bypassing falu2i) correctly shows the raw tid
   value. Conclusion: **flush-to-zero is active for denormal float ALU
   inputs on this hardware.** Any H1 test through float ALU needs a
   normalized (raw value >= 2^23) seed or a non-float consumer.
2. Attempted a `threadgroups_per_grid.x`-seeded, ~8.39M-thread dispatch to
   get a normalized value cheaply. `get_sr(0xa8)` bare does NOT give
   threadgroups_per_grid (EXP-0092's own documented finding, re-confirmed
   informally); reverted to `thread_position_in_grid.x` with a genuinely
   large dispatch (grid=8388609). Dispatch itself completed in ~0.14ms
   GPU time (fast, safe) but a per-thread-indexed readback (needed to
   isolate one large-tid thread's result) hit a NEW, unexpected wall:
   `device_store`'s `index_reg`-based addressing silently fails (reads
   back the buffer's zero-initialized default) for element index >=
   65536 (exact boundary: 65535 last-correct, 65536 first-lost),
   reproducible with a CONSTANT (non-tid-dependent) data value, ruling out
   "the SR value itself truncates" and confirming it's the STORE
   INDEXING. This blocks the large-dispatch approach within budget;
   abandoned in favor of an integer (non-float) consumer instead.
3. Tried `ilogic` (XOR-base, plain 8-bit srcA/srcB fields, no FTZ risk)
   fed by a hand-built `get_sr`-seeded register: gave 0 in every
   construction tried (several field/adjacency variants). Root-caused via
   a compiled reference (`work/ixor_probe.metal`, `int a^b`, EXP-0013's
   own validated field values): the compiled kernel's own device_store
   following ilogic uses `extmode=0` (implicit "preceding op" forwarding,
   matching device_store's own db.json semantics note) -- my hand-built
   attempts had this right, but grafting a `get_sr` in place of the
   compiled kernel's OWN `device_load` (replacing 14 bytes with 4 bytes
   of get_sr + 10 bytes of mov_imm padding) still read back 0 for EVERY
   tested register and `form` value. Abandoned the get_sr-graft variant;
   see Milestone 2 for what worked instead (relocating the COMPILED
   kernel's OWN device_load, not substituting get_sr for it).

## Milestone 2 -- H1_LOADFWD discovery (device_load-fed plain-8-bit consumer)

Compiled `work/ixor_probe.metal` (`out=a^b`) and `work/imax_probe.metal`
(`out=max(a,b)`), both functionally verified unspliced. Decoded the
compiled instruction stream (`isadb.decode_one`) and found: relocating
BOTH the first `device_load`'s `dst_lo`/`dst_ext9` fields (encoding a
candidate register R via `dst = dst_lo | (dst_ext9<<2)`) AND the
immediately-following consumer's own register field (ilogic `srcA` /
iminmax `srcA`) to the SAME value R, in lockstep, preserves correct
output (`out = a` exactly, since `b` buffer = all zero) across an
enormous R sweep: 5,7,16,20,31,32,63,67,85,94,95,96,97,100,110,120,127 all
correctly show `a`'s host-supplied value (1234/5678/9/10); R=15 and R=90
are the ONLY exceptions found (read 0). This spans FAR beyond the
established 96-GPR physical file boundary (EXP-0092), which is already
suspicious.

Built a bigger carrier (`work/imax_carrier.metal`, extra dead min/add/sub
arithmetic for spare `_agc.main` length) to test TWO decisive follow-ups:

- **Persistence:** add a SECOND, later, independently-issued
  iminmax+store reading the SAME nominal R. At R=67: first store MATCHES
  `a[]` exactly; SECOND store reads exactly 0 -- the apparent "read"
  does NOT persist for a non-adjacent reader.
- **Shape-sensitivity:** the SAME two-consumer construction at R=7 (an
  ORDINARY low register that succeeds in ISOLATION, per the singlehop
  sweep) -- BOTH stores read 0. Merely adding a second consumer breaks
  even the FIRST read, at a register that works fine alone.
- **Mismatch:** load targets R=67, consumer's own field names R=3
  (mismatched). Thread 0 (gid=0) reads `a[0]`=1234 anyway; threads 1-3
  read 0. Neither "always forwards regardless of field" nor "requires
  field match" cleanly explains this.

Conclusion: the apparent R-sweep success is EPHEMERAL, PROGRAM-SHAPE-
SENSITIVE pipeline forwarding, not genuine persistent register-file
access -- generalizing EXP-0105's own flagged, unexplained iminmax splice
anomaly (their finding: splicing srcA on a real compiled instance alone
had "NO EFFECT"; this experiment's finding: even the WORKING construction
falls apart once its shape changes even slightly). This became the
H1_LOADFWD group's design (formalized, re-tested independently under the
frozen PRE_REGISTRATION.md contract -- none of this milestone's own runs
are part of the gated capture).

## Milestone 3 -- formal harness built

`isa_helpers.py`, `casematrix.py` (46 cases, 6 groups), `kernels/*.metal`
(5 carriers), `harness/case_exec.py`+`build.sh`, `run.py`, `verify.py`,
`make_manifest.py`, `baseline.py`. `baseline.py` PASS (all 5 carrier
lengths fresh-confirmed). `verify.py --selftest` PASS (212 checks,
including the static `2b0009c0` reproduction). `verify.py --seqtest` PASS
(PRE_GPU). Smoke case (case 0, `control_r3_falu2i`) run for real,
`STATUS OK`, `match=True`, saved as `harness/recorded_fixture_case0.json`.

## Milestone 4 -- gated captures

`run01` (m4-20260828-run01): 46/46 cases `STATUS OK`, 37 matched / 9
mismatched oracle (every mismatch pre-registered as an exploratory/
falsification case, see PRE_REGISTRATION.md). `run02`
(m4-20260828-run02): 46/46 `STATUS OK`, 34 matched / 12 mismatched.

**`verify.py --captured` FAILS**: `01_results.jsonl` is NOT byte-identical
between the two runs. Diffed precisely: exactly 4/46 cases differ
(`loadfwd_singlehop_r7`, `loadfwd_singlehop_r16`, `loadfwd_singlehop_r63`,
`loadfwd_mismatch_load67_read3`) -- ALL FOUR in the `H1_LOADFWD` group.
Every other group (`SEED_CHECK`, `H1_ALIAS_RECONFIRM`,
`H1_CTRL_BITS_4_6`, `H2_REGMOVE_C9`, `H3_BUFFER_SIGNATURE` -- 5/6 groups,
42/46 cases, including `H1_LOADFWD`'s own `loadfwd_persist_*` and
`loadfwd_singlehop_r{5,15,32,67,90,96,127}` cases) reproduced
BYTE-IDENTICALLY across both independent hardware runs. **This is treated
as a decisive, first-class finding, not a harness defect**: the SAME
spliced bytes, on the SAME hardware, across two independent process
launches, give DIFFERENT results for `loadfwd_singlehop_r7/r16/r63`
(MATCH in run01, all-zero MISMATCH in run02) and for
`loadfwd_mismatch_load67_read3` (thread0 succeeds in run01, fails in
run02). No retry, no repair, no third run -- both captures are retained
exactly as recorded (`raw/m4-20260828-run01/`, `raw/m4-20260828-run02/`);
`analysis.py` reports BOTH runs' values explicitly for every H1_LOADFWD
case rather than assuming byte-identity. See RESULTS.md for the full
account and its implication for H1c (the apparent load-forwarding
"success" is not even reproducible with identical bytes on identical
hardware, let alone a validated addressing mechanism).

`analysis.py --write` PASS (post-hoc H2 producer-independence,
pair-quantization, and H3 buffer-count correlation computed; the
byte-identity assertion was widened to tolerate -- and explicitly
report -- H1_LOADFWD's own cross-run divergence while still hard-failing
on any divergence OUTSIDE that group, which did not occur).
