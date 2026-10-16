import io

import numpy as np
from flask import Flask, jsonify, render_template, request
from PIL import Image

from algorithms.chi_square import chi_square_attack, summarize_chi_square
from algorithms.rs_analysis import rs_analysis, summarize_rs

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024  # 20 MB

ALLOWED_EXTENSIONS = {"png", "bmp", "tif", "tiff", "jpg", "jpeg"}

CHI_THRESHOLD = 0.5
RS_THRESHOLD_PERCENT = 3.0


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def build_summary(details):
    """
    Grayscale (luminance) adalah sinyal utama: channel warna individual
    (R/G/B) rawan false positive akibat noise sensor/demosaicing kamera,
    sehingga tidak diberi bobot setara. R/G/B hanya dipakai sebagai bukti
    pendukung untuk menaikkan atau melemahkan keyakinan dari Grayscale.
    """
    grayscale = next(d for d in details if d["channel"] == "Grayscale")
    rgb = [d for d in details if d["channel"] != "Grayscale"]

    g_chi = grayscale["chi_square_suspect"]
    g_rs = grayscale["rs_suspect"]

    if g_chi and g_rs:
        verdict = "Terindikasi kuat steganografi LSB"
        confidence = "Tinggi"
    elif g_chi or g_rs:
        verdict = "Terindikasi kemungkinan steganografi LSB"
        confidence = "Sedang"
    else:
        verdict = "Tidak terindikasi steganografi LSB"
        confidence = "Rendah"

    rgb_strong_support = sum(1 for d in rgb if d["chi_square_suspect"] and d["rs_suspect"])
    rgb_any_support = sum(1 for d in rgb if d["chi_square_suspect"] or d["rs_suspect"])

    note = None

    if confidence == "Sedang" and rgb_strong_support >= 2:
        confidence = "Tinggi"
        verdict = "Terindikasi kuat steganografi LSB (didukung channel warna)"
        note = f"{rgb_strong_support} dari 3 channel warna (R/G/B) turut menunjukkan indikasi kuat, memperkuat sinyal dari Grayscale."
    elif confidence == "Rendah" and rgb_any_support > 0:
        note = (
            f"Grayscale bersih, namun {rgb_any_support} dari 3 channel warna (R/G/B) menunjukkan indikasi. "
            "Ini kemungkinan besar noise sensor/demosaicing warna, bukan pesan tersembunyi — "
            "Grayscale tetap jadi acuan utama."
        )
    elif confidence in ("Tinggi", "Sedang") and rgb_any_support == 0:
        note = "Tidak ada channel warna yang mendukung indikasi dari Grayscale. Periksa ulang, atau pesan mungkin hanya disisipkan pada channel luminance."

    return {
        "verdict": verdict,
        "confidence": confidence,
        "note": note,
        "grayscale_chi_suspect": g_chi,
        "grayscale_rs_suspect": g_rs,
        "rgb_strong_support": rgb_strong_support,
        "rgb_any_support": rgb_any_support,
        "details": details,
    }


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    if "image" not in request.files:
        return jsonify({"error": "Tidak ada file yang diunggah."}), 400

    file = request.files["image"]
    if file.filename == "":
        return jsonify({"error": "Nama file kosong."}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "Format file tidak didukung. Gunakan PNG, BMP, TIFF, atau JPG."}), 400

    try:
        img = Image.open(io.BytesIO(file.read())).convert("RGB")
    except Exception:
        return jsonify({"error": "Gagal membaca file sebagai citra."}), 400

    arr = np.array(img)
    height, width = arr.shape[0], arr.shape[1]

    grayscale = np.array(img.convert("L"))

    channels = {
        "Grayscale": grayscale,
        "Red": arr[:, :, 0],
        "Green": arr[:, :, 1],
        "Blue": arr[:, :, 2],
    }

    channel_results = {}
    details = []

    for name, channel in channels.items():
        chi_curve = chi_square_attack(channel)
        chi_summary = summarize_chi_square(chi_curve, threshold=CHI_THRESHOLD)

        rs_result = rs_analysis(channel)
        rs_summary = summarize_rs(rs_result, threshold_percent=RS_THRESHOLD_PERCENT)

        channel_results[name] = {
            "chi_square_curve": chi_curve,
            "chi_square_summary": chi_summary,
            "rs_analysis": rs_result,
            "rs_summary": rs_summary,
        }

        details.append({
            "channel": name,
            "role": "primary" if name == "Grayscale" else "supporting",
            "chi_square_suspect": chi_summary["suspect"],
            "chi_square_early_p_max": chi_summary["early_p_max"],
            "chi_square_estimated_percent": chi_summary["estimated_embedding_percent"],
            "rs_suspect": rs_summary["suspect"],
            "rs_estimated_percent": rs_summary["estimated_embedding_percent"],
            "agreement": chi_summary["suspect"] == rs_summary["suspect"],
        })

    summary = build_summary(details)

    return jsonify({
        "filename": file.filename,
        "width": width,
        "height": height,
        "channels": channel_results,
        "summary": summary,
    })


if __name__ == "__main__":
    app.run(debug=True)
