# Analysis artifact notes

- `m4_20260817_run01_descriptor_diff.txt` and `...run02...` are the
  authoritative paired metadata/resource/allowlisted-state reports.
- `m4_20260817_repeatability.txt` is the authoritative cross-run comparison.
- `m4_20260817_run01_code_census_v2.txt` supersedes the earlier
  `...code_census.txt` by adding an exact `60 00 00 00` byte-pattern census.
  Both are preserved so the analysis history remains traceable.
- `m4_20260817_scale_control01_v2.txt` supersedes the earlier
  `...scale_control01.txt` by reporting exact ordered resource-map equality in
  addition to the allocation-size multiset. Both derive from unchanged raw logs.

The ISA census is explicitly incomplete: the current tokenizer stops at an
unknown instruction in the large pressure programs. It may support a positive
observation before that point or an exact raw-pattern absence, but it cannot
support an absence claim for decoded scratch/doorbell operations.
