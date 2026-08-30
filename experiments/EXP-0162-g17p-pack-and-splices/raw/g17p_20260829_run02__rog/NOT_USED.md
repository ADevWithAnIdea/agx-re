# RETAINED, UNUSED — backs no label

This capture aborted at its **pre-mutation baseline**: every dispatch attempt came back
`kIOGPUCommandBufferCallbackErrorInnocentVictim` while at least six sibling GPU experiments
(EXP-0155, 0156, 0157, 0158, 0159, 0160) were driving the same device.

Per `CODEX.md` §6 and `SUBAGENT_BRIEF.md` it is retained exactly as captured and **never
topped up, edited, or reused**. The replacement captures took new ids:

* `raw/g17p_20260829_run04__*` — the `rog` arm in full (2048 cases, 0 hangs)
* `raw/g17p_20260829_run05__*` — the `kill` and `vary` arms

There is deliberately **no `run03`**: it was launched under `~/agxre/gpulease.sh`, was still
queued behind other holders when `experiments/NEO-TARGET-BRIEF.md` was updated to remove the
lease entirely, and was killed without dispatching a single case, so it never created a
directory.
