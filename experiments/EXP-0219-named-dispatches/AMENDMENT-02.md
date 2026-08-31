# EXP-0219 — AMENDMENT 02

**Frozen 2026-08-30, BEFORE the dispatch that uses it.** One control capture. No
hypothesis, gate, harness file or budget changes (`--arms` is an existing
`harness/run_b.py` parameter; its sha256 is unchanged).

## Why

`analysis/quiet_table.py` shows that during every part-B repeat capture there
were **five** of our own `gfrun4` children alive at once — one per carrier
(`msread`, `mslodq`, `msfilt`, `mscmp`, `msread1`) — because `run_b.py` opens one
persistent renderer per carrier and then walks the arms sequentially. Four of
them are idle at any moment, but they hold GPU contexts.

That is a confounder for the periodicity result specifically: a period of 4 or 8
in the dispatch index could plausibly be a property of **how many contexts are
resident**, not of the instruction. The quiet metric cannot see it, because the
processes are ours.

## The dispatch

`g17p_e0219_B_rep_ctl04`: `--phase repeat --order forward --repeats 24
--arms tex_sample@msread/0` — **one arm, therefore ONE renderer child and one GPU
context**, everything else identical to `g17p_e0219_B_rep_run03`.

## The prediction, stated before the run

* **If the periodicity is an artefact of the four idle sibling contexts:** the
  single-context capture shows **0 of 32** bit6-set values unstable, i.e. the
  effect disappears.
* **If the periodicity is a property of the instruction:** `tex_sample@msread/0`
  again shows unstable bit6-set values whose sequences have smallest period in
  {4, 8}, and the bit6-clear control set again shows 0 of 33.

Either outcome is reported. A disappearance would **not** retract the live/inert
partition (which is measured against the bit6-clear twin, not against
stability); it would bound the periodicity claim to "with N sibling contexts
resident".
