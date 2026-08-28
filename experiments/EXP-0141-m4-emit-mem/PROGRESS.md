# PROGRESS — EXP-0141

Append-only milestone log. Timestamps UTC.

- **M1 2026-08-28** — read `CLAUDE.md`, `CODEX.md`, `SUBAGENT_BRIEF.md`,
  `FIELD-SWEEP-PROTOCOL.md`, `docs/evidence-classification.md`,
  `work/DOC-02-LABELLING-REPORT.md`, `db.json` + `validation.json` for the ten
  target instructions. Confirmed the blocking count: **58 of 81 fields** are
  below emitter grade (device_load 6, device_store 5, atomic_mem 14,
  atomic_rmw 14, atomic_tg 11, threadgroup_barrier 2, mem_fence 3, mem_fence8 2,
  dev_scoreboard_fence 1, tg_addr_compute 0-modelled-but-VETOED).
- **M2 2026-08-28** — authored six carriers (`kernels/*.metal`), rebuilt the
  EXP-0101 synthesis path on the CURRENT `db.json` schema (`mov_imm` is now
  `imm7`+`imm_top` with a 4-bit `dst`; `falu2`/`falu2i` split `srcA_reg` into
  6 bits + `srcA_reg_top`; `stop` is 4 bytes). PILOT: EXP-0101's construction
  reproduces exactly (`-7.0`), `(0,0)` silently zeroes to `1.5`, and a NEW
  result appeared immediately — a direct load->store forward needs
  `device_store.addr_mode = 0x56`; `0x54` stores 0.
- **M3 2026-08-28** — TWO HARNESS DEFECTS found and fixed before freezing:
  (a) reusing one splice-archive filename across persistent-runner requests
  gives **28/360 spurious `CMDBUF_ERROR`** on byte-identical known-good
  archives; a unique path per request (unlinked afterwards) gives **0/360**.
  (b) a real GPU fault poisons following command buffers, which return
  `kIOGPUCommandBufferCallbackErrorInnocentVictim / Discarded (victim of GPU
  error/recovery)`; a bounded retry keyed on that exact error text made the
  13-case control set **fully deterministic over 4 repeats** (was 3 different
  outcome vectors in 3 repeats). Both are recorded in `PRE_REGISTRATION.md` 6.
- **M4 2026-08-28** — all six carriers' HOST-COMPUTED oracles verified against
  the UNSPLICED compiled kernels (6/6 match). Case matrix frozen: 93 arms,
  20 529 cases, 6 pre-registered falsifiers, 61 pre-registered baselines.
  `PRE_REGISTRATION.md` + `CAPTURE_CONTRACT.json` frozen (15 authored blobs).
