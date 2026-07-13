# EXP-M5-13 — remaining OBJ-1 command-stream deltas (M5 / Apple10 / G17g)

**Device:** Apple M5 (T8142, macOS 27.0, 8 GPU cores, `AGXAcceleratorG17G`). **Method:** own-process IOKit
DATA-TRACE (`tools/iotrace`, arm64e) + change-one-Metal-parameter BO diffing + own-MSL probe. All 41 GPU
submits STATUS=4, zero faults. Closes REVIEW-M5-OBJ1-01 MAJOR-6/7/9 + gap-8. No Apple binary introspected.

## Gaps closed
**MAJOR-7 — USC graphics bind grammar (measured, was asserted).** FS arg buffer `0x10000248000`→`0x10000250000`,
**grammar byte-identical to A18**: 8-byte-LE header (high32=`0x00000100`) `+0x600`=texture-array ptr,
`+0x608`=sampler-array ptr, `+0x610`=buffer[0] VA (`+0x618`=buffer[1]); 0x20-byte texture descs, 0x20-stride
samplers, `0x60000000` terminator. `num_tex=(samp_ptr−tex_ptr)/0x20`, `num_samp=(term−samp_ptr)/0x20` (HW-clean
tex1/2/3 × samp1/2/3). Uniform-preamble USC program `0x10000130000`→`0x10000138000`; UVS scalar-output count
`0x58000+0x2c`→`+0x164` (=`4+#scalar-outputs`).

**gap-8 — PPP output-select word (unblocks OBJ-2 layered rendering).** Relocated `0x58000+0x20`→`+0x158`,
**bit positions bit-identical to A18**: clip mask bits[7:0]=`(1<<N)-1`, **point_size bit18**,
**viewport_array_index bit19**, **`render_target_array_index` (layer) bit20** — layer is NEW (A18 never measured;
co-sets bit19). **Layered-rendering enable = VDM `0x18000+0x20` bit6.**

**MAJOR-6 — mesh grid-dispatch record.** The EXP-M5-10 abort was a HARNESS bug (called the tile
`newRenderPipelineStateWithDescriptor:` on a mesh descriptor; correct is `newRenderPipelineStateWithMeshDescriptor:`).
Fixed → mesh renders (STATUS=4). Record: **single graphics submit (no CDM BO)**; tiler stream `0x18000` opcode
**`0x70000600` (UNSHIFTED — same as A18**, unlike the +0x0800 draw opcodes) + 6 grid-dim words + `0xc0000000`
term; UVB in tiler-heap `0x10000018000`. No separate `0x100000f8000` BO on minimal M5 mesh.

**MAJOR-9 — CDM config constants.** `0x100000b0000` `+0x04=0x01000000`, `+0x0c=0x40000001`, `+0x28=0x60000160`
are **invariant** across grid/tg/tgmem/occupancy sweeps (occupancy `--heavy` flips only `+0x00` bit23) — structural
template constants, not parametric. (Corrects the doc's `+0x04=0x1` → measured LE `0x01000000`.)

**FF `+0x194` write-mask packing.** bits[3:0] = write mask, **STRAIGHT order R=bit0·G=bit1·B=bit2·A=bit3** — the
**REVERSE of A18** (`+0x5c` was bit-reversed); HW-validated all 16 subsets. bits[16:4]=`0x1fff` engage iff alpha
is written (store-class `+0x128` co-varies 0x4c0/0x480).

## Still open (honest)
- User-varying-reorder HW-proof (A18 EXP-G1a analog) not re-run — linkage opcodes inherited from ISA work, only
  the count field re-measured.
- Vertex-amplification + payload-heavy mesh records (incl. `0x100000f8000`'s M5 role) not probed.
- USC `+0x610` buffer-slot inline-vs-indirect form beyond 2 buffers unconfirmed.

## Deliverables
`docs/cmdstream/README-M5-deltas.md` (new §PPP output-select, §USC bind grammar, §Mesh grid-dispatch; resolved
write-mask + CDM-constants). Evidence: `captures/decoded-evidence.txt` + `captures/diffs.txt`. Scripts in
`scripts/`. Bulk BO snapshots on device (gitignored).

## Clean-room attestation
Own-process DATA-TRACE only; interposer wraps the public IOKit C API from our own non-hardened arm64e dylib and
logs non-copyrightable command-buffer/descriptor bytes our own Metal process registered. All MSL is ours,
runtime-compiled. No Apple binary disassembled/introspected. Every decoded field traces to observed bytes.
