# Paket SITL: Single-EDF + 4 vane (ArduPilot SingleCopter)

## Status jujur (baca dulu)

- Backend fisika ini **sudah diuji tanpa ArduPilot** (`selftest.py`: 16 pengujian, semua lulus pada saat dibuat). Pengujian itu membuktikan kode konsisten secara internal: protokol UDP/JSON, dinamika, konvensi tanda vane, dan algoritma autosign.
- Backend ini **belum diuji terhadap ArduPilot sungguhan** karena lingkungan tempat saya membuatnya tidak punya ArduPilot dan tidak punya akses internet. Integrasi pertama adalah pekerjaanmu di Fase 7 (uji T1-T9 pada panduan). Jika ada selisih perilaku, catat dan kita perbaiki bersama.
- **`vehicle.json` masih PLACEHOLDER.** Saya tidak bisa membaca massa, inersia, atau CG dari file SolidWorks. Semua angka itu diberi label dan harus kamu ganti sebelum hasil simulasi boleh dikaitkan dengan CAD-mu.

## 1. Isi vehicle.json dari CAD (15 menit di SolidWorks)

Buka konfigurasi "Baseline-EDF" (CRM2413 assembly ditekan/suppress), lalu:

| Isi di vehicle.json | Ambil dari SolidWorks |
|---|---|
| `mass_kg` | Evaluate > Mass Properties, Mass (kg) |
| `inertia_kgm2` [Ixx, Iyy, Izz] | Mass Properties > "Principal moments" atau "Moments of inertia at center of mass" dengan Coordinate System di CG, sumbu Z sejajar sumbu EDF. Satuan kg.m2 |
| `vane_lever_L_m` | Measure: jarak CG ke bidang engsel vane, searah sumbu EDF (m) |
| `vane_radial_m` | Measure: jarak radial pusat vane dari sumbu EDF (m) |
| `vane_span_m`, `vane_chord_m` | Measure: dimensi vane (STEP: 50 x 15,5 x 35,3 mm; tentukan sisi mana chord/span) |
| `vane_limit_deg` | Motion Study: sudut maksimum bebas tabrakan |
| `fan_area_m2` | Luas lingkaran fan (m2) |

Setelah itu ubah `_status` menjadi `"CAD-VERIFIED"` supaya peringatan hilang. Jika kamu menempelkan hasil Mass Properties ke saya, saya bisa memasukkannya.

## 2. Jalankan self-test (tanpa ArduPilot)

```
python3 selftest.py
```
Semua baris harus `[PASS]`. Perlu Python 3.10+ dan numpy (`pip install numpy`).

## 3. Pasang ArduPilot SITL (sekali saja)

Ikuti halaman resmi (Ubuntu/WSL2): https://ardupilot.org/dev/docs/using-sitl-for-ardupilot-testing.html

```
git clone --recurse-submodules https://github.com/ArduPilot/ardupilot.git
cd ardupilot
Tools/environment_install/install-prereqs-ubuntu.sh -y
. ~/.profile
git checkout <tag Copter stabil terbaru>     # catat tag + hash commit di REPRODUCIBILITY.md
```
Uji kontrol dulu (tanpa backend-mu): `Tools/autotest/sim_vehicle.py -v ArduCopter -f singlecopter --console --map -w`. Jika ini gagal, masalahnya di instalasi, bukan di model.

## 4. Kalibrasi tanda servo (wajib, sekali per perubahan geometri)

Tanda hubungan PWM -> arah vane tidak boleh ditebak; salah satu tanda yang terbalik membuat kendaraan divergen (terbukti di T7 self-test). Backend punya mode `autosign` yang menahan kendaraan diam, memutar sikap secara terprogram (roll, pitch, yaw), membaca respons PWM ArduPilot, dan menghitung `servo_sign` dan `yaw_dir`.

1. Terminal A: `python3 physics_backend.py --mode autosign --write`
2. Terminal B: `Tools/autotest/sim_vehicle.py -v ArduCopter -f singlecopter --model JSON:127.0.0.1 --add-param-file=<path>/edf_tvc.parm --console --map -w`
3. Tunggu EKF siap (konsol menampilkan inisialisasi EKF, sekitar 30-60 detik).
4. Di MAVProxy: `mode stabilize`, lalu `arm throttle` (bila ditolak: `arm throttle force`), lalu `rc 3 1500`.
5. Biarkan sekitar 80 detik. Backend mencetak hasil dan menulisnya ke vehicle.json. Lalu `disarm` dan hentikan keduanya.
6. Periksa catatan (`notes`) pada keluaran. Jika ada peringatan "respons PWM < 5 us", ulangi dengan throttle lebih tinggi.

Mode `freeze` (`--mode freeze`) hanya memantau selisih PWM tiap 0,5 detik; berguna untuk mencocokkan uji flap resmi ArduPilot (roll kanan: vane depan dan belakang ke kanan; pitch maju: vane kiri dan kanan ke depan; yaw kanan: depan ke kiri, kanan ke depan, belakang ke kanan, kiri ke belakang).

## 5. Menjalankan simulasi

Terminal A: `python3 physics_backend.py --vehicle vehicle.json --log run_log.csv`
Terminal B: perintah SITL yang sama seperti langkah 4.2.

`run_sitl.sh` mencetak kedua perintah. Argumen `-f singlecopter --model JSON:127.0.0.1` mengikuti praktik yang dilaporkan di forum ArduPilot [CEK: bentuk argumen dapat berbeda antar versi; lihat `sim_vehicle.py --help`].

Skenario uji T1-T9 ada di Fase 7 panduan. Log fisika backend (`run_log.csv`: waktu, posisi, sikap, thrust, defleksi vane, PWM ESC) dan log .BIN ArduPilot dianalisis bersama.

## 6. Mengganti asumsi dengan hasil CFD

Setelah `data/cfd_vane_table.csv` ada (kolom `alpha_deg, thrust_N, force_side_N` untuk satu vane diuji sendirian):

```
python3 cn_from_cfd.py ../data/cfd_vane_table.csv --vehicle vehicle.json
```
Ini mengisi `cn_table` dan `vane_stall_deg`. Ganti juga `thrust_max_N` (CFD pada RPM_maks) dan `q0_per_N` (torsi Z pada alpha = 0, dibagi thrust).

## 7. Model fisika dan batasannya

Dimodelkan: dinamika 6-DOF kaku; thrust ~ throttle^2 dengan lag orde satu; gaya vane = q.S.CN(alpha) dengan q = T/(2A); momen vane = r x F; torsi reaksi yaw EDF residual; servo orde satu dengan batas laju dan sudut; hambatan badan kuadratik; kontak tanah datar.

Tidak dimodelkan (batasan yang harus kamu nyatakan di portofolio): interaksi antar vane dan efek swirl pada gaya vane, penurunan thrust aksial akibat defleksi vane, efek gyroscopic rotor EDF, kelonggaran mekanis (backlash), sensor noise khusus (SITL menambahkan sendiri), baterai dinamis (pakai `SIM_BATT_*` SITL), angin dinamis (hanya `wind_ned_mps` konstan di vehicle.json karena parameter `SIM_WIND_*` ArduPilot tidak mengatur backend eksternal [CEK]).

## 8. Protokol (sumber)

Paket ArduPilot ke backend: `uint16 magic=18458, uint16 frame_rate, uint32 frame_count, uint16 pwm[16]` (varian 32 kanal: magic 29569). Balasan backend: JSON berawalan dan berakhiran newline dengan `timestamp`, `imu.gyro`, `imu.accel_body`, `position` (NED), `velocity` (NED), `quaternion`. Sumber: kode SIM_JSON.cpp di repositori ArduPilot dan contoh antarmuka JSON (https://github.com/ArduPilot/ardupilot/blob/master/libraries/SITL/SIM_JSON.cpp).
