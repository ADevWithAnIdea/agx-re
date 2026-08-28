# EXP-0092 Pre-registration — M4 sysval / get_sr ABI (Bundle C: GLIO-A02/A03/A05/A06)

Frozen before any GPU capture. Git revision at registration: `1e0c481a96eb595b5b1f41b19d07a911a43c75a2`
(recorded for provenance only — per `experiments/SUBAGENT_BRIEF.md`'s pinned-revision rule, this
experiment's cross-run gate compares **authored file hashes**, never live repo `HEAD`, so a sibling
experiment landing between run01 and run02 is not a gate failure).

Target: **Apple M4 / G16G, local host only**, macOS 26.6.2 (25G82), Metal 4, `xcrun` 72,
Python 3.14.6. A18 Pro is hands-off (no data from it in this experiment). M5 is out of scope.

## Questions under test

- **GLIO-A02** — the complete `get_sr` operand/result model beyond the SR-number table EXP-0031
  established: exact usable SR-selector range, holes, first-invalid value, observed failure mode;
  destination low/high bits across the legal GPR range, first-invalid destination.
- **GLIO-A03** — `base_vertex`/`base_instance` (SR `0x88`/`0x8a`, currently `docs/isa/README.md`
  "(inferred)") and whether `vertex_id`/`instance_id` already fold in the base, established with a
  real indexed+instanced draw with independently distinguishable, nonzero, host-controlled
  `baseVertex`/`baseInstance`.
- **GLIO-A05** — how a shader obtains the workgroup count (`threadgroups_per_grid` /
  `load_num_workgroups`): SR read vs. computed value, under direct 3D and indirect dispatch,
  including malformed/overflowing indirect records.
- **GLIO-A06** — the finite-resource table row for every sysval touched by the above.

## Hypotheses and falsifiers

1. **SR-selector namespace.** H: the legal `get_sr` selector space is sparse — most of 0x00-0xFF is
   either unpopulated (reads a stable value with no distinguishing per-thread pattern, most likely a
   constant) or aliases an already-known SR; a `STATUS != OK` (fault/hang) region, if any, is the
   `first_invalid` boundary. Refuter: any splice that raises `STATUS != OK` proves the field can be
   illegal — a single such case falsifies "no encoding is illegal." A splice whose observed 64-value
   pattern exactly matches a KNOWN SR's independently-computed pattern at a *different* selector value
   would prove aliasing.
2. **Destination register range.** H: `get_sr`'s destination field is structurally 7 bits (0-127,
   `dst | dst_hi<<4`), but the physical GPR file is documented at 96 registers elsewhere in this repo,
   so registers 96-127 will misbehave (alias, read stale/zero, or fault) relative to 0-95. Refuter: a
   round trip that succeeds identically across the WHOLE 0-127 range refutes a 96-register ceiling for
   this addressing path; a failure boundary below 95 or an unexpected aliasing pattern (e.g. `R mod 96`)
   would refute the naive "everything under 96 works, nothing at/above doesn't" model.
3. **base_vertex/base_instance.** H (currently INFERRED per `docs/isa/README.md`): `bv == baseVertex`
   and `bi == baseInstance` exactly, and `vertex_id == index + baseVertex (mod 2**32)`,
   `instance_id == instance_ordinal + baseInstance (mod 2**32)`, matching Metal's documented public
   vertex-stage builtin contract. Refuter: any recorded `(vid,iid,bv,bi)` tuple that does not match the
   host-computed expected tuple for its case (including the negative-`baseVertex` and wraparound cases)
   falsifies the current inferred mapping.
4. **num_workgroups.** H: `threadgroups_per_grid` (the compiler's `load_num_workgroups` lowering)
   reports exactly the threadgroup count Metal was told to dispatch — the requested `(X,Y,Z)` for a
   direct dispatch, and the raw indirect-buffer record for an indirect dispatch — for every tested
   legal value, including non-power-of-two and asymmetric grids; a record of `(0,0,0)` dispatches zero
   threadgroups (no invocation runs; not independently checkable) without fault/hang. Refuter: any
   mismatch between the reported value and the host-supplied dispatch parameter, for either dispatch
   mode, falsifies the "same numeric ABI in both modes" hypothesis; a fault/hang/incorrect completion on
   a huge or `X*Y*Z`-overflowing indirect record would be a first-class negative result, not swept
   under "undefined behavior."

## Independent/controlled variables

- `sr_sel` (`get_sr` byte1, `0x00`-`0xFF`, exhaustive — one full-range sweep is affordable: 256 cases).
- destination register candidate (`get_sr` `dst`/`dst_hi` fields + `device_store` `index_reg`, spliced
  in lockstep to the SAME candidate register; boundary set `{0,1,15,16,31,32,47,48,63,64,79,80,87,88,
  94,95,96,97,100,111,112,120,127}`).
- draw parameters: index-buffer contents, `instanceCount`, `baseVertex` (signed, incl. negative and
  `INT32_MAX`), `baseInstance` (unsigned, incl. `UINT32_MAX` and an instance-count wraparound case).
- dispatch parameters: direct threadgroup count `(X,Y,Z)` (asymmetric, non-power-of-two, large single
  axis, non-power-of-two local size) and indirect-buffer raw record (legal, zero, all-zero, `UINT32_MAX`,
  large product).
- controlled/held fixed per sub-probe: kernel source, grid/local size (srsweep/dstsweep), fragment
  function (drawparam), everything not named above.

## Expected observation if each hypothesis holds

Exact host-computed expected values are in `casematrix.py` (`srsweep_expected`, `dstsweep_expected`,
`drawparam_expected`, and the `NUMWG_CASES` table) — computed BEFORE any GPU run, never adjusted to
match an observed result.

## Known confounders

- **Compiler-emitted vs. spliced code**: `srsweep`/`dstsweep` values come from a byte-spliced
  instruction — this is `HW-VALIDATED`-tier evidence for the FIELD's legality/effect, not proof the
  Metal *compiler* ever emits that exact selector. `drawparam`/`numworkgroups` are the opposite:
  natively compiler-emitted code on a real draw/dispatch (`OWN-SHADER` + `HW-PROBE`), stronger evidence
  for the ABI those two items ask about, but they do not exercise the raw encoding space at all.
- **Later-read discipline** (`docs/isa/register-move-and-liveness.md`, EXP-0086): `srprobe`'s spliced
  `get_sr` is consumed by a later, separate `iadd2`, then a third, separate `device_store` — not
  adjacent same-instruction inspection. `dstprobe`'s spliced `get_sr` is consumed by `device_store`'s
  own explicit `index_reg` field (an address computation reading the GPR by number), also a genuinely
  separate later instruction. Neither design can be fooled by a hypothetical bit that only corrupts an
  *adjacent* consumer.
- **`R==0` collision in `dstsweep`**: `dstprobe.metal`'s `mov_imm` (the sentinel-1 constant) is fixed at
  `dst=0` and is never spliced. Routing the candidate register through `R=0` collides with it by
  construction: `get_sr` writes r0, then `mov_imm` overwrites r0 with 1, then the store reads
  `index_reg=0` and finds 1 — so `out[1]` (not `out[0]`) becomes the sentinel. This is a predicted,
  not anomalous, outcome and is encoded directly in `dstsweep_expected(0)`.
- **Compiler determinism**: `baseline.py` re-derives `SRPROBE_MAIN_HEX`/`DSTPROBE_MAIN_HEX` from a
  fresh compile before every capture and stops (exit 3) on any drift — a toolchain change invalidates
  the frozen anchors rather than silently re-pinning them.
- **Draw-ID**: Metal exposes no multidraw primitive with an automatic per-draw index visible to a
  vertex function (an ICB's per-command index is visible only to the *encoding* compute kernel, not the
  executed vertex shader) — this experiment does not attempt a hardware `load_draw_id` test and reports
  that gap as `UNKNOWN`/`PUBLIC`-sourced rather than fabricating a claim from an untested mechanism.
- **`indirect_all_zero`**: a `(0,0,0)` indirect record dispatches zero threadgroups; thread `(0,0,0)`
  never executes, so the output buffer is observed in its untouched zero-initialized state. This is
  NOT independent confirmation that `threadgroups_per_grid` would itself read `(0,0,0)` — `casematrix.py`
  marks this case `expected=None` (status-only verdict) rather than claiming a value read.
- **GPU faults are expected and fault-contained** per `CLAUDE.md`/`CODEX.md`: a `CMDBUF_ERROR`/`HANG`
  on an out-of-range register or a malformed dispatch record is a recorded RESULT, not an error to
  suppress or retry past.

## Kernels (frozen; `casematrix.KERNELS`)

`kernels/srprobe.metal` (srsweep), `kernels/dstprobe.metal` (dstsweep),
`kernels/vdraw_probe.metal` (drawparam), `kernels/numwg_probe.metal` (numworkgroups).

## Case matrix size (frozen; `casematrix.full_case_list()`)

300 cases total: `srsweep` 256, `dstsweep` 23, `drawparam` 9, `numworkgroups` 12. `REPEAT_N=1` per run
(the two independently required capture runs, `m4-20260828b-run01`/`m4-20260828b-run02`, are themselves
the determinism check via the byte-exact gated cross-run gate; the srsweep/dstsweep sample size — full
256-value and a 23-point boundary sweep — is the intra-run replication for those two backends).

## Environment / timeouts (frozen; see `run.py` `TIMEOUTS`)

`env_command=10s`, `host_build=60s`, `baseline=60s`, `case_process=60s`, `smoke_process=60s`. Every
sub-process is a hard-timeout blocking call in its OWN fresh process; a timeout is recorded as
`STATUS HANG` / `verdict FAULT`, never retried in place.

## Standing gate set implemented (verify.py)

(a) `--selftest` — synthetic, no-Metal, no-device fixtures built from the SAME record shapes `run.py`
    writes, driving `static()`/`captured()`; proves clean shapes pass and each broken shape fails for
    the right reason, including the NO-NONDETERMINISM distinction (gate class d).
(b) `--seqtest` — walks `PRE_GPU -> RUN01_PRESENT -> RUN02_PRESENT` through synthetic states, proving
    every gate (`--preflight`/`--between-runs`/`--captured`) is satisfiable exactly where the contract
    invokes it and refused everywhere else.
(c) NON-RECORDED smoke gate — one scratch `drawparam` case (`baseline_zero`), run and discarded BEFORE
    `raw/<run>/` is created; a smoke failure is a pre-capture stop (`sys.exit(3)`), never a raw artifact.
(d) NO-NONDETERMINISM — `04_results.jsonl` (`CASE_KEYS`) never carries a timing/duration/pid/address
    field; only `04_results_raw.jsonl` (`CASE_RAW_KEYS`) does. The cross-run gate requires the GATED
    file byte-identical between run01/run02 while deliberately never comparing the raw file.
(e) selftest fixtures from RECORDED REALITY — the synthetic fixtures encode the SAME case identities,
    key sets, and `EXPECTED`/oracle functions `casematrix.py` derives from the pilot HW compile/decode,
    not ad hoc constants invented in `verify.py`.
