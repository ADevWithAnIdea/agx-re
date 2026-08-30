#!/usr/bin/env python3
"""EXP-0176: check PROVENANCE.md's markdown table integrity with GFM semantics.

A GFM table cell is delimited by an UNESCAPED `|`. A bare `|` inside backticks is
NOT protected — it still splits the cell. This is why rows carrying `a|b` in code
spans render with shifted columns.

    python3 experiments/EXP-0176-provenance-chain/analysis/table_integrity.py
"""
import json, os, re
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.abspath(os.path.join(HERE,'..','..','..'))
lines=open(os.path.join(ROOT,'PROVENANCE.md')).read().splitlines()

def cells(l):
    b=l.strip()
    if b.startswith('|'): b=b[1:]
    if b.endswith('|') and not b.endswith('\\|'): b=b[:-1]
    return re.split(r'(?<!\\)\|', b)

hdr=[i for i,l in enumerate(lines,1) if re.match(r'^\|\s*Date\s*\|',l)]
delim=[i for i,l in enumerate(lines,1) if re.match(r'^\|[-: |]+\|?\s*$',l)]
first_nontable=None
rows=[]
for i,l in enumerate(lines,1):
    if l.startswith('|'):
        if i in hdr or i in delim: continue
        rows.append(i)
    elif i>min(hdr or [1e9]) and l.strip():
        if first_nontable is None: first_nontable=i

out={"header_rows":hdr,"delimiter_rows":delim,"data_rows":len(rows),
     "first_non_table_line_after_header":first_nontable}
bad=[]
for i in rows:
    c=cells(lines[i-1])
    if len(c)!=5:
        bad.append({"line":i,"cells":len(c),"first_60":lines[i-1][:60],
                    "cell_previews":[x.strip()[:45] for x in c]})
out["rows_with_wrong_cell_count"]=bad
# rows that fall OUTSIDE the single table (after the first non-table line)
if first_nontable:
    out["rows_after_the_table_breaks"]=[i for i in rows if i>first_nontable]
    out["n_rows_outside_table"]=len(out["rows_after_the_table_breaks"])
# glued rows: a second `| <date> |` starting mid-line
glued=[]
for i in rows:
    for m in re.finditer(r'\|\s*\|?\s*(20\d\d-\d\d-\d\d)\s*\|', lines[i-1][2:]):
        glued.append({"line":i,"second_row_date":m.group(1)})
out["physical_lines_carrying_two_logical_rows"]=glued
json.dump(out, open(os.path.join(HERE,'table_integrity.json'),'w'), indent=1)
print(json.dumps({k:v for k,v in out.items() if k!='rows_with_wrong_cell_count'}, indent=1))
print("\nrows with wrong cell count:", len(bad))
for b in bad: print("  L%-4d cells=%d  %s" % (b['line'],b['cells'],b['first_60']))
