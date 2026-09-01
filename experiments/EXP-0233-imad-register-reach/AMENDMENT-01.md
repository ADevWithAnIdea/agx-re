# EXP-0233 Amendment 01 — replace boundary02 target metadata

Frozen after the `boundary02` evidence-handling defect was identified and before any
`boundary03` dispatch.

## What happened

The original `g17p_e0233_boundary02` shader run completed all 13 append-only sweep records, and its
five H cases agree byte-for-byte and semantically with `boundary01`. A later status command
mistakenly invoked the capture wrapper with the already-used `boundary02` ID. `run233.py` correctly
refused to reuse the raw sweep directory, but the wrapper started target sampling before that check
and then copied the refused attempt's `procs.jsonl`, `gpu_pre.json`, `gpu_post.json`, `03_stdout.txt`,
and `06_harness_sha256.txt` over the earlier ancillary files.

The 13 original `sweep.jsonl` records, input manifest, slot probe, and run manifest remain intact.
The overwritten target metadata timestamps visibly postdate the shader run and show the two
original recovery increments inside the process samples but before the mislabeled pre-snapshot.
They are retained as evidence of the defect, not accepted for Gate E.

## Frozen correction

- Both capture wrappers now reject an existing `raw/$RUN` directory before starting sampling or
  writing any work file.
- Run a replacement reverse-order boundary capture as `g17p_e0233_boundary03`.
- Formal boundary promotion compares `boundary01` with `boundary03`. `boundary02` remains excluded
  only from the surrounding-target gate; its immutable shader records are not rewritten or hidden.
- The corrected wrapper does not change `run233.py` or generated program bytes.

If SSH or the device becomes unresponsive, immediately stop and report blocked. No recovery or
reboot is authorized.

Clean-room provenance: OWN-SHADER + HW-PROBE. Apple binary introspection: **NONE**.
