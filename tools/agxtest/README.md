# agxtest — AGX hardware round-trip testbed (assemble → run → observe)

Takes a (possibly hand-modified) `_agc.main` AGX byte sequence, makes it runnable
on the **real A18 Pro GPU**, dispatches it with controlled inputs, and reads back
the outputs. This is the validation engine for all of Phase 1: any candidate
encoding can be checked `bytes + inputs → outputs`.

**Clean-room:** OWN-SHADER + PUBLIC. Every byte we inspect or splice is the
compiled form of **our own** MSL (compiled by `shdump` from our own source). No
Apple binary is ever disassembled or introspected. The splice-and-reload
technique mirrors the public MIT applegpu `hwtestbed` (`metallib_replacer.py` +
`runner-mac.mm`); this is our own independent implementation.

## Pieces

| file | role | runs on |
|---|---|---|
| `agxrun.m` | ObjC runner. Loads a serialized Metal binary archive (possibly spliced), forces the compute pipeline to instantiate **from the archive's precompiled machine code** (`MTLPipelineOptionFailOnBinaryArchiveMiss`), dispatches, dumps output buffers as hex. | device (A18) |
| `agxtest.py` | Driver. Compiles our MSL → archive (`shdump`), locates `_agc.main` in the archive (`agxparse`), splices caller bytes in place, writes inputs, runs `agxrun` under a hard timeout, decodes/compares outputs. | device (A18) |
| `shdump.m` | (from `tools/shdump`) compile our MSL → serialized binary archive. | device |
| `agxparse.py` | (from `tools/shdump`) Mach-O/Metal-fat parser; `--locate SYM` returns the absolute file offset+length of a symbol region for in-place splicing. | anywhere |

`shdump.m` and `agxparse.py` are the EXP-0001 tools; agxtest depends on them and
expects them alongside `agxrun`/`agxtest.py` in the same directory on the device.

## Build (device, Command Line Tools only — no `metal` CLI needed)

```sh
clang -fobjc-arc -framework Metal -framework Foundation -o shdump shdump.m
clang -fobjc-arc -framework Metal -framework Foundation -o agxrun agxrun.m
```

## Use — "give me bytes + inputs → outputs"

```sh
# Identity round-trip: compile out[i]=a[i]+b[i], run it, read back.
python3 agxtest.py --source add.metal --function k --grid 8 --tg 8 \
    --buf 0=1,2,3,4,5,6,7,8 --buf 1=10,20,30,40,50,60,70,80 --out 2=8 \
    --expect 2=11,22,33,44,55,66,77,88

# Splice a byte into _agc.main and run it (flip float op-select 1c=add -> 1d=mul):
python3 agxtest.py --source add.metal --function k --grid 8 --tg 8 \
    --buf 0=1,2,3,4,5,6,7,8 --buf 1=10,20,30,40,50,60,70,80 --out 2=8 \
    --splice _agc.main@0x22=1d --dump-main
```

### agxtest.py options

- `--source SRC --function NAME` — our MSL and the kernel to run.
- `--grid N --tg T` — 1-D dispatch (`dispatchThreads`): N total threads, T per threadgroup.
- `--buf IDX=v0,v1,...` or `--buf IDX=@file` — input buffer (float32 by default, `--int` for int32).
- `--out IDX=NELEMS` — request an output buffer of NELEMS 4-byte elements.
- `--splice SYM@OFF=HEX` — splice HEX bytes at byte offset OFF inside symbol region
  SYM (default `_agc.main`); repeatable; length must fit the region (in-place only).
- `--expect IDX=v0,...` — compare a buffer to expected values (float tol 1e-4, or exact int).
- `--dump-main` — print `_agc.main` hex before/after splicing.
- `--run-timeout SEC` — kill `agxrun` after SEC (wedged-GPU guard; default 25). On
  timeout the driver prints `STATUS HANG` and exits 3.
- `--rebuild`, `--workdir DIR`, `--archive PATH`, `--shdump/--agxrun/--agxparse PATH`.

Output lines: `MAIN_LEN`, `MAIN_ORIG`/`MAIN_SPLICED` (with `--dump-main`),
`SPLICE ...`, `PIPELINE_SOURCE archive`, `GPUTIME_NS`, `STATUS OK|...`,
`RESULT IDX v0 v1 ...`, `EXPECT`/`COMPARE MATCH|MISMATCH`.

## How it forces the archived (spliced) bytes to run

`agxrun` builds the `MTLFunction` identity by recompiling the same source (same
AIR hash the archive was keyed on), then attaches the on-disk binary archive and
creates the pipeline with `MTLPipelineOptionFailOnBinaryArchiveMiss`. That flag
makes pipeline creation **fail** rather than silently recompile from AIR if the
archive does not supply the code — so a successful run proves the *archived*
machine code (which we spliced) was executed. Validated on hardware: splicing the
op-select `1c→1d` changes the output from `a+b` to `a*b` while the AIR still says
"add", which is only possible if the spliced machine code is what ran
(EXP-0003).

## Wedged-GPU guard

Bad shader bytes can fault or hang the GPU. `agxtest.py --run-timeout` kills a
stalled dispatch on the device; for host-side protection run the SSH invocation
under a hard timeout (see `experiments/EXP-0003-hw-testbed/run_all.sh` /
`sshto.py`). Observed on G17P/macOS 26.6: an illegal ALU op raised a **contained**
`kIOGPUCommandBufferCallbackErrorHang` command-buffer error — the device survived
and the next dispatch worked, no reboot (EXP-0003 §fault behavior).
