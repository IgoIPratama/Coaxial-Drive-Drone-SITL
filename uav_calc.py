#!/usr/bin/env python3
"""
uav_calc.py  -  Kalkulasi verifikasi desain Single-EDF thrust-vectoring UAV
===========================================================================
Semua angka input diberi label sumber:
  [DOC]  = dari dokumen proyekmu (Electronics_Solar_Suppliers / Architecture)
  [DS]   = dari datasheet/listing vendor (verifikasi ulang ke datasheet resmi)
  [CAD]  = dibaca dari file CAD/STEP (verifikasi ulang di SolidWorks)
  [ASM]  = ASUMSI (WAJIB diganti dengan data terukur/CFD/CAD)

Jalankan:  python3 uav_calc.py
Ubah nilai pada blok INPUT, lalu jalankan ulang. Tidak ada library eksternal.
"""
import math

# ------------------------------------------------------------------ INPUT
g = 9.80665          # m/s^2
rho = 1.225          # kg/m^3  [ASM] ISA permukaan laut; ganti sesuai kondisi lokasi

# Massa
MTOW = 2.08102   # kg   [CAD] SolidWorks Mass Properties Baseline-EDF; koreksi part kecil ~+0.09 kg, item non-CAD ~+0.15-0.25 kg
m_batt = 0.660       # kg   [DOC] 2 x ~330 g
m_edf = 0.369        # kg   [DOC]

# Baterai
cells = 6
v_cell_nom_lihv = 3.8        # V  [DS] LiHV nominal
v_cell_full_lihv = 4.35      # V  [DS] LiHV full charge
v_cell_full_lipo = 4.20      # V  [DS] LiPo standar
cap_ah_each = 2.0            # Ah [DOC]
n_parallel = 2               # [DOC]
usable_frac = 0.80           # [ASM] batas pemakaian aman (sisakan 20%)

# EDF (klaim vendor, BELUM terverifikasi independen)
edf_diam = 0.090             # m   [DOC]
edf_thrust_max_kg = 3.790    # kgf [DOC] klaim vendor
edf_i_peak = 124.0           # A   [DOC] klaim vendor
edf_vmax = 25.2              # V   [DOC] batas tegangan vendor
edf_kv = 1450                # rpm/V [DOC]
edf_blades = 12              # [DOC]
eta_range = (0.55, 0.65)     # [ASM] efisiensi gabungan listrik->daya ideal; dikalibrasi dari klaim vendor di bawah

# Kawat
awg8_ohm_per_m = 2.061e-3    # ohm/m [DS] tembaga AWG8 pada 20 C
wire_len_one_way = 0.30      # m   [ASM] ganti dengan panjang rute dari CAD

# Vane (bounding box STEP 'Vein' = 50 x 15.5 x 35.3 mm)  [CAD]
vane_dim_a = 0.0500          # m   [CAD] sisi panjang 50 mm
vane_dim_b = 0.0353          # m   [CAD] sisi 35.3 mm
vane_defl_deg = 15.0         # deg [ASM] defleksi uji
servo_stall_kgcm_48 = 1.8    # kgf.cm [DS] MG90S @4.8 V
servo_stall_kgcm_60 = 2.2    # kgf.cm [DS] MG90S @6.0 V
servo_speed_s60_60 = 0.08    # s/60deg [DS] MG90S @6.0 V (tanpa beban)

# Surya - ILUSTRATIF (geometri kerucut belum diukur)
cone_r_base = 0.055          # m  [ASM] ganti dengan ukuran CAD
cone_r_top = 0.020           # m  [ASM]
cell_eff = 0.20              # [ASM] efisiensi modul setelah dipotong
packing = 0.80               # [ASM] fraksi area tertutup sel
irr_peak = 1000.0            # W/m2 [ASM] STC
vmp_cell = 0.50              # V  [ASM] tegangan MPP per sel (suhu panas)
# ------------------------------------------------------------------ END INPUT


def hdr(t):
    print("\n" + "=" * 72 + f"\n{t}\n" + "=" * 72)


# 1. Tegangan & RPM
hdr("1. TEGANGAN PACK & RPM (EDF)")
v_nom = cells * v_cell_nom_lihv
v_full_lihv = round(cells * v_cell_full_lihv, 3)
v_full_lipo = round(cells * v_cell_full_lipo, 3)
print(f"V nominal LiHV          : {v_nom:.1f} V")
print(f"V penuh LiHV (4.35/sel) : {v_full_lihv:.1f} V   -> batas EDF vendor {edf_vmax} V : "
      f"{'MELEBIHI' if v_full_lihv > edf_vmax else 'OK'} (+{(v_full_lihv/edf_vmax-1)*100:.1f}%)")
print(f"V penuh 4.20 V/sel      : {v_full_lipo:.1f} V   -> {'OK' if v_full_lipo <= edf_vmax else 'MELEBIHI'}")
for v in (v_nom, v_full_lipo, v_full_lihv):
    rpm = edf_kv * v
    print(f"RPM tanpa beban @ {v:5.1f} V : {rpm:8.0f} rpm = {rpm/60:6.1f} Hz ; blade-pass = {rpm/60*edf_blades/1000:5.2f} kHz")

# 2. Massa
hdr("2. ANGGARAN MASSA")
m_rest = MTOW - m_batt - m_edf
print(f"MTOW {MTOW*1000:.0f} g - baterai {m_batt*1000:.0f} g - EDF {m_edf*1000:.0f} g = sisa {m_rest*1000:.0f} g "
      f"untuk SEMUA struktur+elektronik")
print(f"Thrust/weight maks (klaim vendor): {edf_thrust_max_kg/MTOW:.2f}")

# 3. Energi & hover
hdr("3. ENERGI BATERAI, DAYA HOVER, ENDURANCE (estimasi momentum-theory)")
cap_ah = cap_ah_each * n_parallel
e_total = cap_ah * v_nom
e_use = e_total * usable_frac
print(f"Kapasitas {cap_ah:.1f} Ah x {v_nom:.1f} V = {e_total:.1f} Wh ; dipakai {usable_frac*100:.0f}% = {e_use:.1f} Wh")

A = math.pi / 4 * edf_diam ** 2   # luas penuh (batas atas; hub tidak dikurangkan)


def p_ideal(T):
    return T ** 1.5 / math.sqrt(2 * rho * A)


T_hover = MTOW * g
T_max = edf_thrust_max_kg * g
P_id_hover, P_id_max = p_ideal(T_hover), p_ideal(T_max)
print(f"Luas fan (Ø{edf_diam*1000:.0f} mm, tanpa pengurangan hub): {A*1e4:.3f} cm2")
print(f"Thrust hover {T_hover:.2f} N ({T_hover/T_max*100:.1f}% dari maks vendor {T_max:.1f} N)")
print(f"Daya ideal hover {P_id_hover:.0f} W ; daya ideal pada thrust maks {P_id_max:.0f} W")
for vref in (v_nom, edf_vmax):
    pe = edf_i_peak * vref
    print(f"  Kalibrasi vendor: {edf_i_peak:.0f} A x {vref:.1f} V = {pe:.0f} W -> eta gabungan = {P_id_max/pe:.2f}")
print("  (eta_range yang dipakai di bawah adalah ASUMSI berdasar kalibrasi ini)")
for eta in eta_range:
    p = P_id_hover / eta
    i = p / v_nom
    t = e_use / p * 60
    print(f"  eta={eta:.2f}: P_hover={p:5.0f} W | I={i:4.1f} A ({i/cap_ah:4.1f} C) | endurance hover = {t:4.1f} menit")
print(f"  Arus puncak {edf_i_peak:.0f} A / {cap_ah:.0f} Ah = {edf_i_peak/cap_ah:.0f} C total "
      f"({edf_i_peak/n_parallel:.0f} A/pack bila berbagi sama rata)")

# 4. Kawat
hdr("4. RUGI KAWAT AWG8 PADA ARUS PUNCAK")
R = awg8_ohm_per_m * wire_len_one_way * 2
print(f"R loop = {R*1e3:.2f} mohm ; drop = {edf_i_peak*R:.3f} V ; rugi = {edf_i_peak**2*R:.1f} W @ {edf_i_peak:.0f} A")
print("  (belum termasuk konektor/solder/ESC; tambahkan hasil ukur CAD untuk panjang sebenarnya)")

# 5. Vane
hdr("5. MOMEN ENGSEL VANE (orde besaran; GANTI dengan hasil CFD Flow Simulation)")
print("Asumsi: luas keluar = luas fan; bila duct menyempit, kecepatan & momen NAIK -> tinjau ulang SF.")
S = vane_dim_a * vane_dim_b
for name, T in (("hover", T_hover), ("thrust maks", T_max)):
    ve = math.sqrt(T / (rho * A))          # kecepatan keluar ideal, luas keluar = luas fan (bila luas keluar lebih kecil, kecepatan dan momen lebih BESAR)
    q = 0.5 * rho * ve ** 2
    for (span, chord) in ((vane_dim_a, vane_dim_b), (vane_dim_b, vane_dim_a)):
        AR = span / chord
        cna = 2 * math.pi * AR / (AR + 2)  # kemiringan gaya normal sayap hingga (aproksimasi)
        cn = cna * math.radians(vane_defl_deg)
        F = q * S * cn
        for arm_frac in (0.25, 0.50):
            M = F * chord * arm_frac
            sf = servo_stall_kgcm_48 * 0.0980665 / M
            print(f"{name:11s} ve={ve:5.1f} m/s q={q:6.0f} Pa | span={span*1e3:4.1f} chord={chord*1e3:4.1f} mm AR={AR:4.2f} "
                  f"| F={F:5.2f} N | lengan={arm_frac:.2f}c M={M*100:5.2f} N.cm ({M/0.0980665:4.2f} kgf.cm) | SF vs 1.8 kgf.cm = {sf:4.1f}")
print(f"Slew maks servo (datasheet, tanpa beban): 60 deg/{servo_speed_s60_60}s = {60/servo_speed_s60_60:.0f} deg/s "
      f"(gunakan <= 50% pada model beban nyata)")

# 6. Surya
hdr("6. SURYA - ILUSTRATIF (ganti geometri dengan ukuran CAD)")
slant = math.hypot(cone_r_base - cone_r_top, 0.035)  # [ASM] tinggi kerucut 35 mm
area_slant = math.pi * (cone_r_base + cone_r_top) * slant
area_proj = math.pi * (cone_r_base ** 2 - cone_r_top ** 2)  # proyeksi ke arah matahari tegak lurus sumbu
P_peak = irr_peak * area_proj * cell_eff * packing
print(f"Luas selimut kerucut = {area_slant*1e4:.1f} cm2 ; proyeksi (matahari di atas) = {area_proj*1e4:.1f} cm2")
print(f"Daya puncak teoretis ~ {P_peak:.2f} W (matahari tepat di atas, kondisi STC)")
print(f"Waktu isi 'dipakai' {e_use:.0f} Wh pada daya puncak terus-menerus: {e_use/P_peak:.0f} jam (belum cuaca/geometri)")
n_series_buck = math.ceil((v_full_lipo + 1.5) / vmp_cell)
print(f"Jumlah sel seri bila charger topologi BUCK (butuh Vin > Vbat+~1.5 V): {n_series_buck} sel -> tidak muat di bodi Ø110 mm")
print("  => Topologi pengisi harus BOOST/step-up (atau modul seri tegangan tinggi) - bukan buck seperti BQ24650.")

print("\nSelesai. Periksa semua baris berlabel [ASM] sebelum mengutip angka di portofolio.")
