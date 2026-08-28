# PROGRESS — EXP-0101

All timestamps local (host clock), 2026-08-27 session.

## Milestone 1 — reading, setup (no GPU)

Read `CLAUDE.md`, `CODEX.md`, `experiments/SUBAGENT_BRIEF.md`,
`docs/isa/register-move-and-liveness.md` (sections 2.6/2.7 especially),
and RESULTS.md of EXP-0099, EXP-0090, EXP-0087, EXP-0082. Confirmed host
is the real M4 (macOS 26.6.2/25G82, Metal 4, `xcrun metal --version` ->
`metalfe-32023.883`). Built `tools/shdump`/`tools/agxtest` binaries into a
scratch `work/pilot_bin/` (tools/ themselves untouched, read-only).

## Milestone 2 — Blocker 1 pilot: OWN-SHADER differential census (GPU:
compile + one unspliced dispatch only, no field mutation)

Compiled our own minimal MSL (`float v = mem[tid]; out[tid] = v + 10.0;`)
and disassembled the result with `tools/agx-isa`. Decisive finding:
`device_load` wrote its result with `dst_lo=1, dst_ext9=1` (EXP-M4-13's own
formula `dst = dst_lo | (dst_ext9<<2)` predicts register **5**), yet the
immediately-following, functionally-verified-correct `falu2i` consumed it
via `srcA_reg=0`, NOT 5. Ran the UNMODIFIED compiled kernel (no splicing
at all) and confirmed it is functionally correct (`mem[0]=42.5 ->
out[0]=52.5`), so this is not a broken/uncompiled example -- it is a real,
working compiler output that directly contradicts the standing dst
formula.

Built a second, richer census kernel (10 independent `mem[tid+i]` loads,
each kept live to its own later `+K` use, forcing the register allocator
to place each in a genuinely different register) and got a 10-point
correspondence table. Cross-checked against each load's OWN corresponding
`device_store`'s `extmode` field (EXP-0090's own HW-VALIDATED
`extmode=2*data_reg` store formula) as an INDEPENDENT confirmation of which
register each `falu2i` was really reading. Result: in all 10 rows,
`device_load`'s **`extmode` field, divided by 2, exactly equals the
consumer's `srcA_reg`** -- while the `dst_lo`/`dst_ext9`-derived "formula"
value matches in 0/10 rows beyond coincidence. Ran the unmodified compiled
10-load kernel and confirmed all 10 outputs are correct
(`mem[i]=i*10+0.25 -> out[i]=mem[i]+(i+1)`).

**Hypothesis formed: `device_load`'s `extmode` field (not
`dst_lo`/`dst_ext9`) is the SAME mechanism as `device_store`'s
`extmode=2*data_reg` -- it is the register a later ALU op must reference,
independent of `dst_lo`/`dst_ext9`.**

## Milestone 3 — Blocker 1 pilot: splice validation + boundary characterization (GPU, field mutation)

Took the compiled, verified-correct 42-byte `load_add.metal` program and,
via `tools/agx-isa`'s own `disassemble()`+`assemble()` (never manual byte
edits), produced 12 field-mutated variants differing from the known-good
baseline by exactly one or two named fields, spliced each over the SAME
unmodified carrier, and ran each on real hardware with a fixed,
distinguishable `mem[0]=42.5`:

- Relocating the consumer register via `extmode` ALONE (leaving
  `dst_lo`/`dst_ext9` at their ORIGINAL COMPILED values, 1,1) to r3
  (`extmode=6`) and r7 (`extmode=14`): **both correct** (52.5).
- The SAME relocation but ALSO "fixing" `dst_lo`/`dst_ext9` to match the
  target register via the naive `dst=dst_lo|(dst_ext9<<2)` formula (e.g.
  r3 -> dst_lo=3,dst_ext9=0): **FAILS** (reads 10.0, i.e. srcA read as 0).
- `extmode` correct, `dst_lo`/`dst_ext9` set to an unrelated `(0,0)`:
  **FAILS.**
- `extmode` UNCHANGED at its already-correct value (0, targeting r0), but
  `dst_lo`/`dst_ext9` ALSO changed away from the compiled (1,1) to (0,0)
  (i.e. `extmode` is right and untouched, only `dst_lo`/`dst_ext9` is
  disturbed): **STILL FAILS.** This rules out "dst_lo/dst_ext9 only
  matters if it disagrees with extmode" -- disturbing it AT ALL, even when
  extmode is already correct, breaks the load.
- `extmode` unchanged (0, correct for r0) but `srcA_reg` mismatched to 3
  (a plain field-mismatch control): **FAILS**, as expected -- this is the
  actual mechanism behind EXP-0099's ROUTE_LOAD failure (which always used
  extmode=0 while pointing srcA_reg at 7), not "route".
- `dst_lo`/`dst_ext9`=(0,0) reproduced in a DIFFERENT context (a
  non-terminal, `addr_mode=0x54` load inside the 10-load census kernel,
  where it DOES work) shows (0,0) is not universally forbidden -- its
  legality is context-dependent in a way this experiment does NOT fully
  characterize (see RESULTS.md "open/unknown").
- srcA reading a HIGH register (r15, later changed to r16 in the frozen
  matrix to avoid colliding with R_IDX) with the ALU's OWN `dst` nibble
  set to an UNRELATED low register (0, not matching r15's low 4 bits):
  **works correctly**, falsifying an early over-theory (from a *different*,
  unrelated part of the pilot -- a compiler self-update pattern `v+=K`
  where `dst` happened to equal `srcA`'s low bits) that `dst` must alias
  `srcA`'s low nibble. `dst` is confirmed an independent low-register
  (0-15) write target; a mismatched downstream `device_store` data
  register (not updated to match a relocated `dst`) was the actual cause
  of an earlier, since-understood, confusing negative result.
- Reproduced the EXACT EXP-0099 `ROUTE_LOAD` shape (its own carrier, its
  own `falu2` register-register construction, `mod_hi`/route=6) with ONLY
  `extmode` fixed (14) and `dst_lo`/`dst_ext9` copied (1,1) instead of
  derived from the target register: **reads V_LOAD=-8.5 exactly**,
  directly reversing that experiment's own documented failure.

**INCIDENT (self-corrected, not hidden):** the FIRST attempt at this fix
(before realizing `dst_lo`/`dst_ext9` must be COPIED, not derived) used
`isa_helpers.device_load(dst=7, ..., extmode=14)`, whose OLD helper
computed `dst_lo`/`dst_ext9` FROM the same register 7 -- and it FAILED
(read 0.0). This negative result was itself informative: it is exactly the
"adversarial_dstfields_naive_formula" case in the frozen matrix, and is
the reason the fix required TWO changes (extmode AND leave dst_lo/dst_ext9
alone), not one.

## Milestone 4 — Blocker 1 pilot: falu2i's `mods` field (GPU, field mutation)

While building the frozen case matrix (see Milestone 6), the `falu2i`
variant of the fix (`fix_extmode_reg7_falu2i`, built via
`isa_helpers.falu2i_raw()` with its NAIVE default `mods=0`) failed a
pre-freeze smoke check (read `K_SMALL` alone, i.e. srcA read as 0), while
the `falu2` (register-register) variant of the identical fix worked. Root
cause found by direct mods sweep (`{0, 0xC0, 0x80, 0x40, 0x08, 0x04, 0x02,
0x01}`, one field at a time, same carrier/mem): **ONLY `mods=0xC0` (bits 6
AND 7 both set) works; every other tested value, including each of those
two bits set ALONE, fails identically to 0.** `0xC0` is exactly the value
the compiler's own `census_load_add.metal` anchor emits for this field
(Milestone 2). This is structurally the same shape as EXP-0090's own
"`falu2`'s `opflags` must be 3, not 1" finding (a required PAIR of bits,
neither sufmicient alone) -- now found in `falu2i`'s analogous tail field
for a LOAD-sourced (not ALU-sourced) operand specifically. Folded into the
frozen matrix as `fix_extmode_reg7_falu2i` (now using `mods=0xC0`) plus a
new falsifying case, `adversarial_falu2i_mods_naive_default` (identical
construction, `mods=0`, predicted MISMATCH).

## Milestone 5 — Blocker 2 pilot: producer-independence + mechanism characterization (GPU, field mutation)

Reproduced EXP-0099's exact `move_baseline_fail_replicate` shape (`falu2i`
writes 30.0 to r2, `reg_move(dst=3,src=2)`) and got the SAME documented
`0x00000100` bit pattern. Changed ONLY the producer's value (30.0 -> 2.0,
same construction otherwise): **output UNCHANGED at 0x00000100** --
decisive: the observed output does not depend on what the GPR actually
holds.

Swept `src_reg` (0,1,2,3,4,5,6,7,8,14,20) at `src_flag=0` (nominal "GPR
mode") on the SAME carrier: registers PAIR up (0,1 identical; 2,3
identical at 0x100; 4,5 identical [a DIFFERENT value]; 6,7 identical
[SAME as 2,3]; 8/14/20 all read exactly 0.0). Swept `src_flag=1` (nominal
"uniform/class" mode) at src=0,1,2,3: got back the LITERAL integers
0,1,2,3 as raw bits -- a clean, kernel-specific, easily-distinguished
signal, proving the harness and this instruction CAN read genuinely
different content when the addressing is right; it just never lands on a
live GPR at `src_flag=0` for this op_desc.

Recompiled the SAME probe against a DIFFERENT carrier (3 buffers instead
of 2): most probed `src_flag=0` slots' content CHANGED (consistent with
reading a per-kernel PRELOADED/uniform region whose content depends on the
compiled kernel's own buffer/argument layout), but `src_reg` pair (2,3)
was STABLE at 0x00000100 across BOTH carriers and across two different
dispatch sizes (grid/tg 1x1 and 4x4). This informal cross-carrier/
cross-dispatch check is NOT gated (a different, ungated carrier file was
used) -- recorded here as a pilot-phase finding per SUBAGENT_BRIEF's
"informal, not hidden" convention; the GATED matrix instead uses
producer-value/producer-family independence (both provable on the ONE
gated carrier) as its formal evidence for "this reads a fixed slot, not a
GPR".

Retested EXP-0087's own explicitly-left-`UNKNOWN` `byte+2=0x21`
(`src_class=2`) case (docs/isa/register-move-and-liveness.md section 1.3)
against a genuine ALU-computed r2=30.0 on this carrier (EXP-0087's own
carrier had no independent way to tell "real move" from "lucky no-op"):
reads the SAME 0x00000100 as `src_class=0`, NOT 30.0 -- resolves that open
question as "reads the uniform file like src_class=0, not a real move."
Swept `src_class`/`op_desc` more broadly (10,12,14 and 0,2,4,12): every
combination outside `(src_class∈{0,2}, op_desc=8)` reads a silent 0.0,
matching EXP-0087's own byte+2 sweep pattern (done there on a
uniform-sourced carrier; reconfirmed here on an ALU-sourced one).

**No construction was found, across every field combination tried, that
reads a GPR written by `falu2`/`falu2i`/`device_load`. Blocker 2 is NOT
resolved** -- but its failure mode is now characterized (fixed,
producer-independent uniform/preload-slot content, register-pair-
quantized addressing) rather than a bare "returns 0x00000100, unexplained".

## Milestone 6 — frozen matrix, pre-registration, formal capture

Built `casematrix.py` (29 cases: 4 SEED_CHECK/positive-control, 6 LOAD_FIX,
6 LOAD_ADVERSARIAL, 13 MOVE_UNIFORM), ran the FULL matrix informally
(`work/pilot_full_run2/`, not gated) to confirm every case's `match`
equals its pre-written `expect_match` BEFORE writing this pre-registration
and freezing `CAPTURE_CONTRACT.json`. All 29/29 matched their prediction on
this informal run (see the table in this milestone's own commit -- also
independently re-derived by the formal two gated runs below). Captured
`harness/recorded_fixture_case0.json` from a real hardware run of case 0
for `verify.py --selftest`'s fixture (CODEX gate (e): recorded reality, not
the implementation's own constants). Ran `analysis/census.py --write`:
11/11 compiler-emitted load->ALU pairs confirm `extmode/2==srcA_reg`;
both census kernels functionally verified unspliced.

Proceeding to the formal two-run gated capture per `CAPTURE_CONTRACT.json`.

## Milestone 7 — formal two-run gated capture (GPU, CLOSED)

Ran the full contracted sequence: `verify.py --selftest`/`--seqtest`/
`--preflight`, `baseline.py` (fresh re-derivation: `CARRIER_LEN=170`,
`SLOT_MEM=1`, `SLOT_OUT=0`, confirmed), `run.py --execute --run-id
m4-20260827-run01` (29/29 cases, 21 matched/8 mismatched, ALL 8 mismatches
exactly the pre-registered `expect_match=False` cases, ZERO unexpected
results), `verify.py --between-runs`, `run.py --execute --run-id
m4-20260827-run02` (identical 21/8 split), `verify.py --captured`
(`01_results.jsonl` byte-identical across both runs, sha256
`dd8ff10b2c5dce29d15a50365329d996d9df04fd9ac3ca65c128da2f224521ab`),
`make_manifest.py --write`+`--check`. No `STOP.json` in either run. No
host wedge, no unexpected result, no repair needed. Cleaned up
pilot-phase scratch directories (`work/pilot*`, `work/pilot_full_run*`,
`work/census_run`) after the gated capture closed; `work/baseline_bin`
and `work/census_bin` (rebuilt tool binaries, referenced by
`baseline.py`/`analysis/census.py`) retained, matching EXP-0099's own
convention. Re-ran `--selftest`/`--seqtest`/`--captured`/
`make_manifest.py --check` after cleanup to confirm nothing load-bearing
was removed -- all still PASS.

**CAPTURE COMPLETE. Both named blockers investigated; see RESULTS.md for
the full per-blocker verdict.**
