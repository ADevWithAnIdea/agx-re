# EXP-0182 has no raw captures, by construction

This experiment ran **no device work at all** — no SSH, no GPU, no dispatch. Its dispatch was
explicitly "PURE ANALYSIS", and two other experiments were live on the neo throughout.

Its evidence is therefore **other experiments' committed raw**, cited by exact path in
`RESULTS.md` §1 and enumerated machine-readably in `analysis/anchors.json` (255 anchors, each
carrying the `raw` file it was read from, the run id, the carrier and the note). Nothing in
`experiments/*/raw/` was written, edited or moved by this experiment; it is read-only input.

The three raw trees this experiment leans on hardest:

* `experiments/EXP-0156-g17p-emit-cf-mem/raw/g17p-20260830-bf03/` — `sweep.jsonl` (the
  `bf_add_dst`, `bf_fma_dst`, `hminmax` anchors, each `ok` against a host semantic oracle) and
  `00_inputs.json` (`raw_sites`, and `carrier_tokens`, which is the committed proof that the
  tokenizer mis-read our own compiled kernel).
* `experiments/EXP-0162-g17p-pack-and-splices/raw/g17p_20260829_run01__{cvt_bf16,cvt_f2h_dst}/`
  — the two convert anchors, and the dense byte+4 sweep that refutes `cvt_bf16`'s `match`
  constant.
* `experiments/EXP-0180-g17p-halfalu-rerecord/raw/g17p_run0{2,3}/` — via that experiment's
  `analysis/length_rule.json`, the measured half-ALU length table.
