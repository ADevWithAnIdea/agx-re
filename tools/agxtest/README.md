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
| `agxrun.m` | ObjC runner (one-shot, one process per dispatch). Loads a serialized Metal binary archive (possibly spliced), forces the compute pipeline to instantiate **from the archive's precompiled machine code** (`MTLPipelineOptionFailOnBinaryArchiveMiss`), dispatches, dumps output buffers as hex. | device (A18) |
| `agxrender.m` | **Render runner (EXP-0008).** The vertex/fragment analogue of `agxrun`: loads a serialized **render** binary archive (possibly spliced), forces the render pipeline from the archive (`FailOnBinaryArchiveMiss`), draws a full-screen triangle into a small `bgra8Unorm` target, reads pixels back. HW-validated: splicing fragment bytes changes the pixel. | device (A18) |
| `agxrun_persist.m` | **Persistent runner (EXP-0005).** One live `MTLDevice`+queue for its whole lifetime; loops over `(spliced-archive, inputs) → outputs` requests read from stdin, **logging-and-continuing past command-buffer faults** (contained illegal-ALU-op hangs), so a 256-value field sweep is one process launch instead of 256. | device (A18) |
| `persistrun.py` | Driver/library for `agxrun_persist`: issues requests, parses responses, and applies a **per-request watchdog** that kills+restarts the child (optional reboot hook) on a true GPU wedge, so big sweeps are robust. | device (A18) |
| `saferunner.py` | **Leak-free wrappers for the persistent runners (DEF-0178-1).** One reader thread per child, tagged by owner; a malformed response becomes the new `MALFORMED` status instead of an exception. Use over the shared or over an experiment's pinned `PersistRunner`. | anywhere |
| `verify_remote.py` | **Post-push hash verification, as its own unchained step.** Hashes the pushed blobs *on the device* against the contract's frozen `authored_sha256`; exit 3 = do not start a capture. | anywhere |
| `closure_scan.py` | **AST gate: no closure may read a name its enclosing scope rebinds.** Exit 1 on a finding; drops into any experiment's selftest. | anywhere |
| `fakepersist.py` | Device-free stand-in for `agxrun_persist` (modes `good` / `truncate` / `hang_first` / `eof_first`), so the host-side plumbing can be gated with no GPU. | anywhere |
| `selftest_tools.py` | The offline gate suite (T0-T7) for the three checks above. **No GPU, no device, no SSH.** | anywhere |
| `agxtest.py` | One-shot driver. Compiles our MSL → archive (`shdump`), locates `_agc.main` in the archive (`agxparse`), splices caller bytes in place, writes inputs, runs `agxrun` under a hard timeout, decodes/compares outputs. | device (A18) |
| `shdump.m` | (from `tools/shdump`) compile our MSL → serialized binary archive. | device |
| `agxparse.py` | (from `tools/shdump`) Mach-O/Metal-fat parser; `--locate SYM` returns the absolute file offset+length of a symbol region for in-place splicing. | anywhere |

`shdump.m` and `agxparse.py` are the EXP-0001 tools; agxtest depends on them and
expects them alongside `agxrun`/`agxtest.py` in the same directory on the device.

## Build (device, Command Line Tools only — no `metal` CLI needed)

```sh
clang -fobjc-arc -framework Metal -framework Foundation -o shdump shdump.m
clang -fobjc-arc -framework Metal -framework Foundation -o agxrun agxrun.m
clang -fobjc-arc -framework Metal -framework Foundation -o agxrender agxrender.m   # render (EXP-0008)
```

## Render testbed — "give me a (spliced) fragment/vertex → pixel" (EXP-0008)

```sh
# 1. compile a render pair -> archive (shdump --render), then draw + read back:
./shdump -o r.bin --render --vertex v_main --fragment f_main render.metal
./agxrender --archive r.bin --source render.metal --vertex v_main --fragment f_main \
    --width 1 --height 1                         # 1x1 target, prints PIXEL rgba
#   --tex-fill R,G,B,A  binds a solid input texture+sampler at [texture(0)]/[sampler(0)]

# 2. splice fragment bytes in place and observe the pixel change:
LOC=$(python3 agxparse.py r.bin --stage fragment --locate _agc.main)   # "ABS_OFF LEN"
#   ... write your byte(s) at ABS_OFF+offset into a copy of r.bin, then:
./agxrender --archive r_spliced.bin --source render.metal --vertex v_main --fragment f_main
```

`agxrender` is one-shot (fresh `MTLDevice` per run), so each spliced archive
actually executes (no in-process code memoization). `PIPELINE_SOURCE archive` in
the output proves the archived (spliced) machine code ran — creation fails with
`STATUS PIPELINE_MISS` otherwise. Proven on hardware: splicing the constant-color
fragment's green byte flipped the read-back pixel green 0.502→0.251 (EXP-0008).
For large fragment sweeps, add a `newLibraryWithURL:`-per-request persistent loop
(as `agxrun_persist` does for compute) — noted follow-up.

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

## Persistent runner (`agxrun_persist` + `persistrun.py`, EXP-0005)

For field sweeps, spawning one process per splice is dominated by process/Metal
startup. `agxrun_persist` keeps one `MTLDevice` alive and takes requests on
stdin:

```
READY <device>                                  # printed once at startup
# request:  <id> <archive> <grid> <tg> <nin> [idx:file ...] <nout> [idx:nbytes ...]
# response: REQ <id> / STATUS ... / [GPUTIME_NS n] / [OUT idx hex ...] / DONE <id>
```

**Critical gotcha it solves:** a library built from *source*
(`newLibraryWithSource:`) has a fixed AIR hash whose native code the device
**memoizes in-process** — so after the first pipeline build, a later *spliced*
archive is silently ignored and the ORIGINAL code runs. `agxrun_persist` instead
loads a **fresh `MTLLibrary` from the spliced archive's own bytes**
(`newLibraryWithURL:`) each request (the public hwtestbed's approach), so each
splice actually executes. Verified: `1c→1d` flips add→mul, `0xff` faults
(contained), the next request recovers — all in one process.

```sh
clang -fobjc-arc -framework Metal -framework Foundation -o agxrun_persist agxrun_persist.m
# see experiments/EXP-0005-float-alu-isa/opsweep.py for a full sweep driver
```

---

# Shared offline checks — why each one exists

Upstreamed **2026-08-30 by EXP-0185** from `EXP-0178-g17p-sysval-tileread/harness/` and
`EXP-0179-g17p-call/harness/`, where each was written and where each caught a real, live
defect within an hour. They were one-off copies; the next agent would not have had them.

Every one of them keeps its gate. Run all of them, on any machine, with **no GPU, no
device and no SSH**:

```sh
python3 tools/agxtest/selftest_tools.py      # T0..T7, ~3 s, exit 0 iff all pass
```

A check that has been copied without its gate is a check nobody will trust.

## 1. `saferunner.py` — one reader per child, and a malformed response is not an observation

**The failure it catches (DEF-0178-1).** `persistrun.py` starts a **fresh reader thread per
line and abandons it on timeout**, and that thread **re-resolves `self.proc` at execution
time** — so after the first watchdog timeout the abandoned thread can wake on the
*replacement* child's stdout and race the foreground reader. Responses come back truncated
(`OUT 0 ` with the hex missing) and the shared parser raises
`ValueError: not enough values to unpack (expected 3, got 2)`.

**What it cost.** In EXP-0178's pilot, one benign case poisoned **every later request
including the unspliced health check**, and three consecutive cases were recorded `hang`
with `restarts=99` — all false.

**The severity, widened.** A *real* hang is not required: **a mere WATCHDOG TIMEOUT is
enough to start the cascade.** EXP-0178 verified by hand, outside the harness, that its
pre-registered hang candidate runs clean on G17P (`STATUS OK`, `GPUTIME_NS 5000`, sentinel
written) — so **all four "hangs" in its pilots were manufactured on a case the hardware
handles fine.** The suspect set is therefore *any experiment whose runner ever timed out*,
not merely those that hit a real hang. **A false hang and a real inertness are
indistinguishable in a summary**, so one timeout can withdraw fields for an artefact.

**The two changes**, either usable alone, both defaults-preserving:

1. **One reader thread per child, tagged by owner.** The pump pushes `(proc, line)`; the
   reader discards any tuple whose `proc` is not the current child. DEF-0153-2 (an exited
   child must read as a wedge, not `""` forever) is preserved by an explicit `None` at EOF.
2. **A malformed response is a MEASUREMENT FAILURE**, recorded as the new `MALFORMED`
   status with the raw lines kept — never a crash, never a `hang`. Downstream, score it as
   `measurement_failed` and **remove it from the agreement computation and from
   `values_dispatched`** (EXP-0178 `analysis/verdicts.py`); refuse a field whose
   measurement failures exceed 1% of its dispatched values.

**Its gate.** `selftest_tools.py` T2 reproduces the defect deterministically against the
device-free stub: the **shared** runner *raises*, the safe one returns `MALFORMED` with the
raw kept. T3 runs the cascade (one genuine timeout, then two benign requests) and T4 proves
the owner tag discards a dead child's line without relying on scheduling luck.

**Note what T3 does *not* claim.** On the stub, the shared runner often does *not* cascade —
the abandoned thread usually binds to the old child at `rd()` entry, so the real failure
needs scheduling luck. That result is printed as an OBSERVATION, never as a gate: **a clean
result from a stub is not evidence a defect is absent.** What is relied on is the structural
fix.

## 2. `verify_remote.py` — a frozen contract hashes what you *authored*, not what the device *runs*

**The failure it catches.** Every experiment freezes `authored_sha256` and re-verifies it
before a capture — against the **local** files, which of course match, because they are the
files that were hashed. Nothing checked the remote copy, so a push that silently failed left
a contract **whose every hash was correct and whose every claim about the executing harness
was false**.

**What it cost.** On its very first run, against its own author: **11 of 18 blobs matched** —
two files missing on the neo, five stale, every amendment since the first push having
silently failed to arrive. A gated pair started at that moment would have run the
pre-amendment harness under a contract asserting otherwise, and nothing before or after
would have noticed. EXP-0179 hit the same failure in the other order: a `push` returning
non-zero inside an `&&` chain ran a pass against a stale harness and burned a run id.

**The rule.** It is a **separate, never-chained step**. Running it inside the same chain as
the push reintroduces the defect it exists to catch, because a silent no-op inside a chain is
indistinguishable from success in the exit code.

```sh
export SSHPASS=...                                  # never written to any file
bash harness/sync.sh push
python3 ../../tools/agxtest/verify_remote.py \
    --contract CAPTURE_CONTRACT.json --remote agxre/EXP-0185 ; echo $?
# 0 = go ; 3 = MISSING/STALE, do NOT start a capture ; 2 = nothing was verified
```

An empty check is **not** a pass: if `--prefix` matches no contract keys it exits 2 and says so.

**Its gate.** T7 builds a fake "remote" tree locally (`--local-root`) and asserts OK,
MISSING, STALE and the empty-check refusal all come back with the right exit codes.

## 3. `closure_scan.py` — no closure may read a name its enclosing scope rebinds

**The failure it catches.** EXP-0178's `run.py` bound the compute arm's read-back size as
`nb` and a closure passed it as `outs={0: nb, 4: nb}`. Two hundred lines later the
pre-registered falsifier did `nb = bytearray(blk0)`. Python resolves a free variable at
*call* time, so from the falsifier onward every request asked for a read-back of *a
bytearray* bytes. `raw/g17p_20260830_run01` was lost.

**Why it is worth a mechanical check rather than care — the general lesson.** The failure
presented as a HANG CASCADE (one clean case, then everything unrecoverable including the
unspliced health check), which is **byte-for-byte the signature of DEF-0178-1, the defect the
same agent had fixed twenty minutes earlier**. Four pilots did not separate them. What
resolved it was a traceback, not reasoning. **Having just fixed a cascade-shaped defect makes
the next cascade-shaped defect harder to see**, because the first explanation is available and
it fits.

```sh
python3 tools/agxtest/closure_scan.py harness/run.py main \
    --allow 'mnem:assigned in two mutually exclusive if/else branches'
```

Mutually exclusive `if`/`else` branches are safe and are the expected false positive, so
pass an explicit allow-list **with a reason** rather than weakening the rule.

**Its gate.** T6 flags the planted rebind in `testdata/closure_shadow_bad.py`, clears the
corrected fixture, and proves the allow-list is load-bearing. Run against the file the
defect was actually found in, it reports exactly EXP-0178's three allow-listed names and
nothing else.

---

# Pitfall: a promotion gate written `moved >= 2.0 × max(disagree, 1)` cannot promote ANY width-1 field

Not a tool — a defect shape to recognise while writing a gate, because it is silent and it
suppresses exactly the fields you most want.

EXP-0178 found it **in its own gate, against its own frozen text**. `PRE_REGISTRATION` §8 and
`CAPTURE_CONTRACT.promotion_gate` both say

> movement `>= 2.0 ×` the number of disagreeing values, **and `> 0`**

but the implementation wrote:

```python
ok_move = len(moved) >= 2.0 * max(len(disagree), 1)          # WRONG: silently stricter
```

With zero disagreements — the *best possible* outcome — the `max(...,1)` clamps the
threshold to 2, so a field needs **two moving values**. A **width-1 field has at most one
value that can differ from its own baseline**, so no 1-bit field can ever clear it. It was
suppressing `read_en`, the silent-zero read-enable the experiment was dispatched to
re-verify, on an arithmetic artefact rather than on the evidence.

```python
ok_move = len(moved) >= 2.0 * len(disagree) and len(moved) > 0   # the frozen, correct form
```

Two habits fall out of this, and they generalise past this one expression:

- **Write the gate's cases before the gate.** EXP-0178's G6 drives synthetic run pairs that
  *should* pass and each broken shape that *should* fail, checking that each refusal names
  its own reason. A gate with no refusal test is a gate you are trusting on its looks.
- **Re-read the gate against the frozen text, not against your memory of it.** This defect
  survived because the code and the contract were both read as saying the same thing.
