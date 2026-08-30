# RESULTS — EXP-0157 (G17P): the MISC family

**Headline: the acceleration-structure testbed gap is CLOSED, and `op04_len8`'s declared
length is wrong on hardware.**

| | |
|---|---|
| Target | **Apple A18 Pro / G17P** (`Mac17,5`, `AGXAcceleratorG17P`, `applegpu_g17p`, 5 GPU cores, macOS 26.6 build 25G5043d). Every record is `target: G17P`. |
| Gated captures | `raw/g17p_run01` and `raw/g17p_run02` (same resolved case list, `--replay`) |
| Fault confirmation | `raw/g17p_reval01`, 5x per case **under `~/agxre/gpulease.sh`** (FIELD-SWEEP-PROTOCOL §7A) |
| Post-freeze controls | `raw/g17p_reach01` (reachability), `raw/g17p_bbox01` (custom-intersection carriers), `raw/g17p_lenmap01`, `raw/g17p_qlen01`, `raw/g17p_qlen02` (hardware length probe) |
| Concurrency | unlocked and concurrent with the rest of the wave throughout; see §9 |
