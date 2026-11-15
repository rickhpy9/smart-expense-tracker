# 🧾 Smart Expense & Receipt Tracker

> **Aplikasi Cerdas Pengelola Keuangan Pribadi Berbasis Monorepo: React (Vite + Tailwind CSS), Laravel 11 (Sanctum REST API), dan Python FastAPI (EasyOCR & K-Means Machine Learning Clustering).**

---

## 📌 Gambaran Umum Proyek

**Smart Expense & Receipt Tracker** adalah sistem modern pencatat pengeluaran yang menggabungkan kemampuan **Computer Vision (OCR)** dan **Machine Learning (AI Clustering)**. Pengguna dapat dengan mudah mengunggah foto struk belanja fisik atau tangkapan layar bukti pembayaran e-wallet/QRIS (ShopeePay, GoPay, DANA, OVO, m-Banking), lalu sistem akan mengekstrak nama toko/merchant, nominal harga, dan tanggal transaksi secara otomatis (*auto-fill*), sekaligus mengelompokkan kebiasaan belanja ke dalam 3 klaster pengeluaran finansial.

---

## 🏗️ Arsitektur Sistem 3-Tier (Monorepo)

Proyek ini dibangun menggunakan arsitektur monorepo modular:

```text
smart-expense-tracker/
│
├── backend-laravel/          # Tier 2: Core REST API Gateway & Database Management
│   ├── app/Http/Controllers/ # Auth, Transactions, Categories, Receipts Controller
│   ├── app/Services/         # ReceiptProcessorService (HTTP Client ke Python FastAPI)
│   ├── database/migrations/  # Skema MySQL (users, categories, transactions, receipts)
│   ├── database/seeders/     # Kategori default Indonesia
│   └── routes/api.php        # Protected routes via Laravel Sanctum
│
├── service-python/           # Tier 3: Microservice AI & Machine Learning
│   ├── app/api/endpoints/    # POST /ocr/extract & POST /ml/cluster
│   ├── app/services/         # OpenCV Preprocessing, EasyOCR, K-Means Scikit-Learn
│   ├── app/schemas/          # Pydantic v2 Models
│   ├── main.py               # Uvicorn FastAPI Entrypoint (Port 8001)
│   └── requirements.txt
│
├── frontend-react/           # Tier 1: Single Page Application (SPA)
│   ├── src/api/axios.js      # Axios Interceptor (Auto Bearer Token & 401 Handler)
│   ├── src/context/          # AuthContext (State Management Global)
│   ├── src/pages/            # Dashboard, Login, Register
│   ├── src/components/       # Navbar, ProtectedRoute, Charts
│   └── package.json          # React 18, Vite, Tailwind CSS, Recharts, Lucide Icons
│
├── ARCHITECTURE.md           # Dokumen Blueprint & Kontrak Komunikasi API
└── README.md                 # Panduan Proyek & Setup
```

---

## ✨ Fitur Utama

### 1. Smart Receipt & QRIS OCR Scanner
- **Preprocessing Citra:** Grayscale, Gaussian Blur, dan CLAHE (*Contrast Limited Adaptive Histogram Equalization*) dengan OpenCV.
- **Deep Learning Text Recognition:** Ekstraksi teks multi-bahasa (Indonesia & Inggris) menggunakan EasyOCR.
- **Regex & AI Normalization:** 
  - Membersihkan noise tipis karakter OCR (`Rp11.00o` otomatis dinormalisasi menjadi `11000`).
  - Mendeteksi penerima transfer/QRIS (`Bayar Ke`, `Penerima`, `Merchant`, `Outlet Name`) dan memfilter teks generik UI e-wallet (`Rincian Pesanan`, `Saldo ShopeePay`).
  - Mendeteksi format tanggal bahasa Indonesia & Inggris (`12 Nov 2026` $\rightarrow$ `2026-11-12`).
  - Rekomendasi kategori cerdas (*Makanan & Minuman, Belanja, Transportasi, Tagihan, Hiburan*).

### 2. K-Means Financial Clustering & AI Insights
- Menggunakan `scikit-learn` `StandardScaler` dan algoritma **K-Means Clustering** ($k=3$).
- Mengelompokkan riwayat transaksi ke dalam 3 profil belanja:
  - **Pengeluaran Ringan:** Mikro / Kebutuhan harian.
  - **Pengeluaran Sedang:** Belanja rutin / berkala.
  - **Pengeluaran Besar:** Pengeluaran mayor / prioritas.
- Menghasilkan ringkasan insight dan rekomendasi finansial otomatis.
- Dilengkapi mekanisme *fallback* yang aman jika data transaksi belum mencukupi ($< 3$ transaksi).

### 3. Autentikasi API yang Aman
- Dilindungi oleh **Laravel Sanctum** token-based authentication (`Bearer Token`).
- Form Request Validation ketat untuk pendaftaran, login, dan pencatatan transaksi.
- Hak akses terisolasi secara aman per-user (*multi-tenant safe*).

### 4. Dashboard Interaktif & Responsif
- **Kartu Statistik:** Total Pengeluaran, Jumlah Catatan, dan Status Profil Klaster AI.
- **Widget Scanner Struk:** Upload drag-and-drop dengan animasi loading EasyOCR, lalu hasil ekstraksi otomatis mengisi formulir transaksi.
- **Visualisasi Recharts:** Grafik Pie Chart distribusi kategori dan Bar Chart sebaran nominal klaster K-Means.
- **Tabel Riwayat Transaksi:** Filter kategori, badge struk OCR terverifikasi, dan opsi hapus transaksi.

---

## 🚀 Panduan Instalasi & Menjalankan Lokal

### Prasyarat Sistem
Pastikan perangkat Anda telah terinstal:
- **PHP:** >= 8.2 (dengan ekstensi `pdo_mysql`, `curl`, `mbstring`, `fileinfo`)
- **Composer:** >= 2.0
- **Node.js:** >= 18.0 & `npm`
- **Python:** >= 3.10
- **MySQL Server:** Laragon / XAMPP / Native MySQL

---

### Langkah 1: Konfigurasi Database MySQL
Pastikan MySQL aktif, lalu buat database:
```sql
CREATE DATABASE smart_expense_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

---

### Langkah 2: Setup Backend Laravel (`/backend-laravel`)

1. Masuk ke folder backend:
   ```bash
   cd backend-laravel
   ```
2. Salin environment file dan instal dependencies:
   ```bash
   cp .env.example .env
   composer install
   ```
3. Sesuaikan konfigurasi database dan microservice Python di file `.env`:
   ```env
   DB_CONNECTION=mysql
   DB_HOST=127.0.0.1
   DB_PORT=3306        # Sesuaikan port MySQL Anda (misal 3306 atau 3309)
   DB_DATABASE=smart_expense_db
   DB_USERNAME=root
   DB_PASSWORD=

   PYTHON_SERVICE_URL=http://127.0.0.1:8001
   PYTHON_SERVICE_TOKEN=smart-expense-secret-key-2026
   ```
4. Generate Application Key, jalankan migrasi dan seeder:
   ```bash
   php artisan key:generate
   php artisan migrate --seed
   php artisan storage:link
   ```
5. Jalankan server Laravel:
   ```bash
   php artisan serve
   ```
   *Backend berjalan di: `http://127.0.0.1:8000`*

---

### Langkah 3: Setup Microservice Python FastAPI (`/service-python`)

1. Buka terminal baru dan masuk ke folder Python service:
   ```bash
   cd service-python
   ```
2. Buat dan aktifkan virtual environment:
   - **Windows (PowerShell):**
     ```powershell
     python -m venv venv
     .\venv\Scripts\Activate.ps1
     ```
   - **Linux / macOS:**
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```
3. Instal dependencies:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```
4. Jalankan Uvicorn server:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8001 --reload
   ```
   *Service Python aktif di: `http://127.0.0.1:8001` (Swagger UI: `http://127.0.0.1:8001/docs`)*

---

### Langkah 4: Setup Frontend React (`/frontend-react`)

1. Buka terminal ketiga dan masuk ke folder frontend:
   ```bash
   cd frontend-react
   ```
2. Instal dependencies Node.js:
   ```bash
   npm install
   ```
3. Jalankan server pengembangan Vite:
   ```bash
   npm run dev
   ```
   *Frontend React aktif di: `http://localhost:5173`*

---

## 🧪 Perintah Pengujian & Verifikasi (Automated Tests)

### 1. Uji Service Python (OCR & K-Means)
```powershell
cd service-python
.\venv\Scripts\python.exe test_service.py
```
*Menguji pembersihan noise nominal Rupiah (`Rp11.000` & `Rp11.00o`), multi-line Total struk fisik, QRIS ShopeePay/GoPay, dan algoritma clustering K-Means.*

### 2. Uji Backend Laravel API (Feature Tests)
```bash
cd backend-laravel
php artisan test
```
*Menguji registrasi, login, token Sanctum, CRUD transaksi, mock OCR receipt upload, dan transaction insights.*

### 3. Uji Build Produksi Frontend React
```bash
cd frontend-react
npm run build
```

---

## 📡 Ringkasan API Endpoints

| Method | Endpoint | Deskripsi | Akses |
|---|---|---|---|
| `POST` | `/api/auth/register` | Mendaftarkan akun pengguna baru | Publik |
| `POST` | `/api/auth/login` | Login & mendapatkan Sanctum Bearer Token | Publik |
| `GET` | `/api/auth/me` | Mengambil profil user yang sedang login | `auth:sanctum` |
| `POST` | `/api/auth/logout` | Menghapus token sesi aktif | `auth:sanctum` |
| `GET` | `/api/categories` | Mengambil daftar seluruh kategori | `auth:sanctum` |
| `GET` | `/api/transactions` | Mengambil riwayat transaksi user (paginate & filter) | `auth:sanctum` |
| `POST` | `/api/transactions` | Mencatat transaksi baru | `auth:sanctum` |
| `GET` | `/api/transactions/{id}` | Mengambil detail transaksi spesifik | `auth:sanctum` |
| `PUT` | `/api/transactions/{id}` | Memperbarui transaksi | `auth:sanctum` |
| `DELETE` | `/api/transactions/{id}` | Menghapus transaksi | `auth:sanctum` |
| `POST` | `/api/receipts/scan` | Unggah struk & ekstraksi data via Python OCR | `auth:sanctum` |
| `GET` | `/api/transactions/insights` | Segmentasi K-Means & rekomendasi keuangan AI | `auth:sanctum` |

---

## 📄 Lisensi
Proyek ini dibuat dan dikembangkan untuk keperluan evaluasi teknis dan penggunaan profesional dengan lisensi **MIT License**.
#   s m a r t - e x p e n s e - t r a c k e r  
 