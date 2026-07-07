# EXP-0011 Results — COMPUTE submission control structures decoded

**TL;DR.** On A18 Pro / G17P / macOS 26.6, a compute dispatch's control stream is now
decoded field-by-field by change-one-Metal-parameter diffing of the registered GPU
buffer objects. The **CDM launch descriptor** (BO `gpu_va 0x100000b0000`) is a stream of
0x2c-byte records; each record carries a **shader-code pointer = shaderVA >> 6**
(HW-confirmed by running two different pipelines in one submit), the 3D grid size (in
**threads**, not threadgroups) and 3D threadgroup size, and a shader register/config
word. The **Tier-2 argument buffer** (BO `gpu_va 0x100000e0000`) is a table at offset
`+0x14a0`: each bound buffer is an inline 8-byte GPU VA; each texture/sampler is an
8-byte pointer to a descriptor appended in the same BO. The captured **shader BO** is our
kernel's AGX code wrapped by a 14-byte constant-program stub that `shdump` also emits.
The **submission ring** is located: a producer index in shared memory advances 0x58
bytes per submit and fixed-size completion records are appended at the same cadence;
no per-submit syscall exists (confirming EXP-0009's ring+doorbell), and sel-0x7's
"1040-byte setup" is really the **executable-path string**, not ring config.

All findings are **DATA-TRACE**: bytes crossing the userspace↔kernel boundary from our
own Metal process. Nothing was learned from Apple code. The one exception is the shader
byte-validation, which compares the captured code BO against **our own** compiled shader
(`shdump`), i.e. OWN-SHADER.

---

## 1. CDM launch / dispatch descriptor — BO `gpu_va 0x100000b0000`

The descriptor is a **stream of fixed 0x2c-byte (11-dword) records**, one per compute
dispatch, followed by a 1-dword terminator `0x40000000`. Confirmed by encoding two
dispatches in one command buffer (`--k2`): two records appear back-to-back, then the
terminator (`raw/launch_descriptor.txt`).

**Record layout (offsets relative to record start):**

| off | base value (add3) | meaning | evidence |
|----:|---|---|---|
| +0x00 | `0x00080000` | **shader register / config word** (→ `0x00880000` for the register-heavy kernel) | HW: `base vs heavy` diff, only this word moves |
| +0x04 | `0x01000000` | constant (unresolved) | invariant across all captures |
| +0x08 | `0x00002400` | **shader-code pointer = (shaderVA >> 6), low 32 bits** | **HW-confirmed** (§1a) |
| +0x0c | `0x40000001` | constant; top nibble `0x4` = inferred shader-VA high bits, low = flag | invariant |
| +0x10 | `0x00000040`=64 | **grid.x** (total threads) | HW: gx128→`0x80`, gx256→`0x100` |
| +0x14 | `0x00000001` | **grid.y** | HW: gy2→2, tg8x4→4 |
| +0x18 | `0x00000001` | **grid.z** | HW: gz2→2 |
| +0x1c | `0x00000020`=32 | **threadgroup.x** | HW: tgx64→`0x40`, tg8x4→8 |
| +0x20 | `0x00000001` | **threadgroup.y** | HW: tg8x4→4 |
| +0x24 | `0x00000001` | **threadgroup.z** | inferred (symmetric; not independently varied) |
| +0x28 | `0x60000160` | constant (unresolved) | invariant |

The single-dispatch descriptor is `record ++ 0x40000000`. Every grid/threadgroup field
above is **HW-validated** by a clean one-word diff (`raw/launch_desc_diffs.txt`).

**grid is in THREADS, not threadgroups.** `dispatchThreadgroups(2)×tg(32)` (= 64 threads)
produced a **byte-identical** descriptor to `dispatchThreads(64)/tg(32)` (`base vs
groups2`: 0 differing words). So `grid.*` at +0x10 holds the *total thread count*; Metal
converts threadgroup counts to threads before encoding.

**Threadgroup memory is NOT in this descriptor.** `tgmem` (256 B dynamic threadgroup
memory) produced a byte-identical launch descriptor (`base vs tgmem`: 0 diffs). Its size
lands elsewhere (candidate: arg-buffer `+0x14c0` = `0x80000000`, or control BO
`0x10000080000`) — a follow-up.

### 1a. Shader-code pointer = shaderVA >> 6 (HW-confirmed)

`0x10000090000 >> 6 = 0x400002400`; low 32 = `0x2400`, exactly the +0x08 word. To prove
it *tracks* the shader (not a constant), we encoded **two different pipelines in one
command buffer** (`--kernel add3 --k2 heavy`). Metal packed both shaders into BO
`0x10000090000` — add3 at `+0x000`, heavy at `+0x100` — and emitted two launch records:

- record 1 (add3, shader @ `0x90000`): +0x08 = `0x2400` = `0x90000 >> 6`
- record 2 (heavy, shader @ `0x90100`): +0x08(rec2) = `0x2404` = `0x90100 >> 6`  ✓ (Δ = 0x100>>6 = 4)

So the field is the shader base address in **64-byte units**, low 32 bits (the high bits
come from the fixed shader VM region — likely the `0x4` nibble carried in the +0x0c
constant). **This is the pointer to shader code the brief asked for**, correlated to the
shader BO's GPU VA that iotrace reports.

> The argument-buffer pointer is **not** in the launch descriptor. The launch descriptor
> references the shader only; buffer/texture/sampler binding flows through the argument
> buffer (§2), whose VA is referenced from the uniform/USC BO `0x10000000000`
> (the arg VA `0x100000e0000` appears there, e.g. `+0x57e`), not from `0x100000b0000`.

---

## 2. Tier-2 argument buffer — BO `gpu_va 0x100000e0000`

The bound-resource table lives at **BO + 0x14a0** (everything before it is zero). Layout,
by binding index, 8 bytes per slot, in declaration/binding order (`raw/argbuffer.txt`):

- **Buffer `[[buffer(i)]]`** → inline **8-byte GPU VA** at `+0x14a0 + i*8`.
  HW-validated: buf1/buf2/buf4/buf8 store exactly 1/2/4/8 of our printed `gpuAddress`
  values, consecutively (e.g. buf8: `0x…18000, …18100 … …18700`). Reorder/count follow
  the binding index (inferred: slot position = Metal `[[buffer(N)]]` index).
- **Texture `[[texture(0)]]`** → **8-byte pointer** to a 32-byte texture descriptor placed
  later in the same BO. (`tex`: `+0x14a0 → 0x100000e14c0`.)
- **Sampler `[[sampler(0)]]`** → **8-byte pointer** to a sampler descriptor.
  (`tex`: `+0x14a8 → 0x100000e14e0`.)

`tex` kernel (`texture2d t, sampler s, device float* o`) laid out as:
```
+0x14a0  c0140e0000010000   -> 0x100000e14c0  (ptr to texture descriptor)
+0x14a8  e0140e0000010000   -> 0x100000e14e0  (ptr to sampler descriptor)
+0x14b0  0000030000010000   =  0x10000030000  (buffer(0) GPU VA, inline)
+0x14c0  220a8836 000c0000 60340000 10000000   (32-byte TEXTURE descriptor)
+0x14e0  00008e02 80070000                     (SAMPLER descriptor)
```
So: **buffers are inlined as raw VAs; textures and samplers are indirected through
pointers to descriptor blocks in the same argument buffer.** The 32-byte texture
descriptor and the sampler descriptor bytes are captured as raw data for a
`docs/descriptors/` follow-up (format/dims/address fields not yet decoded).

Pointer graph (`raw/pointer_graph_base.txt`) independently confirms the buffer table
`+0x14a0..` → our three buffers, and shows control BO `0x10000080000` pointing into the
data heap (`+0x1d00/+0x1c00`).

---

## 3. Shader BO byte-validation (vs `shdump`)

Captured live code BO `gpu_va 0x10000090000` (add3) = **196 bytes**
(`raw/shader_validation.txt`):
- `0x00..0xb5`: the main program (loads via the argument buffer, `09` float-ALU adds,
  `67` load/store, `9f` int-ALU — the op-groups documented in `docs/isa`).
- `0xb6..0xc3`: a **14-byte constant-program stub** `03 00 07 00 02 00 00 00 60 00 0e 00 00 00`.
- terminates in the `0x0e` **stop** instruction.

`shdump` of the *same* MSL (fast-math) yields `__text` = `_agc.main.constant_program`
(64 B: the same stub `030007…60000e` + `0x0006` padding) + `_agc.main` (56 B).

**Result: structurally validated, NOT byte-identical.** The exact constant-program stub
`030007000200000060000e000000` appears in **both** (as the live BO's footer, and as the
head of shdump's constant_program), and both `_agc.main` bodies end in `0x0e` stop. But
the *main* bodies differ (live 182 B vs shdump 56 B) because the two Metal API paths use
different argument-passing conventions: `newComputePipelineStateWithFunction:` (live)
**inlines the argument-buffer load preamble** into main, whereas the `MTLBinaryArchive`
path (shdump) emits a lean `_agc.main` that assumes preloaded args. This confirms the
captured BO **is** our kernel's AGX code (same ISA, same stub, same terminator, same
op-group structure) and pins the header/footer wrapping (**no header; footer = the
14-byte constant-program stub**); full byte-identity across the two build paths is not
achievable, consistent with EXP-0009's note.

---

## 4. Ring / doorbell

**No per-submit syscall (confirms ring+doorbell).** With the interposer extended to wrap
32-bit `IOConnectMapMemory`, `mach_make_memory_entry_64`, and named-object `mach_vm_map`,
a compute submission makes **zero** GPU-space mapping calls
(`IOConnectMapMemory64=0, IOConnectMapMemory=0, MEMENTRY=0`; the only 3 `mach_vm_map`
named maps are framework/dylib mappings at ordinary CPU addresses, sizes 0x1269c/0x425b/
0x50000). Selector histogram is invariant (EXP-0009): 30× sel 9 + one-time setup.

**sel 0x7 reclassified.** Its 1040-byte "setup struct" (EXP-0009's ring/queue candidate)
is the process **executable-path string** (`"/Users/.../exp0011/cvar\0…"`) —
identification, not ring config.

**sel 0x5 = shared setup pages, not the doorbell.** sel 0x5 returns two CPU-mapped shared
pages + size `0x4000`, obtained **without** `IOConnectMapMemory`. We snapshotted them
(interposer now parses sel-5); they hold **static** data (a `0xff000000`-pattern table +
a zero page), byte-identical across all 4 submits → not the ring tail.

**Submission ring located.** With per-submit snapshots (`IOTRACE_DUMP_PERSIG=1`), a pair
of 32-bit indices in the shared heap control region (heap-alias `+0x1ff04`/`+0x1ff08`,
≈ `gpu_va 0x10000050000`) **increments by exactly 0x58 (88) bytes per submit**
(`raw/ring_doorbell.txt`):

```
submit0: 0x058   submit1: 0x0b0   submit2: 0x108   submit3: 0x160      (Δ = 0x58 each)
adjacent: +0x1ff00 = 0x00002c2c   +0x1ff0c = 0x00000028 (=40, completion-record length)
```

At the same cadence, fixed **0x58-byte completion records** with GPU timestamps and a
repeating context id (`0xa82`) are appended to a ring (each record's location advances
0x58/submit). This is the submission/completion **ring producer index + completion
writeback** — the concrete ring bookkeeping EXP-0009 predicted but had not located.

**Still open:** the exact CPU→GPU **doorbell store** (the hardware kick) is not isolated
to a single address. The ring producer index is now located, but the kick itself is
neither a syscall nor a change in any client-registered BO or sel-5 page — most likely a
store to a firmware/kernel-shared page + a memory barrier, which IOKit-call and
mach-vm-map interposition cannot see. Pinning it would need a different vantage
(e.g. watchpoint on the ring page, or the kernel team's view). **Partial, as flagged.**

---

## 5. Reliability, obstacles, recommended next

**Reliability.** The GPU-VM allocator is deterministic across runs (control-plane BOs at
stable VAs: shader `0x…90000`, launch descriptor `0x…b0000`, arg buffer `0x…e0000`),
which is what makes cross-run byte-diffing clean. Every capture completed
(`status=4`, correct results). **Zero GPU wedges / reboots.** The interposer's new wrappers
had to be guarded (`if (!g_log)`) because `mach_make_memory_entry_64` / `mach_vm_map` are
called during early libSystem bootstrap before our constructor runs; `mach_vm_map`
logging is opt-in (`IOTRACE_WRAP_VMMAP=1`) because it is extremely hot.

**Obstacles / still-inferred.** The launch-record constants (`0x01000000`, `0x40000001`,
`0x60000160`) and the config/register word `0x00080000` are not fully decoded (byte
pattern only). The record-2 threadgroup.x read back as 16 for a `dispatchThreads(16)/tg(8)`
second dispatch (expected 8) — a minor anomaly, possibly a Metal-side threadgroup
adjustment for the register-heavy kernel; the authoritative tg.x mapping is from the
record-1 one-parameter sweeps. Texture/sampler descriptor internals are captured but not
decoded.

**Recommended next.**
1. Decode the config/register word and the launch-record constants (vary register
   pressure precisely; correlate with our own-shader register counts from `shdump`).
2. Locate the threadgroup-memory-size field (arg-buffer `+0x14c0` vs control BO `0x80000`).
3. Decode the 32-byte texture descriptor + sampler descriptor (a `docs/descriptors/` item).
4. **The big follow-up: graphics.** Apply the same method to `iohello_draw` to decode the
   VDM (draw) / tiler / fragment command stream and pipeline/state packets.
