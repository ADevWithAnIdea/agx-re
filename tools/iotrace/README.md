# iotrace — IOKit/IOGPU DATA-TRACE harness

Captures, from **our own** minimal Metal program, exactly what userspace hands
the kernel to submit GPU work on the A18 Pro / G17P (macOS 26). A
`DYLD_INSERT_LIBRARIES` interposer over the IOKit user-client surface logs the
DATA crossing the userspace↔kernel boundary and snapshots the GPU buffer objects
Metal encodes the control/command stream into. This is ROADMAP 0.5; it answers
the "modern submission path" open question and seeds Phase 2 (cmdstream decode).

**Clean-room: DATA-TRACE + OWN-SHADER.** Everything here logs *data* only — call
selectors, struct payload bytes, and the contents of mapped/registered memory —
from **our own** Metal process. Command buffers, descriptors and register values
are non-copyrightable per the Asahi clean-room policy. Nothing here disassembles
or introspects the **code** of Metal, AGX* or IOGPU. The interposer technique and
the `DYLD_INTERPOSE` macro are the public ones from Apple dyld / the MIT+APSL
Asahi `wrap.c`; this is our own independent implementation, written from the
public IOKit interface (not copied).

## Pieces

| file | role | runs on |
|---|---|---|
| `iotrace.c` | The interposer dylib. Wraps `IOServiceOpen`, `IOConnectCallMethod`/`Scalar`/`Struct`/`Async`, `IOConnectMapMemory64`, and (EXP-0011) 32-bit `IOConnectMapMemory`, `mach_make_memory_entry_64`, named `mach_vm_map`. Logs selector + scalar/struct in/out (full hex), labels each connection by its user-client class, tracks GPU BOs from the resource-map call (sel 9) and the sel-5 shared pages, and on demand snapshots every BO's CPU-side bytes (crash-safe via `mach_vm_read_overwrite`). | device (A18) |
| `iohello_compute.m` | Minimal OWN compute dispatch (`o[i]=a[i]+b[i]`). Prints its buffers' GPU VAs (hex + little-endian) for correlation; `--iters N` repeats the submit; `--dump` triggers a BO snapshot after the last submit. | device |
| `iohello_draw.m` | Minimal OWN full-screen-triangle draw into an offscreen BGRA8 target. Same `--iters`/`--dump`. | device |
| `dumpscan.py` | Host-side. Loads the BO `.hex` snapshots and searches them at byte granularity for caller-supplied 64/32-bit little-endian needles (our resource VAs, dispatch dims). `--list` summarizes every BO. | anywhere (py3) |
| `bograph.py` | Host-side (EXP-0011). Reconstructs the **pointer graph** among captured BOs: for every 8-byte LE value in every BO, reports which other BO's `[gpu_va, gpu_va+size)` window it lands in. Reveals launch-descriptor→shader, arg-buffer→buffers, etc. `--from VA` restricts the source BO. | anywhere (py3) |
| `bodiff.py` | Host-side (EXP-0011). Word-diffs two captures — either two `.hex` files, or two dump dirs pairing BOs by `gpu_va` (the allocator is deterministic across runs). `--va` restricts to one BO, `--maxlen` limits compare length. The core of the change-one-parameter method. | anywhere (py3) |
| `build.sh` | Builds all three on the device. | device |

## Build & run (device, Command Line Tools only)

```sh
sh build.sh
# trace-only: full IOKit call sequence for a compute dispatch
IOTRACE_LOG=compute.log DYLD_INSERT_LIBRARIES=./iotrace.dylib ./iohello_compute
# capture the command/control stream: dump every registered BO after the submit
IOTRACE_LOG=compute.log IOTRACE_DUMP_DIR=maps \
  DYLD_INSERT_LIBRARIES=./iotrace.dylib ./iohello_compute --dump
# is submission per-call or shared-ring? compare call count across submit counts:
for N in 1 3 5; do IOTRACE_LOG=i$N.log DYLD_INSERT_LIBRARIES=./iotrace.dylib \
  ./iohello_compute --iters $N >/dev/null; echo "$N: $(grep -c ^CALL i$N.log)"; done
```

Then, on the host, correlate the dumps with our resources:

```sh
python3 dumpscan.py maps --list
python3 dumpscan.py maps --u64 0x10000030000 0x100000e0000 --u32 64 32
```

## How the BO snapshot is triggered (and why it is safe)

On this platform there is **no per-submit ioctl** to hook (see EXP-0009): work is
submitted through shared memory + a doorbell, so the command stream is finished
being written *after* the last IOKit call. To snapshot it at exactly the right
moment, the harness calls `kill(getpid(), SIGUSR1)` right after
`waitUntilCompleted`, while every BO is still mapped. The interposer blocks
SIGUSR1 in all threads at load time and services it on a dedicated `sigwait`
thread, so the dump runs in normal thread context (safe to take locks / use
stdio), not in an async-signal handler. `kill()` (process-directed) is used
rather than `raise()` (thread-directed) so the dedicated thread receives it.

## Environment knobs (interposer)

| var | meaning | default |
|---|---|---|
| `IOTRACE_LOG` | log file path | stderr |
| `IOTRACE_DUMP_DIR` | directory for BO/map `.hex` snapshots | `iotrace_maps` |
| `IOTRACE_DUMP_ON_USR1` | `1`=snapshot all BOs on SIGUSR1 (harness `--dump`) | 1 |
| `IOTRACE_DUMP_PERSIG` | `1`=each SIGUSR1 dumps into its own `dumpNN/` subdir (per-submit snapshots for ring/doorbell diffing; EXP-0011) | 0 |
| `IOTRACE_WRAP_VMMAP` | `1`=log named-object `mach_vm_map` calls (opt-in; very hot, off by default) | 0 |
| `IOTRACE_DUMP_ON_SEL` | comma list of selectors: snapshot maps before+after any matching `IOConnectCall*` | off |
| `IOTRACE_DUMP_ATEXIT` | `1`=snapshot at process exit (fallback) | 0 |
| `IOTRACE_BO_SEL` | selector treated as the resource-map call (parsed for BO cpu/size/GPU-VA) | 9 |
| `IOTRACE_MAX_STRUCT` / `IOTRACE_MAX_MAP` | hex-dump byte caps | 65536 / 1048576 |
| `IOTRACE_ONLY_CONN` | hex connection id to restrict logging to | all |

## What it found (EXP-0009, G17P / macOS 26.6)

- Submission is **shared-memory + doorbell, not a per-submit ioctl**: the IOKit
  call count is *identical* for 1, 3 and 5 submits (compute 49, draw 58).
- Client GPU memory is **regular userspace VM registered into the GPU VM** via
  `AGXAcceleratorG17P` selector **9** (in@0x38 = CPU base, in@0x48 = size, out@0x0
  = GPU VA). There are **no** `IOConnectMapMemory` ring regions in the client.
- The control/command stream is encoded into those BOs. Correlated against our
  own resources: an **argument buffer** holding our three buffer VAs
  consecutively, a **launch descriptor** carrying our exact dispatch dims
  (grid 64 / threadgroup 32), and a BO of **AGX shader machine code** (op-groups
  + `0e` stop). See `experiments/EXP-0009-iotrace-bringup/`.
- **EXP-0011** decoded those structures via change-one-parameter diffing
  (`bodiff.py`/`bograph.py` + the parametric `cvar.m` harness): the CDM launch
  descriptor is a stream of 0x2c-byte records (shader ptr = `VA>>6`, 3D grid in
  *threads* + 3D threadgroup, register/config word); the Tier-2 argument buffer is
  a table at `+0x14a0` (buffers = inline 8-byte VA, textures/samplers = 8-byte
  pointer to a descriptor). It also located the **submission ring** (a producer
  index that advances 0x58 B/submit in shared memory) and showed the doorbell uses
  **no per-submit syscall** (sel 0x7 = the executable-path string, not ring setup).
  See `experiments/EXP-0011-compute-cmdstream/`.
