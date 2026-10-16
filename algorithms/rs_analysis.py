"""
RS Analysis (Fridrich, Goljan, Du, 2001) untuk deteksi LSB steganography.

Prinsip: citra dibagi menjadi grup-grup piksel. Sebuah mask M menentukan,
untuk setiap posisi dalam grup, apakah posisi tersebut di-flip dengan F1
(LSB flip biasa), F-1 (shifted flip), atau dibiarkan (F0/identity). Setiap
grup diklasifikasikan sebagai Regular (R) jika flipping menambah noise
lokal (fungsi diskriminasi naik), Singular (S) jika menurunkan noise, atau
Unusable (U) jika sama.

Pada citra alami, R_M ~ R_(-M) dan S_M ~ S_(-M). Penyisipan LSB acak
merusak simetri ini secara proporsional terhadap panjang pesan. Estimasi
panjang pesan (p) diperoleh dengan mengukur (RM-SM) dan (R-M - S-M) pada
citra asli (titik x, fraksi LSB yang berubah) dan pada citra yang seluruh
LSB-nya dibalik (yang secara statistik setara dengan titik 1-x), lalu
menyelesaikan solusi tertutup untuk x dari model kuadrat-simetris Fridrich.
"""

import numpy as np

# Mask standar: separuh posisi dalam grup di-flip (+1), separuh dibiarkan (0).
DEFAULT_MASK = np.array([1, 0, 1, 0], dtype=np.int8)


def _discrimination(groups):
    # f(G) = sum |x_i - x_(i+1)| dalam setiap grup
    diffs = np.diff(groups.astype(np.int64), axis=1)
    return np.sum(np.abs(diffs), axis=1)


def _flip_plus_scalar(x):
    # F1: LSB flip standar -> 0<->1, 2<->3, ..., 254<->255
    return x ^ 1


def _flip_minus_scalar(x):
    # F-1: shifted LSB flip -> -1<->0, 1<->2, 3<->4, ..., 255<->256 (clamped)
    x = x.astype(np.int64)
    even_mask = (x % 2 == 0)
    odd_mask = ~even_mask

    result = x.copy()
    can_dec = even_mask & (x > 0)
    can_inc = odd_mask & (x < 255)
    result[can_dec] = x[can_dec] - 1
    result[can_inc] = x[can_inc] + 1
    return result


def _apply_mask(groups, mask_vec):
    """Terapkan F1 pada posisi mask=+1, F-1 pada posisi mask=-1, identitas pada mask=0."""
    result = groups.copy()
    for pos, m in enumerate(mask_vec):
        col = groups[:, pos]
        if m == 1:
            result[:, pos] = _flip_plus_scalar(col)
        elif m == -1:
            result[:, pos] = _flip_minus_scalar(col)
    return result


def _rs_counts(groups, mask_vec):
    f_orig = _discrimination(groups)
    f_pos = _discrimination(_apply_mask(groups, mask_vec))
    f_neg = _discrimination(_apply_mask(groups, -mask_vec))

    total = len(groups)
    if total == 0:
        return 0.0, 0.0, 0.0, 0.0

    r_m = np.sum(f_pos > f_orig) / total
    s_m = np.sum(f_pos < f_orig) / total
    r_nm = np.sum(f_neg > f_orig) / total
    s_nm = np.sum(f_neg < f_orig) / total
    return float(r_m), float(s_m), float(r_nm), float(s_nm)


def rs_analysis(channel, group_size=4, mask_vec=None):
    """
    Menjalankan RS analysis pada satu channel citra (2D numpy array uint8).

    Mengembalikan dict berisi RM, SM, R-M, S-M (dalam persen jumlah grup)
    serta estimated_embedding_rate (perkiraan persentase piksel yang
    disisipi pesan LSB).
    """
    if mask_vec is None:
        mask_vec = DEFAULT_MASK[:group_size] if group_size <= 4 else np.resize(DEFAULT_MASK, group_size)

    flat = channel.flatten().astype(np.int64)
    n = flat.size
    n_groups = n // group_size

    if n_groups < 10:
        return {
            "RM": 0.0, "SM": 0.0, "R_minus_M": 0.0, "S_minus_M": 0.0,
            "RM_bar": 0.0, "SM_bar": 0.0,
            "estimated_embedding_rate": 0.0,
        }

    groups = flat[: n_groups * group_size].reshape(n_groups, group_size)

    r_m, s_m, r_nm, s_nm = _rs_counts(groups, mask_vec)

    # Flip seluruh LSB citra (simulasi F1 pada seluruh piksel), lalu hitung
    # ulang RS (dengan mask yang sama) pada citra yang sudah di-flip ini.
    flipped_groups = _flip_plus_scalar(groups)
    r_m_bar, s_m_bar, r_nm_bar, s_nm_bar = _rs_counts(flipped_groups, mask_vec)

    d0 = r_m - s_m
    d1 = r_nm - s_nm
    d0_bar = r_m_bar - s_m_bar
    d1_bar = r_nm_bar - s_nm_bar

    # Model: (RM-SM)(x) = a*x^2 + b*x + c, (R-M-S-M)(x) = a*x^2 - b*x + c,
    # dengan x = fraksi LSB yang benar-benar berubah akibat penyisipan.
    # Mengukur pada citra asli (titik x) dan pada citra dengan seluruh LSB
    # dibalik (titik 1-x) menghasilkan solusi tertutup untuk x:
    #   x = (d0 - d1) / ((d0_bar - d1_bar) + (d0 - d1))
    # Panjang pesan relatif (asumsi bit pesan acak, separuh LSB berubah)
    # adalah p = 2x.
    denom = (d0_bar - d1_bar) + (d0 - d1)
    if abs(denom) < 1e-9:
        x = 0.0
    else:
        x = (d0 - d1) / denom

    p_estimate = max(0.0, min(1.0, abs(2.0 * x)))

    return {
        "RM": round(r_m * 100, 3),
        "SM": round(s_m * 100, 3),
        "R_minus_M": round(r_nm * 100, 3),
        "S_minus_M": round(s_nm * 100, 3),
        "RM_bar": round(r_m_bar * 100, 3),
        "SM_bar": round(s_m_bar * 100, 3),
        "estimated_embedding_rate": round(p_estimate * 100, 3),
    }


def summarize_rs(rs_result, threshold_percent=3.0):
    rate = rs_result.get("estimated_embedding_rate", 0.0)
    return {
        "estimated_embedding_percent": rate,
        "suspect": bool(rate > threshold_percent),
    }
