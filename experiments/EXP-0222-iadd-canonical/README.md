# EXP-0222 — canonical low-register `iadd2`

This experiment attempts to turn the corrected G17P `iadd2` operand map into a complete generated
compiler recipe, then stress that recipe under register reuse and lifecycle contexts.

Read `PRE_REGISTRATION.md` before any result.  No fresh Metal integer instruction may be inspected
until the three pre-registered independent layouts have failed.

