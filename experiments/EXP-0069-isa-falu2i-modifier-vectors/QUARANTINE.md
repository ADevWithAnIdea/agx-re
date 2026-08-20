# EXP-0069 quarantine

This experiment is **NON-EVIDENCE**. Its first repository-only analyzer run
wrote only the capture-time input record, then raised a decoder truncation
exception before producing a result or a durable failure transcript. The frozen
plan assumed six-byte `falu2i` encodings; the pinned decoder requested eight
bytes for the first assembled vector. That terminal observation was not
retained by the frozen analyzer, so it must not be promoted as an instruction
length, modifier, codec, hardware, M4, or A18 claim.

The retained `raw/run01/00_inputs.json` is append-only process history only.
Do not rerun or repair this experiment in place. A successor must preregister
the decoder-length preflight and write all exceptions atomically before making
any coverage claim.
