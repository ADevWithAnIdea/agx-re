# m4_20260828_run05 — PARTIAL BUT USED, within the scope stated here

Stopped at **8,412 of 22,237** cases by a host-wide `MTLCompilerService` outage (not
a defect of this capture; see `../../RESULTS.md` §6.1). Everything it recorded before
that point is a valid measurement and IS used, within this scope:

* `pack_convert` — **complete** (arms C, S, F, W, X). Gated against
  `m4_20260828_run03`: 6,251/6,255 gated records byte-identical (99.936 %).
* `unpack_convert` — arms C, S and the full per-byte `F` sweep **complete**; the `W`
  arm was in progress and the `X` arm never started. Single observation, not gated.
* Every other instrument — **not reached** (this run used priority carrier order, so
  the `cvt_*` cluster and `packed_half2_hi` come after `unpack_convert`).

This file documents scope; it does not modify the capture. `sweep.jsonl` is exactly
as written, append-only, and its sha256 is recorded in `../../manifest.json`.
