# Diagnostic probe re-derivation

The original ~30 informal pilot probes (`work/pilot1`..`work/pilot33`) that
shaped this experiment's design (see PRE_REGISTRATION.md "pilot diagnostics"
and PROGRESS.md) were run in `work/`, which -- per this experiment's own
process (work/ is scratch, cleaned between gated runs) -- was removed before
the formal two-run capture began. That is the correct disposal for SCRATCH
work, but it left the decisive pilot findings without a permanent raw
artifact, which is a genuine process gap against CODEX.md's evidence-
preservation rule (raw observations should be append-only evidence).

This directory re-derives the SAME decisive findings (not the full 33-probe
exploration trail, which is not practical to fully replay under this
correction) as permanent, timestamped raw output, so every claim in
PRE_REGISTRATION.md/RESULTS.md that cites a "pilotNN" finding has a
reproducible, committed artifact behind it. Each `.txt` file is the
unedited stdout of one `python3 -B diagnostics/probeNN_*.py` run against
real M4 hardware, captured via `script`/redirection at the time this
directory was created (same day as the two gated captures, same repo
revision, same toolchain).
