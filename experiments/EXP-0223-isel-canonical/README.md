# EXP-0223 — generated integer compare/select recipe

Goal: construct and execute a no-donor Apple9 compare/select instruction suitable for lowering
portable NIR integer comparisons and `bcsel`, starting with signed 32-bit register operands.

Read `PRE_REGISTRATION.md` before results.  Fresh own-MSL compare/select machine code is forbidden
until the three frozen operand-packing hypotheses have all executed and failed the complete-state
contract.

