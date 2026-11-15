# ARCHITECTURE & SYSTEM DESIGN
**Project:** Smart Expense & Receipt Tracker  
**Architecture:** Monorepo (`/backend-laravel`, `/service-python`, `/frontend-react`)

---

## 1. Monorepo Structure Overview

```text
smart-expense-tracker/
│
├── backend-laravel/          # Core Business Logic, Authentication, DB Migrations & REST API
│   ├── app/
│   ├── routes/api.php
│   ├── database/migrations/
│   └── ...
│
├── service-python/           # Microservice for OCR & Receipt AI Parsing (FastAPI)
│   ├── app/
│   │   ├── api/
│   │   ├── services/         # OCR & Parser engines
│   │   └── schemas/
│   ├── main.py
│   └── requirements.txt
│
├── frontend-react/           # Single Page Application (Vite + React + Tailwind CSS)
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   └── services/
│   └── package.json
│
└── ARCHITECTURE.md           # System Blueprint & Contracts
```

---

## 2. Tech Stack

- **Backend:** Laravel 11.x (API Mode, Laravel Sanctum, MySQL, GuzzleHttp client)
- **AI/OCR Service:** Python 3.10+ / FastAPI, Uvicorn, Pydantic v2, OCR Engine (Tesseract/PaddleOCR/PyMuPDF)
- **Frontend:** React 18+ (Vite), Tailwind CSS, Axios, Lucide Icons
- **Database:** MySQL 8.0+

---

## 3. Database Schema & MySQL ERD

### Mermaid ERD

```mermaid
erDiagram
    USERS ||--o{ ACCOUNTS : "has"
    USERS ||--o{ CATEGORIES : "defines"
    USERS ||--o{ EXPENSES : "records"
    USERS ||--o{ BUDGETS : "sets"
    ACCOUNTS ||--o{ EXPENSES : "funded_by"
    CATEGORIES ||--o{ EXPENSES : "categorizes"
    CATEGORIES ||--o{ BUDGETS : "limits"
    EXPENSES ||--o| RECEIPTS : "attaches"
    RECEIPTS ||--o{ RECEIPT_ITEMS : "contains"

    USERS {
        bigint id PK
        string name
        string email UK
        string password
        timestamp email_verified_at
        timestamps created_at_updated_at
    }

    ACCOUNTS {
        bigint id PK
        bigint user_id FK
        string name "e.g. BCA, Cash, GoPay"
        enum type "bank, cash, ewallet"
        decimal balance "15,2"
        string currency "IDR, USD, etc."
        timestamps created_at_updated_at
    }

    CATEGORIES {
        bigint id PK
        bigint user_id FK "nullable for system default"
        string name "e.g. Food, Transport, Bills"
        string icon
        string color
        enum type "expense, income"
        timestamps created_at_updated_at
    }

    EXPENSES {
        bigint id PK
        bigint user_id FK
        bigint account_id FK
        bigint category_id FK
        decimal amount "15,2"
        date transaction_date
        text description
        enum payment_method "cash, transfer, card, qris"
        enum status "pending, confirmed"
        timestamps created_at_updated_at
    }

    RECEIPTS {
        bigint id PK
        bigint expense_id FK "nullable before expense creation"
        bigint user_id FK
        string image_path
        string merchant_name
        date receipt_date
        decimal subtotal "15,2"
        decimal tax "15,2"
        decimal total_amount "15,2"
        float confidence_score
        enum processing_status "pending, processed, failed"
        longtext raw_ocr_text
        json ocr_raw_payload
        timestamps created_at_updated_at
    }

    RECEIPT_ITEMS {
        bigint id PK
        bigint receipt_id FK
        string item_name
        int quantity
        decimal unit_price "15,2"
        decimal total_price "15,2"
        timestamps created_at_updated_at
    }

    BUDGETS {
        bigint id PK
        bigint user_id FK
        bigint category_id FK
        decimal amount "15,2"
        int month
        int year
        timestamps created_at_updated_at
    }
```

### Table Definitions Summary

| Table | Purpose |
|---|---|
| `users` | Akun pengguna sistem |
| `accounts` | Sumber dana / dompet (Rekening Bank, Tunai, E-Wallet) |
| `categories` | Kategori pemasukan dan pengeluaran |
| `expenses` | Catatan transaksi keuangan |
| `receipts` | Metadata & hasil ekstraksi OCR dari struk fisik |
| `receipt_items` | Rincian baris barang dari struk belanja |
| `budgets` | Batas anggaran bulanan per kategori |

---

## 4. API Contract: Laravel ⟷ Python (FastAPI) Service

Laravel bertindak sebagai API Gateway & Orchestrator. Saat pengguna mengunggah gambar struk, Laravel meneruskan file atau path gambar ke Python FastAPI service untuk diekstrak.

### Base Configuration
- **Base URL:** `http://127.0.0.1:8001` (Default local development)
- **Security:** Shared API Key via header `X-Service-Token: ${PYTHON_SERVICE_SECRET}`
- **Timeout:** Connection timeout 5s, Read timeout 30s

---

### Endpoint 1: Health & Readiness Check

- **Method:** `GET`
- **Path:** `/api/v1/health`
- **Request Headers:**
  ```http
  Accept: application/json
  ```
- **Response `200 OK`:**
  ```json
  {
    "status": "healthy",
    "version": "1.0.0",
    "ocr_engine": "available"
  }
  ```

---

### Endpoint 2: Extract Receipt Data (Multipart Upload)

Menerima file gambar struk (JPEG, PNG, WEBP, PDF) dan mengembalikan hasil OCR terstruktur.

- **Method:** `POST`
- **Path:** `/api/v1/extract-receipt`
- **Request Headers:**
  ```http
  X-Service-Token: <SECRET_TOKEN>
  Content-Type: multipart/form-data
  ```
- **Form Data:**
  - `file`: `Binary` (Image file, max 10MB)
  - `currency_hint`: `string` (Optional, default: `"IDR"`)

#### Response Success `200 OK`
```json
{
  "success": true,
  "confidence_score": 0.94,
  "data": {
    "merchant": {
      "name": "INDOMARET POINT",
      "address": "Jl. Sudirman No. 45, Jakarta",
      "phone": "021-5551234"
    },
    "transaction": {
      "date": "2026-11-15",
      "time": "14:23:00",
      "invoice_number": "TRX-9821841"
    },
    "financials": {
      "subtotal": 45000.00,
      "tax": 4950.00,
      "discount": 0.00,
      "total_amount": 49950.00,
      "currency": "IDR"
    },
    "items": [
      {
        "name": "ROTI TAWAR SARI ROTI",
        "qty": 1,
        "unit_price": 16500.00,
        "total_price": 16500.00
      },
      {
        "name": "ULTRA MILK PLAIN 1L",
        "qty": 1,
        "unit_price": 21000.00,
        "total_price": 21000.00
      },
      {
        "name": "AQUA 600ML",
        "qty": 2,
        "unit_price": 3725.00,
        "total_price": 7450.00
      }
    ],
    "suggested_category": "Food & Groceries"
  },
  "raw_text": "INDOMARET POINT\nJL SUDIRMAN NO 45\n..."
}
```

#### Response Validation Error `422 Unprocessable Entity`
```json
{
  "success": false,
  "error_code": "UNSUPPORTED_MEDIA_TYPE",
  "message": "File format must be JPEG, PNG, WEBP, or PDF."
}
```

#### Response Processing Error `500 Internal Server Error`
```json
{
  "success": false,
  "error_code": "OCR_EXTRACTION_FAILED",
  "message": "Failed to parse receipt text clearly. Please retake photo with better lighting."
}
```

---

## 5. End-to-End Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    actor User as Pengguna (Browser)
    participant React as Frontend React
    participant Laravel as Backend Laravel API
    participant DB as MySQL Database
    participant Python as Python FastAPI (OCR)

    User->>React: Unggah foto struk belanja
    React->>Laravel: POST /api/v1/receipts/scan (Multipart Form Data)
    Laravel->>Laravel: Simpan file fisik ke storage/app/public/receipts
    Laravel->>Python: POST /api/v1/extract-receipt (Forward file + X-Service-Token)
    Python->>Python: Jalankan OCR & Regex / NLP Parsing
    Python-->>Laravel: Response JSON (Merchant, Total, Items, Confidence)
    Laravel->>DB: INSERT INTO receipts & receipt_items (status: 'processed')
    Laravel-->>React: 200 OK dengan Payload Terstruktur Struk
    React->>User: Tampilkan modal Review & Konfirmasi Form Transaksi
    User->>React: Klik "Konfirmasi Pengeluaran"
    React->>Laravel: POST /api/v1/expenses (dengan receipt_id & konfirmasi kategori)
    Laravel->>DB: INSERT INTO expenses, UPDATE account balance
    Laravel-->>React: 201 Created (Expense tersimpan)
    React->>User: Notifikasi Berhasil & Update Dashboard
```
