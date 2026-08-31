#!/usr/bin/env python3
"""EXP-0219 GATE C predictor for the `imad` arms.

Frozen BEFORE any dispatch.  Every competing model of the addend `A` is written
here; the run driver records, per case, the model-independent product `P`, the
predicted destination under every model whose value is computable WITHOUT the
GPU, and the pre-stated fitting rule for the ones that are not.

THE ONE FITTED PARAMETER, DECLARED IN ADVANCE.  The external file `FILE[j]`
(j = 0..31) is *defined* as the addend recovered from arm `cross`, byte+9 =
0x2e, byte+8 = 0xd0, K = j, SEED SET 1, run01 ONLY.  Everything else in this
experiment is scored HELD OUT against it: the other 15 byte+9 values, seed set
2, run02, both carriers' `b8imm` arms, and every 32-bit fetch.

  dest = m * P + A            m = 1 if (b7 & 3) == 0 else 0
                              P = SEED[b5 >> 2] * SEED[b6 >> 3]   (32-bit wrap)

Models of A:
  M_IMM8        A = ((b8 & 7) << 5) | ((b7 >> 3) & 0x1f)          no fit
  M_K5          A = (b7 >> 3) & 0x1f                              no fit
  M_F16_K5      A = FILE[K]        if (b8 & 7) == 0 else 0        fitted table
  M_F16_K8      A = FILE[K | (b8 & 7) << 5]                       fitted table
  M_F32_PAIR    A = FILE[i] | FILE[i+1] << 16                     fitted table
  M_F32_WORD    A = FILE[i & ~1] | FILE[(i & ~1) + 1] << 16       fitted table
  M_ZERO        A = 0                                             no fit
  M_CONST       A = the anchor's own addend                       fitted scalar

Selectors (which branch of the two-mode model applies):
  S_BIT3   sel = (b9 >> 3) & 1      S_BIT1   sel = (b9 >> 1) & 1
  S_AND    sel = ((b9 >> 3) & 1) & ((b9 >> 1) & 1)
  S_OR     sel = ((b9 >> 3) & 1) | ((b9 >> 1) & 1)
  sel == 0 -> immediate branch (M_IMM8); sel == 1 -> fetch branch
  width: (b9 & 1) == 0 -> 16-bit half, == 1 -> 32-bit word

Outcome buckets this predictor must distinguish (RE_EXPERIMENT_PROCESS_CORRECTIONS
Gate C): correct value / a different but coherent value / silent zero or
no-write (poison) / rejected-faulted-hung / invalid measurement.
"""
M32 = 0xFFFFFFFF


def product(seed_tab, b5, b6):
    """P = SEED[b5>>2] * SEED[b6>>3]; byte+6 bit 0 forces that source to 0."""
    a = seed_tab.get((b5 >> 2) & 0x1F, 0)
    b = 0 if (b6 & 1) else seed_tab.get((b6 >> 3) & 0x1F, 0)
    return (a * b) & M32


def m_of(b7):
    mode = b7 & 3
    if mode == 3:
        return None                     # documented reproducible fault
    return 1 if mode == 0 else 0


def dest(P, m, A):
    return ((m * P) + A) & M32


def imm8(b7, b8):
    return (((b8 & 7) << 5) | ((b7 >> 3) & 0x1F)) & 0xFF


def k5(b7):
    return (b7 >> 3) & 0x1F


def sel_bit3(b9):
    return (b9 >> 3) & 1


def sel_bit1(b9):
    return (b9 >> 1) & 1


def width32(b9):
    return b9 & 1


def fetch_index_5(b7, b8):
    return k5(b7)


def fetch_index_8(b7, b8):
    return k5(b7) | ((b8 & 7) << 5)


def file_get(FILE, j):
    return FILE.get(j, 0) if isinstance(FILE, dict) else (
        FILE[j] if 0 <= j < len(FILE) else 0)


def A_models(b7, b8, b9, FILE=None):
    """Every model's A.  Fitted models return None when FILE is not supplied."""
    out = {"M_IMM8": imm8(b7, b8), "M_K5": k5(b7), "M_ZERO": 0}
    if FILE is None:
        return out
    i5, i8 = fetch_index_5(b7, b8), fetch_index_8(b7, b8)
    out["M_F16_K5"] = file_get(FILE, i5) if (b8 & 7) == 0 else 0
    out["M_F16_K8"] = file_get(FILE, i8)
    for nm, i in (("5", i5), ("8", i8)):
        out["M_F32_PAIR_K" + nm] = (file_get(FILE, i)
                                    | (file_get(FILE, i + 1) << 16)) & M32
        j = i & ~1
        out["M_F32_WORD_K" + nm] = (file_get(FILE, j)
                                    | (file_get(FILE, j + 1) << 16)) & M32
    return out


def unified(b7, b8, b9, FILE, selector="bit3", index="5"):
    """The two-mode model: immediate when sel == 0, external fetch when 1."""
    sel = sel_bit3(b9) if selector == "bit3" else (
        sel_bit1(b9) if selector == "bit1" else (
            (sel_bit3(b9) & sel_bit1(b9)) if selector == "and"
            else (sel_bit3(b9) | sel_bit1(b9))))
    if sel == 0:
        return imm8(b7, b8)
    i = fetch_index_5(b7, b8) if index == "5" else fetch_index_8(b7, b8)
    if index == "5" and (b8 & 7) != 0:
        return 0
    if width32(b9):
        return (file_get(FILE, i) | (file_get(FILE, i + 1) << 16)) & M32
    return file_get(FILE, i)
