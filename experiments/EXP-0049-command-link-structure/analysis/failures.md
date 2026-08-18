# Preserved analysis failure

The first invocation of `analysis/summarize.py` stopped before writing derived
outputs because a Python set key contained the nested `link_offsets` list. No
raw evidence was modified. The comparison key was changed to the canonical JSON
text of that list, after which the same raw inputs were analyzed again.
