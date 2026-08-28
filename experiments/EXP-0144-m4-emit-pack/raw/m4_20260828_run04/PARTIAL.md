# m4_20260828_run04 — RECORD-COMPLETE BUT SCIENTIFICALLY PARTIAL, RETAINED, NOT USED

All 22,237 case records are present, but the run is **not usable as a gate pair**:
it cascaded at case 12105 (`c_f2h_dst`) after only 56.8 s, so the overwhelming
majority of its records are `skipped_after_hangs` placeholders rather than
measurements.

Cause: it was launched immediately after `m4_20260828_run03`, which had itself ended
in a genuine GPU cascade on the MODE-A `packed_half2_hi` arm. The device had not
recovered. Later runs leave a settle gap between captures.

Retained unmodified; **not used for any verdict**. Superseded by the
`m4_20260828_run05` / `m4_20260828_run06` pair, captured with the corrected carrier
ordering (priority, not alphabetical) and with a cascade scoped to the offending
carrier instead of the whole run.
