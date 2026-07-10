# EXP-M5-01 — M5 toolchain bringup + ISA baseline delta vs G17P

**Device:** `user@192.168.170.253` — Apple **M5**, SoC **T8142**, macOS 27.0 (26A5368g),
5→**8 GPU cores**, Metal 4. Clean-room: own-shader compile→extract→disassemble only.

## Goal

Before any M5 characterization can be trusted, prove our own-shader RE toolchain
(`shdump` compile → `agxparse` extract → `agx-isa` disassemble) runs on the M5, and
measure how far the **A18 Pro / G17P** ISA database (170 descriptors, prior phase)
gets on M5 machine code. This sets the scaffolding-vs-rebuild question empirically.

## Procedure (reproducible)

1. Deploy `tools/{shdump,agxtest,agx-isa}` to `~/cleanroom_work/tools` on the M5.
2. Build with the M5's Command Line Tools (clang 21):
   `clang -fobjc-arc -framework Metal -framework Foundation -o shdump shdump.m` (and `agxrun`).
3. Compile a trivial compute kernel (`add.metal`, `out[i]=a[i]+b[i]`) with our own
   `shdump` — **runtime `newLibraryWithSource:` MSL compilation, confirmed working on M5.**
4. Extract `_agc.main` bytes: `agxparse.py add.bin --extract-hex` → `add.main.hex` (50 bytes).
5. Tokenize with the unmodified G17P DB: `agxisa.py tokenize <hex>`.

## Result — toolchain WORKS on M5; G17P DB partially decodes then desyncs

`shdump` metadata: `device = Apple M5`, `threadExecutionWidth = 32`,
`maxThreadsPerThreadgroup = 1024` (SIMD width 32, same as G17P).

`_agc.main` (50 bytes):
```
1ca010060f040302182210402f080302180210c04100800000002900041a2220a002040812000f000302010610400e000000
```

G17P-DB tokenize (`tokenize_g17p.txt`):
```
+0x00  get_sr    1ca01006   form=0x1 dst=0x1 sr_sel=0xa0 dp_width=0x10 dp_marker=0x6  # position_in_grid -> r1
+0x04  mask_op   0f040302   mask_bank=0x3 scope_kind=0x2
+0x08  <UNKNOWN>            (byte0=0x18 not in G17P DB)   -> 42 bytes LEFTOVER, NOT CLEAN
```

## Interpretation (do not over-read one kernel)

- **`get_sr` transfers exactly.** `1c a0 10 06` decodes to `get_sr sr_sel=0xa0`
  (position_in_grid) into r1 — matching the kernel's `[[thread_position_in_grid]]`.
  The special-register read mechanism appears shared with G17P.
- **The M5 is a G17P-*derived* ISA with real deltas, not a clean-sheet ISA.** The DB
  desyncs at `byte0=0x18` (the first memory op for `a[i]`/`b[i]` loads is expected right
  here). Either `0x18` is a new/relocated leader on M5, or an earlier op's *length* differs
  on M5 and misaligns the stream. **Unresolved — needs a corpus census + splice, not a guess.**
- Consequence for the plan: the 170-descriptor A18 DB is **starting scaffolding**, and the
  M5 effort is **delta characterization** (validate each op on M5 HW, fix leaders/lengths/fields
  that moved), not a rebuild from zero. Carry **nothing** over as fact without re-probing on M5.

## Addendum — M5 GPU dispatch + splice-and-observe path validated

The full hardware-validation loop (not just static decode) works on the M5. Running our own
`add.metal` through `agxtest.py` (compile → build spliceable `MTLBinaryArchive` → dispatch →
read back), with the pipeline forced from the archive (`FailOnBinaryArchiveMiss`):

```
PIPELINE_SOURCE archive          # the archived (spliceable) machine code ran, not a recompile
RESULT 0 11 22 33 44 55 66 77 88 # out[i]=a[i]+b[i] over inputs 1..8 / 10..80
COMPARE 0 MATCH
```

So splice-and-observe — the engine of every Phase-1.3 delta validation — is live on the M5.
Splice infra built on the device: `shdump`, `agxrun`, `agxrun_persist` (fast field sweeps),
`agxrender` (fragment→pixel). Evidence: `identity_roundtrip.txt`. **Not yet tested on M5:** the
GPU fault-containment behavior (whether an illegal encoding is contained like G17P or forces a
reboot) — deferred until the compile-only census subagents finish, to avoid disrupting them.

## Next (directs the fan-out)

1. Build a large, diverse **M5 corpus**: compile the prior own-MSL corpus **and** the 54 MB
   permissive `thirdparty/` corpus **on the M5**, extract `_agc.main` for each.
2. Run the census (`EXP-M4-01` walk + trim_padding + classify) with the **unmodified G17P DB**
   to quantify M5 coverage and rank byte0 groups by desync frequency → a prioritized delta list.
3. Fan out per-family delta subagents (byte-diff + splice-and-observe on the reboot-recoverable
   M5) to fix each diverging op; re-census to convergence. Validate on HW; commit each round.

## Files

- `add.metal` — our trivial provocation kernel.
- `add.main.hex` — extracted M5 `_agc.main` machine code (our own shader).
- `tokenize_g17p.txt` / `disasm_with_g17p_db.txt` — G17P-DB decode of the above.
- `shdump.stderr` — compile metadata (device, SIMD width, tg limits).
