# EXP-0225 — generated integer multiply-add recipe

This experiment asks whether G17P can execute a compiler-generated low-32-bit
integer multiply/add without copying an instruction token from a Metal result.
It verifies the complete r0..r23 state, including the lifetime of both
multiplicands, and then promotes the surviving recipe through relocation,
aliases, immediate coverage, load provenance, and generated DAGs.

The first dispatch is governed by `PRE_REGISTRATION.md`.  All generated fields
carry the same provenance ledger and whole-program framing checks introduced by
EXP-0220.

