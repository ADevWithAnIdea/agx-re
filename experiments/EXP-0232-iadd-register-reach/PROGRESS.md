# EXP-0232 progress

- Pre-registered 191 dense per-role reach cases and two negative controls before dispatch.
- Offline geometry/provenance self-test passes for all 193 non-slot-probe programs.
- Main canonical/reverse runs pass: source A r0..r31, source B r0..r63, and destination r0..r94
  are exact in both runs; both wrong-oracle controls fire.
- Amendment 01 corrected a cross-target provenance error in the pre-registration, then hardware
  refuted its inherited M4/G16G boundary: G17P r95 is exact, while r96 and r127 fault.
- Amendment 02 froze the corrected G17P model before dispatch. Two opposite-order runs confirm r95
  as the maximum valid physical destination and r96 as the first invalid destination. Invalid
  writes produce contained command-buffer faults, do not wrap, and exact controls pass afterward.
- All five runs pass target/provenance auditing: no foreign runner, no hang, no restart, and only
  the expected two recovery events in each deliberate-boundary run.
