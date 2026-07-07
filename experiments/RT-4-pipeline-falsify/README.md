# RT-4 — Red-team falsification of the TBDR pipeline facts

**Role:** adversarial verifier. Assume the EXP-0021 TBDR-pipeline findings
(`docs/pipeline/README.md`) may be subtly wrong; run falsification tests designed to
**break** the claims (change-one-Metal-parameter + byte-diff; adversarial RT
sizes / formats / sample-counts / attachment-counts). Report CONFIRMED or DISCREPANCY
per claim, with evidence.

**Clean-room category:** DATA-TRACE + OWN-SHADER. Every shader is our own MSL compiled
at runtime (`newLibraryWithSource:`); we only observe *data* (registered GPU buffer
objects) crossing the userspace↔kernel boundary via the read-only `tools/iotrace`
interposer (built `-arch arm64e`). No Apple binary is disassembled or introspected.

## Claims under test (docs/pipeline/README.md)
1. Tile = **32×32 fixed**, does NOT shrink with bpp; `0x68000+0x904 = 0x80000000|(ceil(W/32)−1)`,
   `+0x908 = ceil(H/32)−1`.
2. Imageblock budget: per-attachment **0x20-byte record**, bgra8 **stride 0x1000**;
   `Σ tile_area×bpp×samples` vs **32 KiB** as the driver feasibility check.
3. MSAA: sample count @attachment `+0x24` (2×`0x08`/4×`0x09`); 8× rejected; MSAA relocates
   the color descriptor into the tiler heap.
4. Memoryless: clear `+0x24` bit27, poison surface addr `0x0eeee000`, zero backing, shrink tile mem.
5. Load/store actions = 0x300-byte segments; store-program id **`0x6f`**; DontCare poisons addrs.
6. NEGATIVES: programmable sample positions **absent** from client BOs (route-to-kernel);
   depth/ZLS store **absent** from client BOs.

## Method
`harness/tvar4.m` — a red-team extension of EXP-0021's `tvar.m` that adds what the original
never probed: **up to 8 color attachments** (original capped at 4), **mixed per-attachment
pixel formats** (`--mrtfmt`), **single-sample memoryless color** (`--mlcolor` at 1×), a
device **capability probe** (`--probe`), and much larger / more extreme RT sizes. Same
change-one-parameter discipline: run each config under iotrace with `--dump`, then byte-diff
the registered BOs (`harness/bodiff.py`, dir-mode pairs BOs by deterministic `gpu_va`).

`harness/run_rt4.sh` drives the whole adversarial matrix on the device
(`~/cleanroom_work/rt4/`) and pulls back text only:
- **Phase 1** tile size: RT 1×1, 31, 32, 33, 63, 65, 512, 1024, 2048, 1000, 777, and extreme
  asymmetric 2048×32 / 32×2048 / 96×1000 / 1000×96; all formats at 64×64; rgba32f+4×MSAA;
  depth+color.
- **Phase 2** imageblock: 1..8 attachments (bgra8), rgba32f/rgba16f MRT, and **mixed-format** MRT.
- **Phase 3** MSAA: 2×/4×/**8×**/**16×**; relocation.
- **Phase 4** memoryless: color-1×, MSAA-color, depth.
- **Phase 5** load/store: every load×store combo; store-program; depth-only partial render.
- **Phase 6** negatives: custom sample positions (2× & 4×); depth store action.

## Layout
- `harness/` — `tvar4.m`, `run_rt4.sh`, and read-only copies of `iotrace.c` / `bodiff.py` /
  `dumpscan.py` / `bograph.py` (from `tools/iotrace`, unmodified).
- `raw/hex/` — curated control-BO hexdumps + `TILEGRID.txt`, `SAMPOS_EVIDENCE.txt`.
- `raw/analysis/` — `diff_*` byte-diffs, `status_summary.txt`, `list_*`.
- `raw/sampos/` — the sample-position BOs (0x100000e8000 / 0x100000e0000), default vs custom.
- `raw/stdout/` — harness stdout for key runs (status + PIXEL correctness).

See `RESULTS.md` for the per-claim verdicts.
