# `work/` — regenerable scratch (not evidence)

Everything here is **regenerable** and is **not** part of the evidence chain:

- `bin/` — our own build of the READ-ONLY tool sources (`tools/shdump/shdump.m`,
  `tools/agxtest/agxrun_persist.m`, `tools/agxtest/agxrun.m`), produced by `harness/build.sh`.
- `pilot/` — the non-mutating carrier-location, smoke, splice-efficacy and flake-rate scripts.
  Their *output* is committed under `raw/pilot/`.
- `run*/` — per-run scratch: `*_base.bin` (a Metal binary archive compiled from OUR OWN MSL in
  `kernels/`), `*_spliced.bin` (the same archive with one instruction mutated) and `*_in*.bin`
  (the frozen input buffers, byte-for-byte what `harness/oracles.py` packs).
- `run0*.log` — driver console logs.

**No Apple binary, blob, firmware or Apple-authored precompiled shader is present.** Every
`.bin` here is either a compile of `kernels/*.metal` (which we wrote) or a plain input buffer.
They are kept only so a reviewer can re-splice without recompiling; deleting the whole directory
and re-running `harness/build.sh` + any `harness/run_*.py` reproduces it.

The immutable evidence lives in `raw/`, which is text/JSON only.
