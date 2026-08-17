# Raw evidence retention

This directory is append-only evidence for EXP-0043.

| Run | Purpose | Cases | Approximate size |
|---|---|---:|---:|
| `m4-20260817-a` | broad repetition/state/mixed/queue matrix | 16 | 207 MiB |
| `m4-20260817-boundaries-a` | exact rollover falsification at 732/733 and 328/329 | 6 | 68 MiB |
| `preflight` | retained untraced build/run successes and the SIGUSR1 failure | n/a | small |

Each case contains its exact command, stdout, stderr, exit status, complete
IOKit boundary trace, and full BO/map snapshots. Evidence-bearing reports live
under `../clean-analysis/` and open only explicit pre-classified command/state/
descriptor BO files. First-generation directory-wide reports are preserved in
paths containing `quarantine` and are excluded from every conclusion and the
evidence manifest. The boundary run additionally carries byte-exact safe
capture inputs in `inputs/`.

`../clean-evidence.json` is the exact evidence allowlist; `../manifest.json`
provides file sizes and SHA-256 hashes while excluding quarantined paths. Raw
snapshot trees are retained locally and intentionally gitignored because they
total 273 MiB; the manifest remains the committed content index. Captures may
contain unclassified runtime bytes. They are retained for provenance, but
Apple-authored executable bytes are never inspected or used as evidence.
