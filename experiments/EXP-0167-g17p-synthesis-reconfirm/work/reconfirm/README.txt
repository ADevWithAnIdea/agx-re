EXP-0167 witness-gated re-confirmation output.

PRIMARY, AUTHORED FILES (these are the evidence):
  reconfirm_iso.jsonl             48 cases x 5 reps -- the mandatory scope fixed in
                                  PRE_REGISTRATION.md 6.1(a)+(b): the 20 named watch
                                  cases, union every case whose outcome in iso01 or
                                  iso02 was not `ok`.
  reconfirm_iso_stratified.jsonl  100 cases x 5 reps -- the OPTIONAL top-up, 6.1(c):
                                  the first 20 cases of each family in case-index
                                  order, minus those already covered above. Reported
                                  separately; never merged into M1/M2/M3.
  *.log                           the runner's own stdout, append-only.

  reconfirm02.jsonl  = reconfirm_iso.jsonl + reconfirm_iso_stratified.jsonl,
  concatenated verbatim.  It exists ONLY because `analysis/summarize.py` is held
  BYTE-IDENTICAL to EXP-0158's (so the metric definitions cannot drift between the
  two experiments) and that file hardcodes the name `reconfirm02.jsonl` for "the
  witness-gated 5-repeat pass".  It is derived, not authored: nothing is in it that
  is not in the two files above, in the same order.
