# EXP-0185 — upstream the three checks that each caught a live defect

**Type:** tooling / process. **PURE ANALYSIS — no device, no SSH, no GPU, no dispatch.**
**Target:** none (host-side plumbing only). **Date:** 2026-08-30.

## The question

Three checks proved themselves on 2026-08-30, each catching a real, live defect within an
hour of being written — and each existed only as a one-off copy inside one experiment, so
the next agent would not have had it:

| check | born in | the defect it caught |
|---|---|---|
| `saferunner.py` | EXP-0178 (`work/pilot02`), re-derived by EXP-0179 | **DEF-0178-1** — the shared runner's abandoned reader thread manufactured a cascade of **false `hang`s**, three in a row with `restarts=99`, from one benign case |
| `verify_remote.py` | EXP-0178 | the neo was running a **stale harness**: on its first run, against its own author, **11 of 18 blobs matched** — 2 missing, 5 stale |
| `closure_scan.py` | EXP-0178 (its selftest gate G10) | a closure read a read-back **size** that a later block rebound to a `bytearray`; it cost `raw/g17p_20260830_run01`, and it **presented as the cascade above** |

Can they be moved into `tools/agxtest/`, **with their gates**, so that they still provably
work after the move — and can the shared runner itself stop being the hazard?

## What was done

1. **Three modules upstreamed into `tools/agxtest/`**, with their `UPSTREAM NOTES` preserved
   and generalised where they were experiment-specific:
   - `saferunner.py` — `PumpedReader`, `make_safe_runner(base)`,
     `make_safe_render_runner(base)`, `SafePersistRunner`. Works over the shared
     `PersistRunner` **or** an experiment's pinned copy.
   - `verify_remote.py` — contract path, remote dir, `--prefix`/`--exclude` and the
     transport are now arguments (`SshRunner` / `LocalRunner`); batched `shasum`;
     exit `0` go / `3` MISSING-or-STALE / `2` nothing-verified.
   - `closure_scan.py` — algorithm unchanged; CLI gains `--allow NAME:reason` / `--ignore`.
2. **Their gates moved with them**, plus the fixtures they need:
   - `fakepersist.py` — device-free stand-in for `agxrun_persist`
     (`good` / `truncate` / `hang_first` / `eof_first`), merged from EXP-0178's
     `fakerunner.py` and EXP-0179's `fakechild.py`.
   - `testdata/closure_shadow_{bad,good}.py` — the `nb`-rebind reproduced in miniature.
   - `selftest_tools.py` — **T0..T7, no GPU / no device / no SSH, ~3 s.**
3. **A reviewed patch for `tools/agxtest/persistrun.py`** implementing both `saferunner`
   changes in the shared runner directly — **generated, gated, and handed over; NOT applied**,
   because EXP-0184 may be running against that file (FIELD-SWEEP-PROTOCOL §7 courtesy).
4. **A drafted addition to `experiments/SUBAGENT_BRIEF.md`** making the pre-capture sequence
   explicit — for the orchestrator, who owns that file.
5. **The width-1 promotion-gate pitfall documented** where a future gate author will see it
   (`tools/agxtest/README.md` final section, plus the brief draft).

## Reproduction (all offline, ~10 s total)

```sh
cd /Users/user/asahi_re/public/agx-re
python3 tools/agxtest/selftest_tools.py                                  # T0..T7
python3 experiments/EXP-0185-tooling-upstream/analysis/make_persistrun_patch.py
git apply --check experiments/EXP-0185-tooling-upstream/analysis/persistrun-DEF-0178-1.patch
python3 experiments/EXP-0185-tooling-upstream/analysis/gate_patched_persistrun.py   # P1..P7
python3 tools/agxtest/closure_scan.py \
    experiments/EXP-0178-g17p-sysval-tileread/harness/run.py main        # reproduces G10
```

Raw output of each is committed under `raw/`.

## Layout note

There is no `harness/` or `kernels/` here on purpose: the authored code **is** the
deliverable and it lives in `tools/agxtest/` (that is the point of the experiment).
`analysis/` holds the two repeatable scripts (patch generation, patch gate) and the patch
itself; `drafts/` holds the text proposed for a file this experiment does not own;
`work/` holds the patched copy the gate runs against and a snapshot of the unpatched original.

No `PRE_REGISTRATION.md`: this experiment makes **no hardware claim** and touches no device,
so there is no hypothesis about the silicon to pre-register and no capture to freeze. Its
claims are all about our own host-side code, and every one of them is checked by a committed
gate that anyone can re-run offline.

## Clean-room statement

```text
Clean-room provenance: none required (host-side process/protocol plumbing and static
                       analysis of OUR OWN harness source)
Inputs inspected:      our own Python harness code in this repository
                       (tools/agxtest/*, experiments/EXP-0178-*/harness/*,
                       experiments/EXP-0179-*/harness/*) and our own committed fixtures
Apple binary introspection: NONE
Device access:         NONE — no SSH, no GPU, no dispatch, no Metal
Reproduction:          the five commands above
Evidence:              raw/selftest_tools_run01.txt, raw/selftest_tools_run02.txt,
                       raw/gate_patched_persistrun_run01.txt, raw/closure_scan_run01.txt
```

No Apple binary, blob, framework or shader is involved anywhere in this experiment.
