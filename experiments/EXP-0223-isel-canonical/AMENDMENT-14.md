# AMENDMENT-14 — close the omitted destination-r15 boundary

Frozen after `g17p_e0223_run03` and `g17p_e0223_run04`, before changing the case generator or
dispatching another program.

The V2 pre-registration requires destination reach over r0..r15.  The generator used
`range(15)`, which exercised r0..r14 and accidentally omitted r15.  The verifier correctly checked
the generated cardinality but repeated that cardinality instead of independently checking the
promised destination set.  The V3 captures remain valid evidence for every case they actually ran;
they do not establish destination r15.

Correct the generator to `range(16)`.  Add an independent verifier assertion that the `v2_dst_*`
case names are exactly `v2_dst_r00` through `v2_dst_r15`.  Freeze a V4 contract of 212 V2 cases:
210 exact positives plus the same two firing refuters.  Repeat canonical and shuffled runs with
zero Gate-A errors/aliases, no donor fields, and byte/output identity by case.

No compiler consultation is authorized or needed.
