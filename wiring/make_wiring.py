#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Menghasilkan wiring_diagram.png/.svg/.pdf (tingkat blok + port). Pinout konektor: ambil dari halaman resmi Holybro [CEK]."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle

W, H = 200, 128
fig = plt.figure(figsize=(22, 14))
ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, W); ax.set_ylim(0, H); ax.axis("off")

C = dict(pwr="#c0392b", gnd="#222222", sig="#e67e22", uart="#2471a3", v5="#1e8449", v6="#8e44ad", box="#f4f6f7", edge="#34495e")

def box(x, y, w, h, text, dashed=False, fc=None, fs=8.5, bold=False):
    p = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.2,rounding_size=1.2", fc=fc or C["box"], ec=C["edge"],
                       lw=1.4, ls="--" if dashed else "-")
    ax.add_patch(p)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, fontweight="bold" if bold else "normal", linespacing=1.25)

def wire(pts, color, lw=2.2, ls="-"):
    xs, ys = zip(*pts)
    ax.plot(xs, ys, color=color, lw=lw, ls=ls, solid_capstyle="round", zorder=2)

def label(x, y, t, color="black", fs=7.2, ha="center", rot=0):
    ax.text(x, y, t, color=color, fontsize=fs, ha=ha, va="center", rotation=rot,
            bbox=dict(fc="white", ec="none", pad=0.6, alpha=0.9), zorder=5)

def port(x, y, name, side="left"):
    ax.plot([x], [y], marker="s", ms=6, color=C["edge"], zorder=4)
    ax.text(x + (1.6 if side == "left" else -1.6), y, name, fontsize=7.6, ha="left" if side == "left" else "right", va="center", fontweight="bold")

ax.text(W / 2, 124.5, "Wiring Diagram - Single-EDF Thrust-Vectoring UAV (konfigurasi Baseline-EDF, ArduPilot FRAME_CLASS 8)", ha="center", fontsize=15, fontweight="bold")
ax.text(W / 2, 121.2, "Tingkat blok dan port. Garis putus-putus = komponen opsional / belum disetujui [CEK]. Pinout konektor mengikuti halaman resmi Holybro; verifikasi sebelum membuat kabel.",
        ha="center", fontsize=9, style="italic")

# ---------------- baris daya (atas)
box(4, 106, 26, 12, "Pack A\nOMPHobby 6S 2000 mAh\n(batas isi 25,2 V)")
box(4, 88, 26, 12, "Pack B\nOMPHobby 6S 2000 mAh\n(batas isi 25,2 V)")
box(36, 107, 14, 10, "Sekering A\n[nilai: CEK]", dashed=True)
box(36, 89, 14, 10, "Sekering B\n[nilai: CEK]", dashed=True)
wire([(30, 112), (36, 112)], C["pwr"], 3); wire([(30, 94), (36, 94)], C["pwr"], 3)
wire([(50, 112), (56, 112), (56, 94), (50, 94)], C["pwr"], 3)
ax.plot([56], [103], "o", color=C["pwr"], ms=8, zorder=4)
label(56, 118.3, "Titik paralel\n(samakan tegangan pack\nsebelum menyambung)", fs=6.8)
box(62, 97, 26, 11, "Sensor arus propulsi\nMauch HS-200-LV\n[D5: cara ke Pixhawk = CEK]", dashed=True)
wire([(56, 103), (62, 103)], C["pwr"], 3)
box(94, 97, 22, 11, "PDB / bus daya\n(titik GND bintang)", fs=8.5)
wire([(88, 103), (94, 103)], C["pwr"], 3)
box(124, 97, 24, 11, "ESC (BELUM DISETUJUI)\nsyarat desain: >=155 A kontinu\n(1,25 x 124 A), >=6S [CEK]", dashed=True, fs=8)
wire([(116, 103), (124, 103)], C["pwr"], 4.5)
label(120, 106.2, "AWG8 [HITUNG]", C["pwr"], 7)
box(158, 97, 38, 11, "EDF 90 mm 12 bilah, 1450 KV\n(klaim vendor: 124 A, 25,2 V maks)", fs=8.2)
for dy in (-2, 0, 2):
    wire([(148, 103 + dy), (158, 103 + dy)], "#555555", 1.8)
label(153, 108.6, "3 fasa", fs=7)

# ---------------- bus daya turun
wire([(105, 97), (105, 91), (62, 91), (62, 61)], C["pwr"], 2.6)
label(84, 91, "+Vbat (bus daya)", C["pwr"], 7)
# PM02
box(66, 74, 22, 10, "PM02 V3\n(hanya cabang FC;\nsensing <= 120 A)", fs=7.6)
wire([(62, 79), (66, 79)], C["pwr"], 2.2)
# BEC 6 V
box(66, 56, 22, 10, "BEC 6,0 V (Pololu D36V50F6)\nuntuk rail servo\n[atur 6,0 V, jangan lebih]", dashed=False, fs=7)
wire([(62, 61), (66, 61)], C["pwr"], 2.2)

# ---------------- Pixhawk
box(94, 5, 38, 84, "", fs=9)
ax.add_patch(Rectangle((94, 78), 38, 11, fc="#d6eaf8", ec=C["edge"], lw=1.4))
ax.text(113, 84.2, "Pixhawk 6C Mini", ha="center", fontsize=11, fontweight="bold")
ax.text(113, 80.8, "ArduPilot Copter, FRAME_CLASS 8 (SingleCopter)", ha="center", fontsize=7.4)
# port kiri
port(94, 74, "POWER", "left"); port(94, 61, "SERVO RAIL (+/-)", "left")
port(94, 46, "TELEM1 (SERIAL1)", "left"); port(94, 34, "TELEM2 (SERIAL2)", "left")
port(94, 22, "GPS1 (SERIAL3)", "left"); port(94, 10, "GPS2 (SERIAL4)", "left")
# port kanan
for y, n in ((70, "MAIN OUT 5"), (60, "MAIN OUT 1"), (51, "MAIN OUT 2"), (42, "MAIN OUT 3"), (33, "MAIN OUT 4")):
    port(132, y, n, "right")
# PM02 -> POWER, BEC -> rail
wire([(88, 79), (91, 79), (91, 74), (94, 74)], C["v5"], 2.4)
label(79, 71.2, "5,2 V + sinyal V/I (kabel POWER)", C["v5"], 6.6)
wire([(88, 61), (94, 61)], C["v6"], 2.6)
label(91, 63.6, "6,0 V", C["v6"], 7)
# perangkat kiri-bawah
box(34, 41, 36, 10, "Radio telemetri MAVLink\n(jenis/frekuensi: BELUM dipilih)", dashed=True, fs=7.8)
box(34, 29, 36, 10, "Receiver ELRS RP1\n(CRSF, SERIAL2_PROTOCOL=23)", fs=7.8)
box(34, 17, 36, 10, "GNSS H-RTK F9P Ultralight\n(+ kompas) [pinout kabel: CEK]", fs=7.8)
box(34, 5, 36, 10, "CM4 + carrier (fase swarm)\nPololu D36V50F5 (5 V) [opsional]", dashed=True, fs=7.6)
for y, c, t in ((46, C["uart"], "UART 3,3 V"), (34, C["uart"], "UART 3,3 V (CRSF)"), (22, C["uart"], "UART + safety switch"), (10, C["uart"], "UART (MAVLink 2)")):
    wire([(70, y), (94, y)], c, 2.2, "--" if y == 10 or y == 46 else "-")
    label(82, y + 2.2, t, c, 6.8)
# servo kanan
ys = {"S1 vane DEPAN": 60, "S2 vane KANAN": 51, "S3 vane BELAKANG": 42, "S4 vane KIRI": 33}
for (name, y) in ys.items():
    box(150, y - 3.5, 38, 7, f"{name}\nMG90S 13,4 g", fs=7.6)
    wire([(132, y), (150, y)], C["sig"], 2.2)
label(141, 63.3, "PWM + rail 6 V (header PWM)", C["sig"], 6.6)
# ESC signal
wire([(132, 70), (139, 70), (139, 97)], C["sig"], 2.4)
label(139, 82, "PWM ESC\n1000-2000 us\n+ GND bersama", C["sig"], 6.8)
label(160, 74.5, "JANGAN sambung +5 V BEC ESC ke rail servo", "#c0392b", 7)
# ---------------- catatan & legenda
box(100 + 40, 4, 56, 24, "", fs=8)
ax.text(142, 25.3, "Koreksi dari dokumen awal", fontsize=8.6, fontweight="bold", va="center")
notes = ["1) MAIN 1-4 = vane, MAIN 5 = ESC (bukan MAIN 1 = ESC)",
         "2) ELRS/CRSF ke UART (TELEM2), bukan pin RC IN",
         "3) Hanya 1 port POWER analog: PM02 dan Mauch tidak bisa",
         "    sekaligus -> putuskan D5 (lihat panduan Fase 5)",
         "4) Servo MG90S maks 6,0 V; pack penuh <= 25,2 V",
         "5) Dua pack 6S paralel BUKAN 12S; monitor per pack"]
for i, t in enumerate(notes):
    ax.text(142, 21.8 - i * 2.9, t, fontsize=7.1, va="center")
# legenda
ax.add_patch(Rectangle((2, 56), 26, 24, fc="white", ec=C["edge"], lw=1))
ax.text(15, 78, "Legenda", ha="center", fontsize=8.4, fontweight="bold")
for i, (c, t) in enumerate(((C["pwr"], "daya baterai (6S)"), (C["v6"], "6,0 V servo"), (C["v5"], "5 V / 5,2 V"),
                            (C["sig"], "sinyal PWM"), (C["uart"], "UART 3,3 V"), (C["gnd"], "GND: bintang di PDB"))):
    ax.plot([4, 10], [74 - i * 3.2] * 2, color=c, lw=3)
    ax.text(12, 74 - i * 3.2, t, fontsize=7.4, va="center")
ax.text(4, 53, "Garis putus-putus pada kotak =\nopsional / belum disetujui", fontsize=7, va="center")

fig.savefig("wiring_diagram.png", dpi=150)
fig.savefig("wiring_diagram.svg")
fig.savefig("wiring_diagram.pdf")
print("ok")
