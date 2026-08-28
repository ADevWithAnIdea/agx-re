# SUPERSEDED — second `m4-20260828-run01` attempt (clean-room boundary correction)

**Disclosure, not deletion**, per `SUBAGENT_BRIEF.md` ("a partial capture is
retained, never reused") and the precedent set by
`experiments/EXP-0107-m4-scratch-helper-abi/RESULTS.md`'s own "Process note"
(a self-disclosed mid-experiment boundary fix, captures superseded and
retained, not silently repaired in place).

## What happened

This was a full, successful, non-aborted run (`aborted_on_hard_fault: false`,
all 5 gated files present and self-consistent). Reviewing its I-family
results (this experiment's own novelty over EXP-0041/EXP-0107 — tracing
BEFORE any of our own compilation) found:

- `code_window_present=True` and `code_window_size=65536` (0x10000 B) already
  at checkpoint 0 (`DEVICE_CREATED`) — i.e. the EXP-0042/EXP-0108-established
  code-window VA (`0x10000000000`) already holds a registered 64 KiB BO
  before this process has compiled a single line of MSL. This size/presence
  fact is fine on its own (structural, address-free, content-free — see the
  corrected run's actual reported finding).
- A follow-up **mechanical, non-interpretive check** (byte value == 0
  count only, never a read of instruction semantics) on the raw capture
  found this pre-first-compile code-window BO's captured content was
  **NOT all-zero** (360 of 4096 captured prefix bytes nonzero).

This experiment's `harness/inittrace.c`, as originally written, captured a
content PREFIX of every registered BO unconditionally, including this one —
inherited directly from EXP-0107's `harness/maptrace.c`, which never needed
an exclusion here because ITS single capture always happened AFTER our own
shader had already compiled (so any code-window content it captured was
always attributable to our own just-compiled program, OWN-SHADER). This
experiment's I family captures BEFORE our first compile too, where that
attribution does not hold, and `harness/inittrace.c` did not carry forward
`EXP-0108-m4-bg-eot-programs/harness/wtrace.c`'s own deliberate,
PRE_REGISTRATION-frozen exclusion of that exact VA range
(`[0x10000000000, 0x10000020000)`) from content capture — an established,
already-reviewed clean-room safeguard this experiment's own harness should
have carried forward from the start and did not.

## Why this matters and what was NOT done

Per `CLAUDE.md`/`CODEX.md`: never disassemble, decompile, or otherwise
introspect the machine code of any Apple binary. Content sitting in the
code-window region before this process has compiled anything of its own
cannot be presumed to be our own code, and its semantic content (were it
Apple-authored machine code) is exactly the forbidden category. **No
disassembly, decoding, instruction-level interpretation, or any
byte-pattern analysis beyond a zero/nonzero count was ever performed on
this content, by any tool or by the agent running this experiment.** The
only operations applied were: (a) the harness's own generic hex-dump
capture (identical code path used for every other BO, not code-window-
specific), and (b) one deliberately minimal all-zero-byte-count check run
specifically to decide whether this disclosure was needed at all.

## Disposition

1. `harness/inittrace.c` is corrected to exclude the code-window VA range
   from content capture entirely, "by construction" — adopting
   `EXP-0108-m4-bg-eot-programs/harness/wtrace.c`'s own exact convention
   (still records presence/size, a content-free stub file replaces the
   hex dump; see the `CODE-WINDOW CONTENT EXCLUSION` comment block in the
   corrected `harness/inittrace.c`).
2. This entire run directory is retained here, disclosed, and NOT
   deleted — but the code-window `.hex` files within it (every
   `bo_va10000000000_sz10000.hex` under every checkpoint of every case) are
   **not to be read, opened, or analyzed by anyone, ever, for any purpose**;
   treat their content field as forbidden material, structurally identical
   in kind to an Apple binary, even though its actual authorship
   (Apple-resident program vs. incidental non-code memory) was never
   determined and is explicitly NOT claimed either way. If retention of
   this content itself is judged unacceptable on review, the resolution is
   to replace those specific `.hex` files with a hash-only manifest entry
   (`CODEX.md`'s own stated contingency for material that "cannot legally
   be committed" -- "commit a manifest containing its exact origin, size,
   cryptographic hash ... never commit an Apple binary"), which the
   orchestrator may apply at commit time; this experiment does not commit
   anything itself.
3. The real capture was re-run fresh, under the SAME originally-contracted
   run id `m4-20260828-run01`, using the corrected `harness/inittrace.c` —
   following the same precedent as the first (crash) supersession in this
   same `raw/` directory and as `EXP-0107-m4-scratch-helper-abi`'s own
   established pattern.
4. `PRE_REGISTRATION.md` carries a dated addendum recording this
   correction; the original hypotheses/falsifiers are unchanged, since the
   fix is a content-capture SAFETY boundary, not a change to what is being
   tested.
5. **Redaction applied.** `analysis/redact_codewindow.py` was run once
   against this directory: it replaced the byte content of all 12
   `bo_va10000000000_sz10000.hex` files (6 checkpoints x 2 variants) with a
   redaction notice carrying only `captured_len`, `nonzero_byte_count`, and
   a `sha256` of the original bytes -- auditable proof that content existed
   and was non-trivial, without retaining the actual bytes. No semantic
   interpretation of the redacted content (before or after redaction) was
   performed beyond the zero/nonzero count already disclosed above.
