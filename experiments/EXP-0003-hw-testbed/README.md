# EXP-0003: Hardware testbed — the round-trip engine (assemble → run → observe)

- **Date:** 2026-07-06
- **Clean-room category:** OWN-SHADER + PUBLIC
- **Phase / question:** Phase 0.4 — build the reusable hardware validation harness
  that turns a (possibly hand-modified) `_agc.main` byte sequence into a real GPU
  dispatch with controlled inputs and read-back outputs. Unblocks all of Phase 1.
- **Device state:** Apple A18 Pro, SoC T8140, G17P, macOS 26.6 (25G5043d), Metal 4 /
  Apple9, SIP disabled. Command Line Tools only (runtime `newLibraryWithSource:`).
  No nvram/boot-arg changes.

## Hypothesis

1. We can re-inject the extracted `_agc.main` bytes of one of our own compiled
   kernels into a runnable pipeline and dispatch it — an **identity round-trip** —
   getting the expected output. This proves the splice mechanism is faithful.
2. Metal will **load and run byte-modified** compiled code (it does not
   checksum/sign the machine code and reject tampering).
3. The EXP-0001 float op-select hypothesis (`1c`=add, `1d`=mul, bit 0 of the byte
   at offset `0x22` of this kernel's `_agc.main`) is real: flipping `1c→1d` in an
   `out[i]=a[i]+b[i]` kernel turns it into `out[i]=a[i]*b[i]` on hardware.

## Method

The public MIT applegpu `hwtestbed` technique, reimplemented as our own tools:
splice raw shader bytes into a **serialized Metal binary archive** in place, then
reload the archive and force the compute pipeline to instantiate **from the
archive's precompiled machine code** (`MTLPipelineOptionFailOnBinaryArchiveMiss`)
rather than recompiling from AIR. Clean-room legal (allowed technique #3 + reading
public materials): we only ever compile our own MSL and splice our own compiled
bytes; no Apple binary is disassembled or introspected.

Tools (`tools/agxtest/`, plus EXP-0001's `tools/shdump/`):
- `shdump.m` — our MSL → serialized binary archive.
- `agxparse.py` — Mach-O/Metal-fat parser; `locate_region()`/`--locate` gives the
  absolute file offset+length of `_agc.main` for exact in-place splicing.
- `agxrun.m` — loads the (spliced) archive, forces archive-backed pipeline
  creation, dispatches with input buffers, dumps outputs as hex.
- `agxtest.py` — driver: compile → locate → splice → run → decode/compare, with a
  hard per-dispatch timeout (wedged-GPU guard).
- `sshto.py` — host-side SSH hard-timeout wrapper (kills a hung remote dispatch).

## Procedure

Reproduce end to end from the repo root:

```sh
experiments/EXP-0003-hw-testbed/run_all.sh   # deploy, build, run all stages
```

Single ad-hoc round-trip (on the device, in `~/cleanroom_work/exp0003`):

```sh
# identity: out[i]=a[i]+b[i]
python3 agxtest.py --source kernels/add.metal --function k --grid 8 --tg 8 \
  --buf 0=1,2,3,4,5,6,7,8 --buf 1=10,20,30,40,50,60,70,80 --out 2=8 \
  --expect 2=11,22,33,44,55,66,77,88 --dump-main

# op-select flip 1c->1d (add -> mul)
python3 agxtest.py --source kernels/add.metal --function k --grid 8 --tg 8 \
  --buf 0=1,2,3,4,5,6,7,8 --buf 1=10,20,30,40,50,60,70,80 --out 2=8 \
  --expect 2=10,40,90,160,250,360,490,640 --splice _agc.main@0x22=1d --dump-main
```

Inputs used throughout: `a = [1..8]`, `b = [10,20,…,80]`, grid = 8 threads.

## Raw results

Text logs in `raw/` (device stdout; no binary archives committed):

| log | what | result |
|---|---|---|
| `stage1_identity.log` | pristine add archive, re-loaded & run | out = `11 22 … 88` = a+b, **MATCH** |
| `stage1b_noop_splice.log` | rewrite the same byte `1c→1c` at `0x22` | out = a+b, **MATCH** (write path faithful) |
| `stage3_opselect_flip.log` | splice `1c→1d` at `0x22` in the add kernel | out = `10 40 90 160 250 360 490 640` = a*b, **MATCH** |
| `stage3_crosscheck_native_mul.log` | compiler's own `mul.metal`, no splice | `_agc.main` byte-identical to spliced-`1d`; same output |
| `fault1_stop_zeroed.log` | `0e000000 → 00000000` at `0x34` | ran fine, out = a+b (no fault) |
| `fault2_stop_ff.log` | `0e000000 → ffffffff` at `0x34` | ran fine, out = a+b (no fault) |
| `fault3_opselect_ff.log` | `1c → ff` at `0x22` (undefined ALU op) | **GPU hang error, contained** (see below) |
| `fault4_all_ff.log` | entire `_agc.main` → 56×`ff` | ran, out = all-zero (benign decode, no fault) |
| `fault_recovery_check.log` | valid dispatch right after the hang | out = a+b, **MATCH** — device survived, no reboot |

Key byte facts (this kernel's 56-byte `_agc.main`):
`1ca010066710540000012000510100404600670044040101200051010040460009051c0100c0e7005400020121001100009011000e000000`
- op-select byte at offset `0x22` = `1c` (add). Compiler's mul differs only here (`1d`).
- absolute file offset of `_agc.main` in this archive: 7520; of byte `0x22`: 7554.

## Analysis

- **Identity round-trip works.** Re-loading the serialized archive and forcing an
  archive-backed pipeline reproduces the expected output exactly. The no-op splice
  proves our in-place write path does not corrupt the container.
- **Metal runs tampered machine code.** The `1c→1d` splice changed the output from
  `a+b` to `a*b` even though the AIR (from which Metal *could* recompile) still says
  "add". That is only possible if the **spliced machine code** is what executed →
  `FailOnBinaryArchiveMiss` genuinely serves the archived bytes, and Metal does not
  checksum/sign/reject a byte-modified compiled shader on G17P/macOS 26.6.
- **Op-select hypothesis hardware-validated.** `1c=add / 1d=mul` (bit 0 of the byte
  at `0x22`) is confirmed on silicon, and the spliced-`1d` program is byte-identical
  to the compiler's own multiply kernel — an independent cross-check.
- **Fault behavior.** Corrupting the trailing 4 bytes (`0x34`, past the store) never
  faulted — execution ends at/after the store; program extent is bounded by
  metadata, not solely the `0e000000` word (so `0e000000` is *not* a simple
  "required trailing stop"). An **undefined ALU op-select** (`1c→ff`) raised
  `kIOGPUCommandBufferCallbackErrorHang`, caught cleanly as an
  `MTLCommandBufferStatusError`; the device **survived** and the very next dispatch
  succeeded — **no reboot**. An all-`ff` program decoded benignly (wrote zeros). So
  fault severity is opcode-specific, and at least this common fault class is
  fully contained in userspace. **Total reboots this experiment: 0.**

## Established facts → docs

- Testbed exists and is hardware-validated (round-trip faithful; archive-backed
  pipeline runs spliced bytes) → `../../docs/isa/README.md` (lift ⏳ on the testbed)
  → add row to `../../PROVENANCE.md`.
- `1c=fadd / 1d=fmul` (float op-select, bit 0) **hardware-validated** → promote the
  EXP-0001 ⏳ item in `../../docs/isa/README.md` → `../../PROVENANCE.md`.
- Metal loads & runs byte-modified compiled shaders on G17P/macOS 26.6 (no
  code-integrity check) → note in `../../docs/isa/README.md` methodology → PROVENANCE.
- `0e000000` is **not** merely a required trailing stop (program extent bounded by
  metadata); revise the EXP-0001 stop ⏳ interpretation → `../../docs/isa/README.md`.
- GPU fault containment: illegal ALU op → contained `kIOGPUCommandBufferCallbackErrorHang`,
  device survives → note for Phase-1 scaling in `../../docs/ROADMAP.md`.

## Follow-ups

- Sweep the op-select byte across all 256 values to enumerate the float ALU op map
  (sub/min/max/etc.), classifying each as valid-op / no-op / hang, via this testbed.
- Nail down where "program end" is actually encoded (store's end bit vs `0e…`).
- Batch harness: pack many candidate shaders per submission and isolate faults, so
  Phase 1 can sweep encodings at throughput (see RESULTS §Phase-1 driving).
