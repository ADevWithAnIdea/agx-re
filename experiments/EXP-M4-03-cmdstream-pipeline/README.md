# EXP-M4-03 — M4 command-stream + TBDR-pipeline delta vs A18 Pro

**Host = target.** Run entirely on the LOCAL machine: **Apple M4** (Mac16,x, Mac Mini M4),
macOS 26.4.1 (25E253), **10 GPU cores**, Metal 4, SIP disabled. No SSH — the M4 is the DUT.

**Hypothesis.** The A18 Pro (G17P / Apple9) command-stream and TBDR-pipeline encodings
documented in `docs/cmdstream/README.md` + `docs/pipeline/README.md` are shared by the M4;
any differences are device-identity strings and firmware/kernel-managed sizing, not
userspace cmdstream field encodings.

**Method — clean-room DATA-TRACE + HW-PROBE.** Built `tools/iotrace` (`iotrace.c`,
`-arch arm64e`) locally, plus the existing A18 parametric Metal harnesses
(`dvar`/`svar`/`tvar`/`rtvar`/`ivar`/`qvar`/`uvar` from EXP-0014/0019/0021/G1b/0027/G1a,
`iohello_compute`, `iohello_mesh`, `tess` from EXP-0030/O2H) — all our own MSL, compiled at
runtime. Ran each under `DYLD_INSERT_LIBRARIES=./iotrace.dylib` to snapshot the GPU BOs
Metal builds, then decoded the same byte offsets the A18 docs pin down (change-one-Metal-
parameter + byte-diff). No Apple binary was disassembled; only our-own-program BO byte
captures were read.

**Clean-room category:** DATA-TRACE (IOKit boundary byte capture of our own programs) +
HW-PROBE (every draw/dispatch ran on the real M4 GPU, status=completed). PUBLIC tool reuse.

## Files
- `work/` — the arm64e-built interposer + harnesses (binaries git-ignored), the `.maps/`
  BO hex snapshots (non-copyrightable data), per-run `.log` IOKit traces, and `decode_all.py`
  (the reproducible field decoder that prints every M4 value next to its A18 baseline).
- `raw/decode_summary.txt` — output of `decode_all.py` (the byte-level evidence table).
- `raw/*.trace.txt` — representative IOKit call traces per run.
- `RESULTS.md` — findings (per item: IDENTICAL / DELTA with bytes).

## Reproduce
```sh
cd work
clang -arch arm64e -dynamiclib -o iotrace.dylib iotrace.c -framework IOKit -framework CoreFoundation
for m in dvar svar tvar rtvar ivar qvar uvar iohello_compute iohello_mesh tess; do \
  clang -arch arm64e -fobjc-arc -framework Metal -framework Foundation -o $m $m.m; done
# e.g. one capture:
IOTRACE_LOG=tb_msaa4.log IOTRACE_DUMP_DIR=tb_msaa4.maps \
  DYLD_INSERT_LIBRARIES=./iotrace.dylib ./tvar --samples 4 --sampos --dump
python3 decode_all.py            # decodes all captured .maps against the A18 baseline
```
