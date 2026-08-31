# EXP-0222 — canonical low-register `iadd2`

This experiment turns the corrected G17P `iadd2` operand map into a complete generated compiler
recipe over the tested r0..r23 32-bit register-register envelope, then stresses it under register
reuse, load provenance, aliases, and lifecycle contexts.

Read `PRE_REGISTRATION.md` before any result.  No fresh Metal integer instruction may be inspected
until the three pre-registered independent layouts have failed.

Result: **canonical recipe proven**. See `RESULTS.md`; reproduce the formal gate with
`python3 analysis/verify222.py`.

