# EXP-0228 — low-nibble-9 compact-class length

This experiment broadens EXP-0227's single G17P length point to 22 selected
selector-0/1 byte+2 values, including the full upper-five-bit endpoints.

```sh
python3 harness/selftest228.py
export SSHPASS=...
sh harness/push228.sh
sh harness/verify228_remote.sh
# Neo: sh harness/capture228_pilot.sh g17p_e0228_pilot01
```
