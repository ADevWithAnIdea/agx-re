#!/usr/bin/env python3
"""auxdecode.py -- EXP-0134 descriptor + compression-aux decoder.

Host-side (anywhere, py3). Loads the iotrace .hex BO dumps a cprobe "probe" case
wrote (harness/cprobe.m, run under the READ-ONLY tools/iotrace interposer, built
unmodified into work/iotrace.dylib), locates the texture's 32-byte sampled
descriptor (same technique as EXP-0017's twiddle.py / EXP-M4-07's solve3d.py --
our own prior authored code, extended here to read words 4-7 for the secondary
(aux) VA and to accept a caller-supplied type nibble), decodes the compression
flags (word1 bit27, word3 bit31), the secondary VA, and -- when present --
measures the exact aux byte count as (aux BO's captured size) - (secondaryVA -
aux BO base), i.e. read directly off the captured allocation, not assumed from
a formula. Optionally extracts the raw aux byte array for state-correlation
analysis.

CLEAN-ROOM: operates only on DATA captured from our own process (byte contents
of registered BOs). No Apple binary is read or introspected.

Usage (library, imported by run.py, or standalone):
  auxdecode.py DUMPDIR --type 2d --w 32 --h 32 [--aux-hex]
"""
import argparse, glob, json, os, re, sys

HEXLINE = re.compile(r'^([0-9a-f]{8}):\s+(.*)$')
HDR     = re.compile(r'gpu_va=0x([0-9a-f]+) cpu=0x([0-9a-f]+) size=0x([0-9a-f]+)')

# texture-type nibble (byte0 low nibble), docs/tiling/README.md §1.6 / docs/descriptors
TYPECODE = {'2d': 2, '2darray': 3, '2dms': 4, '3d': 5, 'cube': 6, 'cubearray': 7}


def load_bos(dumpdir):
    bos = []
    for path in sorted(glob.glob(os.path.join(dumpdir, '*.hex'))):
        gpu_va = cpu = size = 0
        data = bytearray()
        with open(path) as f:
            for line in f:
                if line.startswith('#'):
                    m = HDR.search(line)
                    if m:
                        gpu_va, cpu, size = (int(m.group(i), 16) for i in (1, 2, 3))
                    continue
                m = HEXLINE.match(line)
                if not m:
                    continue
                off = int(m.group(1), 16)
                b = bytes.fromhex(m.group(2).replace(' ', ''))
                if len(data) < off + len(b):
                    data.extend(b'\x00' * (off + len(b) - len(data)))
                data[off:off + len(b)] = b
        bos.append({'path': path, 'gpu_va': gpu_va, 'cpu': cpu, 'size': size, 'data': bytes(data)})
    return bos


def find_descriptors(bos, W, H, typecode):
    """Scan every captured BO at 4-byte granularity for a 32-byte texture
    descriptor whose type nibble and width-1/height-1 fields match. Returns a
    list of (bo, offset, words[8]) -- normally exactly one for a single-texture
    probe process, but callers should tolerate >1 (e.g. cpuop=blit creates a
    second same-shaped texture) and disambiguate by base VA."""
    out = []
    for b in bos:
        d = b['data']
        for o in range(0, len(d) - 32, 4):
            w0 = int.from_bytes(d[o:o + 4], 'little')
            if (w0 & 0xf) != typecode:
                continue
            w1 = int.from_bytes(d[o + 4:o + 8], 'little')
            width = (((w0 >> 28) & 0xf) | ((w1 & 0x3ff) << 4)) + 1
            height = ((w1 >> 10) & 0x3fff) + 1
            if width != W or height != H:
                continue
            words = [int.from_bytes(d[o + 4 * i:o + 4 * i + 4], 'little') for i in range(8)]
            base_va = (words[2] | ((words[3] & 0xfff) << 32)) << 4
            if not any(bb['gpu_va'] and bb['gpu_va'] <= base_va < bb['gpu_va'] + bb['size'] for bb in bos):
                continue
            out.append({'desc_bo': b['path'], 'desc_off': o, 'words': words, 'base_va': base_va})
    return out


def decode_descriptor(words, bos):
    w = words
    compressed = (w[1] >> 27) & 1
    aux_layout = (w[3] >> 31) & 1
    mipmapped = (w[1] >> 26) & 1
    mip_count_minus1 = (w[5] >> 16) & 0xf
    sample_count_field = (w[1] >> 24) & 3  # log2(n)-1
    base_va = (w[2] | ((w[3] & 0xfff) << 32)) << 4
    sec_va = (w[4] | ((w[5] & 0xfff) << 32)) << 4 if w[4] or (w[5] & 0xfff) else 0

    main_bo = next((bb for bb in bos if bb['gpu_va'] and bb['gpu_va'] <= base_va < bb['gpu_va'] + bb['size']), None)
    result = {
        'words_hex': [f'{x:08x}' for x in w],
        'compression_flag_word1_b27': compressed,
        'aux_layout_flag_word3_b31': aux_layout,
        'mipmapped_word1_b26': mipmapped,
        'mip_count_minus1': mip_count_minus1,
        'sample_count_field_log2n_minus1': sample_count_field,
        'base_va': hex(base_va),
        'secondary_va': hex(sec_va) if sec_va else None,
        'main_bo_gpu_va': hex(main_bo['gpu_va']) if main_bo else None,
        'main_bo_size': hex(main_bo['size']) if main_bo else None,
        'main_image_offset_in_bo': hex(base_va - main_bo['gpu_va']) if main_bo else None,
    }
    if sec_va:
        aux_bo = next((bb for bb in bos if bb['gpu_va'] and bb['gpu_va'] <= sec_va < bb['gpu_va'] + bb['size']), None)
        if aux_bo:
            aux_off = sec_va - aux_bo['gpu_va']
            aux_bytes_measured = aux_bo['size'] - aux_off
            result['aux_bo_gpu_va'] = hex(aux_bo['gpu_va'])
            result['aux_bo_size'] = hex(aux_bo['size'])
            result['aux_offset_in_bo'] = hex(aux_off)
            result['aux_bytes_measured'] = aux_bytes_measured
            result['aux_same_bo_as_main'] = (main_bo is not None and aux_bo['gpu_va'] == main_bo['gpu_va'])
            result['main_image_bytes_measured'] = aux_off - (base_va - main_bo['gpu_va']) if main_bo else None
            result['_aux_hex_full'] = aux_bo['data'][aux_off:aux_off + aux_bytes_measured].hex()
        else:
            result['aux_bo_gpu_va'] = None
            result['aux_lookup_error'] = 'secondary VA not inside any captured BO'
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dumpdir')
    ap.add_argument('--type', default='2d', choices=list(TYPECODE))
    ap.add_argument('--w', type=int, required=True)
    ap.add_argument('--h', type=int, required=True)
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()
    bos = load_bos(a.dumpdir)
    if not bos:
        print(json.dumps({'error': 'no .hex dumps found', 'dumpdir': a.dumpdir}))
        return 1
    cands = find_descriptors(bos, a.w, a.h, TYPECODE[a.type])
    if not cands:
        print(json.dumps({'error': 'no matching descriptor found', 'dumpdir': a.dumpdir,
                           'w': a.w, 'h': a.h, 'type': a.type,
                           'bo_summary': [{'gpu_va': hex(b['gpu_va']), 'size': hex(b['size'])} for b in bos]}))
        return 1
    decoded = [decode_descriptor(c['words'], bos) for c in cands]
    out = {'n_descriptors_found': len(decoded), 'descriptors': decoded}
    print(json.dumps(out, indent=2 if a.json else None))
    return 0


if __name__ == '__main__':
    sys.exit(main())
