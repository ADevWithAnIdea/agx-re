# analysis/pilot -- differential-compilation pilot evidence

Pilot artifacts from PROGRESS.md T2 (register-field isolation method development), referenced
by RESULTS.md secs. 3.3/3.6/6. Per `tools/shdump/README.md`'s standing convention ("keep [the
.bin archive] on the device workspace; commit only the extracted hex/text"), the compiled Metal
binary-archive containers themselves are NOT committed here -- only their extracted AGX hex
(`hex/*.hex`, produced by `tools/shdump/agxparse.py --extract-hex`, read-only tool, our own
compiled bytes).

## Regeneration

Every `.bin` this directory's `hex/` files were extracted from is regenerable from the committed
MSL source (`kernels/regpair_bias_{A,B}.metal`, `kernels/regpair_grad_{A,B}.metal`,
`kernels/generated/regpress_{bias,grad}_n*.metal`) via `harness/bin/shdump` (built from the
read-only `tools/shdump/shdump.m` by `harness/build.sh`):

```sh
harness/bin/shdump -o /tmp/x.bin --render --vertex vmain --fragment fmain kernels/regpair_bias_A.metal
python3 tools/shdump/agxparse.py /tmp/x.bin --stage fragment --extract-hex
# (grad_*: plain compute, no --render)
```

`hex/` filenames mirror the original artifact name with the extracted stage appended
(`.fragment.hex` / `.compute.hex`). The regdiff register-pressure sweep (`regdiff_bytes/`) and
the minimal-pair splice pilot (`regsplice_probe/`, including the fast-math-ON F32-color archives
used to derive the frozen splice offset in `PRE_REGISTRATION.md` hypothesis 3) are both
represented this way.
