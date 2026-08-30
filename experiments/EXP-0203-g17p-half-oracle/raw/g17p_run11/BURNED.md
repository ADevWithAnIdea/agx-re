# `g17p_run11` — BURNED RUN ID, retained, never reused

This directory contains **no case records**. It was created by `harness/procsample.py`
(the concurrent-GPU-activity sampler) one second before `harness/run.py` started, and
`run.py`'s own guard then refused to write into a run directory that already existed:

    run id g17p_run11 already exists -- run ids are NEVER reused or topped up
    (SUBAGENT_BRIEF.md). Burn it and take a new id.

That guard did exactly its job. Per `SUBAGENT_BRIEF.md` ("never reuse or overwrite a run id;
a partial capture is retained, never reused") the id is **burned**: it is kept exactly as it
is, it is not topped up, and the three gated runs took the NEW ids `g17p_run11`,
`g17p_run12` and `g17p_run13`.

The launch order was corrected so the sampler starts a few seconds AFTER the run driver.

**Second occurrence, same cause, different shell bug.** The launch line was changed to
`( sleep 8; nohup procsample & ) ; run.py`, but a parenthesised subshell runs in the
FOREGROUND, so it still slept and started the sampler before `run.py` ever ran. Corrected to
start `run.py` first and attach the sampler ten seconds later. Both burned ids are retained.
