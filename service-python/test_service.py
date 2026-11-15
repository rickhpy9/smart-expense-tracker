import io
import numpy as np
import cv2
from fastapi.testclient import TestClient
from main import app
from app.services.ocr_service import OCRService

client = TestClient(app)


def test_parse_amount_rupiah_rules():
    # Verifikasi ketat aturan konversi Rupiah & penanganan noise OCR
    assert OCRService.parse_amount("Rp11.000") == 11000.0, "Rp11.000 harus 11000.0"
    assert OCRService.parse_amount("Rp11.00o") == 11000.0, "Rp11.00o harus 11000.0"
    assert OCRService.parse_amount("11.00o") == 11000.0, "11.00o harus 11000.0"
    assert OCRService.parse_amount("Rp11.00") == 11000.0, "Rp11.00 (1 nol terpotong) harus 11000.0"
    assert OCRService.parse_amount("11.000") == 11000.0
    assert OCRService.parse_amount("11.000,00") == 11000.0
    assert OCRService.parse_amount("11,000.00") == 11000.0
    assert OCRService.parse_amount("74.00o") == 74000.0
    assert OCRService.parse_amount("Rp74.00o") == 74000.0
    assert OCRService.parse_amount("Rp74.00") == 74000.0
    assert OCRService.parse_amount("1.250.500") == 1250500.0
    assert OCRService.parse_amount("Rp. 45.000") == 45000.0
    assert OCRService.parse_amount("Kamu Membayar Rp11.00o") == 11000.0
    assert OCRService.parse_amount("Kamu Membayar Rp11.000") == 11000.0
    print("✓ test_parse_amount_rupiah_rules Passed (Rp11.000, Rp11.00o, Rp11.00 -> 11000.0)")


def test_qris_and_ewallet_parsing():
    # 1. Test Kasus Nyata: QRIS ShopeePay (Padang Murah Hasanudin, Kamu Membayar Rp11.000)
    lines_shopeepay = [
        "Rincian Pesanan",
        "Pembayaran Berhasil",
        "Kamu Membayar",
        "Rp11.000",
        "Bayar Ke",
        "Padang Murah Hasanudin",
        "Waktu Pembayaran: 15 Nov 2026 12:30:15 WIB",
        "Transaksi SN: 202611151234567890",
        "Metode Pembayaran: Saldo ShopeePay",
        "Nama Pengakuisisi: PT AirPay International",
        "Nama Penerbit: PT AirPay International"
    ]

    total = OCRService.extract_total(lines_shopeepay)
    merchant = OCRService.extract_merchant(lines_shopeepay)
    date_val = OCRService.extract_date(lines_shopeepay)
    cat = OCRService.suggest_category(merchant, "\n".join(lines_shopeepay))

    assert total == 11000.0, f"Expected total 11000.0, got {total}"
    assert merchant == "Padang Murah Hasanudin", f"Expected 'Padang Murah Hasanudin', got '{merchant}'"
    assert date_val == "2026-11-15", f"Expected 2026-11-15, got {date_val}"
    assert cat == "Makanan & Minuman", f"Expected 'Makanan & Minuman', got '{cat}'"
    # 1b. Test Kasus Nyata dengan Noise EasyOCR 'Rp11.00o'
    lines_shopeepay_noisy = [
        "Rincian Pesanan",
        "Pembayaran Berhasil",
        "Kamu Membayar",
        "Rp11.00o",
        "Bayar Ke",
        "Padang Murah Hasanudin",
        "Waktu Pembayaran: 15 Nov 2026 12:30:15 WIB"
    ]
    total_noisy = OCRService.extract_total(lines_shopeepay_noisy)
    assert total_noisy == 11000.0, f"Expected total 11000.0 from Rp11.00o, got {total_noisy}"
    print("✓ Test QRIS ShopeePay dengan Noise Rp11.00o Passed: Rp 11.000")

    # 2. Test E-Wallet GoPay / DANA / QRIS Format Variasi
    lines_gopay = [
        "Bukti Pembayaran",
        "Transaksi Berhasil",
        "Nominal: Rp 45.000",
        "Penerima: Soto Ayam Pak Man",
        "Tanggal: 14/11/2026",
        "Order SN: 8912481928312",
        "ID Transaksi: 19823192"
    ]

    total_g = OCRService.extract_total(lines_gopay)
    merchant_g = OCRService.extract_merchant(lines_gopay)
    date_g = OCRService.extract_date(lines_gopay)
    cat_g = OCRService.suggest_category(merchant_g, "\n".join(lines_gopay))

    assert total_g == 45000.0, f"Expected 45000.0, got {total_g}"
    assert merchant_g == "Soto Ayam Pak Man", f"Expected 'Soto Ayam Pak Man', got '{merchant_g}'"
    assert date_g == "2026-11-14", f"Expected 2026-11-14, got {date_g}"
    assert cat_g == "Makanan & Minuman"
    print("✓ Test E-Wallet GoPay/DANA Passed: Rp 45.000, Soto Ayam Pak Man")

    # 3. Test Kasus Struk Fisik: Kopi Kenangan multi-line Total 74.00o
    lines_kenangan = [
        "Receipt #982184",
        "Kenangan",
        "Outlet Name",
        "Ruko Telagamas Semarang",
        "Subtotal",
        "60.000",
        "Total",
        "74.00o",
        "Date: 12 Nov 2026"
    ]
    assert OCRService.extract_total(lines_kenangan) == 74000.0
    assert "Kopi Kenangan" in OCRService.extract_merchant(lines_kenangan)
    assert OCRService.extract_date(lines_kenangan) == "2026-11-12"
    print("✓ Test Struk Fisik Kopi Kenangan Passed: Rp 74.000 (74.00o cleaned)")


def test_health_check():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    print("✓ Health Check Passed")


def test_ml_cluster_normal():
    transactions = [
        {"id": 1, "amount": 15000, "category_name": "Makanan & Minuman", "description": "Es Teh"},
        {"id": 2, "amount": 25000, "category_name": "Makanan & Minuman", "description": "Nasi Goreng"},
        {"id": 3, "amount": 150000, "category_name": "Belanja", "description": "Kemeja"},
        {"id": 4, "amount": 200000, "category_name": "Belanja", "description": "Sepatu"},
        {"id": 5, "amount": 1200000, "category_name": "Tagihan", "description": "Listrik & AC"},
        {"id": 6, "amount": 1500000, "category_name": "Tagihan", "description": "Sewa Kost"}
    ]

    response = client.post(
        "/api/v1/ml/cluster",
        json=transactions,
        headers={"x-service-token": "smart-expense-secret-key-2026"}
    )
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["success"] is True
    assert res_data["status"] == "clustered"
    assert len(res_data["clusters_summary"]) == 3
    print("✓ ML Cluster (Normal >= 3) Passed")


def test_ml_cluster_fallback():
    transactions = [
        {"id": 1, "amount": 50000, "category_name": "Makanan & Minuman", "description": "Kopi"},
        {"id": 2, "amount": 25000, "category_name": "Transportasi", "description": "Ojek Online"}
    ]

    response = client.post(
        "/api/v1/ml/cluster",
        json=transactions,
        headers={"x-service-token": "smart-expense-secret-key-2026"}
    )
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["success"] is True
    assert res_data["status"] == "fallback"
    print("✓ ML Cluster Fallback (< 3 items) Passed")


if __name__ == "__main__":
    test_parse_amount_rupiah_rules()
    test_qris_and_ewallet_parsing()
    test_health_check()
    test_ml_cluster_fallback()
    test_ml_cluster_normal()
    print("\nALL PYTHON SERVICE TESTS PASSED SUCCESSFULLY!")
