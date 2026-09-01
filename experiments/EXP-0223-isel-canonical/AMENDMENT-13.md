# AMENDMENT-13 — preempt the trailing-word shadow, narrowly

Frozen after the first offline application of AMENDMENT-12 and before another decoder edit or any
hardware dispatch.

The first offline reconstruction falsified the proposed placement, not the instruction grammar.
`instr_length()` consults the corpus-derived `_R9_SIGS`/`_R9_TRIPLES` trailing-word tables before it
reaches the low-nibble-2 instruction group.  Some valid generated `isel10` prefixes are present in
those tables, so a rule placed later cannot repair their walk.

Move the proven-form recognition before the R9 lookup.  Narrow it from all previously swept flags
and false-source values to the exact V2 formal envelope:

- `flags == 0xc0`;
- `selFalse_file in {0x00, 0x80}`.

All other AMENDMENT-12 structural predicates remain required.  These added predicates cover every
V2 canonical and release case while avoiding a general precedence claim for noncanonical values.
In particular, the existing tokenizer documents an ambiguous corpus case in which bytes +8..+9
are the head of a following store; keeping this correction inside V2's proven false-source classes
does not preempt that old rule.

The same acceptance criteria remain: reconstructed V2 bodies must walk exactly, all existing
round-trip/tokenizer tests must remain green, corpus regressions are forbidden, and the eventual
replacement hardware captures must have zero aliases.
