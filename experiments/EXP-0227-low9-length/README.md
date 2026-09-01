# EXP-0227 — G17P low-nibble-9 length pilot

This is the first bounded hardware action under Step 1 of
`APPLE9_COMPILER_RE_COMPLETION_PLAN.md`. It tests one stream-grammar claim:
whether `09 01 20 05` consumes four bytes on G17P.

The candidate and every following instruction are generated from documented
fields. No compiler-emitted instruction bytes are copied. Four two-byte marker
instructions begin at candidate-relative offsets 4, 6, 8, and 10; a fifth at
offset 12 is the resynchronization control. The complete r0..r23 state is read
back. See `PRE_REGISTRATION.md` for predictions and refuters.

The carrier is a byte-identical copy of the repository's own authored
`EXP-0220` MSL carrier. Its compiled arithmetic is never executed: the complete
`_agc.main` region is replaced by this experiment's generated program.

```sh
python3 harness/selftest227.py

# Only after the frozen pre-registration commit:
export SSHPASS=...                 # lab credential, never place it in a file
sh harness/push227.sh
sh harness/verify227_remote.sh     # deliberately separate transaction

# On the Neo:
sh harness/capture227_pilot.sh g17p_e0227_pilot01
```

The pilot writes to `work/pilot/`, not `raw/`, and cannot close Step 1. A later
amendment must freeze the formal two-run capture if the pilot is interpretable.
