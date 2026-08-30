# EXP-0183 — `raw/` is deliberately EMPTY of new observations

This experiment is **PURE ANALYSIS. No device, no SSH, no GPU.** It produced no new
hardware observation, so it has no raw capture of its own; inventing one would be a
fabricated artifact.

Everything it concludes is recomputed from raw trees that already exist in this
repository, append-only and untouched by this experiment:

| tree | what was read |
|---|---|
| `../EXP-0180-g17p-halfalu-rerecord/raw/g17p_run02/` | 16,735 gated cases, reverse order (`sweep.jsonl`, `anchor.jsonl`) |
| `../EXP-0180-g17p-halfalu-rerecord/raw/g17p_run03/` | 16,735 gated cases, forward order |
| `../EXP-0169-g17p-rerecord/raw/g17p_20260830_run01/` | `falu2_uni.dst`, `reg_move_cb.dst`, `reg_move_cb.form`, `half_alu.dst` sweeps |
| `../EXP-0169-g17p-rerecord/raw/g17p_20260830_run02/` | the same, second gated run |
| `../EXP-0168-g17p-dst-resweep/raw/g17p_20260830_rclean0{1,7,8,9}/` | `iter_at.grp` render arm |
| `../EXP-0162-g17p-pack-and-splices/raw/g17p_20260829_run01__cvt_bf16/` | the dense byte+4 sweep behind the `cvt_bf16` match fix |

`manifest.json` records their sizes and sha256. `analysis/rederive.py` reads exactly these
files and nothing else; it does **not** import any of those experiments' analysis modules,
so their conclusions are re-derived rather than inherited.

The one exception, declared: `analysis/rederive.py` imports
`../EXP-0180-g17p-halfalu-rerecord/harness/isa_helpers.py` to recover the *authored*
encoding of that experiment's seed instructions (`half_add`, `LOW_PAIRS`). That is our own
probe source, not an observation, and it is what makes the H1b2 identity check possible.
