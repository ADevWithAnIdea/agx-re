# Experiments

One directory per experiment: `EXP-NNNN-short-slug/` (zero-padded, sequential).

Each must be **reproducible by a third party** and contain:

```
EXP-NNNN-slug/
  README.md      ← hypothesis, method, exact procedure (commands), clean-room category
  run.sh / *.m / *.py / *.metal   ← the exact code/scripts used (ours)
  raw/           ← raw captured output (logs, byte dumps, disassembly of our shaders)
  RESULTS.md     ← what was observed + analysis + which docs/ facts it establishes
```

Rules:
- State the **clean-room category** (HW-PROBE / DATA-TRACE / OWN-SHADER / PUBLIC) up front.
  If an experiment can't be cleanly categorized, don't run it — ask.
- Only device-side data comes back; **no Apple binaries/blobs** get committed (see `../CLAUDE.md`).
- On device, work under `~/cleanroom_work`; pull artifacts here to commit.
- After committing, add the established facts to `../PROVENANCE.md` and update `../docs/`.

See `TEMPLATE.md` for the README skeleton.
