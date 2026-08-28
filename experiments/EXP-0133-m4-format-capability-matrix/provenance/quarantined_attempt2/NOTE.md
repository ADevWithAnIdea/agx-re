# Quarantined capture attempt 2 (m4-20260828-run03, X32_Stencil8 misclassification)

Retained, NOT reused. `run.py --run-id m4-20260828-run03 --execute` ran
1462/1548 cases cleanly under the corrected fully-per-axis grammar (the F3
fix), then correctly STOPped at `cap_depth_stencil_00261_X32_Stencil8`: exit
-6 (SIGABRT), stderr "depthAttachmentPixelFormat MTLPixelFormatX32_Stencil8
is not depth renderable."

Root cause: a harness classification bug, not new hardware information.
`analysis/gen_formats.py`'s `classify()` grouped `X32_Stencil8`/
`X24_Stencil8` into the SAME `(kind=float, family=depthstencil)` bucket as
the two real combined depth+stencil formats (`Depth24Unorm_Stencil8`,
`Depth32Float_Stencil8`). X32_Stencil8/X24_Stencil8 are actually **view-only
stencil-aspect** formats (uint8, family `stencil_view`) -- reachable only
via `newTextureViewWithPixelFormat:` on a parent combined-format texture,
exactly the path `conv_split_depth_stencil` already uses correctly. The
`depthstencil` misclassification made the harness try
`depthAttachmentPixelFormat = MTLPixelFormatX32_Stencil8`, which Metal
correctly (and, per F1, fatally) rejects -- but for the wrong underlying
reason, and it meant every OTHER axis run for X32_Stencil8 in this capture
(1461 of its sibling cases had already run by the time of the STOP; the
`cap_*_00261_X32_Stencil8` ones among them used the WRONG MSL binding type,
`texture2d<float>` instead of `texture2d<uint>`) is not valid evidence for
that format, even where it happened not to crash.

Fixed in `analysis/gen_formats.py` (X32_Stencil8/X24_Stencil8 now
`kind=uint, family=stencil_view`, matching `docs/descriptors/
format-table.md`'s existing `x32_stencil8` code, which is IDENTICAL to
`stencil8`'s own `byte0`/`byte1`). Contract regenerated; a 138x11 precheck
re-run (`provenance/pre_freeze/precheck/`) confirmed the fix and found no
further classification defects. Run ids retired again: `m4-20260828-run03`/
`m4-20260828-run04` are never reused; the real captures moved to
`m4-20260828-run05`/`m4-20260828-run06`.
