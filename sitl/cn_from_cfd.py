#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cn_from_cfd.py - Ubah tabel CFD vane (Fase 3) menjadi cn_table di vehicle.json.

Masukan CSV (satu vane diuji sendirian), kolom wajib:
    alpha_deg, thrust_N, force_side_N
  force_side_N = gaya samping pada vane itu (N), positif untuk alpha positif.
Definisi: CN = F / (q * S), q = T / (2 * A)  (sama dengan yang dipakai physics_backend.py).
Pemakaian:  python3 cn_from_cfd.py ../data/cfd_vane_table.csv --vehicle vehicle.json
"""
import argparse
import csv
import json
import math
from collections import defaultdict


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--vehicle", default="vehicle.json")
    a = ap.parse_args()
    with open(a.vehicle, encoding="utf-8") as f:
        veh = json.load(f)
    S = veh["vane_span_m"] * veh["vane_chord_m"]
    A = veh["fan_area_m2"]
    acc = defaultdict(list)
    with open(a.csv, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            al, T, F = float(r["alpha_deg"]), float(r["thrust_N"]), float(r["force_side_N"])
            if T <= 0:
                continue
            q = T / (2 * A)
            acc[round(abs(al), 3)].append(math.copysign(1, al if al else 1) * F / (q * S))
    pts = {0.0: 0.0}
    for al, vals in acc.items():
        if al > 0:
            pts[al] = sum(vals) / len(vals)
    xs = sorted(pts)
    cn = [pts[x] for x in xs]
    veh["cn_table"] = {"alpha_deg": xs, "cn": cn}
    # estimasi alpha_stall: kemiringan turun > 50% dari kemiringan awal
    if len(xs) >= 3:
        s0 = (cn[1] - cn[0]) / (xs[1] - xs[0])
        for i in range(2, len(xs)):
            s = (cn[i] - cn[i - 1]) / (xs[i] - xs[i - 1])
            if s < 0.5 * s0:
                veh["vane_stall_deg"] = xs[i - 1]
                print(f"alpha_stall (kemiringan turun >50%): {xs[i-1]} deg")
                break
    with open(a.vehicle, "w", encoding="utf-8") as f:
        json.dump(veh, f, indent=2, ensure_ascii=False)
    print("cn_table ditulis:", list(zip(xs, [round(c, 4) for c in cn])))


if __name__ == "__main__":
    main()
