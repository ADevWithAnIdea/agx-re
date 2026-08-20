# EXP-0056: M4 compute-to-render transition framing

See `PRE_REGISTRATION.md` for the frozen question, boundary, matrix, and
falsifiers. After its preregistration commit, reproduce append-only evidence:

```sh
python3 -B run.py --run-id m4-YYYYMMDD-run01
python3 -B run.py --run-id m4-YYYYMMDD-run02
```

The runner performs metadata/trace preflight before it hashes or opens any
allowed payload. It captures only the four exact EXP-0043 command BO starts;
all other BO contents remain unread. Results are M4-only structural evidence.
