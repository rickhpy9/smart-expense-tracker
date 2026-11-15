import io
import numpy as np
import cv2
from fastapi.testclient import TestClient
from main import app
from app.services.ocr_service import OCRService

client = TestClient(app)


def test_ocr_parser_logic():
    # Test OCRService parsing helper methods directly
    # 1. Test clean_ocr_number_noise and parse_amount
    assert OCRService.parse_amount("74.00o") == 74000.0
    assert OCRService.parse_amount("7400o") == 74000.0
    assert OCRService.parse_amount("Rp. 74.000") == 74000.0
    assert OCRService.parse_amount("15o00") == 15000.0
    print("✓ clean_ocr_number_noise & parse_amount Passed (e.g. 74.00o -> 74000)")

    # 2. Test multi-line total search excluding subtotal
    lines_multi_line = [
        "Receipt #982184",
        "Kopi Kenangan",
        "Subtotal",
        "60.000",
        "Tax 10%",
        "6.000",
        "Total",
        "74.00o",
        "Cash",
        "100.000"
    ]
    extracted_total = OCRService.extract_total(lines_multi_line)
    assert extracted_total == 74000.0, f"Expected 74000.0, got {extracted_total}"
    print("✓ extract_total (Multi-line & exclude Subtotal) Passed")

    # 3. Test merchant with Outlet Name and Brand
    lines_merchant = [
        "Receipt #12345",
        "Kenangan",
        "Outlet Name",
        "Ruko Telagamas Semarang",
        "Order #001"
    ]
    merchant = OCRService.extract_merchant(lines_merchant)
    assert "Kopi Kenangan" in merchant
    assert "Ruko Telagamas Semarang" in merchant
    print(f"✓ extract_merchant Passed: '{merchant}'")

    # 4. Test date normalization (e.g. '12 Nov 2026' -> '2026-11-12')
    lines_date = [
        "Store ID 99",
        "Date: 12 Nov 2026 14:30",
        "Total: 50.000"
    ]
    date_val = OCRService.extract_date(lines_date)
    assert date_val == "2026-11-12", f"Expected 2026-11-12, got {date_val}"

    lines_date_id = [
        "Tanggal: 05 Agt 2026"
    ]
    assert OCRService.extract_date(lines_date_id) == "2026-08-05"
    print("✓ extract_date ('12 Nov 2026' -> '2026-11-12') Passed")


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
    test_ocr_parser_logic()
    test_health_check()
    test_ml_cluster_fallback()
    test_ml_cluster_normal()
    print("\nALL PYTHON SERVICE TESTS PASSED SUCCESSFULLY!")
