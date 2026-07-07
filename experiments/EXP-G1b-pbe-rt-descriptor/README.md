# EXP-G1b: PBE / render-target (storage-image) descriptor full bit layout

- **Date:** 2026-07-07
- **Clean-room category:** DATA-TRACE + OWN-SHADER + HW-PROBE (no Apple binary disassembled)
- **Phase / question:** objective-1 gap **G1-b** — the sampled 32-byte texture descriptor is fully
  specified (EXP-0015); the **render-target / storage-image (write) binding** descriptor was only
  partly decoded (EXP-0021 got format @+0x22 / samples @+0x24 / clear @+0x170 / the 3-segment chain
  existed but load/render/store meaning + surface VA / dims / stride / MRT array were open).
- **Device:** Apple A18 Pro (G17P), SoC T8140, macOS 26.6, Metal 4 / Apple9. SIP disabled.

## Hypothesis
1. A texture bound as `[[texture(n), access::write]]` / `read_write` is described by a **distinct
   "PBE" descriptor** in the Tier-2 argument buffer (not the sampled 32-byte texture descriptor),
   whose fields differ (write-specific packing, no lossless-compression aux).
2. The 3D attachment descriptor at `0x10000110000` (EXP-0021) is a chain of 0x300-byte load/render/
   store segments whose per-segment body encodes the RT **surface VA, width/height, stride/rowBytes,
   load-action, store-action**; the STORE segment is itself a PBE descriptor.
3. N color attachments (MRT) are arrayed with a fixed per-attachment stride.

## Method
Change **one** Metal parameter, re-capture the registered GPU BOs under the read-only
`tools/iotrace` interposer (arm64e), and byte-diff. Two parametric OWN-MSL harnesses:
- `svar.m` — a compute dispatch that binds ONE texture with a chosen MSL **access qualifier**
  (`sample`/`read`/`write`/`read_write`) + format + dims; the appended descriptor block in the
  Tier-2 auto argument buffer is extracted (`argx2.py`) and diffed. Buffer-backed (`--bb`) variants
  give a printable surface VA + write readback (HW-validation).
- `rtvar.m` — a draw into buffer-backed color attachment(s) (so every RT surface VA is printable and
  its pixels read back), varying RT size / format / load-store action / MRT count / MSAA; the 3D
  attachment descriptor is located (`attloc.py`) and diffed. Surface pointers are correlated to the
  printed `rtBuf` VA.

Clean-room: every shader is our own MSL compiled at runtime; we log only *data* (descriptor bytes,
our own resource VAs). Nothing disassembles any Apple binary (CLAUDE.md rules).

## Procedure
On the device under `~/cleanroom_work/exp_g1b/`: `sh run.sh` builds `iotrace.dylib` + `svar` + `rtvar`
(arm64e), runs the storage-image matrix (15 dispatches) and render-target matrix (21 draws), curates
the descriptor / attachment hex per run, correlates surface VAs, and writes `analysis/DIFFS.txt`.
Reused read-only: `tools/iotrace/{iotrace.c,bodiff.py,dumpscan.py,bograph.py}`,
`experiments/EXP-O2B/descx.py`.

## Raw results
`raw/` — curated descriptor/attachment hex per run, `rt_store_sweep.txt` (RT store-PBE descriptor
across the size/format sweep), `storage_descriptors.txt` (per-access-qualifier arg-buffer blocks).
`analysis/DIFFS.txt` — all byte-diffs. `caps_out/*.out` — per-run stdout (CONFIG + surface VAs +
pixel/write readbacks). Summary + field maps in `RESULTS.md`.

## Established facts → docs
See `RESULTS.md` §5. Storage-image (PBE) descriptor field map → `docs/descriptors/`; RT attachment
descriptor + MRT array + load/store → `docs/pipeline/` (+ `docs/cmdstream/`). Orchestrator owns docs.

## Follow-ups
width>256 high-bits field; 8-byte read/write control-word bit decode (mipmapped storage image);
Private compressed-RT aux isolation; seg+0x2d0 format-class byte; store-program config word.
