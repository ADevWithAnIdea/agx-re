# EXP-0048 pre-registered blend control

Date: 2026-08-17

This file is frozen after the two main matrix runs and before either control
run. It does not alter the main matrix hypotheses. The main matrix's blend case
uses Load/Store so initialized destination bytes make blending observable, but
its baseline uses Clear/Store. Although the two empty-pass cases showed that
Clear and Load produce byte-identical state in all four allowlisted BOs, a
same-draw, same-source, same-Load/Store negative control is required before
attributing the blend-case structural deltas to blending alone.

The control is `rgba8-load-store-draw`: the same two authored RGBA8 outputs,
same full-screen draw, same initialized attachments, and same Load/Store actions
as `rgba8-load-store-blend`, with blending disabled. It is run twice with the
exact EXP-0048 fixed allowlist and prohibitions in `PRE_REGISTRATION.md`.

- Support for the blend attribution: control PBE descriptor bytes equal the
  blend case, control target bytes equal the unblended authored output, and the
  fixed-function deltas between control and blend reproduce exactly.
- Falsifier: any other configuration or descriptor delta, an unexpected target
  result, or disagreement between the two control runs.

No Apple binary, helper code, shader binary, or unknown BO may be inspected.
