# EXP-0225 amendment 02 — lifecycle result and pre-formal reach probe

Frozen after `g17p_e0225_pilot02` and before any P2 dispatch.

All six L1 cases are complete-state exact. Byte+9 is now directly mapped at
the retained literal point:

```text
bit 1 = release byte+5 / X source after the read
bit 2 = release byte+6 / Y source after the read
```

With both set, both sources are released. With a destination/source alias,
destination publication wins. The compiler recipe remains `b9=0x20`, retaining
both inputs.

## P2 questions before the formal contract

Using only the generated H1 recipe, measure:

- both source fields over r0..r23 after one visibility instruction;
- destination relocation over r0..r23;
- a just-loaded X or Y with 0, 1, and 4 intervening instructions;
- every immediate K in 0..255;
- negative and overflowing modulo-2^32 arithmetic;
- 100 deterministic H1-only DAGs of 2..64 operations;
- destination/source aliases and two wrong-model refuters.

Every case checks the protected register set and all other non-sacrificed dump
registers. A low scratch register outside that protected set is set to zero and
used to address the dump, allowing r15 itself to be an operand or destination.
The sacrificial dump index is part of the predicted scaffold, never mistaken
for an instruction side effect.

P2 is still a disclosed pilot under `work/pilot/`; it does not count as formal
promotion. Its purpose is to select an honest compiler-safe reach/load envelope
before freezing the two-run capture contract.

