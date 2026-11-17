# Perubahan CAD yang harus dilakukan (daftar edit persis)

Saya tidak bisa menghasilkan file SolidWorks (.SLDASM) yang sudah diedit: format itu proprietary, dan di lingkungan saya hanya bisa dibaca strukturnya, tidak ditulis. File CAD terbaru yang ada saat ini adalah Final UAV.SLDASM dalam ZIP-mu. Berikut edit yang membuatnya konsisten dengan baseline Single-EDF (setiap butir sudah ditemukan lewat pembacaan file-mu):

1. **Konfigurasi baru "Baseline-EDF"** (Configuration Manager > Add Configuration). Di dalamnya, suppress "CRM2413 assembly" beserta isinya: Base ring, CRM2413, Extension rods, Cone screw, Propeller 2 base, Propeller 2 cover, propeller 8038 CW dan CCW, propeller 15 inci dan pasangan lawannya. Periksa daftarnya di FeatureManager karena daftar ini diurutkan dari referensi file.
2. **Baterai:** CAD memuat instance Tattu R-Line V4.0 1300 mAh bernomor -1, -3, -5 (kemungkinan 3 pack). Ganti menjadi 2 pack OMPHobby 6S 2000 mAh (kotak envelope dengan dimensi datasheet [CEK] dan Override Mass ~330 g).
3. **ESC:** pasangan "T-motor ESC AM 116A" (STEP 41,2 x 104,7 x 22,6 mm) adalah penahan. Ganti dimensinya setelah ESC disetujui (D3).
4. **Komputer pendamping:** pertahankan envelope Raspberry Pi 4 sebagai penahan volume konservatif (D4).
5. **Massa part impor STEP** (Vein, Reinforcement Spar, Screw 2mm, ESC) tidak punya material: setel material atau Override Mass Properties.
6. **Ekspor Mass Properties** ke vehicle.json (tabel ada di sitl/README_SITL.md).

Jika kamu menempelkan hasil Mass Properties (massa, CG, momen inersia) dan nilai Measure ke chat, saya isikan ke vehicle.json dan menjalankan ulang self-test.
