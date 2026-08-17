# EXP-0044 Results — unchanged-UAPI userspace obligations

## Direct public-source observations

At Mesa revision `3c4d3e46d19f2f4e951f3ae059543b03592f7944`:

- Queue creation contains `usc_exec_base`, a queue-wide 64-bit base for 32-bit-relative
  vertex, fragment, and compute USC addresses.
- `drm_asahi_helper_program` is supplied by userspace and contains `binary`, `cfg`, and
  uninterpreted `data`. The UAPI says helper code dynamically allocates scratch/stack and
  reads the `data` sideband through special registers.
- Render submits contain separate vertex and fragment helpers. Compute submits contain a
  compute helper.
- `drm_asahi_bg_eot` is supplied by userspace and contains a tagged USC program address
  plus a packed resource specifier.
- Render submits contain BG, EOT, partial-BG, and partial-EOT programs.
- Render submits also require userspace-provided values or addresses for ZLS pixels,
  VDM stream base, scissor/depth-bias/occlusion arrays, depth and stencil buffers,
  `zls_ctrl`, `ppp_multisamplectl`, sampler heap/count, `ppp_ctrl`, framebuffer/tile
  dimensions, sample size, merge values, clear values, and timestamps.
- Compute submits require both the start and the end of the first contiguous CDM stream
  segment, a sampler heap/count, a helper program, and timestamps.
- Render flags explicitly include vertex scratch, process-empty-tiles, no-vertex-
  clustering, and integer-depth-bias selection.

## Interpretation

The hypothesis is confirmed. Under the unchanged UAPI, the listed programs and values are
userspace obligations even when the kernel marshals them into firmware structures or writes
hardware registers. A macOS data trace that does not expose a value is not evidence that an
unchanged Linux UAPI may move the responsibility to the kernel.

This result defines requirements only. Apple9 encodings and semantics must be established by
live probing and remain open until the corresponding closure evidence in
`docs/P0-P1-CLOSURE.md` exists.

## Limitations

- This is not a hardware experiment.
- It does not prove the UAPI is already implemented for G16/G17.
- It does not establish that macOS and Linux package work identically.
- Any Apple9 mapping still needs local-M4 evidence and eventual A18 re-validation where the
  closure matrix requires it.

## Clean-room status

PUBLIC source only. No Apple binary was disassembled, scanned, debugged, or otherwise
introspected.

