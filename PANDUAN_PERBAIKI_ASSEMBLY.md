# Panduan: menyatukan UAV-mu menjadi assembly utuh di Inventor

## 1. Yang saya temukan di dalam file SLDASM-mu (fakta, bukan dugaan)

Saya membaca struktur internal `Final UAV.SLDASM` (daftar komponen, transformasi tiap komponen, dan ukuran tiap part). Hasilnya:

1. **File SLDASM-mu menyimpan keadaan TERPASANG.** Posisi tersimpan membentuk tumpukan yang rapi sepanjang sumbu X assembly: Top section (kerucut), Carbon Fiber Mount, 2nd Electronics Space, 1st Electronics Space, Air Intake Zone, Fan Housing + Ducted Fan, lalu vane di ujung bawah. Baterai berada di sisi bodi, kaki di bawah, Pixhawk di dalam 2nd Electronics Space. Jadi bentuk UAV utuh ada di data; yang hilang adalah di Inventor.
2. **Gambar kecil (thumbnail) di dalam file itu bentuk exploded.** Artinya file terakhir disimpan saat tampilan exploded aktif. Itu hanya tampilan, bukan posisi komponen.
3. **Mate SolidWorks tidak ikut ke Inventor.** Inventor tidak menerjemahkan mate. Jika posisi tersimpan tidak terbawa dengan benar (terutama untuk sub-assembly), komponen berada di posisi bawaan dan tampak berserakan. Saya tidak bisa melihat isi file `.iam`-mu, jadi ini penjelasan yang paling mungkin, bukan kepastian. Langkah diagnosa di bawah akan memastikannya.
4. **Sumbu UAV = sumbu X** pada koordinat SLDASM. Ujung "atas" (kerucut, rotor) ada di arah -X; ujung knalpot (vane, kaki) ada di arah +X. Sumbu bodi melewati titik Y = 11,1 mm, Z = -9,7 mm.

### Ukuran asli dari CAD-mu (mm)

| Bagian | Posisi sumbu X | Catatan |
|---|---|---|
| Top section (kerucut) | -312 sampai -262 | panjang 50 |
| Carbon Fiber Mount | -265 sampai -262 | pelat tebal 3 |
| 2nd Electronics Space | -268 sampai -216 | panjang 52 |
| 1st Electronics Space | -222 sampai -99 | panjang 122 |
| Air Intake Zone | -182 sampai -62 | panjang 120 |
| Ducted Fan | -64 sampai 52 | |
| Fan Housing and Base | -70 sampai 78 | |
| Vane (4 buah) | 36 sampai 87 | chord 50 sepanjang sumbu, span 38 radial |
| Pipa kaki (4 buah) | -21 sampai 143 | |
| Rotor CRM2413 | -358 sampai -277 | |
| Propeller "15 inci" | -414 sampai -320 | bentang 762 mm (30 inci ujung ke ujung) |

- **Diameter bodi = 119,2 mm**, bukan 110 mm seperti di dokumenmu. Perbarui dokumen.
- Tanpa rotor kontra-rotasi, seluruh pesawat (termasuk kaki) berukuran 455 x 275 x 275 mm. Dengan rotor: 561 x 728 x 677 mm.
- Bentang propeller 762 mm itu sekitar 6,4 kali diameter bodi. Ini mengingatkan keputusan D1 di panduan utama: konfigurasi dengan rotor kontra-rotasi adalah pesawat yang sangat berbeda dari konfigurasi Single-EDF.

## 2. Perbaikan di Inventor

### Jalur A: skrip iLogic (paling cepat, tanpa SolidWorks)

File: `inventor/snap_to_sldasm.iLogicVb` dan `inventor/uav_transforms.csv` (179 baris, semua sudah saya validasi: tidak ada komponen mirror atau berskala, semua nama unik per assembly).

Penting: skrip ini **belum diuji di Inventor** karena saya tidak punya Inventor. Karena itu ia diatur untuk mode diagnosa dulu.

1. **Backup**: salin seluruh folder proyek Inventor-mu.
2. Salin `uav_transforms.csv` ke `C:\UAV\`.
3. Buka `Final UAV.iam` sehingga jendela assembly aktif.
4. Tab **Manage > iLogic > Add Rule**. Beri nama `snap`, tempel seluruh isi `snap_to_sldasm.iLogicVb`, ubah `csvPath` bila lokasinya berbeda, lalu **Save**.
5. Jalankan aturan (klik kanan pada aturan di panel iLogic > Run). Dengan `applyChanges = False` ia hanya melaporkan:
   - Cocok: komponen yang posisinya sudah benar.
   - Berbeda: komponen yang posisinya salah.
   - Tidak ada di CSV: nama komponen yang tidak ditemukan.
   - Rincian lengkap ditulis ke `C:\UAV\snap_log.txt`.
6. Jika "Tidak ada di CSV" banyak, nama komponen di Inventor-mu berbeda dari nama SolidWorks. Kirim isi `snap_log.txt` ke saya dan saya sesuaikan. (Skrip sudah membuang awalan seperti `[o]:` dan mengganti `:` menjadi `-`.)
7. Jika "Berbeda" banyak dan "Tidak ada di CSV" nol, ubah `applyChanges = True` dan jalankan lagi. Skrip akan me-nonaktifkan ground pada komponen yang salah, memindahkannya ke posisi yang tersimpan, lalu meng-ground `Fan Housing and Base-1`.
8. **Save All** (assembly dan sub-assembly akan ikut tersimpan, karena posisi di dalam sub-assembly ikut diperbaiki).
9. Verifikasi (Bagian 3).

### Jalur B: bila kamu bisa memakai SolidWorks (kampus, teman, atau komputer lama)

1. Buka `Final UAV.SLDASM`. Di ConfigurationManager, klik kanan konfigurasi > **Collapse** bila ada exploded view. Tekan Ctrl+Q (rebuild) dan pastikan tidak ada mate bertanda error.
2. **Save As > STEP AP214**. Di Options pilih ekspor sebagai assembly (bukan satu part) bila kamu ingin tiap komponen terpisah [nama opsi dapat berbeda antar versi].
3. Di Inventor: **File > Open**, pilih file STEP. Hasilnya sudah terpasang.

### Jalur C: manual (cadangan)

Pakai Joint atau Constrain, mulai dari sub-assembly lalu bodi: ground `Fan Housing and Base`, lalu susun ke arah -X mengikuti tabel posisi di Bagian 1, kemudian vane + servo, baterai, kaki, dan terakhir rotor. Baut (49 buah) paling akhir dengan Constrain Insert. Ini lambat dan rawan salah; pakai Jalur A atau B jika bisa.

## 3. Verifikasi setelah terpasang

Gunakan Measure dan bandingkan dengan tabel Bagian 1 (toleransi 0,5 mm):

- Jarak dari ujung atas Top section ke ujung bawah Fan Housing = 390 mm (X: -312 ke 78).
- Diameter bodi (Air Intake Zone) = 119,2 mm.
- Ujung kaki terjauh berada di X = 143 mm.
- Pusat vane berada di X = 61,5 mm.
- Tidak ada komponen yang berada di luar kotak X -418 sampai 143, Y -353 sampai 375, Z -348 sampai 328 mm (kotak seluruh assembly dengan rotor).

Lalu buat **Design View Representation "Baseline-EDF"**: sembunyikan `CRM2413 assembly-1` (propeller dan motornya). Ini adalah padanan konfigurasi Baseline-EDF di SolidWorks.

## 4. STL: kapan dipakai dan kapan tidak

STL **bukan** cara untuk menggabungkan komponen. STL hanya "foto" permukaan bentuk akhir: tanpa satuan (dianggap mm), tanpa warna, tanpa struktur assembly, dan berbentuk segitiga sehingga tidak cocok untuk CFD yang akurat. Jadi urutannya selalu: **perbaiki posisi dulu, baru ekspor**.

| Tujuan | Format yang dipakai |
|---|---|
| Menyatukan/menyimpan assembly | `.iam` (Inventor) atau STEP |
| CFD dan FEA | STEP (bukan STL) |
| Simulasi ArduPilot SITL | **Tidak butuh file CAD sama sekali.** Backend hanya butuh angka: massa, inersia, CG, lengan vane, dimensi vane (`vehicle.json`) |
| Visualisasi 3D (Blender, animasi hasil simulasi, portofolio) | STL atau OBJ |
| Cetak 3D | STL per part |

Cara ekspor STL satu assembly di Inventor: aktifkan Design View "Baseline-EDF", lalu **File > Save As > Save Copy As**, jenis file **STL**, buka **Options**: satuan Millimeter, resolusi High, dan pilih opsi yang menyatukan semua komponen yang terlihat menjadi satu file [nama opsi dapat berbeda antar versi]. Sembunyikan baut dan detail kecil dulu agar file tidak berat.

## 5. Mengisi vehicle.json dari Inventor (setelah assembly benar)

1. Beri material tiap part. Part hasil impor sering bermaterial generik; massa total jadi salah. Untuk komponen beli, atur kepadatan agar massanya sama dengan datasheet: kepadatan = massa datasheet / volume part (volume ada di iProperties > Physical).
2. Klik kanan assembly di browser > **iProperties > Physical**. Pilih Update, akurasi High. Catat massa, pusat gravitasi (CG), dan momen inersia pada CG.
3. **Hati-hati sumbu.** Sumbu UAV pada CAD adalah **X**, sedangkan `vehicle.json` memakai sumbu badan dengan sumbu EDF = **Z**. Pemetaan: `inertia_kgm2` = [momen transversal pertama (Iyy atau Izz CAD), momen transversal kedua, **Ixx CAD (aksial)**]. Dua momen transversal harusnya hampir sama.
4. Satuan inersia di Inventor sering kg mm2. Ubah ke kg m2 dengan dikalikan 1e-6.
5. `vane_lever_L_m` = (61,5 mm - CG_x dalam mm) / 1000, di mana CG_x diukur pada koordinat assembly yang sama.
6. Ubah `_status` di `vehicle.json` menjadi `"CAD-VERIFIED"`.

Ukuran vane di `vehicle.json` sudah saya perbarui dari CAD-mu: chord 50 mm, span 38 mm, radial 33 mm. Nilai `vane_lever_L_m` = 0,13 m masih perkiraan kasar dari CG dugaan (X sekitar -65 mm); ganti dengan CG asli.

## 6. Yang saya butuhkan darimu berikutnya

- Isi `snap_log.txt` setelah menjalankan skrip dalam mode diagnosa (atau tangkapan layar pesan hasilnya).
- Hasil iProperties > Physical setelah assembly benar.
- Keputusan D1: Single-EDF saja, atau rotor kontra-rotasi tetap dipakai? Rotornya sangat besar (762 mm) dan akan mengubah seluruh rencana simulasi.
