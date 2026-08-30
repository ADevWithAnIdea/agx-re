# EXP-0178 — G17P sysvals (`get_sr`) and the tilebuffer read (`tile_read` / `tile_read_mrt`)

## Question

Two rows from `EXP-0177`'s P0.8 / DRV-ABI-01 gap ranking, both on the documentation target:

1. **Can a compiler back end emit a system-value read on G17P?** `get_sr.sr_sel` is
   `untested` there (EXP-0169: 256 dense values, **one carrier**, ladder failed), and every
   `[[thread_position_in_grid]]`, `[[vertex_id]]`, `[[instance_id]]`, `[[base_vertex]]`,
   `[[base_instance]]`, fragment pixel X/Y and `[[front_facing]]` goes through it. The
   exhaustive characterization exists — on M4 (EXP-0092).
2. **Does EXP-0147's silent-zero tile-read hazard reproduce on G17P?** `tile_read` and
   `tile_read_mrt` are measured only on M4. The fact that matters to an implementer is the
   failure *mode*: **byte+6 bit 0 is a read-enable whose EVEN values return a silent zero
   rather than faulting**, and so does a wrong `rt_index`. In a BG/EOT program that is a
   **black tile, not a loud failure**.

A documented negative on either is worth more than a promoted field elsewhere.

## Method

Splice-and-observe on real G17P hardware, with a host-computed oracle per case.

* **Three `get_sr` carriers, one per stage** (`kernels/sysval.metal`), because EXP-0031
  established the special-register namespace is stage-contextual, so two carriers in the same
  stage are one carrier: a **compute** probe at grid=64/tg=64 (the geometry EXP-0169 lacked —
  at grid=1/tg=1 every reachable SR reads 0, which is why its ladder failed), a **fragment**
  probe on `[[position]]`, and a **vertex** probe drawn indexed with a non-zero
  `baseVertex`/`baseInstance` so `vertex_id`, `instance_id`, `base_vertex` and
  `base_instance` are mutually distinguishable in the read-back.
* **Four tilebuffer carriers** (`kernels/tilebuf.metal`): `f_tile` and `f_mrt` reproduce our
  own EXP-0147 carriers exactly so the G17P numbers are directly comparable, and `f_tile2`
  (2 attachments, 4×4) and `f_mrt3` (3 attachments, 2×2) are the second, structurally
  different carriers EXP-0164 demanded before a never-moving field can be ruled on.
* **Full encodable range** for every field of width ≤ 8; per-constituent-byte dense plus a
  structured whole-field set for the 32-bit `tail`.
* **No hang budget and no per-arm abort** — rule 3(c): a budget guarantees a contiguous
  hazard is never mapped. Full-range dispatch maps it inside the gated run, which is how
  EXP-0169's DSTORE arm pinned two fault walls exactly.
* **Two gated runs**, promoted only at ≥ 99 % per-value cross-run agreement with movement
  ≥ 2× the disagreement count, and only if the arm's liveness ladder moved on every step and
  its pre-registered falsifier failed as pre-registered.

The full hypothesis / variable / oracle / refuter / confounder statement is
`PRE_REGISTRATION.md`; the frozen contract is `CAPTURE_CONTRACT.json`.

## Commands

```sh
cd experiments/EXP-0178-g17p-sysval-tileread
python3 harness/pinned_isa.py                     # pinned toolchain gate
python3 analysis/covary_audit.py                  # FIELD-SWEEP-PROTOCOL 3(a)
python3 harness/selftest.py                       # G1..G8, offline, no device

export SSHPASS='...'                              # never written to any file
harness/sync.sh push && harness/sync.sh build
harness/sync.sh shell 'cd ~/agxre/EXP-0178 && python3 harness/run.py --run-id g17p_20260830_run01 --out-root raw'
harness/sync.sh shell 'cd ~/agxre/EXP-0178 && python3 harness/run.py --run-id g17p_20260830_run02 --out-root raw'
harness/sync.sh pull

python3 analysis/verdicts.py --run01 raw/g17p_20260830_run01 --run02 raw/g17p_20260830_run02
```

## Clean-room category

`OWN-SHADER` + `HW-PROBE`. Every byte spliced is the compiled form of MSL **we wrote**,
produced by the public `newLibraryWithSource:` API and manipulated with our own tools
(`tools/shdump`, `tools/agxtest`, `tools/agx-isa` — pinned into `pinned/` with recorded
hashes). No Apple binary, framework, kext or firmware is disassembled, decompiled,
symbol-dumped, strings-scanned or debugged.

Clean-room provenance: **OWN-SHADER + HW-PROBE**
Inputs inspected: `kernels/sysval.metal`, `kernels/tilebuf.metal`, and the AGX bytes the
public runtime API compiled from them.
Apple binary introspection: **NONE**
Reproduction: the commands above.
Evidence: `raw/<run_id>/{00_env.json,00_arm_resolution.json,sweep.jsonl,02_summary.json}`

## Layout

```
PRE_REGISTRATION.md   frozen hypothesis, carriers, oracles, ladder, gate, safety
CAPTURE_CONTRACT.json frozen schema, hashes, timeouts, promotion gate, outcome vocabulary
kernels/              authored MSL: sysval.metal (3 get_sr carriers), tilebuf.metal (4)
harness/              pinned_isa.py (hard pin), sweepplan.py (frozen plan + host oracles),
                      run.py (capture driver), selftest.py (G1..G8 offline gates),
                      rendersweep.m / rsdrv.py / shdump2.m (our EXP-0147 runners),
                      sync.sh (push/build/pull; SSHPASS only)
analysis/             covary_audit.py (rule 3a), verdicts.py -> field_verdicts.json
pinned/               isadb.py + db.json + agxparse.py, sha256-pinned
raw/                  immutable per-run evidence
work/                 pilots and build products; retained, never evidence
```
