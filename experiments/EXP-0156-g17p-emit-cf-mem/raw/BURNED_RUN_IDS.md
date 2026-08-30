# Burned run ids — retained, never reused

`SUBAGENT_BRIEF.md`: *"Never reuse or overwrite a run id."* These ids were created on the
neo and are **permanently retired**. They are recorded here rather than as empty
directories because they contain nothing at all — the failure happened before the first
artifact was written.

## Batch #1, aborted in `baseline.py` (nine ids)

`g17p-20260830-cf02a`, `cf02b`, `cf02c`, `mem01`, `mem02`, `mtg01`, `mtg02`, `bf01`, `bf02`

Each created its `raw/<id>/` directory and then died in
`harness/baseline.py` with:

```
TypeError: %d format: a number is required, not NoneType
```

**Cause (this experiment's own mistake, recorded not hidden):** the addendum carrier
`tgac141` was pushed to the neo with `"main_len": None` **while batch #1 was still
running**, so `baseline.py`'s length assertion could not format its message. No GPU work
was done under any of these ids and no `sweep.jsonl` or `00_inputs.json` exists for them.

**Successors:** `cf02d`, `cf02e`, `cf02f`, `mem03`, `mem04`, `mtg03`, `mtg04`, `bf03`,
`bf04` — all captured cleanly in batch #2.

**Lesson:** never push a partially-edited harness to the compute target while a capture
batch is live.

## `g17p-20260830-cf01d` (first attempt)

Exited **75** from `~/agxre/gpulease.sh` after waiting 900 s for the GPU lease (held by
EXP-0153). `run.py` never started, so **no directory was created** and the id was still
free; it was reused for the real capture, which is the one in `raw/g17p-20260830-cf01d/`.

## Retained PARTIAL (a directory that DOES exist)

`raw/g17p-20260830-cf01a/` — 887 records, killed by a transport failure. See its
`PARTIAL.md`. Cited by no verdict. Successor: `cf01d`.
