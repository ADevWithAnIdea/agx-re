# EXP-0101 — M4 synthesis blockers (DRV-ISA-01)

## Question

`docs/isa/register-move-and-liveness.md` §2.6/§2.7 name two named,
open blockers that survived EXP-0090 (whole-program synthesis) and
EXP-0099 (lifetime-field model): (1) `device_load`'s result cannot be
fed into `falu2`/`falu2i` by independent construction, and (2)
`reg_move` cannot read a GPR written by `falu2`/`falu2i` or
`device_load` — returning an exact, reproducible `0x00000100` instead.
Both gate arbitrary program synthesis, which gates DRV-ISA-01. This
experiment attacks both by differential/bisection method: diff a
compiler-emitted working sequence against the hand-built failing one,
enumerate every differing field, bisect which difference matters, and
validate the result by independent hardware splice with a host-computed
oracle (never by trusting the spliced instruction's own claimed result —
this ISA fails silently-to-zero, not by faulting, per
`docs/isa/register-move-and-liveness.md` §2.5).

## Hypotheses

See `PRE_REGISTRATION.md` for the full falsifier design. In short:

- **H1 (Blocker 1):** `device_load`'s `extmode` field (not
  `dst_lo`/`dst_ext9`, EXP-M4-13's own formula) determines the register a
  later ALU instruction must reference to read the loaded value; formula
  `extmode = 2 * target_register`, unifying with EXP-0090's own
  `device_store extmode = 2*data_reg` formula. `dst_lo`/`dst_ext9` remain
  a separate, independently-required field that must be copied from a
  compiler-observed value, not derived from the target register.
- **H2 (Blocker 2):** the compact-move family, at the one encoding
  EXP-0087 found to read anything (`byte+2=0x01,op_desc=0x08`), never
  addresses the live GPR file regardless of `src_flag`'s documented
  meaning — its output is a fixed, producer-independent function of
  `src_reg` alone (register-pair-quantized), consistent with reading a
  per-kernel preloaded/uniform-file slot. This does not resolve the
  blocker (no fix found) but characterizes its failure mechanism.

## Method

Compile our own minimal MSL, disassemble with `tools/agx-isa` (OWN-SHADER
differential census, `analysis/census.py`), diff the compiler-emitted
device_load→ALU sequence field-by-field against the hand-built EXP-0099
construction, form a hypothesis, then validate by independently
hand-assembling (`tools/agx-isa isadb.assemble()`) mutated programs and
splicing them over a compiled carrier (`tools/agxtest`), reading back an
independent host-computed oracle. Two gated hardware capture runs per
`CAPTURE_CONTRACT.json`; promotion requires byte-identical
`01_results.jsonl` across both.

## Commands

```sh
# static, no GPU
python3 -B casematrix.py                  # dump the case matrix
python3 -B verify.py --selftest           # synthetic gate, runnable anytime
python3 -B verify.py --seqtest
python3 -B make_manifest.py --check

# compiler census (GPU: compile + ONE unspliced dispatch per kernel, no field mutation)
python3 -B analysis/census.py --write

# re-derive carrier facts fresh (GPU: compile only)
python3 -B baseline.py

# gated hardware capture (GPU: splice + dispatch, one process per case)
python3 -B verify.py --preflight
python3 -B run.py --execute --run-id m4-20260827-run01
python3 -B verify.py --between-runs
python3 -B run.py --execute --run-id m4-20260827-run02
python3 -B verify.py --captured
python3 -B make_manifest.py --write
```

## Clean-room

```text
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: our own carrier/census MSL (kernels/*.metal), our own
  hand-assembled instruction bytes (isa_helpers.py/casematrix.py, built
  entirely from tools/agx-isa's read-only isadb.assemble()/disassemble()/
  imm_encode/imm_decode), our own splice+run harness (harness/case_exec.py
  over tools/agxtest/agxtest.py, tools/shdump for carrier/census
  compilation).
Apple binary introspection: NONE.
Reproduction: see Commands above.
Evidence: raw/m4-20260827-run01/, raw/m4-20260827-run02/,
  analysis/census_report.json, manifest.json.
```

See `RESULTS.md` for outcomes, `PROGRESS.md` for the full pilot-phase
trail (including a self-corrected negative result and the `mods=0xC0`
discovery), and `docs/isa/register-move-and-liveness.md` §2.6/§2.7 for the
blockers this experiment attacks.
