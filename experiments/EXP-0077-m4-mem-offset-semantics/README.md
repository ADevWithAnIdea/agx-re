# EXP-0077 M4 device_load/store memory-offset semantics (MEM-01..MEM-05)

User-directed top-priority splice experiment (load/store/SSBO = compiler
critical path). Answers Part-II questionnaire items **MEM-01 … MEM-05** of
`APPLE9_RE_IMPLEMENTATION_GAPS.md` (P0 "Memory addressing and robustness") on
the **local M4 (G16G)** — the sole test target per the standing directive — by
splicing address fields of our own compiled `device_load`/`device_store` and
observing the touched bytes:

- **MEM-01** is the GPR index scaled by the encoded element size?
- **MEM-02** is the immediate offset in element units (not bytes)?
- **MEM-03** exact signedness/range/holes/first-invalid/failure-mode of the
  11-bit immediate element offset — full dense 0…2047 sweep (finite-resource
  mandate);
- **MEM-04** is `base + index*stride + offset` encodable for arbitrary strides
  (element-code ceiling; non-power-of-two strides reachable?);
- **MEM-05** does 32-bit address arithmetic wrap exactly mod 2^32?

Method: two authored kernels (`kernels/ld_bank.metal`: `out[0] = a[i0+i1]`,
`kernels/st_bank.metal`: `tgt[i0+i1] = 0x5A17C0DE`) are compiled with our
`shdump`; the probe instruction is located structurally (`baseline.py`,
byte-frozen); every case re-assembles the probe with **our own DB**
(`tools/agx-isa`), splices it through the **agxtest** binary-archive testbed
(`FailOnBinaryArchiveMiss` proves the spliced machine code ran), executes on
the M4 in a **fresh process per case** under a hard timeout, and reads back
which bytes moved. `a[w] = 0x3CA50000 | w` makes any 32-bit read at any byte
offset uniquely decodable; the zeroed `tgt` makes the store byte offset
directly observable. A fault/hang/timeout is a recorded result; the sweep
continues in a fresh process. 2164 frozen cases.

Gates (contract-named, in order):
`verify.py --selftest` and `--seqtest` are required before **every** capture
and are runnable in **every** tree state (they only ever build synthetic
scratch trees; `--seqtest` walks the contracted gate order through synthetic
PRE_GPU / RUN01_PRESENT / RUN02_PRESENT states and proves each gate is
satisfiable exactly where the contract invokes it — the EXP-0075 fix);
`make_manifest.py --check`; `--preflight`; a **non-recorded smoke gate** inside
`run.py` (one spliced scratch case, output must parse completely, before any
raw/ artifact); then the two append-only runs `raw/m4-20260827-run01/-run02`;
then `analysis.py --write`, `make_manifest.py --write && --check`,
`verify.py --captured`.

Commands (in order):

```sh
python3 -B verify.py --selftest        # required before any build (any state)
python3 -B verify.py --seqtest         # gate-order state-machine self-test
python3 -B make_manifest.py --check
python3 -B verify.py --preflight       # PRE_GPU: no raw tree may exist
python3 -B run.py --execute --run-id m4-20260827-run01
python3 -B verify.py --between-runs
python3 -B run.py --execute --run-id m4-20260827-run02
python3 -B analysis.py --run-a m4-20260827-run01 --run-b m4-20260827-run02 --write
python3 -B make_manifest.py --write && python3 -B make_manifest.py --check
python3 -B verify.py --captured
```

Clean-room provenance: HW-PROBE / OWN-SHADER
Inputs inspected: authored MSL/harness/runner/verifier/analysis sources and the
compiled bytes of our own kernels (the only machine code inspected or spliced)
Apple binary introspection: NONE
Reproduction: the command sequence above, from this directory
Evidence: `raw/m4-20260827-run01`, `raw/m4-20260827-run02`, `analysis.json`,
`manifest.json`
