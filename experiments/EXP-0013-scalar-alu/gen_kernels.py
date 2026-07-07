#!/usr/bin/env python3
# gen_kernels.py -- EXP-0013 scalar-ALU provocation kernels (conversions, FMA,
# float unary, fmin/fmax, bitwise/shift/bitfield/compare condition codes).
# Each kernel is minimal and writes a device buffer so the op cannot be DCE'd.
# CLEAN-ROOM: all of these are OUR OWN MSL.
import os
HERE = os.path.dirname(os.path.abspath(__file__))
KD = os.path.join(HERE, "kernels")
os.makedirs(KD, exist_ok=True)
HDR = "#include <metal_stdlib>\nusing namespace metal;\n\n"

def w(name, body):
    with open(os.path.join(KD, name + ".metal"), "w") as f:
        f.write(HDR + body + "\n")

def k1(ta, to, expr, aname="a"):
    # one input buffer 'a' (type ta) -> out (type to); expr uses a[gid]
    return (f"kernel void k(device const {ta} *{aname} [[buffer(0)]],\n"
            f"              device {to} *out [[buffer(1)]],\n"
            f"              uint gid [[thread_position_in_grid]]) {{\n"
            f"    out[gid] = {expr};\n}}")

def k2(ta, tb, to, expr):
    return (f"kernel void k(device const {ta} *a [[buffer(0)]],\n"
            f"              device const {tb} *b [[buffer(1)]],\n"
            f"              device {to} *out [[buffer(2)]],\n"
            f"              uint gid [[thread_position_in_grid]]) {{\n"
            f"    out[gid] = {expr};\n}}")

def k3(ta, tb, tc, to, expr):
    return (f"kernel void k(device const {ta} *a [[buffer(0)]],\n"
            f"              device const {tb} *b [[buffer(1)]],\n"
            f"              device const {tc} *c [[buffer(2)]],\n"
            f"              device {to} *out [[buffer(3)]],\n"
            f"              uint gid [[thread_position_in_grid]]) {{\n"
            f"    out[gid] = {expr};\n}}")

# ---------------- 1. CONVERSIONS ----------------
w("cv_f2h", k1("float", "half",  "half(a[gid])"))      # fp32 -> fp16
w("cv_h2f", k1("half",  "float", "float(a[gid])"))     # fp16 -> fp32
w("cv_f2i", k1("float", "int",   "int(a[gid])"))       # fp32 -> int (trunc)
w("cv_i2f", k1("int",   "float", "float(a[gid])"))     # int  -> fp32
w("cv_f2u", k1("float", "uint",  "uint(a[gid])"))      # fp32 -> uint
w("cv_u2f", k1("uint",  "float", "float(a[gid])"))     # uint -> fp32
w("cv_i2h", k1("int",   "half",  "half(a[gid])"))      # int  -> fp16
w("cv_h2i", k1("half",  "int",   "int(a[gid])"))       # fp16 -> int
w("cv_h2u", k1("half",  "uint",  "uint(a[gid])"))      # fp16 -> uint
w("cv_u2h", k1("uint",  "half",  "half(a[gid])"))      # uint -> fp16
# integer width / sign conversions (via 32-bit store so we see the convert reg-side)
w("cv_i2s", k1("int",   "int",   "int(short(a[gid]))"))   # int->short->int (sign-narrow+widen)
w("cv_i2c", k1("int",   "int",   "int(char(a[gid]))"))    # int->char->int (sign extend from 8)
w("cv_u2us",k1("uint",  "uint",  "uint(ushort(a[gid]))")) # zero-extend from 16
w("cv_u2uc",k1("uint",  "uint",  "uint(uchar(a[gid]))"))  # zero-extend from 8
w("cv_i2u", k1("int",   "uint",  "uint(a[gid])"))         # int<->uint bit reinterpret (no-op?)
w("cv_bitcast", k1("float","uint", "as_type<uint>(a[gid])"))  # bit reinterpret (no convert)
w("cv_ibitcast",k1("uint", "float","as_type<float>(a[gid])")) # bit reinterpret
# store-narrowing (does the STORE do the fp convert or a prior instr?)
w("cv_f2h_store", ("kernel void k(device const float *a [[buffer(0)]],\n"
    "              device half *out [[buffer(1)]],\n"
    "              uint gid [[thread_position_in_grid]]) {\n"
    "    out[gid] = half(a[gid] + a[gid]);\n}"))  # force an ALU before the narrowing store

# ---------------- 2. FMA / 3-source ----------------
w("fma",    k3("float","float","float","float", "fma(a[gid], b[gid], c[gid])"))
w("fma_mad",k3("float","float","float","float", "a[gid]*b[gid] + c[gid]"))  # contracts under fast-math

# ---------------- 3. FLOAT UNARY (0x0b, 10B) ----------------
w("un_fneg",  k1("float","float","-a[gid]"))
w("un_fabs",  k1("float","float","fabs(a[gid])"))
w("un_frcp",  k1("float","float","1.0f / a[gid]"))          # reciprocal (fast-math)
w("un_frsqrt",k1("float","float","rsqrt(a[gid])"))
w("un_fsqrt", k1("float","float","sqrt(a[gid])"))
w("un_fexp2", k1("float","float","exp2(a[gid])"))
w("un_flog2", k1("float","float","log2(a[gid])"))
w("un_fsin",  k1("float","float","sin(a[gid])"))
w("un_fcos",  k1("float","float","cos(a[gid])"))
w("un_ffloor",k1("float","float","floor(a[gid])"))
w("un_fceil", k1("float","float","ceil(a[gid])"))
w("un_ftrunc",k1("float","float","trunc(a[gid])"))
w("un_frint", k1("float","float","rint(a[gid])"))
w("un_fsat",  k1("float","float","saturate(a[gid])"))
w("un_fmov",  k1("float","float","a[gid] * 1.0f"))          # try to elicit a plain move/copy

# ---------------- 4. FMIN / FMAX (0x12, 6B) ----------------
w("fmin",  k2("float","float","float","fmin(a[gid], b[gid])"))
w("fmax",  k2("float","float","float","fmax(a[gid], b[gid])"))
w("fmin_min", k2("float","float","float","min(a[gid], b[gid])"))
w("fmax_max", k2("float","float","float","max(a[gid], b[gid])"))

# ---------------- 5a. BITWISE (0x0b, 10B truth-table) ----------------
w("iand", k2("uint","uint","uint","a[gid] & b[gid]"))
w("ior",  k2("uint","uint","uint","a[gid] | b[gid]"))
w("ixor", k2("uint","uint","uint","a[gid] ^ b[gid]"))
w("inot", k1("uint","uint","~a[gid]"))
w("iandn",k2("uint","uint","uint","a[gid] & ~b[gid]"))   # and-not (invert srcB)
w("iorn", k2("uint","uint","uint","a[gid] | ~b[gid]"))
w("ixnor",k2("uint","uint","uint","~(a[gid] ^ b[gid])"))
w("inand",k2("uint","uint","uint","~(a[gid] & b[gid])"))
w("inor", k2("uint","uint","uint","~(a[gid] | b[gid])"))

# ---------------- 5b. SHIFT / BITFIELD (0xa7) ----------------
w("ishl",  k2("int", "int", "int", "a[gid] << b[gid]"))
w("iashr", k2("int", "int", "int", "a[gid] >> b[gid]"))   # arithmetic (signed)
w("ushr",  k2("uint","uint","uint","a[gid] >> b[gid]"))   # logical (unsigned)
w("ushl",  k2("uint","uint","uint","a[gid] << b[gid]"))
w("ishl_i",k1("int", "int", "a[gid] << 3"))               # shift by imm
w("iashr_i",k1("int","int", "a[gid] >> 2"))
w("ushr_i",k1("uint","uint","a[gid] >> 2"))
w("ibfe",  k1("uint","uint","extract_bits(a[gid], 4u, 8u)"))
w("ibfe_s",k1("int", "int", "extract_bits(a[gid], 4, 8)"))  # signed extract
w("ibfi",  k2("uint","uint","uint","insert_bits(a[gid], b[gid], 3u, 5u)"))

# ---------------- 5c. COMPARE condition codes ----------------
# integer compare producing 0/1 (icmpsel / 0x12 form)
for nm, ty, op in [("icmp_eq","int","=="),("icmp_ne","int","!="),
                   ("icmp_lt","int","<"),("icmp_le","int","<="),
                   ("icmp_gt","int",">"),("icmp_ge","int",">="),
                   ("ucmp_lt","uint","<"),("ucmp_le","uint","<="),
                   ("ucmp_gt","uint",">"),("ucmp_ge","uint",">="),
                   ("ucmp_eq","uint","=="),("ucmp_ne","uint","!=")]:
    w(nm, ("kernel void k(device const %s *a [[buffer(0)]],\n"
           "              device const %s *b [[buffer(1)]],\n"
           "              device int *out [[buffer(2)]],\n"
           "              uint gid [[thread_position_in_grid]]) {\n"
           "    out[gid] = (a[gid] %s b[gid]) ? 1 : 0;\n}" % (ty, ty, op)))
# float compare producing 0/1
for nm, op in [("fcmp_eq","=="),("fcmp_ne","!="),("fcmp_lt","<"),
               ("fcmp_le","<="),("fcmp_gt",">"),("fcmp_ge",">=")]:
    w(nm, ("kernel void k(device const float *a [[buffer(0)]],\n"
           "              device const float *b [[buffer(1)]],\n"
           "              device int *out [[buffer(2)]],\n"
           "              uint gid [[thread_position_in_grid]]) {\n"
           "    out[gid] = (a[gid] %s b[gid]) ? 1 : 0;\n}" % op))
# compare -> control-flow predicate (0x0a) via early-out select on a scalar
for nm, ty, op in [("pcmp_lt","int","<"),("pcmp_ge","int",">="),
                   ("pcmp_eq","int","=="),("pcmp_ne","int","!=")]:
    w(nm, ("kernel void k(device const %s *a [[buffer(0)]],\n"
           "              device %s *out [[buffer(1)]],\n"
           "              uint gid [[thread_position_in_grid]]) {\n"
           "    %s v = a[gid];\n"
           "    if (v %s 3) { out[gid] = 100; } else { out[gid] = 200; }\n}" % (ty, ty, ty, op)))
# ternary select on compare (produces 0x02 compare + select)
for nm, ty, op in [("sel_lt","float","<"),("sel_gt","float",">")]:
    w(nm, ("kernel void k(device const %s *a [[buffer(0)]],\n"
           "              device const %s *b [[buffer(1)]],\n"
           "              device %s *out [[buffer(2)]],\n"
           "              uint gid [[thread_position_in_grid]]) {\n"
           "    out[gid] = (a[gid] %s b[gid]) ? a[gid] : b[gid];\n}" % (ty, ty, ty, op)))

names = sorted(f[:-6] for f in os.listdir(KD) if f.endswith(".metal"))
print(f"wrote {len(names)} kernels to {KD}")
for n in names:
    print("  ", n)
