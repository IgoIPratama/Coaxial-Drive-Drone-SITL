# Yang masih kurang di daftar komponenmu

Dibandingkan dokumen arsitektur (apa yang dibutuhkan) dengan dokumen supplier (apa yang sudah kamu pilih) untuk konfigurasi Single-EDF.

## Belum ada di BOM sama sekali
1. **PDB, sekering, konektor daya, dan harness paralel dua pack.** Dokumen arsitektur menulis "Power distribution, fuse, connectors | 1 set", tetapi dokumen supplier tidak memuatnya. Perlu: PDB atau bus daya yang tahan puncak 124 A, sekering per pack (nilai [CEK] lewat kurva waktu-arus), konektor pack (XT90 atau setara), kawat AWG8 [HITUNG].
2. **Radio telemetri MAVLink ke laptop.** Dokumen arsitektur menyebut 1 pasang; dokumen supplier hanya memuat XBee 3 DigiMesh untuk jaringan swarm, bukan untuk MAVLink satu pesawat. Jenis dan frekuensi radio belum dipilih (perhatikan aturan frekuensi di negaramu).
3. **Buzzer / indikator arming.** Dokumen arsitektur menyebut provisi buzzer; tidak ada di dokumen supplier.
4. **Kabel dan mounting.** Kabel JST-GH (TELEM, GPS), kabel servo, heat-shrink, standoff peredam getaran: tidak tercantum.

## Sudah ada tetapi belum bisa dipakai
5. **ESC belum disetujui.** Thunder 120 A berstatus NOT approved (klaim EDF 124 A lebih besar dari 120 A); ESC di CAD (T-motor "AM 116A") berbeda dari dokumen. Syarat desain: minimal 155 A kontinu [ASUMSI margin 1,25 x 124 A], minimal 6S, input PWM standar.
6. **Cara membaca arus propulsi (D5).** Pixhawk 6C Mini hanya punya satu port POWER analog [SUMBER]. PM02 V3 sensing sampai 120 A; Mauch HS-200-LV perlu antarmuka yang cocok. Pilih: Mauch di POWER dan PM02 sebagai catu 5 V saja; atau PM02 di POWER dan arus dibaca lewat telemetri ESC / monitor baterai CAN.
7. **Jenis servo.** MG90S di listing ada yang analog dan ada yang digital; arus stall belum tercatat. Torsi engsel vane menunggu hasil CFD.
8. **Baterai di CAD tidak sama dengan BOM.** CAD: Tattu 1300 mAh 130C (3 nama instance); BOM: OMPHobby 2000 mAh x 2.
9. **Sistem surya/pengisian belum dipilih** (kata dokumenmu sendiri): BMS/balancer 6S, isolasi jalur charge, sekering pack, sensor suhu, telemetri surya. Catatan desain: topologi charger harus boost, bukan buck seperti BQ24650 (lihat Fase 8).

## Untuk simulasi saja
Tidak satu pun dari butir di atas menghalangi simulasi. Butir 1-9 hanya perlu diputuskan agar BOM, CAD, dan skematik konsisten; simulasi hanya butuh angka dari CAD (massa, inersia, lengan) dan hasil CFD.
