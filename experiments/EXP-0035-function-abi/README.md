# EXP-0035: function-call / function-pointer / dynamic-library ABI (A18 Pro / G17P)

- **Date:** 2026-07-07
- **Clean-room category:** OWN-SHADER + HW-PROBE + DATA-TRACE (+ PUBLIC for the applegpu *shape*)
- **Phase / question:** capability backlog #13 — the calling convention for indirect calls / callable
  (ray) shaders that a Vulkan driver needs. Metal caps report `supportsFunctionPointers`
  (+FromRender) and `supportsDynamicLibraries`.
- **Device state:** Apple A18 Pro / G17P, macOS 26.6 (25G5043d), 5 GPU cores, Metal 4 / Apple9,
  SIP off. Compute kernels only. Reboots: 0.

## Hypothesis
G17P must have a real call/return mechanism (function pointers + dynamic libraries are advertised).
Either a dedicated new opcode group (like matrix `0xcf` / RT `0xea`) or a reuse of the control-flow
family. A `[[visible]]`/`noinline` helper should compile out-of-line; `visible_function_table` should
resolve like the RT `intersection_function_table` (EXP-0023). A calling convention (arg/return
registers, caller/callee-saved, a scratch stack frame tying to EXP-0020 spill) should be observable.

## Method (clean-room legal)
- **OWN-SHADER:** compile our own MSL (`kernels/*.metal`) with the public Metal API, extract the AGX
  bytes with our own parser (`agxparse.py`), and byte-diff / tokenize them (`agxisa.py`). Only our own
  compiled bytes are ever inspected — no Apple binary is disassembled.
- **HW-PROBE:** dispatch the archived machine code on the real GPU (`agxtest.py`, and our own
  `fndump.m` which links visible functions and builds a real `MTLVisibleFunctionTable`) and compare
  outputs — the call/return and the indirect call are validated end-to-end.
- **DATA-TRACE:** snapshot our OWN process' GPU buffers (`iotrace`, SIGUSR1) to read the
  visible_function_table descriptor (non-copyrightable data).

## Procedure
- `fndump.m` — our own compile+link+dispatch harness (public Metal API). Adds `MTLLinkedFunctions`
  (so an indirect call is emitted, not DCE'd), builds an `MTLVisibleFunctionTable`, and dispatches.
- `dynlib.m` — our own `MTLDynamicLibrary` probe (create/serialize a dynamic library, link a consumer).
- `dump_regions.py` — list + tokenize every symbol region of a compiled archive.
- Kernels: `direct_call.metal` (noinline helper vs inlined baseline), `abi.metal` (arg-register
  mapping, return isolation, many-arg, callee spill, two call sites), `chain.metal` (nested calls +
  recursion), `fptr_table.metal` / `fptr2.metal` (visible_function_table), `dylib_provider/consumer`.

Reproduce (device `~/cleanroom_work/exp0035/`):
```sh
clang -fobjc-arc -framework Metal -framework Foundation -o fndump fndump.m
./shdump -o dc.bin -f call_noinline kernels/direct_call.metal   # direct call/return
python3 dump_regions.py dc.bin
./fndump -o fp2.bin -f fptr_call --visible vadd,vmul kernels/fptr_table.metal   # indirect call
FNDUMP_SIGUSR1=1 IOTRACE_DUMP_ON_USR1=1 IOTRACE_DUMP_DIR=ftmaps \
  DYLD_INSERT_LIBRARIES=./iotrace.dylib ./fndump -o fpr.bin -f fptr_call \
  --visible vadd,vmul --run --A 3,3,4,4 --B 5,5,6,6 --sel 0,1,0,1 --n 4 kernels/fptr_table.metal
./dynlib kernels/dylib_provider.metal kernels/dylib_consumer.metal x use_dylib dlcons.bin
```

## Raw results
See `raw/`: `direct_call.txt`, `abi_and_frames.txt`, `call_offset_verify.txt`,
`fptr_table_and_vft.txt`, `vft_iotrace_excerpt.txt`, `dynamic_library.txt`, `hwval.txt`.
Validated descriptors + length-rule/ABI/function-table/dynamic-library facts:
`new_descriptors.json` (for merge into `tools/agx-isa/db.json`).

## Analysis / established facts
See `RESULTS.md`. Headline: CALL/RETURN live in the **control-flow family** (not a new opcode group);
args in r10,r11.., return in r10; the return address is a **hardware link/CF-stack**; function-table
entries are **8-byte code VAs**; a `MTLDynamicLibrary` is a **userspace-visible Mach-O dylib** whose
symbol resolves at pipeline-build to an ordinary direct call.

## Follow-ups
- Full operand bit-decode of `call_indirect` (0f 80) — needs an indirect-call splice testbed.
- The `0x07` link save/restore and `0x6f` non-leaf prologue exact fields.
- RT-from-render callable shaders; `supportsFunctionPointersFromRender` (fragment-stage calls).
