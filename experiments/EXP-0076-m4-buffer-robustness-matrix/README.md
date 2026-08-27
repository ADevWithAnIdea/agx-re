# EXP-0076 M4 owned-buffer robustness matrix (MEM-06..MEM-10)

Successor of the superseded scaffold `../EXP-0068-m4-robustness-contract`
(see its `SUPERSEDED.md`: nothing was captured, it binds nothing).

Public-Metal behavioral probe answering Part-II questionnaire items
**MEM-06, MEM-07, MEM-08, MEM-09, MEM-10** of
`APPLE9_RE_IMPLEMENTATION_GAPS.md` (plus MEM-11-adjacent observations and
MEM-12 input): what the hardware does for authored MSL device-buffer accesses
at unaligned byte offsets, past the allocation end, and across the
end-boundary.

Method: a 64-byte owned `MTLBuffer` (exact length, no slack) CPU-filled with
`F(i) = (0xA5 + 0x1B*i) mod 256`, bracketed by 256-byte guard allocations
(`0x5A` before, `0xC3` after) checked after every case; a result buffer with
guarded payload. Frozen MSL access idioms (`*(device uint *)p` etc., one
kernel entry point per operation/width) read the byte offset at runtime from
a device uniform, so the compiler can never specialize the address. 106 frozen
cases per run (52 loads, 52 stores, 2 atomic-exchange stretch cases), one
case per fresh harness process, per-case hard timeout 120 s. Loads are
compared byte-exactly against the fill-derived expectation; stores against
the full-buffer model (window written, all other bytes unchanged); OOB and
boundary-straddling cases are recorded verbatim. A fault, hang, or kill is a
result (`watchdog`/`proc_fail`/`proc_timeout`), never retried in place.

Process: pre-registration + capture contract with frozen hashes first;
`verify.py --selftest` proves every gate satisfiable and fail-correct and that
guard-violating OOB observations are admissible evidence; a NON-RECORDED
smoke invocation (one scratch case) runs before the append-only raw tree is
created, so a payload-truncation defect (the EXP-0072 quarantine class) is a
pre-capture stop. Two contracted runs; in-bounds cases must be byte-identical
between runs (OOB/straddle/atomic per-case identity is reported as the
determinism observation). Fail-closed verify, deterministic analysis,
manifest over every artifact.

Scope: **public-Metal behavioral evidence on the local M4 (G16G) only.**
No native-encoding or ISA claim, no Linux/UAPI claim, and no A18 (G17P)
inference — the A18 is hands-off for this work and nothing here is run on it.

Commands (in order):

```sh
python3 -B verify.py --selftest        # required before any build
python3 -B make_manifest.py --check
python3 -B verify.py --preflight       # PRE_GPU: no raw tree may exist
python3 -B run.py --execute --run-id m4-20260827-run01
python3 -B verify.py --between-runs
python3 -B run.py --execute --run-id m4-20260827-run02
python3 -B analysis.py --run-a m4-20260827-run01 --run-b m4-20260827-run02 --write
python3 -B verify.py --captured
python3 -B make_manifest.py --write && python3 -B make_manifest.py --check
```

Clean-room provenance: HW-PROBE / OWN-SHADER / PUBLIC API
Inputs inspected: authored MSL/harness/runner/verifier/analysis sources
Apple binary introspection: NONE
Reproduction: the command sequence above, from this directory
Evidence: `raw/m4-20260827-run01`, `raw/m4-20260827-run02`, `analysis.json`, `manifest.json`
