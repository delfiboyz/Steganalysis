"""
Chi-Square Attack (Westfeld, 2001) untuk deteksi LSB steganography.

Prinsip: penyisipan LSB sekuensial menyamakan frekuensi pasangan nilai
(2k, 2k+1) dalam histogram citra. Uji chi-square dilakukan secara
bertahap (sliding sample size) dari awal citra untuk mengestimasi
seberapa besar bagian citra yang kemungkinan berisi pesan tersembunyi.
"""

import numpy as np
from scipy import stats


def chi_square_attack(channel, step_percent=5):
    """
    Menjalankan chi-square attack pada satu channel citra (2D numpy array uint8).

    Mengembalikan list of dict: {"sample_percentage": float, "p_value": float, "chi_square": float}
    p_value mendekati 1 -> pola histogram sangat konsisten dengan penyisipan LSB acak
    p_value mendekati 0 -> pola histogram konsisten dengan citra alami (belum disisipi)
    """
    flat = channel.flatten().astype(np.int64)
    n = flat.size

    results = []
    step = max(1, step_percent)
    percentages = list(range(step, 101, step))

    for pct in percentages:
        sample_n = int(n * pct / 100.0)
        if sample_n < 256:
            continue

        sample = flat[:sample_n]
        hist = np.bincount(sample, minlength=256)[:256].astype(np.float64)

        observed_even = hist[0::2]
        observed_odd = hist[1::2]
        expected = (observed_even + observed_odd) / 2.0

        valid = expected > 0
        if not np.any(valid):
            continue

        chi2 = np.sum(((observed_even[valid] - expected[valid]) ** 2) / expected[valid])
        dof = int(np.sum(valid)) - 1

        if dof > 0:
            p_value = float(1.0 - stats.chi2.cdf(chi2, dof))
        else:
            p_value = 0.0

        results.append({
            "sample_percentage": pct,
            "chi_square": round(float(chi2), 4),
            "p_value": round(p_value, 6),
        })

    return results


def summarize_chi_square(results, early_cutoff_percent=20, threshold=0.5):
    """
    Mengambil kesimpulan ringkas dari kurva p-value chi-square.

    - early_p_max: p-value maksimum pada bagian awal citra (indikasi kuat
      jika pesan disisipkan sekuensial dari awal file).
    - estimated_embedding_percent: perkiraan proporsi citra yang berisi
      pesan, diambil dari titik terakhir dimana p-value masih di atas
      threshold sebelum turun drastis.
    """
    if not results:
        return {
            "early_p_max": 0.0,
            "estimated_embedding_percent": 0.0,
            "suspect": False,
        }

    early_vals = [r["p_value"] for r in results if r["sample_percentage"] <= early_cutoff_percent]
    early_p_max = max(early_vals) if early_vals else results[0]["p_value"]

    estimated_embedding_percent = 0.0
    for r in results:
        if r["p_value"] > threshold:
            estimated_embedding_percent = r["sample_percentage"]
        else:
            break

    suspect = early_p_max > threshold

    return {
        "early_p_max": round(early_p_max, 6),
        "estimated_embedding_percent": estimated_embedding_percent,
        "suspect": bool(suspect),
    }
