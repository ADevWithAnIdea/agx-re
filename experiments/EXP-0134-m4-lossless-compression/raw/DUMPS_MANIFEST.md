# Raw iotrace BO dump retention manifest

Every case in both official runs writes its full set of `tools/iotrace`-captured GPU
buffer-object hex dumps to `work/dumps/<run_id>/<case_id>/dumpNN/*.hex` (one `dumpNN/`
subdirectory per SIGUSR1 snapshot; two subdirectories for `descriptor2`-decode cases,
one otherwise). These are the complete raw byte-traces `harness/auxdecode.py` reads to
produce the decoded fields recorded in `02_gated.jsonl`.

**Origin:** generated on this host (Apple M4 / G16G) by `harness/run.py`, which invokes
`work/bin/cprobe` under `DYLD_INSERT_LIBRARIES=work/iotrace.dylib` with
`IOTRACE_DUMP_DIR` pointed at the per-case directory.

**Size:** `m4_20260828_run01/` ≈ 1.1 GiB, `m4_20260828_run02/` ≈ 1.2 GiB (7170 `.hex`
files total across both runs) — far too large to commit, and the great majority of each
BO snapshot is unrelated heap/allocator padding rather than load-bearing content (a
single case's dump directory can span many megabytes even though the descriptor + aux
region `auxdecode.py` extracts from it is a few hundred bytes).

**Retention location:** `work/dumps/<run_id>/<case_id>/` on this host only. Excluded from
git via this experiment's local `.gitignore` (`work/`). **Not committed.**

**Generation command (exact reproduction):**
```sh
python3 harness/run.py --run <run_id> --out raw/<run_id>
```
This is fully deterministic given the frozen `harness/casematrix.py` + pinned repository
revision (`CAPTURE_CONTRACT.json`) on this same physical M4 — proven by the cross-run gate
(`harness/verify.py --captured m4_20260828_run01 m4_20260828_run02`, `issues_total: 0`,
every gated `observed` field byte-identical across the two independently-generated dump
trees).

**Cryptographic hash:** not computed per-file (7170 files); the *decoded* content derived
from every dump is instead committed verbatim in `raw/<run_id>/02_gated.jsonl`, and that
file's reproducibility across two independent dump-generation passes is itself the
integrity check (a corrupted or nondeterministic dump would have produced a cross-run
`observed` mismatch, which the gate checks explicitly and found none).

**Small lawful diagnostic excerpt:** `raw/state_and_cpu_aux_excerpts.txt` — the full
128–2048-byte aux arrays (not just the 64-hex-char head shown in `02_gated.jsonl`) for
every `state_pattern`/`state_format_repeat` case and both `cpu_replace` before/after
pairs, i.e. the exact bytes behind every state-correlation and CPU-op-sync claim in
`RESULTS.md` §3–§4.
