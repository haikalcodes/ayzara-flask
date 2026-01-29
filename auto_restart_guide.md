# Panduan Setup Auto-Restart (PM2) - Windows

Panduan lengkap untuk mengatur aplikasi agar **otomatis menyala** saat Windows dihidupkan atau restart, dan **otomatis bangkit** jika crash.

## 1. Persiapan (Wajib)

Pastikan Anda sudah menjalankan opsi "Install Node.js & PM2" di `install.bat`. 
Untuk mengecek apakah PM2 sudah terinstall, buka CMD dan ketik:

```cmd
pm2 -v
```
*Jika muncul nomor versi, berarti aman.*

---

## 2. Generate Startup Script

Langkah ini akan mendaftarkan PM2 ke dalam registry Windows agar jalan saat booting.

1.  Buka **CMD** atau **PowerShell** sebagai **ADMINISTRATOR** (Klik Kanan -> Run as Administrator).
2.  Jalankan perintah ini:

    ```cmd
    pm2-startup install
    ```

3.  Jika sukses, akan muncul pesan "PM2 Service Installed".

---

## 3. Mendaftarkan Aplikasi

Sekarang kita akan menyuruh PM2 untuk menjalankan aplikasi kita.

1.  Buka CMD (biasa/admin) dan pindah ke folder aplikasi:
    ```cmd
    cd /d D:\projects\REKAMVIDEOAYZARA\ayzara\dashboard_flask
    ```
    *(Sesuaikan path jika folder Anda berbeda)*

2.  Jalankan perintah start:
    ```cmd
    pm2 start start_app.bat --name "ayzara-cam"
    ```

3.  Cek apakah sudah jalan:
    ```cmd
    pm2 status
    ```
    Anda harusnya melihat status `online`.

---

## 4. Simpan Konfigurasi (PENTING!)

Agar daftar aplikasi tersimpan permanen, jalankan:

```cmd
pm2 save
```

**SELESAI!**
Sekarang aplikasi Anda memiliki 2 kemampuan:
1.  **Auto-Start saat Boot:** Nyala sendiri saat Windows hidup.
2.  **Auto-Restart saat Crash:** Jika aplikasi error/mati sendiri, PM2 akan langsung menghidupkannya lagi dalam < 1 detik.

---

## Cara Test "Auto-Restart on Crash"

Ingin membuktikan? Lakukan ini:
1.  Jalankan aplikasi via PM2.
2.  Buka Task Manager.
3.  Cari `python.exe` atau `cmd.exe` yang menjalankan aplikasi ini.
4.  Klik Kanan -> **End Task** (Paksa matikan).
5.  Lihat di CMD PM2 (`pm2 status`), statusnya akan tetap `online` dan uptime-nya tereset (artinya baru saja dinyalakan ulang otomatis).

---

## Troubleshooting / Perintah Berguna

*   **Melihat Log Aplikasi:**
    ```cmd
    pm2 log ayzara-cam
    ```

*   **Stop Aplikasi:**
    ```cmd
    pm2 stop ayzara-cam
    ```

*   **Restart Aplikasi:**
    ```cmd
    pm2 restart ayzara-cam
    ```

*   **Menghapus Aplikasi dari Auto-Start:**
    ```cmd
    pm2 delete ayzara-cam
    pm2 save
    ```

*   **Update Aplikasi:**
    Jika ada update kode, cukup lakukan `git pull` atau copy file baru, lalu:
    ```cmd
    pm2 restart ayzara-cam
    ```
