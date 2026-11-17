#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
physics_backend.py - Backend fisika (JSON interface) ArduPilot SITL
Kendaraan: Single-EDF + 4 vane (ArduPilot FRAME_CLASS 8, SingleCopter)

Protokol (diverifikasi ke sumber ArduPilot, lihat README_SITL.md):
  ArduPilot -> backend (UDP port 9002, little-endian):
      uint16 magic=18458 | uint16 frame_rate | uint32 frame_count | uint16 pwm[16]
      (varian 32 kanal: magic=29569, pwm[32])
  backend -> ArduPilot (UDP, ke alamat pengirim): teks JSON diapit newline:
      \n{"timestamp":s,"imu":{"gyro":[..],"accel_body":[..]},
         "position":[N,E,D],"velocity":[N,E,D],"quaternion":[w,x,y,z]}\n

Konvensi: dunia NED, badan FRD (x depan, y kanan, z bawah). Sumbu z badan = sumbu EDF,
thrust bekerja ke arah -z. Quaternion = rotasi badan -> NED.
Pemetaan servo: output ArduPilot 1..4 = vane depan, kanan, belakang, kiri; output 5 = ESC.

Konvensi vane (defleksi positif d_i, gaya pada kendaraan):
   depan  : +y     kanan : -x     belakang : -y     kiri : +x
   -> d_i positif pada keempat vane menghasilkan momen yaw POSITIF (searah jarum jam dari atas).
   -> depan+/belakang- = momen roll negatif; kanan+/kiri- = momen pitch negatif.

PERINGATAN: parameter di vehicle.json masih PLACEHOLDER sampai diganti data CAD/CFD.
Mode:
   normal   : dinamika penuh
   freeze   : kendaraan diam, hanya memantau PWM (uji bangku / cek wiring)
   autosign : kendaraan diam, sikap diprogram bergantian roll/pitch/yaw; menghitung servo_sign & yaw_dir
"""
import argparse
import json
import math
import os
import socket
import struct
import sys
import time

import numpy as np

G = 9.80665
MAGIC16, MAGIC32 = 18458, 29569
HDR = struct.Struct("<HHI")


def clamp(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


def quat_mul(a, b):
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return np.array([aw * bw - ax * bx - ay * by - az * bz,
                     aw * bx + ax * bw + ay * bz - az * by,
                     aw * by - ax * bz + ay * bw + az * bx,
                     aw * bz + ax * by - ay * bx + az * bw])


def quat_to_dcm(q):
    w, x, y, z = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
                     [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
                     [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)]])


def quat_from_euler(roll, pitch, yaw):
    cr, sr = math.cos(roll / 2), math.sin(roll / 2)
    cp, sp = math.cos(pitch / 2), math.sin(pitch / 2)
    cy, sy = math.cos(yaw / 2), math.sin(yaw / 2)
    return np.array([cr * cp * cy + sr * sp * sy,
                     sr * cp * cy - cr * sp * sy,
                     cr * sp * cy + sr * cp * sy,
                     cr * cp * sy - sr * sp * cy])


def euler_from_quat(q):
    w, x, y, z = q
    roll = math.atan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y))
    pitch = math.asin(clamp(2 * (w * y - z * x), -1.0, 1.0))
    yaw = math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))
    return roll, pitch, yaw


class Config:
    """Memuat vehicle.json dan menyiapkan besaran turunan."""

    def __init__(self, path):
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
        self.raw = d
        self.status = d.get("_status", "")
        self.m = float(d["mass_kg"])
        self.I = np.diag([float(v) for v in d["inertia_kgm2"]])
        self.Iinv = np.linalg.inv(self.I)
        self.L = float(d["vane_lever_L_m"])
        self.rv = float(d["vane_radial_m"])
        self.span = float(d["vane_span_m"])
        self.chord = float(d["vane_chord_m"])
        self.S = self.span * self.chord
        self.AR = self.span / self.chord
        self.cna = 2 * math.pi * self.AR / (self.AR + 2)  # [ASM] gaya normal per rad, sayap hingga
        self.vane_limit = float(d["vane_limit_deg"])
        self.stall = float(d["vane_stall_deg"])
        tab = d.get("cn_table")
        if tab:
            self.tab_a = np.array(tab["alpha_deg"], dtype=float)
            self.tab_cn = np.array(tab["cn"], dtype=float)
        else:
            self.tab_a = None
            self.tab_cn = None
        self.full_scale = float(d["servo_full_scale_deg"])
        self.servo_tau = float(d["servo_tau_s"])
        self.servo_rate = float(d["servo_rate_deg_s"])
        self.pwm_min = float(d["pwm_min"])
        self.pwm_max = float(d["pwm_max"])
        self.trim = [float(v) for v in d["pwm_trim"]]
        self.sign = [int(v) for v in d["servo_sign"]]
        self.yaw_dir = int(d["yaw_dir"])
        self.Tmax = float(d["thrust_max_N"])
        self.T_tau = float(d["thrust_tau_s"])
        self.A = float(d["fan_area_m2"])
        self.q0 = float(d["q0_per_N"]) * int(d["q0_sign"])
        self.cda = np.array(d["drag_cda_m2"], dtype=float)
        self.rot_damp = float(d["rot_damping_nms"])
        self.rho = float(d["rho"])
        self.wind = np.array(d["wind_ned_mps"], dtype=float)
        # arah gaya pada kendaraan untuk defleksi positif: depan, kanan, belakang, kiri
        self.vane_dir = [np.array([0.0, 1.0, 0.0]), np.array([-1.0, 0.0, 0.0]),
                         np.array([0.0, -1.0, 0.0]), np.array([1.0, 0.0, 0.0])]
        rv = self.yaw_dir * self.rv
        self.vane_pos = [np.array([rv, 0.0, self.L]), np.array([0.0, rv, self.L]),
                         np.array([-rv, 0.0, self.L]), np.array([0.0, -rv, self.L])]

    def cn(self, delta_deg):
        if self.tab_a is not None:
            v = float(np.interp(abs(delta_deg), self.tab_a, self.tab_cn))
            return math.copysign(v, delta_deg)
        a = math.radians(clamp(delta_deg, -self.stall, self.stall))
        return self.cna * a


class Vehicle:
    def __init__(self, cfg, pos=(0.0, 0.0, 0.0)):
        self.c = cfg
        self.p = np.array(pos, dtype=float)
        self.v = np.zeros(3)
        self.q = np.array([1.0, 0.0, 0.0, 0.0])
        self.w = np.zeros(3)
        self.T = 0.0
        self.delta = [0.0, 0.0, 0.0, 0.0]
        self.on_ground = self.p[2] >= 0.0
        self.last_acc_w = np.zeros(3)

    def deflection_cmd(self, pwm, i):
        c = self.c
        half = (c.pwm_max - c.pwm_min) / 2.0
        d = c.sign[i] * (pwm[i] - c.trim[i]) / half * c.full_scale
        return clamp(d, -c.vane_limit, c.vane_limit)

    def step(self, dt, pwm):
        c = self.c
        # --- aktuator
        u = clamp((pwm[4] - c.pwm_min) / (c.pwm_max - c.pwm_min), 0.0, 1.0)
        self.T += (c.Tmax * u * u - self.T) * (1.0 - math.exp(-dt / c.T_tau))
        for i in range(4):
            cmd = self.deflection_cmd(pwm, i)
            rate = clamp((cmd - self.delta[i]) / c.servo_tau, -c.servo_rate, c.servo_rate)
            self.delta[i] += rate * dt
        # --- gaya dan momen dalam kerangka badan
        qdyn = self.T / (2.0 * c.A)  # q = T/(2A), luas keluaran = luas fan [ASM]
        F = np.array([0.0, 0.0, -self.T])
        M = np.array([0.0, 0.0, c.q0 * self.T])
        for i in range(4):
            f = qdyn * c.S * c.cn(self.delta[i])
            Fi = f * c.vane_dir[i]
            F += Fi
            M += np.cross(c.vane_pos[i], Fi)
        R = quat_to_dcm(self.q)
        vb = R.T @ (self.v - c.wind)
        F += -0.5 * c.rho * c.cda * np.abs(vb) * vb
        M += -c.rot_damp * self.w
        # --- translasi
        a_w = R @ F / c.m + np.array([0.0, 0.0, G])
        # --- kontak tanah (tanah datar, kaki menahan sikap tegak)
        if self.p[2] >= 0.0 and a_w[2] >= 0.0:
            self.p[2] = 0.0
            self.v[:] = 0.0
            self.w[:] = 0.0
            roll, pitch, yaw = euler_from_quat(self.q)
            self.q = quat_from_euler(0.0, 0.0, yaw)
            a_w = np.zeros(3)
            self.on_ground = True
        else:
            self.on_ground = False
            self.v += a_w * dt
            self.p += self.v * dt
            if self.p[2] > 0.0:  # menyentuh tanah saat turun
                self.p[2] = 0.0
                self.v[2] = min(self.v[2], 0.0)
            # --- rotasi
            alpha = c.Iinv @ (M - np.cross(self.w, c.I @ self.w))
            self.w += alpha * dt
            th = np.linalg.norm(self.w) * dt
            if th > 1e-12:
                axis = self.w / np.linalg.norm(self.w)
                dq = np.array([math.cos(th / 2), *(axis * math.sin(th / 2))])
                self.q = quat_mul(self.q, dq)
                self.q /= np.linalg.norm(self.q)
        self.last_acc_w = a_w

    def sensors(self):
        R = quat_to_dcm(self.q)
        f_w = self.last_acc_w - np.array([0.0, 0.0, G])  # gaya spesifik
        return self.w.copy(), R.T @ f_w


class AutoSign:
    """Memprogram sikap (roll, pitch, yaw) saat ArduPilot armed + throttle naik, lalu menghitung tanda servo."""

    TRIGGER_PWM = 1200.0
    TRIGGER_HOLD_S = 1.0
    ANGLES_DEG = (("roll", 8.0), ("pitch", 8.0), ("yaw", 12.0))
    REST, RAMP, HOLD = 2.0, 1.5, 3.0  # detik per segmen

    def __init__(self, cfg):
        self.c = cfg
        self.t_trig = None
        self.t_above = 0.0
        self.t = 0.0
        self.sums = {k: np.zeros(4) for k, _ in self.ANGLES_DEG}
        self.counts = {k: 0 for k, _ in self.ANGLES_DEG}
        self.done = False
        self.result = None
        self.seg = self.REST + 2 * self.RAMP + self.HOLD

    @staticmethod
    def _smooth(x):
        x = clamp(x, 0.0, 1.0)
        return x * x * (3 - 2 * x)

    @staticmethod
    def _dsmooth(x):
        if x <= 0.0 or x >= 1.0:
            return 0.0
        return 6 * x * (1 - x)

    def update(self, dt, pwm):
        """Mengembalikan (roll, pitch, yaw, rate_roll, rate_pitch, rate_yaw) dalam rad dan rad/s (Euler)."""
        self.t += dt
        if self.t_trig is None:
            self.t_above = self.t_above + dt if pwm[4] >= self.TRIGGER_PWM else 0.0
            if self.t_above >= self.TRIGGER_HOLD_S:
                self.t_trig = self.t
            return (0.0,) * 6
        tau = self.t - self.t_trig
        ang = [0.0, 0.0, 0.0]
        rate = [0.0, 0.0, 0.0]
        for k, (name, a_deg) in enumerate(self.ANGLES_DEG):
            t0 = k * self.seg
            lt = tau - t0
            if lt < 0 or lt > self.seg:
                continue
            a = math.radians(a_deg)
            if lt < self.REST:
                continue
            x = lt - self.REST
            if x < self.RAMP:
                ang[k] = a * self._smooth(x / self.RAMP)
                rate[k] = a * self._dsmooth(x / self.RAMP) / self.RAMP
            elif x < self.RAMP + self.HOLD:
                ang[k] = a
                if x > self.RAMP + 0.5 * self.HOLD:  # ukur separuh akhir masa tahan
                    self.sums[name] += np.array([pwm[i] - self.c.trim[i] for i in range(4)])
                    self.counts[name] += 1
            else:
                y = (x - self.RAMP - self.HOLD) / self.RAMP
                ang[k] = a * (1 - self._smooth(y))
                rate[k] = -a * self._dsmooth(y) / self.RAMP
        if tau > 3 * self.seg and not self.done:
            self.finish()
        return (*ang, *rate)

    def finish(self):
        self.done = True
        mean = {}
        for k in self.sums:
            mean[k] = self.sums[k] / max(self.counts[k], 1)
        notes = []
        for k in mean:
            if np.max(np.abs(mean[k])) < 5.0:
                notes.append(f"Uji {k}: respons PWM < 5 us. Pastikan ARMED, mode STABILIZE, dan throttle naik.")
        sgn = [0, 0, 0, 0]
        sgn[0] = int(np.sign(mean["roll"][0])) or 1
        sgn[2] = -int(np.sign(mean["roll"][2])) or 1
        sgn[1] = int(np.sign(mean["pitch"][1])) or 1
        sgn[3] = -int(np.sign(mean["pitch"][3])) or 1
        ysum = sum(sgn[i] * mean["yaw"][i] for i in range(4))
        yaw_dir = -int(np.sign(ysum)) or 1
        same = all(np.sign(sgn[i] * mean["yaw"][i]) == np.sign(ysum) for i in range(4))
        if not same:
            notes.append("Peringatan yaw: keempat vane tidak searah pada uji yaw. Periksa pemetaan SERVOx_FUNCTION.")
        self.result = {"servo_sign": sgn, "yaw_dir": yaw_dir,
                       "mean_pwm_dev": {k: [round(float(x), 1) for x in v] for k, v in mean.items()},
                       "notes": notes}


class Backend:
    def __init__(self, cfg, mode="normal", pos=(0.0, 0.0, 0.0)):
        self.cfg = cfg
        self.mode = mode
        self.veh = Vehicle(cfg, pos)
        self.t = 0.0
        self.auto = AutoSign(cfg) if mode == "autosign" else None
        self.log = None
        self.last_print = 0.0
        self.step_count = 0

    def handle(self, pwm, dt):
        self.t += dt
        self.step_count += 1
        if self.mode == "normal":
            self.veh.step(dt, pwm)
            gyro, acc = self.veh.sensors()
            p, v, q = self.veh.p, self.veh.v, self.veh.q
        else:
            if self.mode == "autosign":
                r, pi_, ya, rr, rp, ry = self.auto.update(dt, pwm)
                q = quat_from_euler(r, pi_, ya)
                sr, cr = math.sin(r), math.cos(r)
                sp, cp = math.sin(pi_), math.cos(pi_)
                gyro = np.array([rr - ry * sp,
                                 rp * cr + ry * sr * cp,
                                 -rp * sr + ry * cr * cp])
            else:
                q = np.array([1.0, 0.0, 0.0, 0.0])
                gyro = np.zeros(3)
            acc = quat_to_dcm(q).T @ np.array([0.0, 0.0, -G])
            p, v = np.zeros(3), np.zeros(3)
            now = time.time()
            if now - self.last_print > 0.5:
                self.last_print = now
                dev = [pwm[i] - self.cfg.trim[i] for i in range(4)]
                print("PWM1-4 dev vs trim: %+6.0f %+6.0f %+6.0f %+6.0f | PWM5(ESC)=%4.0f" %
                      (*dev, pwm[4]), flush=True)
        msg = {"timestamp": self.t,
               "imu": {"gyro": [float(x) for x in gyro], "accel_body": [float(x) for x in acc]},
               "position": [float(x) for x in p],
               "velocity": [float(x) for x in v],
               "quaternion": [float(x) for x in q]}
        if self.log is not None and self.step_count % 12 == 0:
            r, pi_, ya = euler_from_quat(q)
            self.log.write("%.4f,%.4f,%.4f,%.4f,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.1f\n" % (
                self.t, p[0], p[1], p[2], math.degrees(r), math.degrees(pi_), math.degrees(ya),
                self.veh.T, *self.veh.delta, pwm[4]))
        return msg


def parse_packet(data):
    if len(data) < HDR.size:
        return None
    magic, rate, count = HDR.unpack_from(data, 0)
    if magic == MAGIC16 and len(data) >= HDR.size + 32:
        pwm = struct.unpack_from("<16H", data, HDR.size)
    elif magic == MAGIC32 and len(data) >= HDR.size + 64:
        pwm = struct.unpack_from("<32H", data, HDR.size)
    else:
        return None
    return rate, count, pwm


def serve(backend, port=9002, bind="0.0.0.0", stop=None, max_seconds=None, default_rate=1200):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((bind, port))
    sock.settimeout(0.5)
    print(f"[backend] mendengarkan UDP {bind}:{port} (menunggu paket servo ArduPilot)", flush=True)
    last_count = None
    warned = False
    t_start = None
    try:
        while True:
            if stop is not None and stop.is_set():
                break
            try:
                data, addr = sock.recvfrom(1024)
            except socket.timeout:
                continue
            pkt = parse_packet(data)
            if pkt is None:
                continue
            rate, count, pwm = pkt
            if t_start is None:
                t_start = time.time()
                print(f"[backend] terhubung ke {addr}, frame_rate={rate} Hz", flush=True)
            if last_count is not None and count != last_count + 1 and not warned and count > last_count:
                print(f"[backend] peringatan: frame_count melompat {last_count}->{count}", flush=True)
                warned = True
            last_count = count
            dt = 1.0 / (rate if rate > 0 else default_rate)
            msg = backend.handle(dt=dt, pwm=pwm)
            sock.sendto(("\n" + json.dumps(msg) + "\n").encode("ascii"), addr)
            if max_seconds is not None and backend.t >= max_seconds:
                break
    finally:
        sock.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vehicle", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "vehicle.json"))
    ap.add_argument("--mode", choices=["normal", "freeze", "autosign"], default="normal")
    ap.add_argument("--port", type=int, default=9002)
    ap.add_argument("--bind", default="0.0.0.0")
    ap.add_argument("--log", default=None, help="file CSV log (sekitar 100 Hz)")
    ap.add_argument("--write", action="store_true", help="autosign: tulis hasil ke vehicle.json")
    ap.add_argument("--max-seconds", type=float, default=None)
    args = ap.parse_args()

    cfg = Config(args.vehicle)
    if "PLACEHOLDER" in cfg.status.upper():
        print("=" * 70)
        print("PERINGATAN: vehicle.json masih PLACEHOLDER. Hasil simulasi belum mewakili CAD-mu.")
        print("=" * 70, flush=True)
    elif "SEBAGIAN" in cfg.status.upper():
        print("CATATAN: massa/CG/inersia dari CAD; parameter lain masih asumsi [ASM] (lihat label di vehicle.json).", flush=True)
    be = Backend(cfg, mode=args.mode)
    if args.log:
        be.log = open(args.log, "w")
        be.log.write("t,N,E,D,roll_deg,pitch_deg,yaw_deg,thrust_N,d1,d2,d3,d4,pwm5\n")
    try:
        if args.mode == "autosign":
            import threading
            stop = threading.Event()

            def watcher():
                while not stop.is_set():
                    if be.auto.done:
                        stop.set()
                    time.sleep(0.2)
            threading.Thread(target=watcher, daemon=True).start()
            print("[autosign] ARM di STABILIZE lalu naikkan throttle (mis. di MAVProxy: rc 3 1500).", flush=True)
            serve(be, args.port, args.bind, stop=stop)
            res = be.auto.result
            if res:
                print("\n=== HASIL AUTOSIGN ===")
                print(json.dumps(res, indent=2))
                if args.write:
                    cfg.raw["servo_sign"] = res["servo_sign"]
                    cfg.raw["yaw_dir"] = res["yaw_dir"]
                    with open(args.vehicle, "w", encoding="utf-8") as f:
                        json.dump(cfg.raw, f, indent=2, ensure_ascii=False)
                    print(f"Ditulis ke {args.vehicle}")
        else:
            serve(be, args.port, args.bind, max_seconds=args.max_seconds)
    except KeyboardInterrupt:
        print("\n[backend] dihentikan")
    finally:
        if be.log:
            be.log.close()


if __name__ == "__main__":
    main()
