#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
selftest.py - Menguji physics_backend.py TANPA ArduPilot (ArduPilot palsu lewat UDP loopback).

Yang diuji (semua harus PASS sebelum dipakai dengan ArduPilot sungguhan):
  T1  protokol UDP/JSON: paket 16 dan 32 kanal, field balasan, kenaikan timestamp
  T2  diam di tanah: accel_body = [0,0,-g], posisi 0
  T3  jatuh bebas: v = g*t (tanpa hambatan)
  T4  konvensi geometri vane (tanda momen roll/pitch/yaw)
  T5  hover loop tertutup: lepas landas ke 5 m, sikap < 1 derajat
  T6  autosign: memulihkan servo_sign & yaw_dir tersembunyi pada 6 kombinasi acak
  T7  kontrol negatif: tanda yang salah harus membuat sikap divergen (uji sensitivitas)
  T8  kecepatan: mikrodetik per langkah fisika

Catatan jujur: self-test ini membuktikan backend konsisten secara internal. Ia BELUM membuktikan
integrasi dengan ArduPilot; itu dilakukan lewat skenario T1-T9 di panduan (Fase 7).
"""
import copy
import json
import math
import os
import random
import socket
import struct
import sys
import threading
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import physics_backend as pb  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
VEH = os.path.join(HERE, "vehicle.json")
results = []


def check(name, ok, detail=""):
    results.append((name, ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {detail}")


def make_cfg(**over):
    cfg = pb.Config(VEH)
    for k, v in over.items():
        setattr(cfg, k, v)
    return cfg


def rebuild_pos(cfg):
    rv = cfg.yaw_dir * cfg.rv
    cfg.vane_pos = [np.array([rv, 0, cfg.L]), np.array([0, rv, cfg.L]),
                    np.array([-rv, 0, cfg.L]), np.array([0, -rv, cfg.L])]


class FakeAP:
    """Pengendali palsu = invers eksak plant dengan tautan fisik (s_true, yaw_true) tersembunyi."""

    def __init__(self, cfg, s_true, yaw_true, h_target=5.0, armed=True, wn=6.0):
        self.c = cfg
        self.s = s_true
        self.yaw_true = yaw_true
        self.h_t = h_target
        self.armed = armed
        Ixx, Iyy, Izz = cfg.I[0, 0], cfg.I[1, 1], cfg.I[2, 2]
        self.kp = np.array([Ixx, Iyy, Izz]) * wn ** 2
        self.kd = np.array([Ixx, Iyy, Izz]) * 2 * 0.9 * wn

    def command(self, state, pwm5_override=None):
        c = self.c
        q = np.array(state["quaternion"])
        gyro = np.array(state["imu"]["gyro"])
        h = -state["position"][2]
        vz = -state["velocity"][2]
        roll, pitch, yaw = pb.euler_from_quat(q)
        a_dem = 2.0 * (self.h_t - h) - 2.5 * vz
        T_dem = pb.clamp(c.m * (pb.G + a_dem), 0.0, c.Tmax)
        u = math.sqrt(T_dem / c.Tmax)
        pwm5 = 1000 + 1000 * u if self.armed else 1000
        if pwm5_override is not None:
            pwm5 = pwm5_override
        Mx = -self.kp[0] * roll - self.kd[0] * gyro[0]
        My = -self.kp[1] * pitch - self.kd[1] * gyro[1]
        Mz = -self.kp[2] * math.atan2(math.sin(yaw), math.cos(yaw)) - self.kd[2] * gyro[2]
        T_eff = max(T_dem, 0.3 * c.m * pb.G)
        qd = T_eff / (2 * c.A)
        kv = c.L * qd * c.S * c.cna  # N.m per rad per vane
        kz = c.rv * qd * c.S * c.cna
        d = [-Mx / (2 * kv), -My / (2 * kv), Mx / (2 * kv), My / (2 * kv)]  # depan, kanan, belakang, kiri
        dz = self.yaw_true * Mz / (4 * kz)
        pwm = [1500.0] * 16
        for i in range(4):
            deg = math.degrees(d[i] + dz)
            pwm[i] = c.trim[i] + self.s[i] * deg / c.full_scale * ((c.pwm_max - c.pwm_min) / 2)
        pwm[4] = pwm5
        return [int(round(x)) for x in pwm]


def initial_state():
    return {"quaternion": [1, 0, 0, 0], "imu": {"gyro": [0, 0, 0], "accel_body": [0, 0, -pb.G]},
            "position": [0, 0, 0], "velocity": [0, 0, 0]}


def run_loop(cfg, ap, seconds, mode="normal", rate=1200, pwm5_override=None, record=False):
    be = pb.Backend(cfg, mode=mode)
    st = initial_state()
    dt = 1.0 / rate
    hist = []
    for k in range(int(seconds * rate)):
        pwm = ap.command(st, pwm5_override)
        st = be.handle(pwm=pwm, dt=dt)
        if record and k % 12 == 0:
            r, p, y = pb.euler_from_quat(st["quaternion"])
            hist.append((be.t, -st["position"][2], math.degrees(r), math.degrees(p), math.degrees(y)))
    return be, st, hist


# ---------------------------------------------------------------- T1
def t1_protocol():
    cfg = make_cfg()
    be = pb.Backend(cfg)
    stop = threading.Event()
    port = 19002
    th = threading.Thread(target=pb.serve, args=(be, port, "127.0.0.1", stop), daemon=True)
    th.start()
    time.sleep(0.3)
    cli = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    cli.settimeout(2.0)
    ok_fields, ts = True, []
    for n in range(5):
        pkt = pb.HDR.pack(pb.MAGIC16, 1200, n) + struct.pack("<16H", *([1000] * 16))
        cli.sendto(pkt, ("127.0.0.1", port))
        data, _ = cli.recvfrom(4096)
        txt = data.decode("ascii")
        ok_fields &= txt.startswith("\n") and txt.endswith("\n")
        j = json.loads(txt)
        for key in ("timestamp", "imu", "position", "velocity", "quaternion"):
            ok_fields &= key in j
        ok_fields &= len(j["imu"]["gyro"]) == 3 and len(j["imu"]["accel_body"]) == 3 and len(j["quaternion"]) == 4
        ts.append(j["timestamp"])
    d = np.diff(ts)
    check("T1a protokol 16 kanal: field & newline", ok_fields)
    check("T1b timestamp naik 1/1200 s per paket", np.allclose(d, 1 / 1200, atol=1e-9), f"(dt={d[0]:.6f})")
    pkt32 = pb.HDR.pack(pb.MAGIC32, 1200, 99) + struct.pack("<32H", *([1000] * 32))
    cli.sendto(pkt32, ("127.0.0.1", port))
    data, _ = cli.recvfrom(4096)
    check("T1c paket 32 kanal diterima", "quaternion" in json.loads(data.decode("ascii")))
    cli.sendto(b"\x00\x01garbage", ("127.0.0.1", port))
    cli.settimeout(0.4)
    try:
        cli.recvfrom(4096)
        got = True
    except socket.timeout:
        got = False
    check("T1d paket sampah diabaikan", not got)
    cli.close()
    stop.set()
    th.join(timeout=2)


# ---------------------------------------------------------------- T2/T3
def t2_ground_and_fall():
    cfg = make_cfg()
    be = pb.Backend(cfg)
    st = None
    for _ in range(1200):
        st = be.handle(pwm=[1500] * 4 + [1000], dt=1 / 1200)
    acc = np.array(st["imu"]["accel_body"])
    check("T2 diam di tanah: accel_body=[0,0,-g]", np.allclose(acc, [0, 0, -pb.G], atol=1e-9) and st["position"] == [0, 0, 0],
          f"(acc={acc.round(4).tolist()})")
    cfg = make_cfg(cda=np.zeros(3), rot_damp=0.0)
    be = pb.Backend(cfg, pos=(0, 0, -100.0))
    for _ in range(1200):
        st = be.handle(pwm=[1500] * 4 + [1000], dt=1 / 1200)
    vD = st["velocity"][2]
    pD = st["position"][2]
    check("T3 jatuh bebas 1 s: v=g*t, jarak ~ g t^2/2", abs(vD - pb.G) < 1e-6 and abs((pD + 100) - pb.G / 2) < 0.01,
          f"(v={vD:.6f}, dz={pD + 100:.4f})")
    acc = np.array(st["imu"]["accel_body"])
    check("T3b jatuh bebas: IMU membaca ~0 (gaya spesifik)", np.allclose(acc, 0, atol=1e-6))


# ---------------------------------------------------------------- T4
def t4_geometry():
    cfg = make_cfg(q0=0.0, rot_damp=0.0, cda=np.zeros(3))

    def alpha_after(pwm_dev):
        be = pb.Backend(cfg, pos=(0, 0, -50.0))
        be.veh.T = 19.61
        for _ in range(60):
            be.veh.T = 19.61  # tahan thrust konstan, uji hanya vane
            be.handle(pwm=[1500 + d for d in pwm_dev] + [1727], dt=1 / 1200)
        return be.veh.w.copy()

    w_f = alpha_after([100, 0, 0, 0])
    w_b = alpha_after([0, 0, 100, 0])
    w_r = alpha_after([0, 100, 0, 0])
    w_l = alpha_after([0, 0, 0, 100])
    w_all = alpha_after([100, 100, 100, 100])
    ok = (w_f[0] < 0 and w_b[0] > 0 and w_r[1] < 0 and w_l[1] > 0 and w_all[2] > 0)
    check("T4a tanda momen: depan+ -> roll(-), belakang+ -> roll(+), kanan+ -> pitch(-), kiri+ -> pitch(+), semua+ -> yaw(+)", ok,
          f"(wx_f={w_f[0]:+.3f}, wx_b={w_b[0]:+.3f}, wy_r={w_r[1]:+.3f}, wy_l={w_l[1]:+.3f}, wz_all={w_all[2]:+.3f})")
    pair_roll = alpha_after([100, 0, -100, 0])
    check("T4b roll murni: depan+/belakang- tanpa yaw (selisih lengan radial saling meniadakan)",
          pair_roll[0] < 0 and abs(pair_roll[2]) < 1e-3 * abs(pair_roll[0]), f"(wx={pair_roll[0]:+.3f}, wz={pair_roll[2]:+.2e})")
    # besaran: momen per derajat pada thrust hover dibandingkan hitungan tangan
    be = pb.Backend(cfg, pos=(0, 0, -50.0))
    be.veh.T = 19.61
    be.veh.delta = [5.0, 0, 0, 0]
    q = be.veh.T / (2 * cfg.A)
    Fy = q * cfg.S * cfg.cna * math.radians(5.0)
    Mx_hand = -cfg.L * Fy
    M = np.cross(cfg.vane_pos[0], Fy * cfg.vane_dir[0])
    check("T4c besaran momen vane = hitungan tangan", abs(M[0] - Mx_hand) < 1e-12, f"(Mx={M[0]:+.5f} N.m)")


# ---------------------------------------------------------------- T5
def t5_hover():
    cfg = make_cfg()
    ap = FakeAP(cfg, [1, 1, 1, 1], 1)
    be, st, hist = run_loop(cfg, ap, 25.0, record=True)
    h = -st["position"][2]
    late = [x for x in hist if x[0] > 18]
    max_att = max(max(abs(x[2]), abs(x[3])) for x in late)
    check("T5a hover: mencapai 5 m", abs(h - 5.0) < 0.15, f"(h={h:.3f} m)")
    check("T5b hover: roll/pitch < 1 deg di 7 s terakhir", max_att < 1.0, f"(maks={max_att:.3f} deg)")
    # gangguan: dorong sikap awal 4 deg lalu pulih
    be = pb.Backend(cfg, pos=(0, 0, -5.0))
    be.veh.q = pb.quat_from_euler(math.radians(4), math.radians(-3), 0.0)
    be.veh.T = cfg.m * pb.G
    st = initial_state()
    st["position"] = [0, 0, -5.0]
    ap2 = FakeAP(cfg, [1, 1, 1, 1], 1)
    worst_late = 0
    for k in range(int(10 * 1200)):
        pwm = ap2.command(st)
        st = be.handle(pwm=pwm, dt=1 / 1200)
        if k > 7 * 1200:
            r, p, y = pb.euler_from_quat(st["quaternion"])
            worst_late = max(worst_late, abs(math.degrees(r)), abs(math.degrees(p)))
    check("T5c pulih dari gangguan sikap 4/-3 deg (< 0.5 deg setelah 7 s)", worst_late < 0.5, f"(sisa={worst_late:.3f} deg)")


# ---------------------------------------------------------------- T6 / T7
def run_autosign(s_true, yaw_true):
    cfg = make_cfg()
    be = pb.Backend(cfg, mode="autosign")
    ap = FakeAP(cfg, s_true, yaw_true, armed=True)
    st = initial_state()
    dt = 1 / 1200
    k = 0
    while not be.auto.done and k < 60 * 1200:
        pwm = ap.command(st, pwm5_override=1500)
        st = be.handle(pwm=pwm, dt=dt)
        k += 1
    return be.auto.result


def t6_autosign():
    rnd = random.Random(20261031)
    all_ok = True
    detail = []
    for trial in range(6):
        s_true = [rnd.choice([-1, 1]) for _ in range(4)]
        yaw_true = rnd.choice([-1, 1])
        res = run_autosign(s_true, yaw_true)
        ok = res is not None and res["servo_sign"] == s_true and res["yaw_dir"] == yaw_true
        all_ok &= ok
        detail.append(f"{s_true}/{yaw_true}->{res['servo_sign'] if res else None}/{res['yaw_dir'] if res else None}")
        # loop tertutup dengan hasil pulihan harus stabil
        if res:
            cfg = make_cfg(sign=res["servo_sign"], yaw_dir=res["yaw_dir"])
            rebuild_pos(cfg)
            ap = FakeAP(cfg, s_true, yaw_true)
            be, st, hist = run_loop(cfg, ap, 15.0, record=True)
            late = [x for x in hist if x[0] > 10]
            all_ok &= max(max(abs(x[2]), abs(x[3])) for x in late) < 1.0
    check("T6 autosign memulihkan tanda tersembunyi (6 kombinasi acak) + loop tertutup stabil", all_ok)
    print("      " + " | ".join(detail))


def t7_negative_control():
    cfg = make_cfg(sign=[-1, 1, 1, 1])  # satu tanda salah
    ap = FakeAP(cfg, [1, 1, 1, 1], 1)
    be = pb.Backend(cfg, pos=(0, 0, -5.0))
    be.veh.q = pb.quat_from_euler(math.radians(3), 0, 0)
    be.veh.T = cfg.m * pb.G
    st = initial_state()
    st["position"] = [0, 0, -5.0]
    worst = 0
    for k in range(int(6 * 1200)):
        st = be.handle(pwm=ap.command(st), dt=1 / 1200)
        r, p, y = pb.euler_from_quat(st["quaternion"])
        worst = max(worst, abs(math.degrees(r)), abs(math.degrees(p)))
    check("T7 kontrol negatif: tanda salah -> sikap divergen (> 20 deg)", worst > 20.0, f"(maks={worst:.1f} deg)")


# ---------------------------------------------------------------- T8
def t8_speed():
    cfg = make_cfg()
    be = pb.Backend(cfg, pos=(0, 0, -5.0))
    be.veh.T = cfg.m * pb.G
    t0 = time.perf_counter()
    n = 6000
    for _ in range(n):
        be.handle(pwm=[1500, 1500, 1500, 1500, 1727], dt=1 / 1200)
    us = (time.perf_counter() - t0) / n * 1e6
    check("T8 kecepatan: < 400 us/langkah (real-time pada 1200 Hz butuh < 833 us)", us < 400, f"({us:.0f} us/langkah)")


if __name__ == "__main__":
    print("Self-test physics_backend.py\n" + "-" * 60)
    t1_protocol()
    t2_ground_and_fall()
    t4_geometry()
    t5_hover()
    t6_autosign()
    t7_negative_control()
    t8_speed()
    print("-" * 60)
    bad = [n for n, ok in results if not ok]
    print(f"{len(results) - len(bad)}/{len(results)} lulus")
    sys.exit(1 if bad else 0)
