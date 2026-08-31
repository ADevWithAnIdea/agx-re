# AMENDMENT-01 — fixed member refuted; permit an authored-MSL nomination

Frozen after `work/pilot/g17p_e0223_pilot01`, before compiling any fresh compare/select MSL.

## Observation

All seven generated cases faulted with a contained GPU hang error.  H1, H2, and H3 each faulted
in both true and false predicate directions.  The sensitivity control faulted identically.  Gate A
was clean: the requested ten-byte instructions are exactly the instructions placed in the archive,
and the independent decoder reports the requested fields.

This refutes the fixed `opsel=0`/`flags=0`/`selFalse_file=0` member as a usable starting point.  It
does not distinguish the three register packings and assigns no semantic meaning to the fault.

## Authored compiler differential, now permitted

Compile newly authored dynamic kernels whose four loaded values are unrelated:

```text
out = (cmpA < cmpB) ? trueValue : falseValue
out = (cmpA > cmpB) ? trueValue : falseValue
```

Keep the four inputs separately live after the select so a selected instruction's lifetime fields
can be recognized later.  Dynamic thread indexing prevents constant folding or preshader removal.

Inspect only the `_agc.main` belonging to these new sources.  The output may nominate:

- which compare/select family and length the compiler actually chooses;
- a valid opcode/member and fixed control point;
- candidate register packing and condition fields;
- candidate source-release controls.

No emitted instruction is copied.  The next program must be regenerated field-by-field and must
pass true/false, selector relocation, source reread, and wrong-selector controls on hardware.  If
the compiler uses the narrow `isel8` form, pivot to that form instead of forcing `isel10`.

