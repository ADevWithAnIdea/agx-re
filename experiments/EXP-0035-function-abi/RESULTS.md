# EXP-0035 Results — function-call / function-pointer / dynamic-library ABI (A18 Pro / G17P / Apple9)

**Verdict: G17P has a real CALL/RETURN implemented in the CONTROL-FLOW family (byte0 low-nibble
`0xf`) — NOT a dedicated new opcode group** (unlike matrix `0xcf` / RT `0xea`). Out-of-line helpers,
function pointers (`visible_function_table`), and dynamic libraries (`MTLDynamicLibrary`) all reduce to
the same primitive: a callee is a code region, a **CALL is a PC-relative masked branch that saves a
return context**, and a **RETURN is a target-less jump back via a hardware link/CF-stack**. Function
pointers are a table of **code VAs**; a dynamic-library symbol resolves at pipeline-build to an
ordinary direct call.

Device: Apple A18 Pro / G17P, macOS 26.6 (25G5043d), Metal 4 / Apple9. `supportsFunctionPointers`,
`supportsDynamicLibraries` = YES. **No faults, no reboots.** Everything below is HW-validated unless
tagged *(inferred, byte-diff)*.

---

## 1. Call / return instruction encoding + target/return-address mechanism

A `[[visible]]` or `__attribute__((noinline))` helper compiles **out-of-line** as its own symbol
region in the **same** `__TEXT,__compute` section (mangled `l__Z…` for a static helper, `_vname` for a
visible function, `_<name>.MTL_VISIBLE_FN_REF` for a resolved dynamic-library symbol). The caller's
`_agc.main` invokes it; an inlined baseline with identical math emits neither the marker nor the call.

### CALL — `0f 05 54 1a 8f 00 56 <off40> 00` (14 bytes) ✅ HW-validated
| byte | value | meaning |
|---|---|---|
| +0 | `0x0f` | control-flow group |
| +1 | `0x05` | sub-op = the execution-mask **push** reused as call (masked branch) |
| +2 | `0x54` | CF marker (same marker byte as jump `0f 00 54`) |
| +3 | `0x1a` | constant *(inferred)* |
| +4 | `0x8f` | **CALL/link signature** (also the 14-vs-8-byte disambiguator vs a plain predication push) |
| +5 | `0x00` | — |
| +6 | `0x56` | constant CALL signature |
| +7..+12 | `off40` | **signed little-endian PC-relative offset** |
| +13 | `0x00` | tail |

**Target = (call_instruction_address + 4) + off40.** Verified EXACT for four call sites at different
distances (helper always at section offset 64): `k_add` −104, `k_many` −158, `k_pressure` −552,
dynamic-lib consumer −458 — all predict the callee's exact entry (`raw/call_offset_verify.txt`).

- **Call-site marker `43 00 00 01` (4 B)** precedes **every** out-of-line call. This is the **same
  byte0 `0x43`** that EXP-0030 named `obj_mesh_ctrl` and thought mesh-unique — it is really the
  **call/frame-setup marker**; mesh only showed it because mesh stages call compiler-generated helper
  subroutines. (Cross-experiment correction.)
- After the call: `0f 06 04 02 00 00` (6 B) reconverge. The call reuses the `0f 05`/`0f 06`
  execution-mask push/pop machinery, so a call is a **masked branch that saves the return context**.

### RETURN — `8f <lm> 54 00` (4 bytes) ✅ HW-validated
byte0 `0x8f` = control-flow family with the link/return high bit; byte+2 `0x54` marker.
**No target field** → the return address comes from a **hardware link register / control-flow
(reconvergence) stack**, not the instruction. `8f 02 54 00` is byte-identical at the tail of every leaf
helper regardless of body or return type; `lm` byte+1 = `0x02` (leaf) or `0x12` (non-leaf, restores its
spilled link). *(leaf/nonleaf distinction inferred from the 0x02/0x12 byte-diff + the 6f/07 frame ops.)*

**HW validation:** `k_add` (A+B), `k_mul` (A×B), and 3-level nested `k_chain` (`main→mid→leaf`, leaf
called twice) all dispatch to correct outputs from the archived machine code (`PIPELINE_SOURCE archive`,
`COMPARE MATCH`; `raw/hwval.txt`).

## 2. Calling convention

- **Arguments** pass in consecutive 32-bit GPRs from **r10**: `arg0→r10, arg1→r11, arg2→r12, …`
  (HW-observed: `h_sub` computes `r10 + (−r11) = a−b`; `vadd`/`vmul` read r10,r11). `half` args use the
  low 16 bits of their GPR. For the arg counts tested (≤12) everything passes in registers — a 12-arg
  helper marshals args via vector `device_load`s into consecutive regs; **no separate argument stack**.
- **Return value** → **r10** for float/int/half (the callee's final op always targets r10).
- **Caller/callee-saved:** leaf callees clobber low GPRs freely. A **non-leaf** callee (one that itself
  calls) must preserve its own return address: it emits a `6f…` **prologue** and brackets each nested
  call with a pair of `0x07` ops (`07 00 54 00 81 00 00 00` before, `07 00 54 00 81 ff 1f 00` after)
  that **save/restore the link register to per-thread scratch** (the EXP-0020 spill stack), returning
  via `8f 12 54 00`. Register partitioning beyond the link register is compiler-managed (the program is
  co-compiled), not a HW-enforced split.
- **Stack frame = the EXP-0020 per-thread SCRATCH.** A callee exceeding the 96-GPR file spills there
  (`h_pressure`: 512 B of callee code, spills, dispatches correctly); a non-leaf callee also saves its
  link there around inner calls. Return-address mechanism = a **hardware link register / CF stack**;
  depth is bounded by that stack.
- **Recursion → LOOP.** Tail recursion is lowered to iteration: `rec()` compiled to a single 128-B
  region with a `0f 00 54 <neg-off>` backward jump and **no self-call**. Unbounded recursion is not
  representable → call depth is statically bounded at compile time.

## 3. Function pointers — `visible_function_table` (indirect call) ✅ HW-validated

- Plain `newComputePipelineStateWithFunction:` **DCEs** the indirect call (`_agc.main` = `0e000000`);
  it must be built with **`MTLLinkedFunctions`** (our `fndump.m`). Then the visible functions compile as
  their own regions (`_vadd`, `_vmul`) using the **same ABI** (args r10,r11 → r10).
- **Descriptor (DATA-TRACE, iotrace of our OWN process):** the table is a **flat array of 8-byte
  little-endian CODE VAs**; **entry[i] = the GPU virtual address of function i's entry point**
  (stride 8). Proven: a `{vadd,vmul}` table held exactly `0x100000004c0` and `0x10000000500`, and the
  shader-code BO at `code+0x4c0` / `+0x500` held vadd / vmul (byte-identical to standalone).
  (`raw/fptr_table_and_vft.txt`, `raw/vft_iotrace_excerpt.txt`.)
- **Binding:** a Tier-2 **argument-buffer slot** (buffer index), exactly like the RT
  `intersection_function_table` (EXP-0023) — same model, one mechanism.
- **Resolve sequence:** a **uniform** (thread-invariant) index resolves in the **constant/uniform
  program** (a constant table index changes ONLY one byte, `cp+0x5a: 0x20→0x21` for index 0→1). A
  **per-lane** index device-loads `entry[sel[i]]`, marshals it via a run of `0x4b` moves, and issues the
  **indirect call `0f 80 …`** (byte+1 `0x80` = the call-to-address variant of the CF group), returning
  via `8f…`. **HW:** `fptr_call(sel=0→vadd, sel=1→vmul)` → `RESULT 8 15 10 24` (= 3+5, 3×5, 4+6, 4×6). ✅

## 4. Dynamic libraries — `MTLDynamicLibrary`

- **Userspace-visible artifact:** a dynamic library (`MTLLibraryTypeDynamic` + `installName`) serializes
  to a Metal fat binary whose AppleGPU image is a **Mach-O of filetype 14 (MH_DYLIB)** carrying the
  exported functions' AGX code in `__TEXT,__text` (+ `__descriptor`/`__metallib`). A real shared library
  of GPU code, not an opaque blob.
- **Symbol reference:** a consumer references a dylib symbol as an **external
  `<mangled>.MTL_VISIBLE_FN_REF`**. The consumer *compiles* with the ref unresolved; it is resolved at
  **pipeline build**, which requires the dylib loadable by its `installName`/URL
  (`newDynamicLibraryWithURL` + `compileOptions.libraries` + `preloadedLibraries`). Missing it →
  `Undefined symbols: dl_scale.MTL_VISIBLE_FN_REF`.
- **Resolved call = ordinary direct call.** Once resolved, the dylib function's code is **linked in** as
  a region `_<name>.MTL_VISIBLE_FN_REF` adjacent to `_agc.main` and invoked by the normal
  `0f 05 54 1a 8f 00 56 <off40> 00` (verified: the consumer's PC-relative offset −458 targets exactly
  the linked-in ref region at section offset 0). **No distinct dynamic-lib call instruction** — the
  "dynamic" part is purely **loader resolution**.
- **Kernel/firmware-managed:** placing the dylib code into the GPU address space and binding the
  `.MTL_VISIBLE_FN_REF` symbol to a code VA is done by the Metal runtime + the GPU loader at pipeline
  build (a kernel-interface concern, like shader-code BO residency). Userspace supplies the serialized
  dylib + installName; it does not patch call targets itself.

## 5. HW-validated vs inferred

| Fact | Status |
|---|---|
| CALL opcode `0f 05 …` 14 B, PC-relative target = call+4+off40 | ✅ HW (offset exact ×4; dispatch correct) |
| RETURN opcode `8f 02 54 00`, no encoded target (HW link) | ✅ HW (invariant tail; dispatch correct) |
| Direct + 3-level nested call correctness | ✅ HW (`k_add`/`k_mul`/`k_chain` COMPARE MATCH) |
| ABI: args r10,r11..; return r10 | ✅ HW (h_sub sign; dispatch correct) |
| Non-leaf frame: `6f` prologue + `07` link save/restore + `8f 12` ret | ⏳ byte-diff (structure clear; fields not splice-isolated) |
| Recursion → loop (no self-call) | ✅ (byte-level: back-edge, no self-call) |
| visible_function_table indirect call correctness | ✅ HW (`RESULT 8 15 10 24`) |
| Function-table entry = 8-byte code VA | ✅ DATA-TRACE (iotrace; byte-identical bodies at the VAs) |
| Indirect-call opcode `0f 80` + `0x4b` marshalling | ⏳ byte-diff (behaviour HW-validated; operand fields TBD) |
| `0x43` = call/frame marker (corrects EXP-0030 mesh-unique claim) | ✅ byte-observed in plain compute |
| MTLDynamicLibrary = userspace MH_DYLIB of AGX code | ✅ (our own serialized artifact) |
| Dylib symbol = external `.MTL_VISIBLE_FN_REF`, resolved → direct call | ✅ (offset targets linked-in ref) |

## 6. Recommended next
1. Indirect-call (`0f 80`) full operand bit-decode + the `0x4b` target-marshalling run — build an
   indirect-call splice testbed (like extending `agxtest` with a function table).
2. Splice-isolate the `0x07` link save/restore and `0x6f` non-leaf prologue fields.
3. `supportsFunctionPointersFromRender` — callable functions from a fragment shader (RT-from-render).
4. Feed the `call`/`ret`/`call_indirect` descriptors into `docs/isa`; update EXP-0030's `obj_mesh_ctrl`
   semantics (0x43 = call/frame marker). The function-table code-VA descriptor also feeds
   `docs/descriptors` alongside the RT intersection-table (EXP-0023).

## 7. Clean-room status
Clean. Only our own MSL was compiled; only our own compiled bytes / our own process' GPU buffers were
inspected. `fndump.m`, `dynlib.m`, `dump_regions.py`, and all `kernels/*.metal` are ours; reused
OWN-SHADER tools `shdump`/`agxparse.py`/`agxrun`/`agxtest.py`/`agx-isa`/`iotrace` verbatim (not edited).
`raw/` holds text logs only; `.bin`/`.metallib` archives and iotrace `.hex` snapshots stayed on the
device under `~/cleanroom_work/exp0035/`. `tools/agx-isa/` was NOT edited — validated descriptors are in
`new_descriptors.json` for the orchestrator to merge.
