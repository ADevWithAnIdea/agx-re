# EXP-0003 Results — AGX hardware testbed (round-trip engine)

Clean-room category: **OWN-SHADER + PUBLIC**. Every byte spliced/inspected is the
compiled form of MSL **we wrote** (`kernels/add.metal`, `kernels/mul.metal`). No
Apple binary was disassembled or introspected. The splice-and-reload technique is
the public MIT applegpu `hwtestbed` method, reimplemented as our own tools.

Device: Apple A18 Pro / G17P, SoC T8140, macOS 26.6 (25G5043d), Metal 4 / Apple9.

## TL;DR

- **Identity round-trip: WORKS.** Extract our compiled `_agc.main`, re-inject it
  into the serialized binary archive, force an archive-backed pipeline, dispatch —
  output equals the expected result.
- **Metal runs TAMPERED machine code.** No checksum/signature check on the compiled
  shader: a single spliced byte changed the computed result, proving the spliced
  bytes (not an AIR recompile) executed.
- **`1c→1d` flipped add→mul on hardware.** Op-select hypothesis validated on silicon.
- **Fault behavior:** an illegal ALU op produced a *contained* GPU-hang command-buffer
  error; the device survived and kept running. **Zero reboots** the whole experiment.

## 1. The mechanism (how bytes get onto the GPU)

`shdump` compiles our MSL to a serialized `MTLBinaryArchive` (Metal fat binary,
magic `0xCBFEBABE`; AIR64 image + AppleGPU image; `_agc.main` lives in the AppleGPU
image's nested `__TEXT,__compute → __TEXT,__text`). `agxparse.locate_region` returns
the **absolute file offset** of `_agc.main`, so `agxtest.py` splices replacement
bytes **in place** (same length) without disturbing the container. `agxrun` then:

1. recompiles the same MSL → `MTLFunction` (the AIR-hash identity the archive is keyed on),
2. loads the spliced archive from URL as an `MTLBinaryArchive`,
3. creates the pipeline with `MTLPipelineOptionFailOnBinaryArchiveMiss` — which
   **fails** rather than silently recompiling from AIR if the archive doesn't supply
   the code — so a successful run means the **archived (spliced) machine code ran**,
4. dispatches (`dispatchThreads`) with input buffers and dumps outputs as hex.

Every run reported `PIPELINE_SOURCE archive`, i.e. no binary-archive miss.

## 2. Identity round-trip — WORKS

`kernels/add.metal` (`out[gid]=a[gid]+b[gid]`), inputs `a=[1..8]`,
`b=[10,20,…,80]`, grid=8. `_agc.main` (56 bytes) extracted, re-loaded, dispatched:

```
RESULT 2 11 22 33 44 55 66 77 88   ==  a+b        (stage1_identity.log)   MATCH
```

No-op splice (rewrite the same byte `1c→1c` at `0x22`) also produced `11…88`
(`stage1b_noop_splice.log`) — the in-place write path is byte-faithful (it does not
corrupt the archive). `_agc.main` is byte-identical to EXP-0001 k01_fadd.

## 3. Metal runs tampered code — YES (no code-integrity check)

The decisive test is §4: splicing one byte of the **compiled** shader changed the
**computed output**, while the archive's AIR still encodes "add". If Metal had
recompiled from AIR (or validated/checksummed the machine code), the splice would
have been a no-op or the load would have been rejected. Neither happened — Metal
loaded and executed the modified compiled shader on G17P/macOS 26.6.

Obstacles encountered: **none** for in-place, same-length splices of `_agc.main`
inside the serialized archive. We did not need to rebuild the container or fix any
size/offset/checksum field. (`FailOnBinaryArchiveMiss` + recompiling the identical
source for the `MTLFunction` was required to force archive-backed instantiation;
without a binary archive Metal would just recompile from AIR and ignore our bytes.)

## 4. `1c→1d` op-select flip — add→mul CONFIRMED ON HARDWARE

Same add kernel, same inputs, splice `_agc.main@0x22: 1c→1d`:

```
inputs   a = 1  2  3  4  5  6  7  8
         b = 10 20 30 40 50 60 70 80
add (1c) out = 11 22 33  44  55  66  77  88   = a + b   (baseline)
mul (1d) out = 10 40 90 160 250 360 490 640   = a * b   (stage3_opselect_flip.log)  MATCH
```

Raw output bytes for the `1d` run:
`00002041 00002042 0000b442 00002043 00007a43 0000b443 0000f543 00002044`
= float `10 40 90 160 250 360 490 640`.

**Cross-check:** the compiler's own `mul.metal` (no splice) produces a `_agc.main`
that is **byte-identical** to our spliced-`1d` program, and the same output
(`stage3_crosscheck_native_mul.log`). So the *only* machine-code difference between
the compiler's float-add and float-mul for this kernel is that one byte, and
flipping it on hardware flips the arithmetic. Op-select `1c=fadd / 1d=fmul`
(bit 0 of the byte at offset `0x22`) is **hardware-validated**, not merely inferred.

## 5. GPU fault / reboot behavior

| splice | intent | outcome |
|---|---|---|
| `0x34: 0e000000→00000000` | zero the trailing word (past the store) | ran, out = a+b, **no fault** |
| `0x34: 0e000000→ffffffff` | garbage in the trailing word | ran, out = a+b, **no fault** |
| `0x22: 1c→ff` | undefined float ALU op (isolated) | **GPU HANG error, contained** |
| whole `_agc.main` → 56×`ff` | fully invalid program | ran, out = all-zero, **no fault** |

The undefined-op run returned:
`STATUS CMDBUF_ERROR / Caused GPU Hang Error (00000003:kIOGPUCommandBufferCallbackErrorHang)`
— i.e. the GPU/kernel detected a hang and surfaced it to userspace as an
`MTLCommandBufferStatusError`. `agxrun` caught it; **SSH never wedged**; the very
next valid dispatch produced correct output (`fault_recovery_check.log`).

Readings:
- Fault severity is **opcode-specific**: some invalid bytes hang, others decode
  benignly. There is no blanket "invalid bytes → device wedge".
- At least this common fault class (**illegal ALU op**) is **fully contained**: the
  command buffer errors, the device stays alive, the next submission works — **no
  reboot**. Total reboots needed across the whole experiment: **0**.
- Corrupting only the trailing `0e000000` never faulted → program extent is bounded
  by metadata / the store's terminal effect, so `0e000000` is **not** a simple
  "required trailing stop" (revises the EXP-0001 ⏳ stop interpretation; needs its
  own probe).
- The hard-timeout guards (`agxtest.py --run-timeout`, host `sshto.py`) were never
  tripped here, but remain in place for worse hangs that *do* wedge the GPU (the
  `macvdmtool reboot` protocol is the fallback for those).

## 6. How Phase 1 should drive this testbed at scale

The engine is a clean `bytes + inputs → outputs` primitive; Phase 1 (build the A18
instruction database) is mostly **sweeps** over it. Recommended usage:

- **Encoding sweeps.** For a field of interest (e.g. the op-select byte), sweep all
  256 values through one fixed host kernel and classify each result as
  valid-op / no-op / hang. This is exactly `--splice SYM@OFF=<val>` in a loop; one
  archive compiled once, spliced per value.
- **Throughput / batching.** Each dispatch here is ~6–8 µs of GPU time; cost is
  dominated by process spawn + `newLibraryWithSource:` recompile per run. To scale:
  (a) reuse one compiled base archive across many splices (already done — `shdump`
  runs once, cached by source hash); (b) build a **batched runner** that keeps one
  process/`MTLDevice` alive and runs many spliced archives per launch (amortise
  device/library setup), à la the public hwtestbed's persistent-process protocol;
  (c) pack independent candidate programs into one submission where isolation
  allows. A persistent-runner variant of `agxrun` (loop reading `archive+inputs` on
  stdin) is the natural next tool.
- **Isolation.** For destructive sweeps, keep **one modification per dispatch** so a
  hang localises to a single encoding, and run each under the per-dispatch timeout.
  Because illegal-op faults are contained (no reboot), a persistent runner can log
  the error and continue to the next candidate — big throughput win. Fall back to
  fresh-process isolation + `macvdmtool reboot` only for the rare wedge.

**Limits / caveats.**
- Splices are **same-length, in place** (fits the existing `_agc.main` region).
  Changing program *length* needs container rebuild / offset fix-ups — deferred; not
  needed for field sweeps.
- The `MTLFunction` identity is obtained by recompiling the host MSL, so the host
  kernel's AIR must match the archive it was built from (same source/options). To
  test encodings the compiler never emits, splice into a host kernel whose length
  and I/O shape accommodate them.
- Read-back is via shared `MTLBuffer`s the kernel writes; probes must route their
  result to a bound output buffer to be observable (or reuse the compiler's store).
- Fault containment observed for illegal-ALU-op only; other fault classes (bad
  memory addressing, infinite loops) may behave differently — treat the reboot
  protocol as still live.

## 7. Clean-room status

Clean. Only our own MSL was compiled and only our own compiled `_agc.main` bytes
were spliced and executed. `shdump.m`, `agxparse.py`, `agxrun.m`, `agxtest.py`,
`sshto.py` are our own tools; the only third-party input is the *public* MIT
applegpu hwtestbed, used as a design reference (read), not run on Apple code. No
Apple binary was disassembled or introspected. `raw/` holds only text logs; the
`.bin` binary archives stay on the device under `~/cleanroom_work/exp0003/`.
