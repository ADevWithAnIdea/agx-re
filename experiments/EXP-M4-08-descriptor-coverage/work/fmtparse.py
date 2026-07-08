#!/usr/bin/env python3
"""fmtparse.py — decode the format_capture.txt table into byte0/byte1 fields and
group by (sizeclass, arrangement) to reverse the byte0 channel-arrangement nibble.
Clean-room: operates on captured DATA only."""
import re, sys, collections
lines=open(sys.argv[1] if len(sys.argv)>1 else '../raw/format_capture.txt').read().splitlines()
rows=[]
for ln in lines:
    m=re.match(r'FMT\s+(\S+)\s+word0=([0-9a-f]+)\s+word1=([0-9a-f]+)',ln)
    if not m:
        if 'FAIL' in ln: print('SKIP(fail):',ln)
        continue
    name=m.group(1); w0=int(m.group(2),16); w1=int(m.group(3),16)
    b0=w0&0xff; b1=(w0>>8)&0xff
    ttype=b0&0x7
    arr_nib=(b0>>4)&0xf          # byte0 bits[4:7]
    arr3=(b0>>5)&0x7             # byte0 bits[5:7] (bit4 seen always 0)
    numtype=(b1>>5)&0x7
    sizeclass=b1&0x1f
    swiz=(w0>>16)&0xfff
    rows.append(dict(name=name,w0=w0,b0=b0,b1=b1,ttype=ttype,arr_nib=arr_nib,
                     arr3=arr3,numtype=numtype,sizeclass=sizeclass,swiz=swiz))

NT={0:'unorm',1:'snorm',2:'uint',3:'sint',4:'float',5:'xr'}
print(f'{"format":24} b0   b1   type arr[4:7] arr[5:7] numtype       sizeclass swizzle')
for r in rows:
    print(f'{r["name"]:24} 0x{r["b0"]:02x} 0x{r["b1"]:02x}  {r["ttype"]}    0x{r["arr_nib"]:x}      {r["arr3"]}       '
          f'{NT.get(r["numtype"],"?"+str(r["numtype"])):11} 0x{r["sizeclass"]:02x}     0x{r["swiz"]:03x}')

# byte0 bit4 sanity: is it always 0?
print('\n# byte0 bit4 (0x10) values seen:', sorted(set((r["b0"]>>4)&1 for r in rows)))

# group by sizeclass -> list of (arr3, name, numtype)
print('\n# Grouping by sizeclass -> arrangement sub-index (arr = byte0[5:7]):')
g=collections.defaultdict(list)
for r in rows: g[r['sizeclass']].append(r)
for sc in sorted(g):
    entries=g[sc]
    # for each sizeclass, show arr3 -> {numtype:name}
    print(f'  sizeclass 0x{sc:02x}:')
    byarr=collections.defaultdict(list)
    for r in entries: byarr[r['arr3']].append(r)
    for a in sorted(byarr):
        names=', '.join(f'{r["name"]}({NT.get(r["numtype"],r["numtype"])})' for r in byarr[a])
        print(f'      arr={a}: {names}')

# numtype orthogonality check: for each (sizeclass,arr3) family, list numtypes present
print('\n# numtype orthogonality — (sizeclass,arr) families with >1 numtype:')
fam=collections.defaultdict(set)
famnames=collections.defaultdict(list)
for r in rows:
    fam[(r['sizeclass'],r['arr3'])].add(r['numtype'])
    famnames[(r['sizeclass'],r['arr3'])].append((r['numtype'],r['name']))
for k in sorted(fam):
    if len(fam[k])>1:
        nts=','.join(NT.get(n,str(n)) for n in sorted(fam[k]))
        print(f'  sizeclass=0x{k[0]:02x} arr={k[1]}: numtypes {{{nts}}} -> '
              + ', '.join(f'{n}:{NT.get(nt,nt)}' for nt,n in sorted(famnames[k])))
