# rv01__cvt_bf16 — NEVER RAN

The shard directory was created and the run aborted immediately: compiling the
carrier failed because the host's `MTLCompilerService` had collapsed machine-wide
("... the compiler is no longer active ... Reentrancy avoided"). Not a single case
was dispatched, so there is no `sweep.jsonl`.

Every field of `cvt_bf16` is therefore `untested` in
`analysis/field_verdicts.json`. No label was carried forward from the earlier
contaminated captures (run01-run05) to fill this gap.
