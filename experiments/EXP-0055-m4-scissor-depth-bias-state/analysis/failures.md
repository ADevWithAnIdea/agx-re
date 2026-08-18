# Preserved analysis/verification failures

## Initial final-verifier invocation

The first `python3 verify.py` invocation occurred only after both successful live
runs and manifest generation. Metadata preflight stopped before opening or hashing
any payload because Python's regular-expression match object does not accept a
slice in `match[10:]`:

```text
Traceback (most recent call last):
  File "verify.py", line 538, in <module>
    raise SystemExit(main())
  File "verify.py", line 250, in main
    allowed_payload_paths = metadata_preflight()
  File "verify.py", line 209, in metadata_preflight
    match[10:] == ("1", "1"),
IndexError: no such group
```

The verifier was corrected mechanically to compare
`(match[10], match[11]) == ("1", "1")`. No raw artifact, hypothesis, result,
allowed payload, or analysis output was changed. This file preserves the failed
verification attempt as process evidence.

## Second final-verifier invocation

The next invocation passed metadata preflight, all raw/history/source/build/run
checks, and analysis/manifest regeneration, then rejected the experiment's exact
top-level set because the preceding explicit `py_compile` syntax check had created
untracked `__pycache__` directories:

```text
AssertionError: exact experiment top-level entries
```

The four generated `.pyc` files and their two cache directories were deleted.
They were rebuildable local Python cache products, contained no experiment
evidence, and had already been excluded from the generated manifest. No raw or
derived evidence was changed.

## Independent pre-commit tooling audit

An independent audit then tested the verifier and manifest generator in isolated
copies. The current evidence and claims passed, but four process-tool defects
were found before the evidence commit:

1. retained absolute build/run paths were compared with the verifier checkout's
   current path, so verification failed after relocation;
2. the manifest generator wrote current `HEAD` while the verifier required the
   preregistration revision exactly, so post-commit regeneration was not durable;
3. the trace parsers accepted an injected unknown record family; and
4. the manifest generator hashed a test `rogue.bin` outside the declared state
   matrix before the verifier could reject it.

All four were corrected without altering a raw file. Historical capture paths
are now explicit data and relocation-safe. The manifest keeps a syntactically
validated Git ancestor anchor. Every trace line must match one of the five exact
retained families, and the verifier binds their aggregate counts. The current
runner's post-capture hardening is delimited; the verifier removes only those
blocks in memory and proves the reconstructed live-runner SHA-256 equals the
source hash recorded before both GPU runs. Finally, manifest generation resolves
the exact global files/directories/types and the 152 allowed payload paths before
any artifact digest. Unknown files, symlinks, and special entries fail before
content access.

The injected unknown-line and `rogue.bin` sentinels existed only in isolated test
copies. They were not Apple, shader, auxiliary, command, or captured BO content,
were never added to this experiment, and were used solely to demonstrate the
fail-closed defects. The audit accessed no prohibited payload.
