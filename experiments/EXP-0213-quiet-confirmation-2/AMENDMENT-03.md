# EXP-0213 — AMENDMENT-03

**Frozen before the first post-cascade capture. No earlier capture is re-scored; none is
discarded.**

## What happened

Stage 6B's capture `H1` drove EXP-0206's committed `run.py` — which by design has **no abort
path and no hang budget** — into a **self-inflicted hang cascade**:

* values 0–39 of `if_push.scope@cf_nl2._agc.main+106` reproduce the busy machine's ok/not-ok
  partition **exactly** (`(v & 2) == 0` → hang, else ok; 20 hangs, 20 ok);
* from value **40** onward **every** value hangs — 102 consecutive hangs — including values
  proven `ok` forty cases earlier;
* the driver's `recoveryCount` **never moved** (22868 before, 22868 after, 2220 samples over
  4509 s): the device never recovered, it simply stopped completing anything.

The capture then hit its declared 4500 s cap. Under the frozen stop rule its pair partner `H2`
was not attempted. The next capture, stage 6C's `L1_cl_atomic`, **could not even open its
carrier** — its `carrier_open` baseline is recorded as `hang` — which is direct evidence that
the degraded state outlived the capture that caused it.

## What is added: a device-health gate before any further capture

`harness/health_gate.py`, and a rule:

> No further capture is dispatched until a **health probe** passes. The probe re-runs
> `tex_sample@msfilt/0` — an arm this experiment measured 256/256 payload-stable across three
> orders — through EXP-0204's own unedited `run.py`, and requires **256/256 `mode` payloads
> byte-identical to the B-series** and `baseline_final_ok: true`. If it fails, the device has
> not recovered, **no further capture is taken**, and the remaining phases are reported NOT
> REACHED.

This is not a loosening: it adds a conjunct that can fail and stop the experiment. It exists
because this session has now demonstrated that a capture can contaminate the *next* capture on
a machine with no other GPU client at all — a contamination source the quiet gate cannot see,
because it is us.

## Scope

Applies to phase 6 (the cold-device refuter) and to any further stage. It changes no pair
designation, no budget, no exclusion, no agreement key, and no verdict already computed.
