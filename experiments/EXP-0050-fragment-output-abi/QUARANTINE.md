# EXP-0050 v1 quarantine record

Status: **QUARANTINED / NON-EVIDENCE**

This quarantine applies to both retained v1 runs, all exact-main hex files under
`raw/`, `analysis/summary.json`, `analysis/report.txt`, the historical
`RESULTS.md` claims, and `manifest.json` as an evidence attestation.

No v1 file or raw-run directory has been deleted, renamed, rewritten, or used as
an input to the clean rerun. The raw directories remain append-only historical
records of a failed clean-room process. Their hashes are useful only to show
that the failure history was preserved.

## Reason

The v1 runner invoked the shared parser with `--stage fragment`, but that parser
first carved every shader stage and split every symbol region before returning
the requested fragment main. It therefore materialized bytes outside the
experiment's allowlist, including constant/auxiliary program regions. The v1
splice implementation also loaded whole archive byte arrays. Those operations
contradict the v1 README, environment records, and manifest statements that only
the selected authored fragment `_agc.main` was read.

The selected bytes printed into v1 raw files may themselves correspond to the
authored fragment mains, and the live readbacks were repeatable, but process is
as important as outcome. The false clean-room attestation breaks the provenance
chain, so none of those results may support a hardware fact.

## Required restoration path

Evidence status can be restored only by a new pair of runs that:

1. creates and commits a new clean pre-registration and locked authored inputs;
2. is anchored to a Git commit that predates all compiler and GPU activity;
3. writes only new `raw_v2/m4_clean_YYYYMMDD_runNN` directories;
4. uses an independently audited locator with a provenance-backed exact extent;
5. never reads, scans, mmaps, hashes, or copies an archive in userspace as a
   byte array;
6. never materializes another stage, a whole `__text`, or constant/auxiliary
   program bytes;
7. preserves all failures and records any recovery action; and
8. passes a new independent audit before any result or derived document is
   promoted.

The current `harness/exact_fragment_region.py`, `run_clean_v2.py`, and
`CLEAN_V2_LOCK.json` are **blocked, non-runnable drafts**. Mach-O `nlist`
metadata does not provide symbol size; choosing the next symbol or section end
can include padding, unsymbolized data, or auxiliary/constant code. The draft
also lacks an independent clean provenance basis for treating
`__TEXT,__fragment` as a nested container. These files must not be executed or
used as a pre-registration basis.

The v1 manifest is intentionally not regenerated: doing so would require
reading quarantined compiled-byte artifacts in this preparation turn, and it
would risk presenting v1 as current evidence. This quarantine notice supersedes
that historical manifest's clean-room claims.
